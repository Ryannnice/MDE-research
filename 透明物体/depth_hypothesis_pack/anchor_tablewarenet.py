#!/usr/bin/env python3
"""Anchor DHP metric scale to mask-zeroed TablewareNet background depth."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prediction-root", type=Path, required=True)
    parser.add_argument("--anchor-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--trim-quantile", type=float, default=0.01)
    parser.add_argument("--min-points", type=int, default=1000)
    parser.add_argument("--huber-iterations", type=int, default=5)
    parser.add_argument("--huber-min-scale-m", type=float, default=0.005)
    parser.add_argument("--huber-delta-multiplier", type=float, default=1.345)
    parser.add_argument("--min-slope", type=float, default=0.05)
    parser.add_argument("--max-slope", type=float, default=5.0)
    parser.add_argument("--max-abs-offset-m", type=float, default=5.0)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def fit_robust_affine(
    prediction: np.ndarray,
    anchor: np.ndarray,
    *,
    trim_quantile: float = 0.01,
    huber_iterations: int = 5,
    huber_min_scale_m: float = 0.005,
    huber_delta_multiplier: float = 1.345,
    min_slope: float = 0.05,
    max_slope: float = 5.0,
    max_abs_offset_m: float = 5.0,
) -> tuple[float, float, int]:
    """Fit anchor ~= slope * prediction + offset with deterministic IRLS."""

    prediction = np.asarray(prediction, dtype=np.float64).reshape(-1)
    anchor = np.asarray(anchor, dtype=np.float64).reshape(-1)
    if prediction.shape != anchor.shape:
        raise ValueError("Prediction and anchor vectors must have one shape")
    if not 0 <= trim_quantile < 0.5:
        raise ValueError("trim_quantile must be in [0, 0.5)")
    if huber_iterations < 0 or huber_min_scale_m <= 0:
        raise ValueError("Invalid Huber parameters")
    if not 0 < min_slope <= max_slope or max_abs_offset_m <= 0:
        raise ValueError("Invalid affine bounds")

    if trim_quantile:
        prediction_bounds = np.quantile(
            prediction, [trim_quantile, 1.0 - trim_quantile]
        )
        anchor_bounds = np.quantile(anchor, [trim_quantile, 1.0 - trim_quantile])
        keep = (
            (prediction >= prediction_bounds[0])
            & (prediction <= prediction_bounds[1])
            & (anchor >= anchor_bounds[0])
            & (anchor <= anchor_bounds[1])
        )
        prediction = prediction[keep]
        anchor = anchor[keep]
    design = np.stack([prediction, np.ones_like(prediction)], axis=1)
    coefficients = np.linalg.lstsq(design, anchor, rcond=None)[0]
    for _ in range(huber_iterations):
        residual = anchor - design @ coefficients
        median = np.median(residual)
        robust_scale = max(
            huber_min_scale_m,
            1.4826 * float(np.median(np.abs(residual - median))),
        )
        delta = huber_delta_multiplier * robust_scale
        weights = np.minimum(1.0, delta / np.maximum(np.abs(residual), 1e-12))
        sqrt_weights = np.sqrt(weights)
        coefficients = np.linalg.lstsq(
            design * sqrt_weights[:, None],
            anchor * sqrt_weights,
            rcond=None,
        )[0]
    slope = float(np.clip(coefficients[0], min_slope, max_slope))
    offset = float(
        np.clip(coefficients[1], -max_abs_offset_m, max_abs_offset_m)
    )
    return slope, offset, int(prediction.size)


def atomic_save(path: Path, payload: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(handle, **payload)
    temporary.replace(path)


def quantiles(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        name: float(value)
        for name, value in zip(
            ("min", "p10", "median", "p90", "max"),
            np.quantile(array, [0.0, 0.1, 0.5, 0.9, 1.0]),
        )
    }


def main() -> int:
    args = parse_args()
    prediction_root = args.prediction_root.expanduser().resolve()
    anchor_root = args.anchor_root.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    source_manifest = load_json(prediction_root / "manifest.json")
    source_metrics = load_json(prediction_root / "metrics.json")
    anchor_manifest = load_json(anchor_root / "manifest.json")
    anchor_metrics = load_json(anchor_root / "metrics.json")
    if source_manifest.get("summary", {}).get("prediction_space") != "metric_axial_z_m":
        raise ValueError("DHP source must contain metric axial-z predictions")
    if anchor_manifest.get("summary", {}).get("prediction_space") != "metric_axial_z_m":
        raise ValueError("Anchor source must contain metric axial-z predictions")
    if str(anchor_metrics.get("method")) != "masked_raw":
        raise ValueError("This controlled anchor requires the mask-zeroed raw-depth cache")

    anchors = {
        (str(item["scene_id"]), int(item["view_index"])): anchor_root
        / str(item["prediction_file"])
        for item in anchor_manifest["items"]
    }
    records: list[dict[str, Any]] = []
    slopes: list[float] = []
    offsets: list[float] = []
    points: list[float] = []
    raw_median_errors: list[float] = []
    anchored_median_errors: list[float] = []
    for item in source_manifest["items"]:
        key = (str(item["scene_id"]), int(item["view_index"]))
        anchor_path = anchors.get(key)
        if anchor_path is None or not anchor_path.is_file():
            raise FileNotFoundError(f"Missing background-depth anchor for {key}")
        source_path = prediction_root / str(item["prediction_file"])
        destination = output_dir / "predictions" / f"{key[0]}_view{key[1]}.npz"
        if args.resume and destination.is_file():
            with np.load(destination) as cached:
                slope = float(cached["anchor_slope"].item())
                offset = float(cached["anchor_offset_m"].item())
                point_count = int(cached["anchor_points"].item())
                raw_median = float(cached["anchor_raw_median_abs_error_m"].item())
                anchored_median = float(
                    cached["anchor_fitted_median_abs_error_m"].item()
                )
        else:
            with np.load(source_path) as source:
                depth = source["depth_m"].astype(np.float32)
                presence = source["presence_probability"].astype(np.float32)
                uncertainty = source["uncertainty_m"].astype(np.float32)
            anchor = np.load(anchor_path).astype(np.float32)
            valid = (
                np.isfinite(anchor)
                & (anchor > 0)
                & np.isfinite(depth[0])
                & (depth[0] > 0)
            )
            if int(valid.sum()) < args.min_points:
                raise ValueError(f"Only {int(valid.sum())} anchor points for {key}")
            slope, offset, point_count = fit_robust_affine(
                depth[0][valid],
                anchor[valid],
                trim_quantile=args.trim_quantile,
                huber_iterations=args.huber_iterations,
                huber_min_scale_m=args.huber_min_scale_m,
                huber_delta_multiplier=args.huber_delta_multiplier,
                min_slope=args.min_slope,
                max_slope=args.max_slope,
                max_abs_offset_m=args.max_abs_offset_m,
            )
            raw_median = float(np.median(np.abs(depth[0][valid] - anchor[valid])))
            anchored_median = float(
                np.median(np.abs(slope * depth[0][valid] + offset - anchor[valid]))
            )
            anchored_depth = slope * depth + offset
            if not np.all(np.isfinite(anchored_depth)) or np.any(anchored_depth <= 0):
                raise ValueError(f"Affine anchor produced invalid metric depths for {key}")
            atomic_save(
                destination,
                {
                    "depth_m": anchored_depth.astype(np.float32),
                    "presence_probability": presence,
                    "uncertainty_m": (slope * uncertainty).astype(np.float32),
                    "anchor_slope": np.asarray(slope, dtype=np.float64),
                    "anchor_offset_m": np.asarray(offset, dtype=np.float64),
                    "anchor_points": np.asarray(point_count, dtype=np.int64),
                    "anchor_raw_median_abs_error_m": np.asarray(
                        raw_median, dtype=np.float64
                    ),
                    "anchor_fitted_median_abs_error_m": np.asarray(
                        anchored_median, dtype=np.float64
                    ),
                },
            )
        slopes.append(slope)
        offsets.append(offset)
        points.append(float(point_count))
        raw_median_errors.append(raw_median)
        anchored_median_errors.append(anchored_median)
        output_item = dict(item)
        output_item["prediction_file"] = str(destination.relative_to(output_dir))
        output_item["anchor_slope"] = slope
        output_item["anchor_offset_m"] = offset
        output_item["anchor_points_after_trim"] = point_count
        records.append(output_item)

    method = f"{source_metrics['method']}_BackgroundDepthAffineAnchor_v1"
    summary = {
        **source_metrics,
        "run_kind": "full_tablewarenet_background_depth_affine_anchor",
        "method": method,
        "source_method": source_metrics["method"],
        "source_prediction_root": str(prediction_root),
        "anchor_root": str(anchor_root),
        "anchor_method": anchor_metrics["method"],
        "input_protocol": (
            f"{source_metrics['input_protocol']}; per-frame robust affine fitted only "
            "on mask-zeroed TablewareNet rendered background depth; GT union object "
            "mask is an explicit oracle; no object or shell depth enters the fit"
        ),
        "training_or_threshold_leakage": False,
        "evaluation_input_uses_rendered_background_depth": True,
        "object_depth_used_for_fit": False,
        "anchor_uses_gt_union_object_mask": True,
        "anchor_fit": {
            "trim_quantile_each_tail": args.trim_quantile,
            "huber_iterations": args.huber_iterations,
            "huber_min_scale_m": args.huber_min_scale_m,
            "huber_delta_multiplier": args.huber_delta_multiplier,
            "slope_bounds": [args.min_slope, args.max_slope],
            "offset_bounds_m": [-args.max_abs_offset_m, args.max_abs_offset_m],
            "slope": quantiles(slopes),
            "offset_m": quantiles(offsets),
            "points_after_trim": quantiles(points),
            "raw_background_median_abs_error_m": quantiles(raw_median_errors),
            "anchored_background_median_abs_error_m": quantiles(
                anchored_median_errors
            ),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps({"summary": summary, "items": records}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "metrics.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
