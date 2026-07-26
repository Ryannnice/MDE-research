#!/usr/bin/env python3
"""Evaluate one ShellBench ray-event file or two matching directories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ray_events import RayEvents, add_statistics, empty_statistics, event_statistics, iter_npz_pairs, summarize_statistics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--prediction", type=Path, required=True)
    parser.add_argument("--delta-m", type=float, required=True)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stats = empty_statistics()
    samples = []
    for gt_path, pred_path in iter_npz_pairs(args.ground_truth, args.prediction):
        sample = event_statistics(RayEvents.load(pred_path), RayEvents.load(gt_path), args.delta_m)
        add_statistics(stats, sample)
        samples.append(gt_path.name)
    result = {
        "schema_version": 1,
        "ground_truth": str(args.ground_truth),
        "prediction": str(args.prediction),
        "delta_m": args.delta_m,
        "samples": len(samples),
        "metrics": summarize_statistics(stats),
        "counts": stats,
    }
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(args.output)


if __name__ == "__main__":
    main()
