#!/usr/bin/env python3
"""Generate, capture, and solve PIPER eye-in-hand ChArUco calibration."""

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.request
from pathlib import Path
from typing import Any

import cv2
import numpy as np


SCHEMA_VERSION = 1
CAMERA_SERIAL = "260722303168"
ARM_MODEL = "piper_x"
IMAGE_WIDTH = 848
IMAGE_HEIGHT = 480
IMAGE_FPS = 30
BRIDGE_URL = "http://127.0.0.1:57846"
BOARD_SPEC = {
    "squares_x": 7,
    "squares_y": 5,
    "square_length_m": 0.030,
    "marker_length_m": 0.022,
    "dictionary": "DICT_5X5_100",
    "legacy_pattern": False,
}


def _dictionary():
    return cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_100)


def _board():
    board = cv2.aruco.CharucoBoard(
        (BOARD_SPEC["squares_x"], BOARD_SPEC["squares_y"]),
        BOARD_SPEC["square_length_m"],
        BOARD_SPEC["marker_length_m"],
        _dictionary(),
    )
    board.setLegacyPattern(BOARD_SPEC["legacy_pattern"])
    return board


def _transform(rotation: np.ndarray, translation: np.ndarray) -> np.ndarray:
    result = np.eye(4, dtype=np.float64)
    result[:3, :3] = np.asarray(rotation, dtype=np.float64).reshape(3, 3)
    result[:3, 3] = np.asarray(translation, dtype=np.float64).reshape(3)
    return result


def _invert(transform: np.ndarray) -> np.ndarray:
    result = np.eye(4, dtype=np.float64)
    rotation = transform[:3, :3]
    result[:3, :3] = rotation.T
    result[:3, 3] = -rotation.T @ transform[:3, 3]
    return result


def _rpy_rotation(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """Match pyAgxArm: R = Rz(yaw) @ Ry(pitch) @ Rx(roll)."""
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return np.array(
        [
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr],
        ],
        dtype=np.float64,
    )


def _pose6_transform(pose: list[float]) -> np.ndarray:
    if len(pose) != 6 or not all(math.isfinite(float(value)) for value in pose):
        raise ValueError("flange pose must contain six finite m/rad values")
    return _transform(_rpy_rotation(*map(float, pose[3:])), pose[:3])


def _rotation_distance_deg(first: np.ndarray, second: np.ndarray) -> float:
    relative = first[:3, :3].T @ second[:3, :3]
    cosine = float(np.clip((np.trace(relative) - 1.0) / 2.0, -1.0, 1.0))
    return math.degrees(math.acos(cosine))


def _transform_delta(first: np.ndarray, second: np.ndarray) -> tuple[float, float]:
    translation_m = float(np.linalg.norm(first[:3, 3] - second[:3, 3]))
    return translation_m, _rotation_distance_deg(first, second)


def _json_matrix(matrix: np.ndarray) -> list[list[float]]:
    return np.asarray(matrix, dtype=np.float64).tolist()


def _mean_rotation(rotations: list[np.ndarray]) -> np.ndarray:
    u, _, vt = np.linalg.svd(sum(rotations))
    rotation = u @ vt
    if np.linalg.det(rotation) < 0:
        u[:, -1] *= -1
        rotation = u @ vt
    return rotation


