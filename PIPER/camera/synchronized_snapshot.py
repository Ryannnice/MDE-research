#!/usr/bin/env python3
"""Capture one read-only D455/PIPER-X snapshot and a base-frame point cloud."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image


PIPER_ROOT = Path(__file__).resolve().parents[1]
HAND_EYE_ROOT = PIPER_ROOT / "handeye"
if str(HAND_EYE_ROOT) not in sys.path:
    sys.path.insert(0, str(HAND_EYE_ROOT))

from handeye_calibration import (  # noqa: E402
    ARM_MODEL,
    BRIDGE_URL,
    CAMERA_SERIAL,
    HAND_EYE_METHODS,
    IMAGE_FPS,
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    _json_matrix,
    _pose6_transform,
    _read_bridge_state,
)


DEFAULT_TOKEN_FILE = Path(r"C:\Desktop\PIPER\remote_control\session-token.txt")
DEFAULT_CALIBRATION = HAND_EYE_ROOT / "results" / "handeye_final_park.json"


def _transform_points(transform: np.ndarray, points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    return (transform[:3, :3] @ points.T).T + transform[:3, 3]


def _timed_robot_state(url: str, token: str) -> dict[str, Any]:
    started_ns = time.time_ns()
    state = _read_bridge_state(url, token)
    finished_ns = time.time_ns()
    midpoint_ns = (started_ns + finished_ns) // 2
    arm = state["arm"]
    flange_age_s = float(arm["flange_feedback_age_s"])
    joint_age_s = float(arm["feedback_age_s"])
    return {
        "query_started_unix_ns": started_ns,
        "query_finished_unix_ns": finished_ns,
        "query_midpoint_unix_ns": midpoint_ns,
        "roundtrip_ms": (finished_ns - started_ns) / 1e6,
        "flange_measurement_unix_ns": midpoint_ns - round(flange_age_s * 1e9),
        "joint_measurement_unix_ns": midpoint_ns - round(joint_age_s * 1e9),
        "state": state,
    }


class RobotSampler:
    def __init__(self, url: str, token: str, rate_hz: float, capacity: int = 1000):
        self._url = url
        self._token = token
        self._period_s = 1.0 / rate_hz
        self._records: deque[dict[str, Any]] = deque(maxlen=capacity)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._error: Exception | None = None
        self._thread = threading.Thread(target=self._run, name="piper-state-sampler")

    def _run(self) -> None:
        next_poll = time.perf_counter()
        sequence = 0
        while not self._stop.is_set():
            try:
                record = _timed_robot_state(self._url, self._token)
            except Exception as exc:
                self._error = exc
                return
            record["sequence"] = sequence
            sequence += 1
            with self._lock:
                self._records.append(record)
            next_poll += self._period_s
            self._stop.wait(max(0.0, next_poll - time.perf_counter()))

    def start(self) -> None:
        self._thread.start()

    def records(self) -> list[dict[str, Any]]:
        if self._error is not None:
            raise RuntimeError(f"robot sampler failed: {self._error}") from self._error
        with self._lock:
            return list(self._records)

    def wait_for_records(self, minimum: int, timeout_s: float) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if len(self.records()) >= minimum:
                return True
            self._stop.wait(0.01)
        return len(self.records()) >= minimum

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5.0)


def _select_robot_sample(
    frame_unix_ns: int,
    samples: list[tuple[str, dict[str, Any]]],
) -> tuple[str, dict[str, Any], float]:
    label, sample = min(
        samples,
        key=lambda item: abs(item[1]["flange_measurement_unix_ns"] - frame_unix_ns),
    )
    offset_ms = (sample["flange_measurement_unix_ns"] - frame_unix_ns) / 1e6
    return label, sample, offset_ms


def _record_summary(record: dict[str, Any]) -> dict[str, float | int]:
    return {
        key: record[key]
        for key in (
            "query_started_unix_ns",
            "query_finished_unix_ns",
            "query_midpoint_unix_ns",
            "roundtrip_ms",
            "flange_measurement_unix_ns",
            "joint_measurement_unix_ns",
        )
    }


def _device_info(device: Any, key: Any) -> str | None:
    return device.get_info(key) if device.supports(key) else None


def _intrinsics(profile: Any) -> dict[str, Any]:
    value = profile.as_video_stream_profile().get_intrinsics()
    return {
        "width": value.width,
        "height": value.height,
        "fx": value.fx,
        "fy": value.fy,
        "ppx": value.ppx,
        "ppy": value.ppy,
        "distortion_model": str(value.model),
        "coefficients": [float(item) for item in value.coeffs],
    }


def _frame_metadata(frame: Any, rs: Any) -> dict[str, Any]:
    result = {
        "frame_number": frame.get_frame_number(),
        "timestamp_ms": frame.get_timestamp(),
        "timestamp_domain": str(frame.get_frame_timestamp_domain()),
    }
    for name in (
        "frame_timestamp",
        "sensor_timestamp",
        "backend_timestamp",
        "time_of_arrival",
        "frame_counter",
    ):
        key = getattr(rs.frame_metadata_value, name)
        result[name] = frame.get_frame_metadata(key) if frame.supports_frame_metadata(key) else None
    return result


def _motion_sample(frame: Any | None) -> dict[str, float | int] | None:
    if frame is None:
        return None
    value = frame.as_motion_frame().get_motion_data()
    return {
        "frame_number": frame.get_frame_number(),
        "timestamp_ms": frame.get_timestamp(),
        "x": value.x,
        "y": value.y,
        "z": value.z,
        "norm": math.sqrt(value.x**2 + value.y**2 + value.z**2),
    }


def _next_video_frames(
    pipeline: Any,
    last_color_number: int | None,
    maximum_video_skew_ms: float,
    timeout_s: float = 10.0,
) -> tuple[Any, int, float]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        remaining_ms = max(1, min(5000, round((deadline - time.monotonic()) * 1000)))
        frames = pipeline.wait_for_frames(remaining_ms)
        color = frames.get_color_frame()
        depth = frames.get_depth_frame()
        if not color or not depth or color.get_frame_number() == last_color_number:
            continue
        skew_ms = abs(color.get_timestamp() - depth.get_timestamp())
        if skew_ms > maximum_video_skew_ms:
            last_color_number = color.get_frame_number()
            continue
        return frames, color.get_frame_number(), skew_ms
    raise RuntimeError("no new synchronized RGB-D frame arrived before the timeout")


def _start_ready_pipeline(rs: Any, args: argparse.Namespace) -> tuple[Any, Any, int]:
    last_error: Exception | None = None
    for attempt in range(1, args.start_attempts + 1):
        pipeline = rs.pipeline(rs.context())
        config = rs.config()
        config.enable_device(args.serial)
        config.enable_stream(
            rs.stream.depth, IMAGE_WIDTH, IMAGE_HEIGHT, rs.format.z16, IMAGE_FPS
        )
        config.enable_stream(
            rs.stream.color, IMAGE_WIDTH, IMAGE_HEIGHT, rs.format.rgb8, IMAGE_FPS
        )
        config.enable_stream(rs.stream.accel, rs.format.motion_xyz32f, 200)
        config.enable_stream(rs.stream.gyro, rs.format.motion_xyz32f, 200)
        started = False
        try:
            profile = pipeline.start(config)
            started = True
            last_color_number = None
            for _ in range(args.warmup_frames):
                _, last_color_number, _ = _next_video_frames(
                    pipeline,
                    last_color_number,
                    args.maximum_video_skew_ms,
                )
            if last_color_number is None:
                raise RuntimeError("D455 warmup produced no unique color frames")
            return pipeline, profile, last_color_number
        except RuntimeError as exc:
            last_error = exc
            if started:
                pipeline.stop()
            if attempt < args.start_attempts:
                time.sleep(args.retry_delay_s)
    raise RuntimeError(
        f"D455 did not become ready after {args.start_attempts} attempts: {last_error}"
    )


def _write_binary_ply(path: Path, points_m: np.ndarray, colors_rgb: np.ndarray) -> None:
    if len(points_m) != len(colors_rgb):
        raise ValueError("point and color counts differ")
    vertices = np.empty(
        len(points_m),
        dtype=[
            ("x", "<f4"),
            ("y", "<f4"),
            ("z", "<f4"),
            ("red", "u1"),
            ("green", "u1"),
            ("blue", "u1"),
        ],
    )
    vertices["x"], vertices["y"], vertices["z"] = points_m.T
    vertices["red"], vertices["green"], vertices["blue"] = colors_rgb.T
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        "comment coordinate_frame piper_base\n"
        f"element vertex {len(vertices)}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\n"
        "end_header\n"
    ).encode("ascii")
    with path.open("wb") as stream:
        stream.write(header)
        vertices.tofile(stream)


def _save_images(
    output: Path,
    color_rgb: np.ndarray,
    depth_raw: np.ndarray,
    depth_scale_m: float,
    minimum_depth_m: float,
    maximum_depth_m: float,
) -> None:
    Image.fromarray(color_rgb).save(output / "color.png")
    Image.fromarray(depth_raw).save(output / "aligned_depth_raw.png")
    depth_m = depth_raw.astype(np.float32) * depth_scale_m
    scaled = np.clip(
        (depth_m - minimum_depth_m) / (maximum_depth_m - minimum_depth_m),
        0.0,
        1.0,
    )
    preview = cv2.applyColorMap(
        np.asarray((1.0 - scaled) * 255.0, dtype=np.uint8), cv2.COLORMAP_TURBO
    )
    preview[depth_raw == 0] = 0
    cv2.imwrite(str(output / "depth_preview.png"), preview)


def synthetic_test() -> dict[str, Any]:
    transform = np.eye(4, dtype=np.float64)
    transform[:3, 3] = [0.2, -0.1, 0.4]
    points = np.array([[0.0, 0.0, 0.5], [0.1, -0.2, 1.0]])
    expected = points + transform[:3, 3]
    transformed = _transform_points(transform, points)
    if not np.allclose(transformed, expected, atol=1e-12):
        raise RuntimeError("synthetic point transform failed")

    frame_ns = 1_000_000_000
    earlier = {"flange_measurement_unix_ns": frame_ns - 8_000_000}
    later = {"flange_measurement_unix_ns": frame_ns + 3_000_000}
    label, _, offset_ms = _select_robot_sample(
        frame_ns, [("before", earlier), ("after", later)]
    )
    if label != "after" or abs(offset_ms - 3.0) > 1e-12:
        raise RuntimeError("synthetic timestamp selection failed")
    return {"ok": True, "point_count": len(points), "selected_offset_ms": offset_ms}


def capture_snapshot(args: argparse.Namespace) -> dict[str, Any]:
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
    method = args.method or calibration["recommended_method"]
    flange_from_camera = np.asarray(
        calibration["methods"][method]["camera_to_flange"], dtype=np.float64
    )

    args.output.mkdir(parents=True, exist_ok=True)
    sampler = RobotSampler(
        args.bridge_url, token, rate_hz=args.robot_sample_hz
    )
    sampler.start()
    pipeline = None
    selected = None
    best_offset_ms = float("inf")
    try:
        pipeline, profile, last_color_number = _start_ready_pipeline(rs, args)
        if not sampler.wait_for_records(5, timeout_s=2.0):
            raise RuntimeError("robot sampler did not produce enough timestamped states")
        align = rs.align(rs.stream.color)
        for _ in range(args.sync_attempts):
            frames, last_color_number, video_skew_ms = _next_video_frames(
                pipeline,
                last_color_number,
                args.maximum_video_skew_ms,
            )
            color_frame = frames.get_color_frame()
            frame_domain = color_frame.get_frame_timestamp_domain()
            if frame_domain != rs.timestamp_domain.global_time:
                raise RuntimeError(
                    f"D455 timestamp domain is {frame_domain}; global_time is required"
                )
            frame_unix_ns = round(color_frame.get_timestamp() * 1e6)
            records = sampler.records()
            sampler.wait_for_records(len(records) + 1, timeout_s=0.05)
            records = sampler.records()
            before = max(
                (
                    record
                    for record in records
                    if record["flange_measurement_unix_ns"] <= frame_unix_ns
                ),
                key=lambda record: record["flange_measurement_unix_ns"],
                default=None,
            )
            after = min(
                (
                    record
                    for record in records
                    if record["flange_measurement_unix_ns"] >= frame_unix_ns
                ),
                key=lambda record: record["flange_measurement_unix_ns"],
                default=None,
            )
            if before is None or after is None:
                continue
            label, robot_sample, offset_ms = _select_robot_sample(
                frame_unix_ns,
                [
                    (f"sample_{record['sequence']}", record)
                    for record in records
                ],
            )
            best_offset_ms = min(best_offset_ms, abs(offset_ms))
            if (
                abs(offset_ms) <= args.maximum_sync_offset_ms
                and robot_sample["roundtrip_ms"] <= args.maximum_bridge_rtt_ms
            ):
                selected = {
                    "frames": frames,
                    "before": before,
                    "after": after,
                    "robot_label": label,
                    "robot_sample": robot_sample,
                    "offset_ms": offset_ms,
                    "video_skew_ms": video_skew_ms,
                    "frame_unix_ns": frame_unix_ns,
                    "sampler_records": records,
                }
                break
        if selected is None:
            raise RuntimeError(
                "no frame met the timestamp limits; "
                f"best flange offset was {best_offset_ms:.3f} ms"
            )

        frames = selected["frames"]
        aligned = align.process(frames)
        color_frame = aligned.get_color_frame()
        depth_frame = aligned.get_depth_frame()
        if not color_frame or not depth_frame:
            raise RuntimeError("depth-to-color alignment did not return both frames")
        color_rgb = np.asanyarray(color_frame.get_data()).copy()
        depth_raw = np.asanyarray(depth_frame.get_data()).copy()
        depth_scale_m = profile.get_device().first_depth_sensor().get_depth_scale()

        cloud = rs.pointcloud().calculate(depth_frame)
        camera_points = (
            np.asanyarray(cloud.get_vertices()).view(np.float32).reshape(-1, 3).copy()
        )
        colors_rgb = color_rgb.reshape(-1, 3)
        if len(camera_points) != len(colors_rgb):
            raise RuntimeError("aligned point cloud and color image sizes differ")
        valid = (
            np.all(np.isfinite(camera_points), axis=1)
            & (camera_points[:, 2] >= args.minimum_depth_m)
            & (camera_points[:, 2] <= args.maximum_depth_m)
        )
        camera_points = camera_points[valid]
        colors_rgb = colors_rgb[valid]
        if len(camera_points) < args.minimum_point_count:
            raise RuntimeError(
                f"only {len(camera_points)} valid depth points; "
                f"need {args.minimum_point_count}"
            )

        robot_state = selected["robot_sample"]["state"]
        arm = robot_state["arm"]
        base_from_flange = _pose6_transform(arm["flange_pose_m_rad"])
        base_from_camera = base_from_flange @ flange_from_camera
        base_points = _transform_points(base_from_camera, camera_points).astype(np.float32)

        stream_frames = {frame.profile.stream_type(): frame for frame in frames}
        accel = _motion_sample(stream_frames.get(rs.stream.accel))
        gyro = _motion_sample(stream_frames.get(rs.stream.gyro))
        device = profile.get_device()
        global_time_options = []
        for sensor in device.query_sensors():
            if sensor.supports(rs.option.global_time_enabled):
                global_time_options.append(sensor.get_option(rs.option.global_time_enabled))

        _save_images(
            args.output,
            color_rgb,
            depth_raw,
            depth_scale_m,
            args.minimum_depth_m,
            args.maximum_depth_m,
        )
        _write_binary_ply(args.output / "base_point_cloud.ply", base_points, colors_rgb)
    finally:
        if pipeline is not None:
            pipeline.stop()
        sampler.stop()

    sync_offset_ms = float(selected["offset_ms"])
    query_rtt_ms = float(selected["robot_sample"]["roundtrip_ms"])
    sampler_records = selected["sampler_records"]
    sampler_span_ns = (
        sampler_records[-1]["query_midpoint_unix_ns"]
        - sampler_records[0]["query_midpoint_unix_ns"]
    )
    observed_robot_sample_hz = (
        (len(sampler_records) - 1) * 1e9 / sampler_span_ns
        if len(sampler_records) > 1 and sampler_span_ns > 0
        else None
    )
    acceptance = {
        "observe_bridge": robot_state["bridge"]["mode"] == "observe",
        "piper_x_model": arm["model"] == ARM_MODEL,
        "global_camera_time": bool(global_time_options)
        and all(value == 1.0 for value in global_time_options),
        "video_skew_within_limit": selected["video_skew_ms"]
        <= args.maximum_video_skew_ms,
        "bridge_rtt_within_limit": query_rtt_ms <= args.maximum_bridge_rtt_ms,
        "flange_timestamp_bracketed": selected["before"] is not None
        and selected["after"] is not None,
        "flange_sync_within_limit": abs(sync_offset_ms)
        <= args.maximum_sync_offset_ms,
        "minimum_point_count": len(base_points) >= args.minimum_point_count,
    }
    if not all(acceptance.values()):
        raise RuntimeError(f"snapshot acceptance failed: {acceptance}")

    result = {
        "schema_version": 1,
        "ok": True,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": "d455_aligned_depth_robot_snapshot",
        "camera": {
            "name": _device_info(device, rs.camera_info.name),
            "serial_number": _device_info(device, rs.camera_info.serial_number),
            "firmware_version": _device_info(device, rs.camera_info.firmware_version),
            "usb_type_descriptor": _device_info(
                device, rs.camera_info.usb_type_descriptor
            ),
            "color": _frame_metadata(color_frame, rs),
            "depth": _frame_metadata(depth_frame, rs),
            "accel_m_s2": accel,
            "gyro_rad_s": gyro,
            "aligned_intrinsics": _intrinsics(depth_frame.profile),
            "depth_scale_m_per_unit": depth_scale_m,
            "global_time_options": global_time_options,
        },
        "synchronization": {
            "strategy": "background_flange_buffer_nearest_to_d455_global_timestamp",
            "frame_unix_ns": selected["frame_unix_ns"],
            "selected_robot_sample": selected["robot_label"],
            "flange_feedback_offset_ms": sync_offset_ms,
            "color_depth_skew_ms": selected["video_skew_ms"],
            "bridge_query_roundtrip_ms": query_rtt_ms,
            "limits": {
                "maximum_flange_offset_ms": args.maximum_sync_offset_ms,
                "maximum_color_depth_skew_ms": args.maximum_video_skew_ms,
                "maximum_bridge_roundtrip_ms": args.maximum_bridge_rtt_ms,
            },
            "robot_sampler": {
                "requested_rate_hz": args.robot_sample_hz,
                "observed_rate_hz": observed_robot_sample_hz,
                "buffered_record_count": len(sampler_records),
            },
            "before": _record_summary(selected["before"]),
            "after": _record_summary(selected["after"]),
        },
        "robot": {
            "bridge_version": robot_state["bridge"]["version"],
            "bridge_mode": robot_state["bridge"]["mode"],
            "model": arm["model"],
            "firmware": arm["firmware"],
            "healthy": arm["healthy"],
            "arm_status": arm["arm_status"],
            "ctrl_mode": arm["ctrl_mode"],
            "teach_status": arm["teach_status"],
            "joint_angles_rad": arm["joint_angles_rad"],
            "joint_feedback_hz": arm["joint_feedback_hz"],
            "flange_pose_m_rad": arm["flange_pose_m_rad"],
            "flange_feedback_hz": arm["flange_feedback_hz"],
            "gripper": arm.get("gripper"),
        },
        "calibration": {
            "path": str(args.calibration),
            "sha256": hashlib.sha256(calibration_bytes).hexdigest(),
            "method": method,
        },
        "coordinate_chain": {
            "base_from_flange": _json_matrix(base_from_flange),
            "flange_from_camera": _json_matrix(flange_from_camera),
            "base_from_camera": _json_matrix(base_from_camera),
        },
        "point_cloud": {
            "coordinate_frame": "piper_base",
            "point_count": len(base_points),
            "valid_pixel_fraction": len(base_points) / depth_raw.size,
            "camera_depth_m": {
                "minimum": float(np.min(camera_points[:, 2])),
                "median": float(np.median(camera_points[:, 2])),
                "maximum": float(np.max(camera_points[:, 2])),
            },
            "base_bounds_m": {
                "minimum": np.min(base_points, axis=0).astype(float).tolist(),
                "maximum": np.max(base_points, axis=0).astype(float).tolist(),
            },
        },
        "acceptance": acceptance,
        "files": {
            "color": "color.png",
            "aligned_depth_raw": "aligned_depth_raw.png",
            "depth_preview": "depth_preview.png",
            "base_point_cloud": "base_point_cloud.ply",
        },
    }
    (args.output / "snapshot.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
        newline="\n",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-test", action="store_true")
    parser.add_argument("--serial", default=CAMERA_SERIAL)
    parser.add_argument("--bridge-url", default=BRIDGE_URL)
    parser.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN_FILE)
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--method", choices=sorted(HAND_EYE_METHODS))
    parser.add_argument("--output", type=Path, default=Path("captures/synchronized_latest"))
    parser.add_argument("--warmup-frames", type=int, default=30)
    parser.add_argument("--sync-attempts", type=int, default=10)
    parser.add_argument("--start-attempts", type=int, default=3)
    parser.add_argument("--retry-delay-s", type=float, default=2.0)
    parser.add_argument("--robot-sample-hz", type=float, default=100.0)
    parser.add_argument("--maximum-sync-offset-ms", type=float, default=8.0)
    parser.add_argument("--maximum-video-skew-ms", type=float, default=5.0)
    parser.add_argument("--maximum-bridge-rtt-ms", type=float, default=10.0)
    parser.add_argument("--minimum-depth-m", type=float, default=0.10)
    parser.add_argument("--maximum-depth-m", type=float, default=3.00)
    parser.add_argument("--minimum-point-count", type=int, default=10_000)
    args = parser.parse_args()
    if args.warmup_frames < 1 or args.sync_attempts < 1 or args.start_attempts < 1:
        parser.error("warmup, sync attempts, and start attempts must be positive")
    if args.robot_sample_hz <= 0:
        parser.error("robot-sample-hz must be positive")
    if not 0 < args.minimum_depth_m < args.maximum_depth_m:
        parser.error("depth range is invalid")
    result = synthetic_test() if args.synthetic_test else capture_snapshot(args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
