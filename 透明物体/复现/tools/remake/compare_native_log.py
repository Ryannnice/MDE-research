#!/usr/bin/env python3
"""Compare ReMake's rounded native log against the cache-runner metrics JSON."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-metrics", type=Path, required=True)
    parser.add_argument("--native-log", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--samples", type=int, required=True)
    parser.add_argument("--absolute-tolerance", type=float, default=0.005)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.samples < 1 or args.absolute_tolerance <= 0:
        raise ValueError("samples and absolute-tolerance must be positive")
    cache_payload = json.loads(args.cache_metrics.read_text(encoding="utf-8"))
    cache = cache_payload["native_metrics"]
    log = args.native_log.read_text(encoding="utf-8")
    marker = f"Metrics on {args.samples} samples:"
    position = log.rfind(marker)
    if position < 0:
        raise ValueError(f"Native log has no completed {args.samples}-sample metrics block")
    native = {
        key.strip(): float(value)
        for key, value in re.findall(
            r"\[INFO\]\s+([^:\n]+): ([0-9.eE+-]+) \(tools.py:102\)",
            log[position:],
        )
    }
    if not native:
        raise ValueError("No native metric lines could be parsed")
    missing = sorted(set(native) - set(cache))
    if missing:
        raise KeyError(f"Cache metrics are missing native keys: {missing}")
    differences = {key: abs(float(cache[key]) - value) for key, value in native.items()}
    maximum = max(differences.values())
    payload = {
        "samples": args.samples,
        "native_log": str(args.native_log.resolve()),
        "cache_metrics_file": str(args.cache_metrics.resolve()),
        "native_metrics_rounded_6dp": native,
        "cache_metrics": {key: cache[key] for key in native},
        "absolute_differences": differences,
        "max_absolute_difference": maximum,
        "absolute_tolerance": args.absolute_tolerance,
        "pass": maximum <= args.absolute_tolerance,
        "tolerance_note": (
            "Native logger rounds to six decimals; metrics retain their native units, "
            "and Threshold values are percentage points."
        ),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