def generate_board(output: Path, dpi: int) -> dict[str, Any]:
    from PIL import Image, ImageDraw

    output.mkdir(parents=True, exist_ok=True)
    millimeters_per_inch = 25.4
    page_mm = (297.0, 210.0)
    board_mm = (
        BOARD_SPEC["squares_x"] * BOARD_SPEC["square_length_m"] * 1000.0,
        BOARD_SPEC["squares_y"] * BOARD_SPEC["square_length_m"] * 1000.0,
    )
    page_px = tuple(round(value / millimeters_per_inch * dpi) for value in page_mm)
    board_px = tuple(round(value / millimeters_per_inch * dpi) for value in board_mm)
    board_image = _board().generateImage(board_px, marginSize=0, borderBits=1)
    page = Image.new("L", page_px, 255)
    origin = ((page_px[0] - board_px[0]) // 2, (page_px[1] - board_px[1]) // 2)
    page.paste(Image.fromarray(board_image), origin)

    draw = ImageDraw.Draw(page)
    bar_length_px = round(100.0 / millimeters_per_inch * dpi)
    bar_y = page_px[1] - round(12.0 / millimeters_per_inch * dpi)
    bar_x = (page_px[0] - bar_length_px) // 2
    line_width = max(2, round(dpi / 75))
    draw.line((bar_x, bar_y, bar_x + bar_length_px, bar_y), fill=0, width=line_width)
    tick = round(3.0 / millimeters_per_inch * dpi)
    draw.line((bar_x, bar_y - tick, bar_x, bar_y + tick), fill=0, width=line_width)
    draw.line(
        (bar_x + bar_length_px, bar_y - tick, bar_x + bar_length_px, bar_y + tick),
        fill=0,
        width=line_width,
    )
    draw.text((bar_x, bar_y + tick + 2), "100 mm - verify after printing", fill=0)

    png_path = output / "piper_charuco_7x5_a4_landscape_300dpi.png"
    pdf_path = output / "piper_charuco_7x5_a4_landscape.pdf"
    spec_path = output / "board_spec.json"
    page.save(png_path, dpi=(dpi, dpi))
    page.convert("RGB").save(pdf_path, "PDF", resolution=dpi)
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "board": BOARD_SPEC,
        "page_size_mm": list(page_mm),
        "board_size_mm": list(board_mm),
        "dpi": dpi,
        "print_scale": "100%; disable Fit/Shrink/Oversize",
        "verification": "measure the printed 100 mm bar and 30 mm ChArUco squares",
        "files": {"png": png_path.name, "pdf": pdf_path.name},
    }
    spec_path.write_text(
        json.dumps(metadata, indent=2), encoding="utf-8", newline="\n"
    )
    return metadata


def _read_bridge_state(url: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url.rstrip("/") + "/v1/state",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=3.0) as response:
        payload = json.load(response)
    if payload.get("ok") is not True or not isinstance(payload.get("state"), dict):
        raise RuntimeError(f"unexpected bridge state response: {payload}")
    state = payload["state"]
    arm = state.get("arm", {})
    if state.get("bridge", {}).get("mode") != "observe":
        raise RuntimeError("sample capture requires the observe-only bridge")
    if not arm.get("healthy") or arm.get("err_code") != 0 or arm.get("comm_error"):
        raise RuntimeError("PIPER feedback is not healthy")
    if arm.get("model") != ARM_MODEL:
        raise RuntimeError(
            f"bridge model is {arm.get('model')!r}; expected {ARM_MODEL!r} for this arm"
        )
    pose = arm.get("flange_pose_m_rad")
    if not isinstance(pose, list) or len(pose) != 6:
        raise RuntimeError("bridge v0.6.0 flange pose feedback is unavailable")
    fk_pose = arm.get("flange_pose_fk_m_rad")
    if not isinstance(fk_pose, list) or len(fk_pose) != 6:
        raise RuntimeError("bridge v0.6.0 flange FK cross-check is unavailable")
    if arm.get("flange_feedback_age_s") is None or arm["flange_feedback_age_s"] > 0.1:
        raise RuntimeError("PIPER flange feedback is stale")
    translation_m, rotation_deg = _transform_delta(
        _pose6_transform(pose), _pose6_transform(fk_pose)
    )
    if translation_m > 0.002 or rotation_deg > 0.5:
        raise RuntimeError(
            "controller flange feedback disagrees with joint FK: "
            f"{translation_m * 1000:.3f} mm / {rotation_deg:.3f} deg"
        )
    return state


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    import pyrealsense2 as rs

    token = args.token_file.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError("bridge token file is empty")
    state = _read_bridge_state(args.bridge_url, token)
    arm = state["arm"]
    feedback = _pose6_transform(arm["flange_pose_m_rad"])
    forward_kinematics = _pose6_transform(arm["flange_pose_fk_m_rad"])
    fk_translation_m, fk_rotation_deg = _transform_delta(
        feedback, forward_kinematics
    )

    device = next(
        (
            candidate
            for candidate in rs.context().query_devices()
            if candidate.get_info(rs.camera_info.serial_number) == args.serial
        ),
        None,
    )
    if device is None:
        raise RuntimeError(f"D455 serial {args.serial} was not found")

    def device_info(field: Any) -> str | None:
        return device.get_info(field) if device.supports(field) else None

    return {
        "ok": True,
        "bridge": {
            "version": state["bridge"]["version"],
            "mode": state["bridge"]["mode"],
        },
        "arm": {
            "model": arm["model"],
            "firmware": arm["firmware"],
            "healthy": arm["healthy"],
            "arm_status": arm["arm_status"],
            "teach_status": arm["teach_status"],
            "joint_feedback_hz": arm["joint_feedback_hz"],
            "flange_feedback_age_s": arm["flange_feedback_age_s"],
            "flange_fk_translation_error_mm": fk_translation_m * 1000.0,
            "flange_fk_rotation_error_deg": fk_rotation_deg,
        },
        "camera": {
            "name": device_info(rs.camera_info.name),
            "serial_number": device_info(rs.camera_info.serial_number),
            "firmware_version": device_info(rs.camera_info.firmware_version),
            "usb_type_descriptor": device_info(rs.camera_info.usb_type_descriptor),
        },
    }


