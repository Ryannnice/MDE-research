"""Frozen per-layer presence-threshold helpers."""

from __future__ import annotations

import json
from pathlib import Path


def load_presence_thresholds(path: Path, expected_layers: int = 4) -> list[float]:
    payload = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    thresholds = [float(value) for value in payload["thresholds"]]
    if len(thresholds) != expected_layers:
        raise ValueError(
            f"Expected {expected_layers} calibrated thresholds, got {len(thresholds)}"
        )
    if any(not 0 < value < 1 for value in thresholds):
        raise ValueError("Calibrated presence thresholds must lie in (0,1)")
    return thresholds
