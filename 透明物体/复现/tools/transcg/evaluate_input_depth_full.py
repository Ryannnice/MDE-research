#!/usr/bin/env python3
"""Evaluate the identity input-depth baseline under DFNet or ReMake preprocessing.

The two released methods use different resolutions and preprocessing.  They
are therefore emitted as two explicitly labelled protocol rows, not merged
into a single supposedly resolution-independent "raw depth" number.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np


METRICS = [
    "MSE", "RMSE", "REL", "MAE",
    "Threshold@1.01", "Threshold@1.03", "Threshold@1.05", "Threshold@1.10", "Threshold@1.25",
    "MaskedMSE", "MaskedRMSE", "MaskedREL", "MaskedMAE",
    "MaskedThreshold@1.01", "MaskedThreshold@1.02", "MaskedThreshold@1.03",
    "MaskedThreshold@1.05", "MaskedThreshold@1.10", "MaskedThreshold@1.25",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", choices=("dfnet", "remake"), required=True)
    parser.add_argument("--official-root", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    # ReMake samples include 640x480 RGB, relative-depth input, normals and
    # several masks.  Conservative defaults stay below a 4 GiB /dev/shm.
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--max-samples", type=int, help="debug-only prefix")
    return parser.parse_args()


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def main() -> None:
    args = parse_args()
    if args.batch_size < 1 or args.num_workers < 0:
        raise ValueError("batch-size must be positive and num-workers non-negative")
    official_root = args.official_root.resolve()
    dataset_root = args.dataset_root.resolve()
    if not (dataset_root / "metadata.json").is_file():
        raise FileNotFoundError(dataset_root / "metadata.json")
    if not (official_root / "datasets" / "transcg.py").is_file():
        raise FileNotFoundError(f"Not a compatible official checkout: {official_root}")
    if "bool" not in np.__dict__:
        np.bool = np.bool_  # type: ignore[attr-defined]

    tools_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(tools_dir))
    from audit_transcg import audit

    if args.max_samples is None:
        report = audit(dataset_root, "test")
        if not report["ready_for_full_split"]:
            raise RuntimeError("TransCG test split failed the exact-denominator audit")

    sys.path.insert(0, str(official_root))
    sys.path.insert(0, str(official_root / "datasets"))
    from torch.utils.data import DataLoader, Subset
    from transcg import TransCG
    from utils.metrics import MetricsRecorder

    if args.protocol == "dfnet":
        dataset = TransCG(
            data_dir=str(dataset_root), split="test", image_size=(320, 240),
            use_augmentation=False, depth_min=0.0, depth_max=10.0,
            depth_norm=10.0, with_original=False,
        )
        depth_scale = 10.0
        preprocessing = (
            "official DFNet TransCG input at 320x240; process_data filtering, "
            "inpainting, and per-image affine input normalization are retained"
        )
    else:
        dataset = TransCG(
            data_dir=str(dataset_root), split="test", image_size=(640, 480),
            use_augmentation=False, depth_min=0.0, depth_max=10.0,
            depth_norm=1.0, reldepth_model="depthanything",
        )
        depth_scale = 1.0
        preprocessing = "official ReMake TransCG input depth at 640x480; no learned completion"

    sample_count = len(dataset) if args.max_samples is None else min(args.max_samples, len(dataset))
    if sample_count < 1:
        raise ValueError("max-samples must leave at least one sample")
    data = dataset if sample_count == len(dataset) else Subset(dataset, range(sample_count))
    loader = DataLoader(
        data, batch_size=args.batch_size, shuffle=False, drop_last=False,
        num_workers=args.num_workers, pin_memory=False,
        **({"prefetch_factor": 1} if args.num_workers else {}),
    )
    recorder = MetricsRecorder(
        logger_name=f"input_depth_{args.protocol}", metrics_list=METRICS,
        epsilon=1e-8, depth_scale=depth_scale,
    )
    recorder.clear()
    seen = 0
    for batch in loader:
        if args.protocol == "dfnet":
            scale = (batch["depth_max"] - batch["depth_min"]).reshape(-1, 1, 1)
            offset = batch["depth_min"].reshape(-1, 1, 1)
            batch["pred"] = batch["depth"] * scale + offset
        else:
            batch["pred"] = batch["depth"]
        recorder.evaluate_batch(batch, record=True)
        seen += int(batch["pred"].shape[0])

    payload = {
        "run_kind": "official_full_test" if seen == len(dataset) else "debug_subset",
        "baseline": "identity_preprocessed_input_depth",
        "protocol": args.protocol,
        "official_root": str(official_root),
        "dataset_root": str(dataset_root),
        "samples": seen,
        "preprocessing": preprocessing,
        "native_metrics": jsonable(recorder.get_results()),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
