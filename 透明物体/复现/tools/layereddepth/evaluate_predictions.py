#!/usr/bin/env python3
"""Evaluate saved depth hypotheses on LayeredDepth validation tuples.

The upstream evaluator hard-codes its prediction path and interprets NPY files
as inverse depth. This wrapper keeps those choices explicit and represents a
missing layer by an absent file (or an invalid value), which is required for a
fair single-depth versus multi-layer diagnostic.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np
from datasets import load_dataset


ODD_LAYER_LABELS = (1, 3, 5, 7)
MIN_DEPTH_M = 0.02


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prediction-dir", type=Path, required=True)
    parser.add_argument(
        "--prediction-format",
        choices=("layer-files", "seegroup-npz"),
        default="layer-files",
        help=(
            "'layer-files' reads <id>_<layer>.npy/png; 'seegroup-npz' reads "
            "<id>.npz teacher caches containing layers_m and valid_mask."
        ),
    )
    parser.add_argument(
        "--subset",
        choices=("layer_first", "layer_all", "both"),
        required=True,
    )
    parser.add_argument(
        "--npy-space",
        choices=("depth", "inverse_depth"),
        default="depth",
        help="Semantic space stored in NPY files. PNG files are depth in millimetres.",
    )
    parser.add_argument(
        "--layer-naming",
        choices=("odd", "ordinal"),
        default="odd",
        help="'odd' uses _1/_3/_5/_7; 'ordinal' uses _0/_1/_2/_3.",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Optional streaming smoke-test limit.",
    )
    parser.add_argument(
        "--dataset",
        default="princeton-vl/LayeredDepth",
    )
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument(
        "--local-validation-dir",
        type=Path,
        default=None,
        help="Optional directory containing validation-*.parquet for offline evaluation.",
    )
    parser.add_argument("--output-json", type=Path, default=None)
    return parser.parse_args()


def normalized_index(value: Any) -> str:
    text = str(value)
    return str(int(text)) if text.isdigit() else text


def layer_suffix(layer_position: int, naming: str) -> int:
    if naming == "odd":
        return ODD_LAYER_LABELS[layer_position]
    return layer_position


def prediction_path(
    prediction_dir: Path,
    index: str,
    layer_position: int,
    naming: str,
) -> Path | None:
    stem = f"{index}_{layer_suffix(layer_position, naming)}"
    for extension in (".npy", ".png"):
        candidate = prediction_dir / f"{stem}{extension}"
        if candidate.is_file():
            return candidate
    return None


def read_prediction(path: Path, npy_space: str) -> np.ndarray:
    if path.suffix == ".npy":
        prediction = np.load(path).astype(np.float32, copy=False)
        if npy_space == "inverse_depth":
            valid = np.isfinite(prediction) & (prediction > 0)
            depth = np.zeros_like(prediction, dtype=np.float32)
            np.divide(1.0, prediction, out=depth, where=valid)
            prediction = depth
    else:
        prediction = cv2.imread(path.as_posix(), cv2.IMREAD_UNCHANGED)
        if prediction is None:
            raise ValueError(f"Could not read prediction: {path}")
        if prediction.ndim == 3:
            prediction = prediction[..., 0]
        prediction = prediction.astype(np.float32) / 1000.0

    if prediction.ndim != 2:
        raise ValueError(f"Expected HxW prediction at {path}, got {prediction.shape}")
    prediction[~np.isfinite(prediction)] = 0
    prediction[prediction <= 0] = 0
    return prediction


def load_layers(
    prediction_dir: Path,
    index: str,
    image_hw: tuple[int, int],
    npy_space: str,
    naming: str,
    prediction_format: str = "layer-files",
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    height, width = image_hw
    if prediction_format == "seegroup-npz":
        path = prediction_dir / f"{index}.npz"
        if not path.is_file():
            return (
                np.zeros((len(ODD_LAYER_LABELS), height, width), dtype=np.float32),
                np.zeros((len(ODD_LAYER_LABELS), height, width), dtype=bool),
                [],
            )

        with np.load(path) as payload:
            layers_array = payload["layers_m"].astype(np.float32, copy=False)
            if "valid_mask" in payload:
                mask_array = payload["valid_mask"].astype(bool, copy=False)
            else:
                mask_array = np.isfinite(layers_array) & (layers_array > 0)

        if layers_array.ndim != 3:
            raise ValueError(
                f"Expected LxHxW layers_m at {path}, got {layers_array.shape}"
            )
        if mask_array.shape != layers_array.shape:
            raise ValueError(
                f"valid_mask shape {mask_array.shape} does not match "
                f"layers_m {layers_array.shape} at {path}"
            )

        layers: list[np.ndarray] = []
        masks: list[np.ndarray] = []
        for layer_position in range(len(ODD_LAYER_LABELS)):
            if layer_position >= layers_array.shape[0]:
                prediction = np.zeros((height, width), dtype=np.float32)
                valid = np.zeros((height, width), dtype=bool)
            else:
                prediction = layers_array[layer_position]
                valid = mask_array[layer_position]
                if prediction.shape != (height, width):
                    prediction = cv2.resize(
                        prediction,
                        (width, height),
                        interpolation=cv2.INTER_CUBIC,
                    )
                    valid = cv2.resize(
                        valid.astype(np.uint8),
                        (width, height),
                        interpolation=cv2.INTER_NEAREST,
                    ).astype(bool)
                valid &= np.isfinite(prediction) & (prediction > 0)
                prediction = np.where(valid, prediction, 0).astype(
                    np.float32,
                    copy=False,
                )
            layers.append(prediction)
            masks.append(valid)

        return np.stack(layers), np.stack(masks), [path.as_posix()]

    layers: list[np.ndarray] = []
    masks: list[np.ndarray] = []
    files: list[str] = []

    for layer_position in range(len(ODD_LAYER_LABELS)):
        path = prediction_path(prediction_dir, index, layer_position, naming)
        if path is None:
            prediction = np.zeros((height, width), dtype=np.float32)
            files.append("")
        else:
            prediction = read_prediction(path, npy_space)
            if prediction.shape != (height, width):
                prediction = cv2.resize(
                    prediction,
                    (width, height),
                    interpolation=cv2.INTER_CUBIC,
                )
                prediction[prediction <= 0] = 0
            files.append(path.as_posix())
        layers.append(prediction)
        masks.append(prediction > 0)

    return np.stack(layers), np.stack(masks), files


def unique_sorted_depths(
    layers: np.ndarray,
    valid_mask: np.ndarray,
    x: int,
    y: int,
    epsilon_m: float = 0.02,
) -> list[float]:
    depths = layers[:, y, x][valid_mask[:, y, x]]
    depths = sorted(float(value) for value in depths if value > MIN_DEPTH_M)
    unique: list[float] = []
    for depth in depths:
        if not unique or abs(depth - unique[-1]) > epsilon_m:
            unique.append(depth)
    return unique


def predicted_depth(
    layers: np.ndarray,
    valid_mask: np.ndarray,
    point: Iterable[int],
) -> float | None:
    x, y, odd_layer = (int(value) for value in point)
    if odd_layer not in ODD_LAYER_LABELS:
        return None
    height, width = layers.shape[1:]
    if not (0 <= x < width and 0 <= y < height):
        return None
    layer_position = (odd_layer - 1) // 2
    depths = unique_sorted_depths(layers, valid_mask, x, y)
    return depths[layer_position] if layer_position < len(depths) else None


def tuple_points(single_tuple: dict[str, Any]) -> list[list[int]]:
    return [
        single_tuple[key]
        for key in ("p1", "p2", "p3", "p4")
        if key in single_tuple
    ]


def tuple_layer_name(single_tuple: dict[str, Any]) -> str:
    labels = {int(point[2]) for point in tuple_points(single_tuple)}
    return str(next(iter(labels))) if len(labels) == 1 else "mixed"


def tuple_in_official_protocol(
    single_tuple: dict[str, Any],
    image_hw: tuple[int, int],
) -> bool:
    height, width = image_hw
    points = tuple_points(single_tuple)
    if not points:
        return False
    for point in points:
        if len(point) != 3:
            return False
        x, y, odd_layer = (int(value) for value in point)
        if odd_layer not in ODD_LAYER_LABELS:
            return False
        if not (0 <= x < width and 0 <= y < height):
            return False
    return True


def tuple_correct(
    single_tuple: dict[str, Any],
    layers: np.ndarray,
    valid_mask: np.ndarray,
) -> bool:
    depths = [
        predicted_depth(layers, valid_mask, point)
        for point in tuple_points(single_tuple)
    ]
    if not bool(single_tuple["is_real"]):
        return all(depth is None for depth in depths)
    if any(depth is None for depth in depths):
        return False
    return all(left < right for left, right in zip(depths, depths[1:]))


def image_hw(row: dict[str, Any]) -> tuple[int, int]:
    image = row["image.png"]
    width, height = image.size
    return height, width


def summarize(
    counters: dict[str, list[int]],
) -> tuple[dict[str, float], dict[str, dict[str, int]]]:
    metrics: dict[str, float] = {}
    counts: dict[str, dict[str, int]] = {}
    for key in sorted(counters):
        correct, total = counters[key]
        metrics[key] = correct / total
        counts[key] = {"correct": correct, "total": total}
    return metrics, counts


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    if args.local_validation_dir is not None:
        parquet_files = sorted(
            args.local_validation_dir.expanduser().resolve().glob(
                "validation-*.parquet"
            )
        )
        if not parquet_files:
            raise FileNotFoundError(
                f"No validation parquet files in {args.local_validation_dir}"
            )
        rows = load_dataset(
            "parquet",
            data_files={
                "validation": [path.as_posix() for path in parquet_files]
            },
            split="validation",
            streaming=True,
        )
        dataset_source = args.local_validation_dir.as_posix()
    else:
        rows = load_dataset(
            args.dataset,
            split="validation",
            streaming=True,
            cache_dir=args.cache_dir.as_posix() if args.cache_dir else None,
        )
        dataset_source = args.dataset
    counters: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    processed = 0
    found_files = 0
    subsets = (
        ("layer_first", "layer_all")
        if args.subset == "both"
        else (args.subset,)
    )

    for row in rows:
        if args.max_samples is not None and processed >= args.max_samples:
            break
        index = normalized_index(row["__key__"])
        row_image_hw = image_hw(row)
        layers, valid_mask, files = load_layers(
            args.prediction_dir,
            index,
            row_image_hw,
            args.npy_space,
            args.layer_naming,
            args.prediction_format,
        )
        if not any(files):
            raise FileNotFoundError(
                f"No prediction found for validation sample {index} in "
                f"{args.prediction_dir}"
            )
        found_files += sum(bool(path) for path in files)
        for subset in subsets:
            tuple_group = row["tuples.json"][subset]
            for tuple_type in ("pairs", "trips", "quads"):
                for single_tuple in tuple_group[tuple_type]:
                    if not tuple_in_official_protocol(
                        single_tuple,
                        row_image_hw,
                    ):
                        continue
                    correct = int(
                        tuple_correct(single_tuple, layers, valid_mask)
                    )
                    layer = tuple_layer_name(single_tuple)
                    for suffix in (layer, "all"):
                        key = f"{subset}/{tuple_type}/{suffix}"
                        counters[key][0] += correct
                        counters[key][1] += 1
        processed += 1

    if processed == 0:
        raise ValueError("LayeredDepth validation stream yielded no samples.")
    if found_files == 0:
        raise FileNotFoundError(
            f"No prediction files found in {args.prediction_dir} "
            f"with {args.layer_naming!r} layer naming."
        )

    metrics, counts = summarize(counters)
    return {
        "protocol": {
            "dataset": args.dataset,
            "dataset_source": dataset_source,
            "split": "validation",
            "subset": args.subset,
            "evaluated_subsets": list(subsets),
            "prediction_format": args.prediction_format,
            "npy_space": args.npy_space,
            "layer_naming": args.layer_naming,
            "missing_layer_semantics": "absent",
            "minimum_depth_m": MIN_DEPTH_M,
            "unique_depth_epsilon_m": MIN_DEPTH_M,
        },
        "samples": processed,
        "prediction_files_found": found_files,
        "metrics": metrics,
        "counts": counts,
    }


def main() -> None:
    args = parse_args()
    result = evaluate(args)
    payload = json.dumps(result, indent=2, sort_keys=True)
    print(payload)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(f"{payload}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
