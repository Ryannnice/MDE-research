#!/usr/bin/env python3
"""Calibrate DHP layer-presence thresholds on the synthetic held-out split."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader

from dhp.data import LayeredDepthCacheDataset
from dhp.inference import load_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--checkpoint", default="best.pt")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--bins", type=int, default=2000)
    return parser.parse_args()


def move_batch(batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
    return {
        key: value.to(device, non_blocking=True) if torch.is_tensor(value) else value
        for key, value in batch.items()
    }


def best_threshold(
    positive_histogram: np.ndarray,
    negative_histogram: np.ndarray,
) -> dict[str, float]:
    bins = len(positive_histogram)
    true_positive = np.cumsum(positive_histogram[::-1])[::-1]
    false_positive = np.cumsum(negative_histogram[::-1])[::-1]
    false_negative = positive_histogram.sum() - true_positive
    precision = true_positive / np.maximum(1.0, true_positive + false_positive)
    recall = true_positive / np.maximum(1.0, true_positive + false_negative)
    f1 = 2.0 * precision * recall / np.maximum(1e-12, precision + recall)
    # Prefer the higher threshold on exact ties so deployment does not add
    # unsupported events merely because of histogram quantization.
    best = int(np.flatnonzero(f1 == f1.max())[-1])
    threshold = max(1e-6, min(1.0 - 1e-6, best / bins))
    return {
        "threshold": threshold,
        "precision": float(precision[best]),
        "recall": float(recall[best]),
        "f1": float(f1[best]),
        "positive_pixels": int(positive_histogram.sum()),
        "negative_pixels": int(negative_histogram.sum()),
    }


def main() -> int:
    args = parse_args()
    if args.batch_size < 1 or args.bins < 100:
        raise ValueError("batch-size must be positive and bins must be at least 100")
    run_dir = args.run_dir.expanduser().resolve()
    run_manifest = json.loads(
        (run_dir / "run_manifest.json").read_text(encoding="utf-8")
    )
    if run_manifest.get("run_kind") != "pilot":
        raise ValueError("Presence calibration requires an isolated pilot validation split")
    if run_manifest.get("evaluation_leakage") is not False:
        raise ValueError("Run manifest does not certify evaluation_leakage=false")
    cache_dir = Path(run_manifest["cache_dir"])
    crop_size = int(run_manifest["args"]["crop_size"])
    validation = LayeredDepthCacheDataset(
        cache_dir,
        [int(index) for index in run_manifest["val_indices"]],
        crop_size=crop_size,
        augment=False,
    )
    loader = DataLoader(
        validation,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=args.device.startswith("cuda"),
    )
    device = torch.device(args.device)
    checkpoint = run_dir / args.checkpoint
    model = load_model(checkpoint, device)
    positive = np.zeros((4, args.bins), dtype=np.int64)
    negative = np.zeros((4, args.bins), dtype=np.int64)
    with torch.inference_mode():
        for batch in loader:
            batch = move_batch(batch, device)
            score = model(batch["image"])["presence_probability"]
            target = batch["valid_mask"].bool()
            bin_index = torch.clamp((score * args.bins).long(), 0, args.bins - 1)
            for layer in range(4):
                layer_bins = bin_index[:, layer]
                layer_target = target[:, layer]
                positive[layer] += torch.bincount(
                    layer_bins[layer_target], minlength=args.bins
                ).cpu().numpy()
                negative[layer] += torch.bincount(
                    layer_bins[~layer_target], minlength=args.bins
                ).cpu().numpy()

    layers = [best_threshold(positive[layer], negative[layer]) for layer in range(4)]
    payload = {
        "schema_version": 1,
        "calibration_source": "LayeredDepth-Syn held-out split only",
        "real_evaluation_data_used": False,
        "run_dir": str(run_dir),
        "checkpoint": str(checkpoint),
        "cache_dir": str(cache_dir),
        "validation_indices": run_manifest["val_indices"],
        "crop_size": crop_size,
        "histogram_bins": args.bins,
        "selection": "maximum per-layer pixel F1; highest threshold breaks ties",
        "thresholds": [layer["threshold"] for layer in layers],
        "layers": layers,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