def _detect_pose(image_bgr: np.ndarray, intrinsics: Any, rs: Any) -> dict[str, Any] | None:
    detector = cv2.aruco.CharucoDetector(_board())
    charuco_corners, charuco_ids, marker_corners, marker_ids = detector.detectBoard(image_bgr)
    if charuco_ids is None or len(charuco_ids) < 4:
        return None
    object_points, image_points = _board().matchImagePoints(charuco_corners, charuco_ids)
    normalized = []
    for u, v in image_points.reshape(-1, 2):
        ray = rs.rs2_deproject_pixel_to_point(intrinsics, [float(u), float(v)], 1.0)
        normalized.append([ray[0] / ray[2], ray[1] / ray[2]])
    normalized_points = np.asarray(normalized, dtype=np.float64).reshape(-1, 1, 2)
    identity_camera = np.eye(3, dtype=np.float64)
    result = cv2.solvePnPGeneric(
        np.asarray(object_points, dtype=np.float64),
        normalized_points,
        identity_camera,
        None,
        flags=cv2.SOLVEPNP_IPPE,
    )
    candidates = []
    if result[0]:
        for rvec, tvec in zip(result[1], result[2]):
            if float(tvec.reshape(3)[2]) <= 0:
                continue
            projected, _ = cv2.projectPoints(
                object_points, rvec, tvec, identity_camera, None
            )
            normalized_rms = float(
                np.sqrt(np.mean(np.sum((projected - normalized_points) ** 2, axis=2)))
            )
            candidates.append((normalized_rms, rvec, tvec))
    if not candidates:
        return None
    normalized_rms, rvec, tvec = min(candidates, key=lambda candidate: candidate[0])
    rotation, _ = cv2.Rodrigues(rvec)
    approximate_pixel_rms = normalized_rms * math.sqrt(intrinsics.fx * intrinsics.fy)
    return {
        "charuco_corners": charuco_corners,
        "charuco_ids": charuco_ids,
        "marker_corners": marker_corners,
        "marker_ids": marker_ids,
        "target_to_camera": _transform(rotation, tvec),
        "normalized_rms": normalized_rms,
        "approximate_pixel_rms": approximate_pixel_rms,
    }


def _next_sample_directory(dataset: Path) -> Path:
    indices = []
    for path in dataset.glob("sample_*"):
        try:
            indices.append(int(path.name.split("_", 1)[1]))
        except ValueError:
            continue
    return dataset / f"sample_{max(indices, default=0) + 1:03d}"


def _check_duplicate(dataset: Path, flange: np.ndarray) -> None:
    for metadata_path in dataset.glob("sample_*/sample.json"):
        existing = json.loads(metadata_path.read_text(encoding="utf-8"))
        existing_flange = np.asarray(existing["robot"]["base_from_flange"], dtype=np.float64)
        translation_m, rotation_deg = _transform_delta(existing_flange, flange)
        if translation_m < 0.015 and rotation_deg < 5.0:
            raise RuntimeError(
                f"pose duplicates {metadata_path.parent.name}: "
                f"{translation_m * 1000:.1f} mm / {rotation_deg:.2f} deg"
            )


