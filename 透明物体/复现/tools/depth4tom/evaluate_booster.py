#!/usr/bin/env python3
"""Evaluate Booster predictions with explicit raw or affine-aligned semantics.

``alignment=least_squares`` matches Depth4ToM's per-image fitting in disparity
space. ``alignment=none`` evaluates metric depth directly. Both paths retain
the official per-image averaging and All/ToM/Other category masks.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np


CATEGORIES = ("All", "ToM", "Other")
METRICS = (
    "delta1.25",
    "delta1.20",
    "delta1.15",
    "delta1.10",
    "delta1.05",
    "mae",
    "absrel",
    "rmse",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-root", type=Path, required=True)
    parser.add_argument("--gt-root", type=Path, required=True)
    parser.add_argument("--prediction-root", type=Path, required=True)
    parser.add_argument("--dataset-txt", type=Path, required=True)
    parser.add_argument(
        "--prediction-space",
        choices=("depth", "inverse_depth"),
        required=True,
        help="NPY value semantics; depth is metres.",
    )
    parser.add_argument(
        "--alignment",
        choices=("none", "least_squares"),
        required=True,
    )
    parser.add_argument("--resize-factor", type=float, default=0.25)
    parser.add_argument("--min-depth-mm", type=float, default=1.0)
    parser.add_argument("--max-depth-mm", type=float, default=10000.0)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--output-json", type=Path, default=None)
    return parser.parse_args()


def booster_metrics(
    prediction_mm: np.ndarray,
    target_mm: np.ndarray,
    valid: np.ndarray,
) -> dict[str, float]:
    selected_prediction = prediction_mm[valid]
    selected_target = target_mm[valid]
    error = np.abs(selected_prediction - selected_target)
    threshold = np.maximum(
        selected_prediction / selected_target,
        selected_target / selected_prediction,
    )
    return {
        "delta1.25": float((threshold < 1.25).mean() * 100.0),
        "delta1.20": float((threshold < 1.20).mean() * 100.0),
        "delta1.15": float((threshold < 1.15).mean() * 100.0),
        "delta1.10": float((threshold < 1.10).mean() * 100.0),
        "delta1.05": float((threshold < 1.05).mean() * 100.0),
        "mae": float(error.mean()),
        "absrel": float((error / selected_target).mean()),
        "rmse": float(np.sqrt(np.square(error).mean())),
    }


def align_inverse_depth(
    prediction: np.ndarray,
    prediction_space: str,
    target_disparity: np.ndarray,
    valid: np.ndarray,
    compute_scale_and_shift,
) -> np.ndarray:
    if prediction_space == "depth":
        inverse = np.zeros_like(prediction, dtype=np.float32)
        positive = np.isfinite(prediction) & (prediction > 0)
        np.divide(1.0, prediction, out=inverse, where=positive)
    else:
        inverse = prediction.astype(np.float32, copy=True)
        inverse[~np.isfinite(inverse)] = 0

    values = inverse[valid]
    value_range = float(values.max() - values.min())
    if value_range <= np.finfo(np.float32).eps:
        raise ValueError("Prediction has no usable inverse-depth range.")
    inverse = (inverse - float(values.min())) / value_range
    scale, shift = compute_scale_and_shift(
        inverse[None],
        target_disparity[None],
        valid.astype(np.float32)[None],
    )
    return inverse * scale + shift


def prediction_depth_mm(
    prediction: np.ndarray,
    prediction_space: str,
    alignment: str,
    target_disparity: np.ndarray,
    valid: np.ndarray,
    focal_px: float,
    baseline_mm: float,
    min_depth_mm: float,
    max_depth_mm: float,
    compute_scale_and_shift,
) -> np.ndarray:
    if alignment == "none":
        if prediction_space != "depth":
            raise ValueError("Raw evaluation requires --prediction-space depth.")
        depth_mm = prediction.astype(np.float32, copy=True) * 1000.0
    else:
        disparity = align_inverse_depth(
            prediction,
            prediction_space,
            target_disparity,
            valid,
            compute_scale_and_shift,
        )
        with np.errstate(divide="ignore", invalid="ignore"):
            depth_mm = baseline_mm * focal_px / disparity

    depth_mm[~np.isfinite(depth_mm)] = max_depth_mm
    return np.clip(depth_mm, min_depth_mm, max_depth_mm)


def evaluate(args: argparse.Namespace) -> dict:
    official_root = args.official_root.expanduser().resolve()
    sys.path.insert(0, official_root.as_posix())
    from utils import (  # pylint: disable=import-error,import-outside-toplevel
        compute_scale_and_shift,
        parse_dataset_txt,
        read_calib_xml,
        read_d,
    )

    gt_root = args.gt_root.expanduser().resolve()
    prediction_root = args.prediction_root.expanduser().resolve()
    dataset_txt = args.dataset_txt.expanduser().resolve()
    dataset = parse_dataset_txt(dataset_txt.as_posix())
    sample_count = len(dataset["basenames"])
    if args.max_samples is not None:
        sample_count = min(sample_count, args.max_samples)

    accumulators: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    category_pixels: dict[str, int] = defaultdict(int)

    for index in range(sample_count):
        basename = dataset["basenames"][index]
        gt_path = gt_root / dataset["gt_paths"][index]
        prediction_path = prediction_root / Path(basename).with_suffix(".npy")
        calibration_path = gt_root / dataset["calib_paths"][index]
        if not prediction_path.is_file():
            raise FileNotFoundError(f"Missing prediction: {prediction_path}")

        target_disparity = read_d(gt_path.as_posix(), scale_factor=256.0)
        focal_px, baseline_m = read_calib_xml(calibration_path.as_posix())
        baseline_mm = baseline_m * 1000.0
        target_disparity = cv2.resize(
            target_disparity,
            None,
            fx=args.resize_factor,
            fy=args.resize_factor,
            interpolation=cv2.INTER_NEAREST,
        ).astype(np.float32)
        focal_px *= args.resize_factor
        target_disparity *= args.resize_factor
        target_disparity[
            target_disparity > focal_px * baseline_mm / args.min_depth_mm
        ] = 0
        target_disparity[
            target_disparity < focal_px * baseline_mm / args.max_depth_mm
        ] = 0
        valid_gt = target_disparity > 0

        prediction = np.load(prediction_path).astype(np.float32, copy=False)
        prediction = cv2.resize(
            prediction,
            (target_disparity.shape[1], target_disparity.shape[0]),
            # Upstream passes cv2.INTER_CUBIC as resize's third positional
            # argument. In the Python binding that slot is ``dst``, so the
            # operation actually uses the default bilinear interpolation.
            interpolation=cv2.INTER_LINEAR,
        )
        depth_mm = prediction_depth_mm(
            prediction,
            args.prediction_space,
            args.alignment,
            target_disparity,
            valid_gt,
            focal_px,
            baseline_mm,
            args.min_depth_mm,
            args.max_depth_mm,
            compute_scale_and_shift,
        )
        with np.errstate(divide="ignore", invalid="ignore"):
            target_depth_mm = baseline_mm * focal_px / target_disparity
        target_depth_mm[~np.isfinite(target_depth_mm)] = 0

        mask_path = gt_path.with_name("mask_cat.png")
        segmentation = None
        if mask_path.is_file():
            segmentation = cv2.imread(
                mask_path.as_posix(),
                cv2.IMREAD_UNCHANGED,
            )
            if segmentation is None:
                raise ValueError(f"Could not decode category mask: {mask_path}")
            if segmentation.ndim == 3:
                segmentation = segmentation[..., 0]
            segmentation = cv2.resize(
                segmentation,
                (target_disparity.shape[1], target_disparity.shape[0]),
                interpolation=cv2.INTER_NEAREST,
            )

        for category in CATEGORIES:
            valid = valid_gt.copy()
            if category != "All":
                if segmentation is None:
                    continue
                if category == "Other":
                    category_mask = (segmentation == 0) | (segmentation == 1)
                else:
                    category_mask = (segmentation == 2) | (segmentation == 3)
                valid &= category_mask
            pixels = int(valid.sum())
            if pixels == 0:
                continue
            category_pixels[category] += pixels
            for metric, value in booster_metrics(
                depth_mm,
                target_depth_mm,
                valid,
            ).items():
                accumulators[category][metric].append(value)

    metrics = {
        category: {
            metric: float(np.mean(values))
            for metric, values in accumulators[category].items()
        }
        for category in CATEGORIES
        if category in accumulators
    }
    counts = {
        category: {
            "images": len(accumulators[category].get("rmse", [])),
            "valid_pixels": category_pixels[category],
        }
        for category in metrics
    }
    return {
        "protocol": {
            "dataset": "Booster train/balanced",
            "dataset_txt": dataset_txt.as_posix(),
            "prediction_space": args.prediction_space,
            "alignment": args.alignment,
            "alignment_domain": (
                "inverse_depth" if args.alignment == "least_squares" else None
            ),
            "per_image_averaging": True,
            "resize_factor": args.resize_factor,
            "depth_range_mm": [args.min_depth_mm, args.max_depth_mm],
        },
        "samples": sample_count,
        "metrics": metrics,
        "counts": counts,
    }


def main() -> None:
    args = parse_args()
    result = evaluate(args)
    payload = json.dumps(result, indent=2, sort_keys=True)
    print(payload)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(f"{payload}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
