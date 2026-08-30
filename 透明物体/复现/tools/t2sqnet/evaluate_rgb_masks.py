#!/usr/bin/env python3
"""Evaluate the cached T²SQNet/LangSAM union masks on TablewareNet RGB views."""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--prediction-root", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def metrics(counts: dict[str, int]) -> dict[str, float | int | None]:
    tp, fp, fn, tn = (counts[key] for key in ("tp", "fp", "fn", "tn"))
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    iou = tp / (tp + fp + fn) if tp + fp + fn else None
    f1 = None if precision is None or recall is None or precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {
        **counts,
        "pixel_precision": precision,
        "pixel_recall": recall,
        "pixel_iou": iou,
        "pixel_f1": f1,
        "pixel_accuracy": (tp + tn) / (tp + fp + fn + tn),
    }


def add_counts(target: dict[str, int], prediction: np.ndarray, ground_truth: np.ndarray) -> dict[str, int]:
    if prediction.shape != ground_truth.shape:
        raise ValueError(f"Mask shapes differ: {prediction.shape} vs {ground_truth.shape}")
    current = {
        "tp": int(np.count_nonzero(prediction & ground_truth)),
        "fp": int(np.count_nonzero(prediction & ~ground_truth)),
        "fn": int(np.count_nonzero(~prediction & ground_truth)),
        "tn": int(np.count_nonzero(~prediction & ~ground_truth)),
    }
    for key, value in current.items():
        target[key] += value
    return current


def main() -> None:
    args = parse_args()
    data_root = args.data_root.resolve()
    prediction_root = args.prediction_root.resolve()
    manifest = load_json(prediction_root / "manifest.json")
    run_metadata = load_json(prediction_root / "metrics.json")
    if not isinstance(manifest, list):
        raise ValueError("prediction manifest must be a list")
    by_scene: dict[str, dict[str, str]] = {}
    for item in manifest:
        scene_id = str(item["scene_id"])
        record = {
            "source_file": str(item["source_file"]),
            "masks_file": str(item["masks_file"]),
        }
        if scene_id in by_scene and by_scene[scene_id] != record:
            raise ValueError(f"Conflicting mask metadata for {scene_id}")
        by_scene[scene_id] = record
    expected_scenes = int(run_metadata.get("scenes", len(by_scene)))
    if len(by_scene) != expected_scenes:
        raise ValueError(f"Run declares {expected_scenes} scenes but manifest contains {len(by_scene)}")

    total = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    scenes: list[dict[str, Any]] = []
    for scene_id, record in sorted(by_scene.items()):
        source_path = data_root / record["source_file"]
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        with source_path.open("rb") as handle:
            data = pickle.load(handle)
        with np.load(prediction_root / record["masks_file"]) as payload:
            prediction = np.asarray(payload["mask_imgs"], dtype=bool)
            indices = np.asarray(payload["view_indices"], dtype=np.int64).tolist()
        ground_truth = np.asarray(data["mask_imgs"], dtype=bool)[indices]
        scene_counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
        views: list[dict[str, Any]] = []
        for local_view, source_view in enumerate(indices):
            current = add_counts(scene_counts, prediction[local_view], ground_truth[local_view])
            views.append({"source_view_index": source_view, **metrics(current)})
        for key, value in scene_counts.items():
            total[key] += value
        scenes.append({"scene_id": scene_id, **metrics(scene_counts), "views": views})

    scene_ious = [float(item["pixel_iou"]) for item in scenes if item["pixel_iou"] is not None]
    payload = {
        "method": run_metadata.get("method", "T2SQNet_released_models_with_official_LangSAM"),
        "input_protocol": run_metadata.get("input_protocol", "RGB; upstream LangSAM rgb2mask unchanged"),
        "ground_truth_scope": "TablewareNet synthetic union foreground mask for all tableware objects",
        "scenes_evaluated": len(scenes),
        "views_evaluated": sum(len(item["views"]) for item in scenes),
        "micro": metrics(total),
        "macro_scene_iou": float(np.mean(scene_ious)) if scene_ious else None,
        "run_metadata": run_metadata,
        "scenes": scenes,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "scenes"}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