def capture_sample(args: argparse.Namespace) -> dict[str, Any]:
    import pyrealsense2 as rs

    token = args.token_file.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError("bridge token file is empty")
    args.dataset.mkdir(parents=True, exist_ok=True)

    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_device(args.serial)
    config.enable_stream(
        rs.stream.color, IMAGE_WIDTH, IMAGE_HEIGHT, rs.format.bgr8, IMAGE_FPS
    )
    config.enable_stream(rs.stream.gyro, rs.format.motion_xyz32f, 200)
    started = False
    try:
        profile = pipeline.start(config)
        started = True
        for _ in range(args.warmup_frames):
            pipeline.wait_for_frames(5000)

        before = _read_bridge_state(args.bridge_url, token)
        color_profile = profile.get_stream(rs.stream.color).as_video_stream_profile()
        intrinsics = color_profile.get_intrinsics()
        best = None
        gyro_norms = []
        for _ in range(args.capture_frames):
            frames = pipeline.wait_for_frames(5000)
            color = frames.get_color_frame()
            if not color:
                continue
            gyro_frame = next(
                (frame for frame in frames if frame.profile.stream_type() == rs.stream.gyro),
                None,
            )
            if gyro_frame:
                gyro = gyro_frame.as_motion_frame().get_motion_data()
                gyro_norms.append(math.sqrt(gyro.x**2 + gyro.y**2 + gyro.z**2))
            image = np.asanyarray(color.get_data()).copy()
            detected = _detect_pose(image, intrinsics, rs)
            if detected is None:
                continue
            score = (len(detected["charuco_ids"]), -detected["approximate_pixel_rms"])
            if best is None or score > best[0]:
                best = (score, image, color.get_timestamp(), color.get_frame_number(), detected)
        after = _read_bridge_state(args.bridge_url, token)
    finally:
        if started:
            pipeline.stop()

    if best is None:
        raise RuntimeError("ChArUco board was not detected")
    _, image, camera_timestamp_ms, camera_frame_number, detected = best
    if len(detected["charuco_ids"]) < args.minimum_corners:
        raise RuntimeError(
            f"only {len(detected['charuco_ids'])} ChArUco corners; "
            f"need at least {args.minimum_corners}"
        )
    if detected["approximate_pixel_rms"] > args.maximum_reprojection_px:
        raise RuntimeError(
            f"PnP residual {detected['approximate_pixel_rms']:.3f}px exceeds "
            f"{args.maximum_reprojection_px:.3f}px"
        )

    before_arm, after_arm = before["arm"], after["arm"]
    before_pose = _pose6_transform(before_arm["flange_pose_m_rad"])
    after_pose = _pose6_transform(after_arm["flange_pose_m_rad"])
    after_fk_pose = _pose6_transform(after_arm["flange_pose_fk_m_rad"])
    fk_translation_m, fk_rotation_deg = _transform_delta(after_pose, after_fk_pose)
    flange_translation_m, flange_rotation_deg = _transform_delta(before_pose, after_pose)
    joint_drift_deg = max(
        abs(math.degrees(float(a) - float(b)))
        for a, b in zip(before_arm["joint_angles_rad"], after_arm["joint_angles_rad"])
    )
    maximum_gyro = max(gyro_norms, default=float("inf"))
    if maximum_gyro > args.maximum_gyro_rad_s:
        raise RuntimeError(
            f"camera moved during capture: gyro {maximum_gyro:.4f} rad/s exceeds "
            f"{args.maximum_gyro_rad_s:.4f}"
        )
    if joint_drift_deg > args.maximum_joint_drift_deg:
        raise RuntimeError(
            f"arm moved during capture: joint drift {joint_drift_deg:.4f} deg exceeds "
            f"{args.maximum_joint_drift_deg:.4f} deg"
        )
    if flange_translation_m > 0.001 or flange_rotation_deg > 0.2:
        raise RuntimeError(
            f"flange moved {flange_translation_m * 1000:.3f} mm / "
            f"{flange_rotation_deg:.3f} deg during capture"
        )
    _check_duplicate(args.dataset, after_pose)

    sample_dir = _next_sample_directory(args.dataset)
    sample_dir.mkdir()
    annotated = image.copy()
    cv2.aruco.drawDetectedCornersCharuco(
        annotated, detected["charuco_corners"], detected["charuco_ids"]
    )
    cv2.imwrite(str(sample_dir / "color.png"), image)
    cv2.imwrite(str(sample_dir / "annotated.png"), annotated)
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "captured_at_unix_s": time.time(),
        "camera": {
            "serial_number": args.serial,
            "frame_number": int(camera_frame_number),
            "timestamp_ms": float(camera_timestamp_ms),
            "intrinsics": {
                "width": intrinsics.width,
                "height": intrinsics.height,
                "fx": intrinsics.fx,
                "fy": intrinsics.fy,
                "ppx": intrinsics.ppx,
                "ppy": intrinsics.ppy,
                "model": str(intrinsics.model),
                "coeffs": list(intrinsics.coeffs),
            },
            "maximum_gyro_rad_s": maximum_gyro,
        },
        "board": BOARD_SPEC,
        "detection": {
            "charuco_corner_count": len(detected["charuco_ids"]),
            "charuco_ids": detected["charuco_ids"].reshape(-1).astype(int).tolist(),
            "target_to_camera": _json_matrix(detected["target_to_camera"]),
            "normalized_rms": detected["normalized_rms"],
            "approximate_pixel_rms": detected["approximate_pixel_rms"],
            "normalization": "RealSense deproject_pixel_to_point at z=1m",
        },
        "robot": {
            "bridge_version": after["bridge"]["version"],
            "model": after_arm["model"],
            "control_mode": after_arm["ctrl_mode"],
            "teach_status": after_arm["teach_status"],
            "joint_angles_rad": after_arm["joint_angles_rad"],
            "flange_pose_m_rad": after_arm["flange_pose_m_rad"],
            "flange_pose_fk_m_rad": after_arm["flange_pose_fk_m_rad"],
            "base_from_flange": _json_matrix(after_pose),
            "stability": {
                "maximum_joint_drift_deg": joint_drift_deg,
                "flange_translation_drift_m": flange_translation_m,
                "flange_rotation_drift_deg": flange_rotation_deg,
                "flange_fk_translation_error_m": fk_translation_m,
                "flange_fk_rotation_error_deg": fk_rotation_deg,
            },
        },
        "files": {"color": "color.png", "annotated": "annotated.png"},
    }
    (sample_dir / "sample.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8", newline="\n"
    )
    return {"sample": sample_dir.name, **metadata["detection"], **metadata["robot"]["stability"]}


