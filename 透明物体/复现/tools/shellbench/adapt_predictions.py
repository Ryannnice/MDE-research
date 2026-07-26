#!/usr/bin/env python3
"""Export single-depth or SeeGroup predictions into the ShellBench event schema."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from ray_events import RayEvents, single_depth_events


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--format", choices=("depth-npy", "seegroup-npz"), required=True)
    parser.add_argument("--depth-scale", type=float, default=1.0, help="Divide NPY values by this to obtain metres.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.format == "depth-npy":
        depth = np.load(args.input).astype(np.float32) / args.depth_scale
        events = single_depth_events(depth)
    else:
        with np.load(args.input) as payload:
            events = RayEvents(
                payload["layers_m"],
                payload["valid_mask"],
                uncertainty_m=payload["beta"] if "beta" in payload and payload["beta"].shape else None,
            ).normalized()
    events.save(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
