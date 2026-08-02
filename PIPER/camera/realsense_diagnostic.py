#!/usr/bin/env python3
"""Capture one reproducible RGB-D/IMU diagnostic sample from the PIPER D455."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import pyrealsense2 as rs
from PIL import Image


DEFAULT_SERIAL = "260722303168"
WIDTH = 848
HEIGHT = 480
FPS = 30


def _device_info(device: rs.device, key: rs.camera_info) -> str | None:
    return device.get_info(key) if device.supports(key) else None


def _intrinsics(profile: rs.stream_profile) -> dict[str, Any]:
    intr = profile.as_video_stream_profile().get_intrinsics()
    return {
        "width": intr.width,
        "height": intr.height,
        "fx": intr.fx,
        "fy": intr.fy,
        "ppx": intr.ppx,
        "ppy": intr.ppy,
        "model": str(intr.model),
        "coeffs": list(intr.coeffs),
    }


def _frame_summary(samples: list[tuple[int, float]]) -> dict[str, Any]:
    frame_numbers = [sample[0] for sample in samples]
    timestamps_ms = [sample[1] for sample in samples]
    result: dict[str, Any] = {
        "observed_samples": len(samples),
        "unique_frame_numbers": len(set(frame_numbers)),
        "first_frame_number": frame_numbers[0],
        "last_frame_number": frame_numbers[-1],
        "first_timestamp_ms": timestamps_ms[0],
        "last_timestamp_ms": timestamps_ms[-1],
    }
    elapsed_ms = timestamps_ms[-1] - timestamps_ms[0]
    frame_span = frame_numbers[-1] - frame_numbers[0]
    result["native_rate_estimate_hz"] = (
        frame_span * 1000.0 / elapsed_ms if elapsed_ms > 0 else None
    )
    return result


def _motion_sample(frame: rs.frame) -> dict[str, float | int]:
    data = frame.as_motion_frame().get_motion_data()
    return {
        "frame_number": frame.get_frame_number(),
        "timestamp_ms": frame.get_timestamp(),
        "x": data.x,
        "y": data.y,
        "z": data.z,
        "norm": math.sqrt(data.x * data.x + data.y * data.y + data.z * data.z),
    }


def _save_images(
    output: Path,
    color_rgb: np.ndarray,
    depth_raw: np.ndarray,
    depth_preview_rgb: np.ndarray,
) -> None:
    color_image = Image.fromarray(color_rgb)
    depth_preview = Image.fromarray(depth_preview_rgb)
    Image.fromarray(depth_raw).save(output / "aligned_depth_raw.png")
    color_image.save(output / "color.png")
    depth_preview.save(output / "depth_preview.png")

    combined = Image.new("RGB", (color_image.width * 2, color_image.height))
    combined.paste(color_image, (0, 0))
    combined.paste(depth_preview, (color_image.width, 0))
    combined.save(output / "combined_preview.png")


def capture(
    serial: str,
    output: Path,
    warmup_frames: int,
    capture_frames: int,
    visual_preset: str,
    disparity_shift: int | None,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)

    context = rs.context()
    matching_devices = [
        device
        for device in context.query_devices()
        if _device_info(device, rs.camera_info.serial_number) == serial
    ]
    if len(matching_devices) != 1:
        raise RuntimeError(f"Expected one D455 with serial {serial}, found {len(matching_devices)}")

    camera = matching_devices[0]
    advanced = rs.rs400_advanced_mode(camera)
    original_settings_json = advanced.serialize_json()
    depth_sensor = camera.first_depth_sensor()
    settings_changed = visual_preset != "current" or disparity_shift is not None
    if visual_preset == "high-density":
        depth_sensor.set_option(
            rs.option.visual_preset, float(int(rs.rs400_visual_preset.high_density))
        )
    if disparity_shift is not None:
        depth_table = advanced.get_depth_table()
        depth_table.disparityShift = disparity_shift
        advanced.set_depth_table(depth_table)

    applied_settings = {
        "visual_preset": depth_sensor.get_option(rs.option.visual_preset),
        "emitter_enabled": depth_sensor.get_option(rs.option.emitter_enabled),
        "laser_power": depth_sensor.get_option(rs.option.laser_power),
        "disparity_shift": advanced.get_depth_table().disparityShift,
    }

    pipeline = rs.pipeline(context)
    config = rs.config()
    config.enable_device(serial)
    config.enable_stream(rs.stream.depth, WIDTH, HEIGHT, rs.format.z16, FPS)
    config.enable_stream(rs.stream.color, WIDTH, HEIGHT, rs.format.rgb8, FPS)
    config.enable_stream(rs.stream.accel, rs.format.motion_xyz32f, 200)
    config.enable_stream(rs.stream.gyro, rs.format.motion_xyz32f, 200)

    align = rs.align(rs.stream.color)
    colorizer = rs.colorizer()
    started = False
    profile = None
    last_color = None
    last_depth = None
    last_depth_preview = None
    color_samples: list[tuple[int, float]] = []
    depth_samples: list[tuple[int, float]] = []
    accel_samples: list[tuple[int, float]] = []
    gyro_samples: list[tuple[int, float]] = []
    color_depth_skew_ms: list[float] = []
    latest_accel = None
    latest_gyro = None

    try:
        profile = pipeline.start(config)
        started = True

        for index in range(warmup_frames + capture_frames):
            frames = pipeline.wait_for_frames(5000)
            depth = frames.get_depth_frame()
            color = frames.get_color_frame()
            if not depth or not color:
                raise RuntimeError("A frameset did not contain both depth and color frames")

            frame_by_stream = {frame.profile.stream_type(): frame for frame in frames}
            accel = frame_by_stream.get(rs.stream.accel)
            gyro = frame_by_stream.get(rs.stream.gyro)
            if not accel or not gyro:
                raise RuntimeError("A frameset did not contain both IMU streams")

            if index < warmup_frames:
                continue

            color_samples.append((color.get_frame_number(), color.get_timestamp()))
            depth_samples.append((depth.get_frame_number(), depth.get_timestamp()))
            accel_samples.append((accel.get_frame_number(), accel.get_timestamp()))
            gyro_samples.append((gyro.get_frame_number(), gyro.get_timestamp()))
            color_depth_skew_ms.append(abs(color.get_timestamp() - depth.get_timestamp()))
            latest_accel = _motion_sample(accel)
            latest_gyro = _motion_sample(gyro)

            aligned = align.process(frames)
            aligned_depth = aligned.get_depth_frame()
            aligned_color = aligned.get_color_frame()
            if not aligned_depth or not aligned_color:
                raise RuntimeError("Depth-to-color alignment did not return both video frames")

            last_color = np.asanyarray(aligned_color.get_data()).copy()
            last_depth = np.asanyarray(aligned_depth.get_data()).copy()
            colorized = colorizer.colorize(aligned_depth)
            last_depth_preview = np.asanyarray(colorized.get_data()).copy()
            if colorized.profile.format() == rs.format.bgr8:
                last_depth_preview = last_depth_preview[..., ::-1]
    finally:
        if started:
            pipeline.stop()
        if settings_changed:
            advanced.load_json(original_settings_json)

    if profile is None or last_color is None or last_depth is None or last_depth_preview is None:
        raise RuntimeError("No complete RGB-D sample was captured")

    device = profile.get_device()
    depth_scale_m = device.first_depth_sensor().get_depth_scale()
    depth_m = last_depth.astype(np.float64) * depth_scale_m
    nonzero_depth = depth_m[depth_m > 0]
    plausible_depth = depth_m[(depth_m > 0) & (depth_m <= 10.0)]
    if plausible_depth.size == 0:
        raise RuntimeError("The captured depth image contains no valid pixels")

    center = depth_m[
        HEIGHT * 2 // 5 : HEIGHT * 3 // 5,
        WIDTH * 2 // 5 : WIDTH * 3 // 5,
    ]
    valid_center = center[(center > 0) & (center <= 10.0)]
    color_profile = profile.get_stream(rs.stream.color)
    depth_profile = profile.get_stream(rs.stream.depth)
    extr = depth_profile.get_extrinsics_to(color_profile)

    _save_images(output, last_color, last_depth, last_depth_preview)

    metadata = {
        "captured_at_unix_s": time.time(),
        "device": {
            "name": _device_info(device, rs.camera_info.name),
            "serial_number": _device_info(device, rs.camera_info.serial_number),
            "firmware_version": _device_info(device, rs.camera_info.firmware_version),
            "usb_type_descriptor": _device_info(device, rs.camera_info.usb_type_descriptor),
            "product_line": _device_info(device, rs.camera_info.product_line),
        },
        "configuration": {
            "width": WIDTH,
            "height": HEIGHT,
            "fps": FPS,
            "warmup_frames": warmup_frames,
            "capture_frames": capture_frames,
            "depth_aligned_to_color": True,
            "depth_scale_m_per_unit": depth_scale_m,
            "temporary_settings": applied_settings,
        },
        "calibration": {
            "color_intrinsics": _intrinsics(color_profile),
            "depth_intrinsics": _intrinsics(depth_profile),
            "depth_to_color_extrinsics": {
                "rotation": list(extr.rotation),
                "translation_m": list(extr.translation),
            },
        },
        "stream_health": {
            "color": _frame_summary(color_samples),
            "depth": _frame_summary(depth_samples),
            "accel": _frame_summary(accel_samples),
            "gyro": _frame_summary(gyro_samples),
            "color_depth_skew_ms": {
                "mean": float(np.mean(color_depth_skew_ms)),
                "max": float(np.max(color_depth_skew_ms)),
            },
            "latest_accel_m_s2": latest_accel,
            "latest_gyro_rad_s": latest_gyro,
        },
        "depth_quality": {
            "nonzero_fraction": float(nonzero_depth.size / depth_m.size),
            "plausible_under_10m_fraction": float(plausible_depth.size / depth_m.size),
            "saturated_65535_fraction": float(np.mean(last_depth == 65535)),
            "minimum_m": float(np.min(plausible_depth)),
            "p05_m": float(np.percentile(plausible_depth, 5)),
            "median_m": float(np.median(plausible_depth)),
            "p95_m": float(np.percentile(plausible_depth, 95)),
            "maximum_m": float(np.max(plausible_depth)),
            "center_roi_median_m": (
                float(np.median(valid_center)) if valid_center.size else None
            ),
        },
        "files": {
            "color": "color.png",
            "aligned_depth_raw": "aligned_depth_raw.png",
            "depth_preview": "depth_preview.png",
            "combined_preview": "combined_preview.png",
        },
    }
    (output / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", default=DEFAULT_SERIAL)
    parser.add_argument("--output", type=Path, default=Path("captures/latest"))
    parser.add_argument("--warmup-frames", type=int, default=30)
    parser.add_argument("--capture-frames", type=int, default=120)
    parser.add_argument(
        "--visual-preset", choices=("current", "high-density"), default="current"
    )
    parser.add_argument("--disparity-shift", type=int)
    args = parser.parse_args()
    if args.warmup_frames < 1 or args.capture_frames < 2:
        parser.error("warmup-frames must be >= 1 and capture-frames must be >= 2")
    if args.disparity_shift is not None and not 0 <= args.disparity_shift <= 512:
        parser.error("disparity-shift must be between 0 and 512")

    metadata = capture(
        serial=args.serial,
        output=args.output,
        warmup_frames=args.warmup_frames,
        capture_frames=args.capture_frames,
        visual_preset=args.visual_preset,
        disparity_shift=args.disparity_shift,
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