HAND_EYE_METHODS = {
    "TSAI": cv2.CALIB_HAND_EYE_TSAI,
    "PARK": cv2.CALIB_HAND_EYE_PARK,
    "HORAUD": cv2.CALIB_HAND_EYE_HORAUD,
    "ANDREFF": cv2.CALIB_HAND_EYE_ANDREFF,
    "DANIILIDIS": cv2.CALIB_HAND_EYE_DANIILIDIS,
}


def _pose_diversity(base_from_flange: list[np.ndarray]) -> dict[str, float]:
    maximum_translation_m = 0.0
    maximum_rotation_deg = 0.0
    rotation_vectors = []
    reference = base_from_flange[0]
    for pose in base_from_flange[1:]:
        translation_m, rotation_deg = _transform_delta(reference, pose)
        maximum_translation_m = max(maximum_translation_m, translation_m)
        maximum_rotation_deg = max(maximum_rotation_deg, rotation_deg)
        relative_rotation = reference[:3, :3].T @ pose[:3, :3]
        rvec, _ = cv2.Rodrigues(relative_rotation)
        rotation_vectors.append(rvec.reshape(3))
    singular_values = np.linalg.svd(np.asarray(rotation_vectors), compute_uv=False)
    second_axis_ratio = (
        float(singular_values[1] / singular_values[0]) if singular_values[0] > 0 else 0.0
    )
    return {
        "maximum_translation_m": maximum_translation_m,
        "maximum_rotation_deg": maximum_rotation_deg,
        "second_rotation_axis_ratio": second_axis_ratio,
    }


