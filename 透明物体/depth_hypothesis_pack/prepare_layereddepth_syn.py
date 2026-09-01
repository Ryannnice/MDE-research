#!/usr/bin/env python3
"""Cache a deterministic LayeredDepth-Syn prefix for auditable pilot training."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image


DATASET = "princeton-vl/LayeredDepth-Syn"
REVISION = "78fd900929879332e60d7190d9bd423b8432669b"
DEPTH_FIELDS = ["depth_1.png", "depth_3.png", "depth_5.png", "depth_7.png"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--resize-height", type=int, default=288)
    parser.add_argument("--shuffle-buffer", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resized_size(width: int, height: int, target_height: int) -> tuple[int, int]:
    target_width = max(1, int(round(width * target_height / height)))
    return target_width, target_height


def image_array(value: Image.Image, size: tuple[int, int]) -> np.ndarray:
    return np.asarray(value.convert("RGB").resize(size, Image.Resampling.BICUBIC)).copy()


def depth_array(value: Image.Image, size: tuple[int, int]) -> np.ndarray:
    depth = np.asarray(value.resize(size, Image.Resampling.NEAREST)).copy()
    if depth.ndim == 3:
        depth = depth[..., 0]
    if not np.issubdtype(depth.dtype, np.integer):
        raise TypeError(f"Expected integer depth PNG, got {depth.dtype}")
    return depth.astype(np.uint16, copy=False)


def main() -> int:
    args = parse_args()
    if args.count < 1 or args.resize_height < 32 or args.shuffle_buffer < 0:
        raise ValueError("count must be positive, resize-height >= 32, shuffle-buffer >= 0")
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory must be empty: {output_dir}")

    from datasets import load_dataset

    rows = load_dataset(DATASET, split="train", revision=REVISION, streaming=True)
    if args.shuffle_buffer:
        rows = rows.shuffle(seed=args.seed, buffer_size=args.shuffle_buffer)

    samples = []
    valid_counts = np.zeros(len(DEPTH_FIELDS), dtype=np.int64)
    total_pixels = 0
    order_violations = 0
    for index, row in enumerate(rows):
        if index >= args.count:
            break
        source_image = row["image.png"]
        width, height = source_image.size
        size = resized_size(width, height, args.resize_height)
        image = image_array(source_image, size)
        depth_mm = np.stack([depth_array(row[field], size) for field in DEPTH_FIELDS])
        valid = depth_mm > 0
        valid_counts += valid.reshape(len(DEPTH_FIELDS), -1).sum(axis=1)
        total_pixels += depth_mm.shape[1] * depth_mm.shape[2]
        for layer in range(1, len(DEPTH_FIELDS)):
            pair_valid = valid[layer - 1] & valid[layer]
            order_violations += int(
                np.count_nonzero(pair_valid & (depth_mm[layer] <= depth_mm[layer - 1]))
            )

        destination = output_dir / f"{index:05d}.npz"
        with destination.open("wb") as handle:
            np.savez_compressed(
                handle,
                image=image,
                depth_mm=depth_mm,
                key=np.asarray(str(row.get("__key__", index))),
            )
        samples.append(
            {
                "index": index,
                "key": str(row.get("__key__", index)),
                "file": destination.name,
                "bytes": destination.stat().st_size,
                "sha256": sha256_file(destination),
                "source_size_wh": [width, height],
                "cached_size_wh": list(size),
            }
        )
        print(f"cached {index + 1}/{args.count}: {samples[-1]['key']}", flush=True)

    if len(samples) != args.count:
        raise RuntimeError(f"Requested {args.count} samples, received {len(samples)}")
    manifest = {
        "schema_version": 1,
        "dataset": DATASET,
        "split": "train",
        "revision": REVISION,
        "source_examples": 14800,
        "source_shards": 56,
        "selection": "stream prefix" if not args.shuffle_buffer else "stream shuffle buffer",
        "shuffle_buffer": args.shuffle_buffer,
        "seed": args.seed,
        "resize_height": args.resize_height,
        "image_field": "image.png",
        "depth_fields": DEPTH_FIELDS,
        "depth_encoding": "uint16 millimetres; zero invalid",
        "samples_count": len(samples),
        "valid_fraction_by_layer": (valid_counts / total_pixels).tolist(),
        "adjacent_order_violations_before_canonicalization": order_violations,
        "samples": samples,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in manifest.items() if key != "samples"}, indent=2))
    sys.stdout.flush()
    sys.stderr.flush()
    # datasets 5.0.0 may leave an aiohttp worker alive and abort during CPython
    # finalization after a streaming read. All files are closed and flushed here.
    os._exit(0)


if __name__ == "__main__":
    main()
