#!/usr/bin/env python3
"""Evaluate released T²SQNet GT-mask predictions against TablewareNet shells.

This reader compares *per-object* ray-event files.  It first matches released
T²SQNet objects to known TablewareNet objects by semantic class and predicted
centre distance, then charges unmatched GT objects as empty predictions.  The
result is intentionally labelled GT-mask diagnostic: it evaluates T²SQNet's
released recognition/shape models, not its RGB-to-mask stage.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


THIS_DIR = Path(__file__).resolve().parent
SHELLBENCH_DIR = THIS_DIR.parent / "shellbench"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth-root", type=Path, required=True, help="output root of export_tablewarenet_shell_gt.py")
    parser.add_argument("--prediction-root", type=Path, required=True, help="output root of run_t2sqnet_gt_masks.py")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--delta-m", type=float, default=0.005)
    parser.add_argument("--max-centre-distance-m", type=float, default=0.10)
    parser.add_argument("--allow-missing-scenes", action="store_true", help="debug only; full runs require every GT scene")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def translation(record: dict[str, Any]) -> np.ndarray:
    pose = np.asarray(record["pose_world"], dtype=np.float64)
    if pose.shape != (4, 4):
        raise ValueError(f"pose_world must be [4,4], got {pose.shape}")
    return pose[:3, 3]


def match_objects(
    ground_truth: list[dict[str, Any]],
    predicted: list[dict[str, Any]],
    max_centre_distance_m: float,
) -> tuple[list[tuple[int, int, float]], list[int], list[int]]:
    """Class-constrained Hungarian match, followed by a fixed acceptance gate."""

    if max_centre_distance_m <= 0:
        raise ValueError("max-centre-distance-m must be positive")
    if not ground_truth or not predicted:
        return [], list(range(len(ground_truth))), list(range(len(predicted)))
    from scipy.optimize import linear_sum_assignment

    # A class mismatch is deliberately impossible to accept even when the
    # centres happen to overlap.  The large finite cost keeps Hungarian usable
    # without hiding a semantic error as a numerical exception.
    forbidden = max_centre_distance_m + 1_000.0
    costs = np.full((len(ground_truth), len(predicted)), forbidden, dtype=np.float64)
    for gt_index, gt in enumerate(ground_truth):
        gt_class = str(gt["class"])
        gt_centre = translation(gt)
        for prediction_index, prediction in enumerate(predicted):
            if str(prediction["class"]) != gt_class:
                continue
            costs[gt_index, prediction_index] = np.linalg.norm(gt_centre - translation(prediction))
    row_indices, column_indices = linear_sum_assignment(costs)
    matches: list[tuple[int, int, float]] = []
    matched_gt: set[int] = set()
    matched_prediction: set[int] = set()
    for gt_index, prediction_index in zip(row_indices.tolist(), column_indices.tolist()):
        distance = float(costs[gt_index, prediction_index])
        if distance <= max_centre_distance_m:
            matches.append((gt_index, prediction_index, distance))
            matched_gt.add(gt_index)
            matched_prediction.add(prediction_index)
    return (
        matches,
        [index for index in range(len(ground_truth)) if index not in matched_gt],
        [index for index in range(len(predicted)) if index not in matched_prediction],
    )


def unique_gt_objects(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for item in items:
        object_index = item.get("object_index")
        metadata = item.get("ground_truth_object")
        if object_index is None or metadata is None:
            continue
        result[int(object_index)] = {"object_index": int(object_index), **metadata}
    return [result[key] for key in sorted(result)]


def event_items_by_object_and_view(items: list[dict[str, Any]]) -> dict[tuple[int, int], dict[str, Any]]:
    result: dict[tuple[int, int], dict[str, Any]] = {}
    for item in items:
        if item.get("object_index") is None:
            continue
        result[(int(item["object_index"]), int(item["view_index"]))] = item
    return result


def prediction_event_path(prediction_root: Path, scene_id: str, prediction_index: int, view_index: int) -> Path:
    return prediction_root / "events" / f"{scene_id}_prediction{prediction_index}_view{view_index}.npz"


def main() -> None:
    args = parse_args()
    if args.delta_m <= 0:
        raise ValueError("delta-m must be positive")
    gt_root = args.ground_truth_root.resolve()
    prediction_root = args.prediction_root.resolve()
    gt_payload = load_json(gt_root / "manifest.json")
    if not isinstance(gt_payload, dict) or not isinstance(gt_payload.get("items"), list):
        raise ValueError("ground-truth manifest must be the batch exporter payload")
    prediction_manifest = load_json(prediction_root / "manifest.json")
    if not isinstance(prediction_manifest, list):
        raise ValueError("prediction manifest must be the T²SQNet runner list")
    sys.path.insert(0, str(SHELLBENCH_DIR))
    from ray_events import RayEvents, add_statistics, empty_statistics, event_statistics, summarize_statistics

    gt_by_scene: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in gt_payload["items"]:
        if item.get("object_index") is not None:
            gt_by_scene[str(item["scene_id"])].append(item)
    object_files_by_scene: dict[str, Path] = {}
    for item in prediction_manifest:
        object_file = item.get("objects_file")
        if object_file:
            object_files_by_scene[str(item["scene_id"])] = prediction_root / str(object_file)
    missing_scenes = sorted(set(gt_by_scene) - set(object_files_by_scene))
    if missing_scenes and not args.allow_missing_scenes:
        raise FileNotFoundError(
            f"T²SQNet predictions are missing {len(missing_scenes)} GT scenes; "
            "use --allow-missing-scenes only for an explicitly labelled debug run."
        )

    total_statistics = empty_statistics()
    match_distances: list[float] = []
    totals = {"gt_objects": 0, "predicted_objects": 0, "matched_objects": 0, "unmatched_gt_objects": 0, "unmatched_predicted_objects": 0}
    scene_records: list[dict[str, Any]] = []
    for scene_id, gt_items in sorted(gt_by_scene.items()):
        gt_objects = unique_gt_objects(gt_items)
        by_object_view = event_items_by_object_and_view(gt_items)
        object_file = object_files_by_scene.get(scene_id)
        if object_file is None:
            predicted_objects: list[dict[str, Any]] = []
        else:
            object_payload = load_json(object_file)
            predicted_objects = list(object_payload.get("predicted_objects", []))
        matches, unmatched_gt, unmatched_prediction = match_objects(
            gt_objects, predicted_objects, args.max_centre_distance_m
        )
        totals["gt_objects"] += len(gt_objects)
        totals["predicted_objects"] += len(predicted_objects)
        totals["matched_objects"] += len(matches)
        totals["unmatched_gt_objects"] += len(unmatched_gt)
        totals["unmatched_predicted_objects"] += len(unmatched_prediction)
        mapping = {gt_index: prediction_index for gt_index, prediction_index, distance in matches}
        match_distances.extend(distance for _, _, distance in matches)
        compared_frames = 0
        for gt_index, gt_object in enumerate(gt_objects):
            for (object_index, view_index), gt_item in by_object_view.items():
                if object_index != gt_object["object_index"]:
                    continue
                gt_events = RayEvents.load(gt_root / gt_item["event_file"])
                prediction_index = mapping.get(gt_index)
                prediction_path = (
                    prediction_event_path(prediction_root, scene_id, prediction_index, view_index)
                    if prediction_index is not None
                    else None
                )
                pred_events = (
                    RayEvents.load(prediction_path)
                    if prediction_path is not None and prediction_path.is_file()
                    else RayEvents.empty(gt_events.shape[0], gt_events.shape[1], gt_events.shape[2])
                )
                add_statistics(total_statistics, event_statistics(pred_events, gt_events, args.delta_m))
                compared_frames += 1
        scene_records.append(
            {
                "scene_id": scene_id,
                "gt_objects": len(gt_objects),
                "predicted_objects": len(predicted_objects),
                "matches": [
                    {
                        "gt_object_index": gt_objects[gt_index]["object_index"],
                        "prediction_index": prediction_index,
                        "centre_distance_m": distance,
                    }
                    for gt_index, prediction_index, distance in matches
                ],
                "unmatched_gt_object_indices": [gt_objects[index]["object_index"] for index in unmatched_gt],
                "unmatched_prediction_indices": unmatched_prediction,
                "compared_frames": compared_frames,
            }
        )

    precision = totals["matched_objects"] / totals["predicted_objects"] if totals["predicted_objects"] else None
    recall = totals["matched_objects"] / totals["gt_objects"] if totals["gt_objects"] else None
    payload = {
        "method": "T2SQNet_released_models_with_official_GT_masks",
        "input_protocol": "GT mask; LangSAM segmentation bypassed",
        "ground_truth_scope": "TablewareNet model-induced physical-shell oracle; not measured real-wall GT",
        "ground_truth_root": str(gt_root),
        "prediction_root": str(prediction_root),
        "matching": {
            "requires_exact_class": True,
            "max_centre_distance_m": args.max_centre_distance_m,
            "mean_matched_centre_distance_m": float(np.mean(match_distances)) if match_distances else None,
            "object_precision": precision,
            "object_recall": recall,
            **totals,
        },
        "ray_event_metrics": summarize_statistics(total_statistics),
        "missing_prediction_scenes": missing_scenes,
        "scenes": scene_records,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "scenes"}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