def _solve_transforms(
    base_from_flange: list[np.ndarray], camera_from_target: list[np.ndarray]
) -> dict[str, Any]:
    rotations_gripper_to_base = [pose[:3, :3] for pose in base_from_flange]
    translations_gripper_to_base = [pose[:3, 3].reshape(3, 1) for pose in base_from_flange]
    rotations_target_to_camera = [pose[:3, :3] for pose in camera_from_target]
    translations_target_to_camera = [pose[:3, 3].reshape(3, 1) for pose in camera_from_target]
    results = {}
    for name, method in HAND_EYE_METHODS.items():
        rotation, translation = cv2.calibrateHandEye(
            rotations_gripper_to_base,
            translations_gripper_to_base,
            rotations_target_to_camera,
            translations_target_to_camera,
            method=method,
        )
        camera_to_flange = _transform(rotation, translation)
        base_from_target = [
            base_from_flange[index] @ camera_to_flange @ camera_from_target[index]
            for index in range(len(base_from_flange))
        ]
        mean_translation = np.mean([pose[:3, 3] for pose in base_from_target], axis=0)
        mean_rotation = _mean_rotation([pose[:3, :3] for pose in base_from_target])
        translation_errors = [
            float(np.linalg.norm(pose[:3, 3] - mean_translation))
            for pose in base_from_target
        ]
        rotation_errors = [
            _rotation_distance_deg(_transform(mean_rotation, mean_translation), pose)
            for pose in base_from_target
        ]
        translation_rms_mm = math.sqrt(np.mean(np.square(translation_errors))) * 1000.0
        rotation_rms_deg = math.sqrt(np.mean(np.square(rotation_errors)))
        results[name] = {
            "camera_to_flange": _json_matrix(camera_to_flange),
            "flange_to_camera": _json_matrix(_invert(camera_to_flange)),
            "base_from_target_mean": _json_matrix(
                _transform(mean_rotation, mean_translation)
            ),
            "translation_rms_mm": translation_rms_mm,
            "rotation_rms_deg": rotation_rms_deg,
            "sample_residuals": [
                {
                    "index": index,
                    "translation_mm": translation_errors[index] * 1000.0,
                    "rotation_deg": rotation_errors[index],
                }
                for index in range(len(base_from_target))
            ],
            "score": translation_rms_mm + 2.0 * rotation_rms_deg,
        }
    recommended = min(results, key=lambda name: results[name]["score"])
    reference = np.asarray(results[recommended]["camera_to_flange"])
    method_spread = {
        name: {
            "translation_mm": _transform_delta(
                reference, np.asarray(result["camera_to_flange"])
            )[0]
            * 1000.0,
            "rotation_deg": _transform_delta(
                reference, np.asarray(result["camera_to_flange"])
            )[1],
        }
        for name, result in results.items()
    }
    return {"recommended_method": recommended, "methods": results, "method_spread": method_spread}


def solve_dataset(dataset: Path, output: Path) -> dict[str, Any]:
    metadata_paths = sorted(dataset.glob("sample_*/sample.json"))
    if len(metadata_paths) < 10:
        raise RuntimeError(f"need at least 10 samples, found {len(metadata_paths)}")
    samples = [json.loads(path.read_text(encoding="utf-8")) for path in metadata_paths]
    if any(sample["board"] != BOARD_SPEC for sample in samples):
        raise RuntimeError("dataset contains a different ChArUco board specification")
    serials = {sample["camera"]["serial_number"] for sample in samples}
    if len(serials) != 1:
        raise RuntimeError(f"dataset mixes camera serial numbers: {sorted(serials)}")
    models = {sample.get("robot", {}).get("model") for sample in samples}
    if models != {ARM_MODEL}:
        raise RuntimeError(f"dataset robot models must be only {ARM_MODEL!r}: {models}")
    base_from_flange = [
        np.asarray(sample["robot"]["base_from_flange"], dtype=np.float64)
        for sample in samples
    ]
    camera_from_target = [
        np.asarray(sample["detection"]["target_to_camera"], dtype=np.float64)
        for sample in samples
    ]
    diversity = _pose_diversity(base_from_flange)
    if diversity["maximum_rotation_deg"] < 20.0:
        raise RuntimeError("pose rotation span is below 20 degrees")
    if diversity["second_rotation_axis_ratio"] < 0.15:
        raise RuntimeError("rotations do not sufficiently cover two independent axes")
    result = {
        "schema_version": SCHEMA_VERSION,
        "configuration": "eye_in_hand",
        "sample_count": len(samples),
        "sample_names": [path.parent.name for path in metadata_paths],
        "camera_serial_number": next(iter(serials)),
        "board": BOARD_SPEC,
        "pose_diversity": diversity,
        **_solve_transforms(base_from_flange, camera_from_target),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2), encoding="utf-8", newline="\n"
    )
    return result


def _validation_residuals(
    reference_base_from_target: np.ndarray,
    camera_to_flange: np.ndarray,
    base_from_flange: list[np.ndarray],
    camera_from_target: list[np.ndarray],
) -> list[dict[str, Any]]:
    residuals = []
    for flange, target in zip(base_from_flange, camera_from_target):
        estimate = flange @ camera_to_flange @ target
        translation_m, rotation_deg = _transform_delta(
            reference_base_from_target, estimate
        )
        residuals.append(
            {
                "base_from_target": _json_matrix(estimate),
                "translation_mm": translation_m * 1000.0,
                "rotation_deg": rotation_deg,
            }
        )
    return residuals


