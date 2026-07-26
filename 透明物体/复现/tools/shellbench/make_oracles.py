#!/usr/bin/env python3
"""Derive representational GT oracles from canonical ShellBench ray events."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ray_events import RayEvents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--representation",
        choices=("front", "fixed", "ordered_no_type", "full"),
        required=True,
    )
    parser.add_argument("--layers", type=int, default=None, help="Required for --representation fixed.")
    parser.add_argument("--metadata", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ground_truth = RayEvents.load(args.ground_truth)
    if args.representation == "front":
        oracle = ground_truth.first_layers(1, keep_transitions=False)
    elif args.representation == "fixed":
        if args.layers is None:
            raise ValueError("--layers is required for fixed representation")
        oracle = ground_truth.first_layers(args.layers, keep_transitions=False)
    elif args.representation == "ordered_no_type":
        oracle = ground_truth.without_transitions()
    else:
        oracle = ground_truth.normalized()
    oracle.save(args.output)
    metadata = {
        "source_ground_truth": str(args.ground_truth),
        "representation": args.representation,
        "layers": args.layers,
        "note": "GT-projected representation oracle; it is not a learned baseline.",
    }
    metadata_path = args.metadata or args.output.with_suffix(".json")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
