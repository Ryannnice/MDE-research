#!/usr/bin/env python3
"""Verify an auditable local LayeredDepth-Syn cache."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_cache(cache_dir: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = cache_dir / "manifest.json"
    if not manifest_path.is_file():
        return [f"missing manifest: {manifest_path}"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    samples = manifest.get("samples", [])
    if len(samples) != manifest.get("samples_count"):
        errors.append("samples_count does not match sample entries")
    expected_shape = None
    for entry in samples:
        path = cache_dir / entry["file"]
        if not path.is_file():
            errors.append(f"missing sample: {entry['file']}")
            continue
        if sha256_file(path) != entry["sha256"]:
            errors.append(f"sha256 mismatch: {entry['file']}")
            continue
        with np.load(path) as payload:
            image = payload["image"]
            depth = payload["depth_mm"]
            key = str(payload["key"].item())
        if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
            errors.append(f"invalid RGB array: {entry['file']} {image.shape} {image.dtype}")
        if depth.dtype != np.uint16 or depth.shape != (4, image.shape[0], image.shape[1]):
            errors.append(f"invalid depth array: {entry['file']} {depth.shape} {depth.dtype}")
        if key != str(entry["key"]):
            errors.append(f"key mismatch: {entry['file']}")
        shape = (image.shape[0], image.shape[1])
        if expected_shape is None:
            expected_shape = shape
        elif shape != expected_shape:
            errors.append(f"inconsistent cached shape: {entry['file']} {shape} vs {expected_shape}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache_dir", type=Path)
    args = parser.parse_args()
    cache_dir = args.cache_dir.expanduser().resolve()
    errors = verify_cache(cache_dir)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    manifest = json.loads((cache_dir / "manifest.json").read_text(encoding="utf-8"))
    print(
        "PASS: LayeredDepth-Syn cache verified "
        f"({manifest['samples_count']} samples, revision {manifest['revision']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