def validate_dataset(
    dataset: Path, calibration_path: Path, output: Path, method: str | None
) -> dict[str, Any]:
    metadata_paths = sorted(dataset.glob("sample_*/sample.json"))
    if not metadata_paths:
        raise RuntimeError(f"no validation samples found in {dataset}")
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    selected_method = method or calibration["recommended_method"]
    if selected_method not in calibration.get("methods", {}):
        raise RuntimeError(f"calibration result does not contain method {selected_method}")

    samples = [json.loads(path.read_text(encoding="utf-8")) for path in metadata_paths]
    if any(sample["board"] != calibration["board"] for sample in samples):
        raise RuntimeError("validation dataset uses a different ChArUco board")
    serials = {sample["camera"]["serial_number"] for sample in samples}
    if serials != {calibration["camera_serial_number"]}:
        raise RuntimeError(f"validation camera serial mismatch: {serials}")
    models = {sample.get("robot", {}).get("model") for sample in samples}
    if models != {ARM_MODEL}:
        raise RuntimeError(f"validation robot models must be only {ARM_MODEL!r}: {models}")

    method_result = calibration["methods"][selected_method]
    residuals = _validation_residuals(
        np.asarray(method_result["base_from_target_mean"], dtype=np.float64),
        np.asarray(method_result["camera_to_flange"], dtype=np.float64),
        [
            np.asarray(sample["robot"]["base_from_flange"], dtype=np.float64)
            for sample in samples
        ],
        [
            np.asarray(sample["detection"]["target_to_camera"], dtype=np.float64)
            for sample in samples
        ],
    )
    for name, residual in zip(
        [path.parent.name for path in metadata_paths], residuals
    ):
        residual["sample"] = name
    translation_errors = [residual["translation_mm"] for residual in residuals]
    rotation_errors = [residual["rotation_deg"] for residual in residuals]
    result = {
        "schema_version": SCHEMA_VERSION,
        "configuration": "eye_in_hand_validation",
        "calibration_file": str(calibration_path),
        "method": selected_method,
        "sample_count": len(samples),
        "translation_rms_mm": math.sqrt(np.mean(np.square(translation_errors))),
        "translation_max_mm": max(translation_errors),
        "rotation_rms_deg": math.sqrt(np.mean(np.square(rotation_errors))),
        "rotation_max_deg": max(rotation_errors),
        "sample_residuals": residuals,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2), encoding="utf-8", newline="\n"
    )
    return result


