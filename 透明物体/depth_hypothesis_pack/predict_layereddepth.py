#!/usr/bin/env python3
"""Export DepthHypothesisPack predictions for LayeredDepth validation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from datasets import load_dataset

from dhp.calibration import load_presence_thresholds
from dhp.inference import load_model, predict_image


ODD_LAYERS = (1, 3, 5, 7)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--local-validation-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--input-height", type=int, default=256)
    parser.add_argument("--presence-threshold", type=float, default=0.5)
    parser.add_argument("--presence-calibration", type=Path)
    parser.add_argument("--max-samples", type=int)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_npy(path: Path, value: np.ndarray) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, np.asarray(value, dtype=np.float32))
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    if not 0 < args.presence_threshold < 1:
        raise ValueError("presence-threshold must be in (0,1)")
    thresholds = (
        load_presence_thresholds(args.presence_calibration)
        if args.presence_calibration is not None
        else [args.presence_threshold] * 4
    )
    checkpoint = args.checkpoint.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    validation_dir = args.local_validation_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    parquet_files = sorted(validation_dir.glob("validation-*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No validation parquet files in {validation_dir}")

    device = torch.device(args.device)
    model = load_model(checkpoint, device)
    rows = load_dataset(
        "parquet",
        data_files={"validation": [path.as_posix() for path in parquet_files]},
        split="validation",
        streaming=True,
    )
    items = []
    for order, row in enumerate(rows):
        if args.max_samples is not None and order >= args.max_samples:
            break
        index = str(int(row["__key__"])) if str(row["__key__"]).isdigit() else str(row["__key__"])
        destinations = [output_dir / f"{index}_{layer}.npy" for layer in ODD_LAYERS]
        if args.resume and all(path.is_file() for path in destinations):
            items.append({"index": index, "reused": True})
            continue
        prediction = predict_image(model, row["image.png"], device, args.input_height)
        valid = prediction["presence_probability"] >= np.asarray(thresholds)[:, None, None]
        valid = np.logical_and.accumulate(valid, axis=0)
        for layer_index, destination in enumerate(destinations):
            depth = np.where(valid[layer_index], prediction["depth"][layer_index], 0)
            save_npy(destination, depth)
        items.append(
            {
                "index": index,
                "reused": False,
                "source_size_wh": list(row["image.png"].size),
                "valid_fraction": valid.reshape(4, -1).mean(axis=1).tolist(),
            }
        )
        print(f"predicted {order + 1}: {index}", flush=True)

    manifest = {
        "run_kind": "full_layereddepth_validation" if args.max_samples is None else "debug_subset",
        "model": getattr(model, "model_name", type(model).__name__),
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256_file(checkpoint),
        "dataset": "princeton-vl/LayeredDepth validation",
        "local_validation_dir": str(validation_dir),
        "input_height": args.input_height,
        "presence_thresholds": thresholds,
        "presence_calibration": (
            str(args.presence_calibration.expanduser().resolve())
            if args.presence_calibration is not None
            else None
        ),
        "prediction_space": "metric_depth_m",
        "layer_naming": "odd",
        "samples": len(items),
        "items": items,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in manifest.items() if key != "items"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
