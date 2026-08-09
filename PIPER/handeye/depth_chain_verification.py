#!/usr/bin/env python3
"""Verify D455 aligned depth through the calibrated PIPER-X coordinate chain."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from handeye_calibration import (
    BRIDGE_URL,
    BOARD_SPEC,
    CAMERA_SERIAL,
    HAND_EYE_METHODS,
    IMAGE_FPS,
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    _board,
    _detect_pose,
    _json_matrix,
    _pose6_transform,
    _read_bridge_state,
    _transform,
    _transform_delta,
)


def _fit_rigid(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    source = np.asarray(source, dtype=np.float64).reshape(-1, 3)
    target = np.asarray(target, dtype=np.float64).reshape(-1, 3)
    if source.shape != target.shape or len(source) < 3:
        raise ValueError("rigid fit needs at least three paired 3D points")
    source_center = np.mean(source, axis=0)
    target_center = np.mean(target, axis=0)
    covariance = (source - source_center).T @ (target - target_center)
    u, _, vt = np.linalg.svd(covariance)
    rotation = vt.T @ u.T
    if np.linalg.det(rotation) < 0:
        vt[-1, :] *= -1
        rotation = vt.T @ u.T
    translation = target_center - rotation @ source_center
    return _transform(rotation, translation)


def _apply(transform: np.ndarray, points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    return (transform[:3, :3] @ points.T).T + transform[:3, 3]


def _patch_depth_m(
    depth_raw: np.ndarray,
    u: float,
    v: float,
    depth_scale_m: float,
    radius: int,
) -> float | None:
    x, y = int(round(u)), int(round(v))
    x0, x1 = max(0, x - radius), min(depth_raw.shape[1], x + radius + 1)
    y0, y1 = max(0, y - radius), min(depth_raw.shape[0], y + radius + 1)
    values = depth_raw[y0:y1, x0:x1]
    values = values[(values > 0) & (values < 65535)]
    if values.size < 3:
        return None
    return float(np.median(values)) * depth_scale_m


def _geometry_metrics(object_points: np.ndarray, measured_points: np.ndarray) -> dict[str, float]:
    fitted = _fit_rigid(object_points, measured_points)
    residuals_m = np.linalg.norm(_apply(fitted, object_points) - measured_points, axis=1)
    centered = measured_points - np.mean(measured_points, axis=0)
    _, _, vt = np.linalg.svd(centered)
    plane_distances_m = np.abs(centered @ vt[-1])

    square_errors_m = []
    for first in range(len(object_points)):
        for second in range(first + 1, len(object_points)):
            expected_m = float(np.linalg.norm(object_points[first] - object_points[second]))
            if abs(expected_m - BOARD_SPEC["square_length_m"]) > 1e-6:
                continue
            measured_m = float(np.linalg.norm(measured_points[first] - measured_points[second]))
            square_errors_m.append(measured_m - expected_m)
    if not square_errors_m:
        raise ValueError("depth geometry needs at least one adjacent ChArUco corner pair")
    return {
        "rigid_fit_rms_mm": float(np.sqrt(np.mean(np.square(residuals_m))) * 1000.0),
        "rigid_fit_max_mm": float(np.max(residuals_m) * 1000.0),
        "plane_rms_mm": float(np.sqrt(np.mean(np.square(plane_distances_m))) * 1000.0),
        "square_length_median_mm": float(
            (BOARD_SPEC["square_length_m"] + np.median(square_errors_m)) * 1000.0
        ),
        "square_length_rms_error_mm": float(
            np.sqrt(np.mean(np.square(square_errors_m))) * 1000.0
        ),
    }


def synthetic_test() -> dict[str, Any]:
    object_points = np.asarray(_board().getChessboardCorners(), dtype=np.float64)
    rotation, _ = cv2.Rodrigues(np.array([0.2, -0.1, 0.15], dtype=np.float64))
    expected = _transform(rotation, np.array([0.3, -0.2, 0.4]))
    measured = _apply(expected, object_points)
    fitted = _fit_rigid(object_points, measured)
    translation_m, rotation_deg = _transform_delta(expected, fitted)
    metrics = _geometry_metrics(object_points, measured)
    if translation_m > 1e-10 or rotation_deg > 1e-5:
        raise RuntimeError("synthetic rigid fit did not recover the known transform")
    if metrics["rigid_fit_rms_mm"] > 1e-9 or metrics["plane_rms_mm"] > 1e-9:
        raise RuntimeError("synthetic depth geometry residual is not zero")
    return {"ok": True, "translation_error_m": translation_m, "rotation_error_deg": rotation_deg}


def verify_depth(args: argparse.Namespace) -> dict[str, Any]:
    import pyrealsense2 as rs

    token = args.token_file.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError("bridge token file is empty")
    calibration_bytes = args.calibration.read_bytes()
    calibration = json.loads(calibration_bytes)
    if calibration.get("configuration") != "eye_in_hand":
        raise RuntimeError("calibration is not an eye-in-hand result")
    if calibration.get("camera_serial_number") != args.serial:
        raise RuntimeError("calibration camera serial number does not match the D455")
    if calibration.get("board") != BOARD_SPEC:
        raise RuntimeError("calibration ChArUco board specification does not match")
    method = args.method or calibration["recommended_method"]
    method_result = calibration["methods"][method]
    flange_from_camera = np.asarray(method_result["camera_to_flange"], dtype=np.float64)
    reference_base_from_target = np.asarray(
        method_result["base_from_target_mean"], dtype=np.float64
    )

    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_device(args.serial)
    config.enable_stream(
        rs.stream.depth, IMAGE_WIDTH, IMAGE_HEIGHT, rs.format.z16, IMAGE_FPS
    )
    config.enable_stream(
        rs.stream.color, IMAGE_WIDTH, IMAGE_HEIGHT, rs.format.bgr8, IMAGE_FPS
    )
    config.enable_stream(rs.stream.gyro, rs.format.motion_xyz32f, 200)
    align = rs.align(rs.stream.color)
    samples_by_id: dict[int, list[np.ndarray]] = {}
    gyro_norms = []
    best = None
    started = False
    try:
        profile = pipeline.start(config)
        started = True
        for _ in range(args.warmup_frames):
            pipeline.wait_for_frames(5000)
        before = _read_bridge_state(args.bridge_url, token)
        color_intrinsics = (
            profile.get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()
        )
        depth_scale_m = profile.get_device().first_depth_sensor().get_depth_scale()

        for _ in range(args.capture_frames):
            frames = pipeline.wait_for_frames(5000)
            gyro_frame = next(
                (frame for frame in frames if frame.profile.stream_type() == rs.stream.gyro),
                None,
            )
            if gyro_frame:
                gyro = gyro_frame.as_motion_frame().get_motion_data()
                gyro_norms.append(math.sqrt(gyro.x**2 + gyro.y**2 + gyro.z**2))
            aligned = align.process(frames)
            color_frame = aligned.get_color_frame()
            depth_frame = aligned.get_depth_frame()
            if not color_frame or not depth_frame:
                continue
            image = np.asanyarray(color_frame.get_data()).copy()
            depth_raw = np.asanyarray(depth_frame.get_data()).copy()
            detected = _detect_pose(image, color_intrinsics, rs)
            if detected is None or len(detected["charuco_ids"]) < args.minimum_corners:
                continue

            valid_this_frame = 0
            for corner, identifier in zip(
                detected["charuco_corners"].reshape(-1, 2),
                detected["charuco_ids"].reshape(-1),
            ):
                depth_m = _patch_depth_m(
                    depth_raw,
                    float(corner[0]),
                    float(corner[1]),
                    depth_scale_m,
                    args.patch_radius,
                )
                if depth_m is None or not args.minimum_depth_m <= depth_m <= args.maximum_depth_m:
                    continue
                point = rs.rs2_deproject_pixel_to_point(
                    color_intrinsics,
                    [float(corner[0]), float(corner[1])],
                    depth_m,
                )
                samples_by_id.setdefault(int(identifier), []).append(
                    np.asarray(point, dtype=np.float64)
                )
                valid_this_frame += 1
            score = (
                valid_this_frame,
                len(detected["charuco_ids"]),
                -detected["approximate_pixel_rms"],
            )
            if best is None or score > best[0]:
                best = (score, image, depth_raw, detected)
        after = _read_bridge_state(args.bridge_url, token)
    finally:
        if started:
            pipeline.stop()

    if best is None:
        raise RuntimeError("no RGB-D frame contained a usable ChArUco detection")
    accepted_ids = sorted(
        identifier
        for identifier, points in samples_by_id.items()
        if len(points) >= args.minimum_depth_observations
    )
    if len(accepted_ids) < args.minimum_depth_corners:
        raise RuntimeError(
            f"only {len(accepted_ids)} corners have stable depth; "
            f"need {args.minimum_depth_corners}"
        )

    before_arm, after_arm = before["arm"], after["arm"]
    before_flange = _pose6_transform(before_arm["flange_pose_m_rad"])
    base_from_flange = _pose6_transform(after_arm["flange_pose_m_rad"])
    flange_translation_m, flange_rotation_deg = _transform_delta(
        before_flange, base_from_flange
    )
    joint_drift_deg = max(
        abs(math.degrees(float(a) - float(b)))
        for a, b in zip(before_arm["joint_angles_rad"], after_arm["joint_angles_rad"])
    )
    maximum_gyro = max(gyro_norms, default=float("inf"))
    if maximum_gyro > args.maximum_gyro_rad_s:
        raise RuntimeError(f"camera moved during RGB-D capture: {maximum_gyro:.4f} rad/s")
    if joint_drift_deg > args.maximum_joint_drift_deg:
        raise RuntimeError(f"arm moved during RGB-D capture: {joint_drift_deg:.4f} deg")
    if flange_translation_m > 0.001 or flange_rotation_deg > 0.2:
        raise RuntimeError(
            f"flange moved {flange_translation_m * 1000:.3f} mm / "
            f"{flange_rotation_deg:.3f} deg"
        )

    board_points = np.asarray(_board().getChessboardCorners(), dtype=np.float64)
    object_points = board_points[accepted_ids]
    camera_points = np.asarray(
        [np.median(samples_by_id[identifier], axis=0) for identifier in accepted_ids]
    )
    base_from_camera = base_from_flange @ flange_from_camera
    base_points = _apply(base_from_camera, camera_points)
    depth_base_from_target = _fit_rigid(object_points, base_points)
    pose_translation_m, pose_rotation_deg = _transform_delta(
        reference_base_from_target, depth_base_from_target
    )
    geometry = _geometry_metrics(object_points, camera_points)

    _, image, depth_raw, detected = best
    pnp_camera_from_target = np.asarray(detected["target_to_camera"], dtype=np.float64)
    pnp_camera_points = _apply(pnp_camera_from_target, object_points)
    depth_vs_pnp_m = np.linalg.norm(camera_points - pnp_camera_points, axis=1)

    args.artifacts.mkdir(parents=True, exist_ok=True)
    annotated = image.copy()
    cv2.aruco.drawDetectedCornersCharuco(
        annotated, detected["charuco_corners"], detected["charuco_ids"]
    )
    cv2.imwrite(str(args.artifacts / "color.png"), image)
    cv2.imwrite(str(args.artifacts / "annotated.png"), annotated)
    cv2.imwrite(str(args.artifacts / "aligned_depth_raw.png"), depth_raw)
    depth_preview = cv2.applyColorMap(
        cv2.convertScaleAbs(depth_raw, alpha=255.0 * depth_scale_m),
        cv2.COLORMAP_TURBO,
    )
    cv2.imwrite(str(args.artifacts / "depth_preview.png"), depth_preview)

    acceptance = {
        "minimum_depth_corners": len(accepted_ids) >= args.minimum_depth_corners,
        "rigid_fit_rms_under_8mm": geometry["rigid_fit_rms_mm"] <= 8.0,
        "square_rms_under_5mm": geometry["square_length_rms_error_mm"] <= 5.0,
        "base_target_translation_under_10mm": pose_translation_m <= 0.010,
        "base_target_rotation_under_2deg": pose_rotation_deg <= 2.0,
    }
    result = {
        "schema_version": 1,
        "ok": all(acceptance.values()),
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": "aligned_depth_color_to_flange_to_base",
        "method": method,
        "calibration": {
            "path": str(args.calibration),
            "sha256": hashlib.sha256(calibration_bytes).hexdigest(),
        },
        "camera_serial_number": args.serial,
        "color_intrinsics": {
            "width": color_intrinsics.width,
            "height": color_intrinsics.height,
            "fx": color_intrinsics.fx,
            "fy": color_intrinsics.fy,
            "ppx": color_intrinsics.ppx,
            "ppy": color_intrinsics.ppy,
            "distortion_model": str(color_intrinsics.model),
            "coefficients": [float(value) for value in color_intrinsics.coeffs],
        },
        "board": BOARD_SPEC,
        "coordinate_chain": {
            "base_from_flange": _json_matrix(base_from_flange),
            "flange_from_camera": _json_matrix(flange_from_camera),
            "base_from_camera": _json_matrix(base_from_camera),
        },
        "accepted_corner_ids": accepted_ids,
        "depth_observations_per_corner": {
            str(identifier): len(samples_by_id[identifier]) for identifier in accepted_ids
        },
        "depth_scale_m_per_unit": depth_scale_m,
        "geometry": geometry,
        "depth_vs_color_pnp": {
            "rms_mm": float(np.sqrt(np.mean(np.square(depth_vs_pnp_m))) * 1000.0),
            "max_mm": float(np.max(depth_vs_pnp_m) * 1000.0),
        },
        "base_target_consistency": {
            "translation_mm": pose_translation_m * 1000.0,
            "rotation_deg": pose_rotation_deg,
            "depth_base_from_target": _json_matrix(depth_base_from_target),
            "calibration_base_from_target": _json_matrix(reference_base_from_target),
        },
        "stability": {
            "maximum_gyro_rad_s": maximum_gyro,
            "maximum_joint_drift_deg": joint_drift_deg,
            "flange_translation_drift_mm": flange_translation_m * 1000.0,
            "flange_rotation_drift_deg": flange_rotation_deg,
        },
        "acceptance": acceptance,
        "artifacts": {
            "color": str(args.artifacts / "color.png"),
            "annotated": str(args.artifacts / "annotated.png"),
            "aligned_depth_raw": str(args.artifacts / "aligned_depth_raw.png"),
            "depth_preview": str(args.artifacts / "depth_preview.png"),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2), encoding="utf-8", newline="\n"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-test", action="store_true")
    parser.add_argument("--serial", default=CAMERA_SERIAL)
    parser.add_argument("--bridge-url", default=BRIDGE_URL)
    parser.add_argument(
        "--token-file",
        type=Path,
        default=Path(r"C:\Desktop\PIPER\remote_control\session-token.txt"),
    )
    parser.add_argument(
        "--calibration", type=Path, default=Path("results/handeye_final_park.json")
    )
    parser.add_argument("--method", choices=sorted(HAND_EYE_METHODS))
    parser.add_argument(
        "--output", type=Path, default=Path("results/depth_chain_verification.json")
    )
    parser.add_argument("--artifacts", type=Path, default=Path("depth_verification"))
    parser.add_argument("--warmup-frames", type=int, default=30)
    parser.add_argument("--capture-frames", type=int, default=60)
    parser.add_argument("--minimum-corners", type=int, default=12)
    parser.add_argument("--minimum-depth-corners", type=int, default=12)
    parser.add_argument("--minimum-depth-observations", type=int, default=10)
    parser.add_argument("--patch-radius", type=int, default=2)
    parser.add_argument("--minimum-depth-m", type=float, default=0.10)
    parser.add_argument("--maximum-depth-m", type=float, default=1.00)
    parser.add_argument("--maximum-gyro-rad-s", type=float, default=0.05)
    parser.add_argument("--maximum-joint-drift-deg", type=float, default=0.1)
    args = parser.parse_args()
    result = synthetic_test() if args.synthetic_test else verify_depth(args)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