def synthetic_test() -> dict[str, Any]:
    import pyrealsense2 as rs

    intrinsics = rs.intrinsics()
    intrinsics.width = IMAGE_WIDTH
    intrinsics.height = IMAGE_HEIGHT
    intrinsics.fx = 600.0
    intrinsics.fy = 600.0
    intrinsics.ppx = IMAGE_WIDTH / 2.0
    intrinsics.ppy = IMAGE_HEIGHT / 2.0
    intrinsics.model = rs.distortion.none
    intrinsics.coeffs = [0.0] * 5
    board_image = _board().generateImage((560, 400), marginSize=0, borderBits=1)
    synthetic_image = np.full((IMAGE_HEIGHT, IMAGE_WIDTH, 3), 255, dtype=np.uint8)
    synthetic_image[40:440, 144:704] = cv2.cvtColor(board_image, cv2.COLOR_GRAY2BGR)
    detection = _detect_pose(synthetic_image, intrinsics, rs)
    if detection is None or len(detection["charuco_ids"]) != 24:
        raise RuntimeError("synthetic ChArUco detection did not find all 24 corners")
    if detection["approximate_pixel_rms"] > 0.75:
        raise RuntimeError(
            "synthetic ChArUco PnP residual is too large: "
            f"{detection['approximate_pixel_rms']:.6f}px"
        )

    rng = np.random.default_rng(20260809)
    true_camera_to_flange = _transform(
        cv2.Rodrigues(np.array([0.22, -0.14, 0.18], dtype=np.float64))[0],
        np.array([0.035, -0.028, 0.075]),
    )
    base_from_target = _transform(
        cv2.Rodrigues(np.array([0.08, -0.10, 0.04], dtype=np.float64))[0],
        np.array([0.45, 0.03, 0.20]),
    )
    base_from_flange = []
    camera_from_target = []
    for _ in range(20):
        axis = rng.normal(size=3)
        axis /= np.linalg.norm(axis)
        angle = rng.uniform(-1.0, 1.0)
        flange = _transform(
            cv2.Rodrigues(axis * angle)[0],
            np.array(
                [rng.uniform(0.15, 0.45), rng.uniform(-0.25, 0.25), rng.uniform(0.15, 0.45)]
            ),
        )
        base_from_camera = flange @ true_camera_to_flange
        base_from_flange.append(flange)
        camera_from_target.append(_invert(base_from_camera) @ base_from_target)
    solved = _solve_transforms(base_from_flange, camera_from_target)
    errors = {}
    for name, result in solved["methods"].items():
        estimate = np.asarray(result["camera_to_flange"])
        translation_m, rotation_deg = _transform_delta(true_camera_to_flange, estimate)
        errors[name] = {
            "translation_m": translation_m,
            "rotation_deg": rotation_deg,
        }
        if translation_m > 1e-6 or rotation_deg > 1e-5:
            raise RuntimeError(f"synthetic {name} solution error is too large: {errors[name]}")
    validation = _validation_residuals(
        base_from_target,
        true_camera_to_flange,
        base_from_flange,
        camera_from_target,
    )
    if max(item["translation_mm"] for item in validation) > 1e-9 or max(
        item["rotation_deg"] for item in validation
    ) > 1e-5:
        raise RuntimeError("synthetic validation residual is not zero")
    return {
        "ok": True,
        "charuco_corner_count": len(detection["charuco_ids"]),
        "charuco_approximate_pixel_rms": detection["approximate_pixel_rms"],
        "hand_eye_errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    board_parser = subparsers.add_parser("board")
    board_parser.add_argument("--output", type=Path, default=Path("board"))
    board_parser.add_argument("--dpi", type=int, default=300)

    preflight_parser = subparsers.add_parser("preflight")
    preflight_parser.add_argument("--serial", default=CAMERA_SERIAL)
    preflight_parser.add_argument("--bridge-url", default=BRIDGE_URL)
    preflight_parser.add_argument(
        "--token-file",
        type=Path,
        default=Path(r"C:\Desktop\PIPER\remote_control\session-token.txt"),
    )

    capture_parser = subparsers.add_parser("capture")
    capture_parser.add_argument("--dataset", type=Path, default=Path("dataset"))
    capture_parser.add_argument("--serial", default=CAMERA_SERIAL)
    capture_parser.add_argument("--bridge-url", default=BRIDGE_URL)
    capture_parser.add_argument(
        "--token-file",
        type=Path,
        default=Path(r"C:\Desktop\PIPER\remote_control\session-token.txt"),
    )
    capture_parser.add_argument("--warmup-frames", type=int, default=30)
    capture_parser.add_argument("--capture-frames", type=int, default=24)
    capture_parser.add_argument("--minimum-corners", type=int, default=12)
    capture_parser.add_argument("--maximum-reprojection-px", type=float, default=1.5)
    capture_parser.add_argument("--maximum-gyro-rad-s", type=float, default=0.05)
    capture_parser.add_argument("--maximum-joint-drift-deg", type=float, default=0.1)

    solve_parser = subparsers.add_parser("solve")
    solve_parser.add_argument("--dataset", type=Path, default=Path("dataset"))
    solve_parser.add_argument(
        "--output", type=Path, default=Path("results/handeye_result.json")
    )

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument(
        "--dataset", type=Path, default=Path("validation_dataset")
    )
    validate_parser.add_argument(
        "--calibration", type=Path, default=Path("results/handeye_result.json")
    )
    validate_parser.add_argument(
        "--output", type=Path, default=Path("results/validation_result.json")
    )
    validate_parser.add_argument("--method", choices=sorted(HAND_EYE_METHODS))

    subparsers.add_parser("synthetic-test")
    args = parser.parse_args()
    if args.command == "board":
        result = generate_board(args.output, args.dpi)
    elif args.command == "preflight":
        result = preflight(args)
    elif args.command == "capture":
        result = capture_sample(args)
    elif args.command == "solve":
        result = solve_dataset(args.dataset, args.output)
    elif args.command == "validate":
        result = validate_dataset(
            args.dataset, args.calibration, args.output, args.method
        )
    else:
        result = synthetic_test()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
