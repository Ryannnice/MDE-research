#!/usr/bin/env python3
"""Adapt axial single-depth caches to per-object ShellBench ray events.

Object identity and visibility come from the TablewareNet oracle.  This is a
controlled representation diagnostic: it deliberately removes instance
detection/association as a confound, but it never invents a back surface for a
single-depth model.  A prediction is emitted only where the isolated GT object
is also the rendered scene's visible first surface.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np


THIS_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--ground-truth-root", type=Path, required=True)
    parser.add_argument("--prediction-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--visibility-tolerance-m", type=float, default=0.003)
    parser.add_argument("--scene-id", action="append", default=[], help="debug-only exact scene identifier; repeatable")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def as_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value)


def ray_scale(intrinsics: np.ndarray, shape_hw: tuple[int, int]) -> np.ndarray:
    """Return Euclidean-ray distance / axial-z for every TablewareNet pixel."""

    intrinsics = np.asarray(intrinsics, dtype=np.float64)
    if intrinsics.shape != (3, 3):
        raise ValueError(f"Expected 3x3 intrinsics, got {intrinsics.shape}")
    height, width = shape_hw
    columns, rows = np.meshgrid(np.arange(width, dtype=np.float64), np.arange(height, dtype=np.float64))
    x = (columns - intrinsics[0, 2]) / intrinsics[0, 0]
    y = (rows - intrinsics[1, 2]) / intrinsics[1, 1]
    return np.sqrt(x * x + y * y + 1.0).astype(np.float32)


def visible_object_mask(
    rendered_axial_m: np.ndarray,
    object_front_range_m: np.ndarray,
    object_front_valid: np.ndarray,
    scale: np.ndarray,
    tolerance_m: float,
) -> np.ndarray:
    if tolerance_m <= 0:
        raise ValueError("visibility tolerance must be positive")
    object_front_axial = np.zeros_like(object_front_range_m, dtype=np.float32)
    np.divide(object_front_range_m, scale, out=object_front_axial, where=object_front_valid)
    return (
        object_front_valid
        & np.isfinite(rendered_axial_m)
        & (rendered_axial_m > 0)
        & (np.abs(rendered_axial_m - object_front_axial) <= tolerance_m)
    )


def clean_rendered_depth(depth: np.ndarray, far_m: float) -> np.ndarray:
    depth = np.asarray(depth, dtype=np.float32).copy()
    valid = np.isfinite(depth) & (depth > 0) & (depth < far_m - 1e-4)
    depth[~valid] = 0
    return depth


def unique_gt_objects(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    objects: dict[int, dict[str, Any]] = {}
    for item in items:
        object_index = item.get("object_index")
        metadata = item.get("ground_truth_object")
        if object_index is not None and metadata is not None:
            objects[int(object_index)] = {"object_index": int(object_index), **metadata}
    return [objects[index] for index in sorted(objects)]


def main() -> None:
    args = parse_args()
    if args.visibility_tolerance_m <= 0:
        raise ValueError("visibility-tolerance-m must be positive")
    data_root = args.data_root.expanduser().resolve()
    gt_root = args.ground_truth_root.expanduser().resolve()
    prediction_root = args.prediction_root.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    gt_payload = load_json(gt_root / "manifest.json")
    prediction_payload = load_json(prediction_root / "manifest.json")
    source_metrics = load_json(prediction_root / "metrics.json")
    if gt_payload.get("summary", {}).get("object_mode") != "per_hollow_object":
        raise ValueError("ground truth must use per_hollow_object mode")
    if not isinstance(prediction_payload, dict) or not isinstance(prediction_payload.get("items"), list):
        raise ValueError("prediction manifest must come from run_tablewarenet_depth_baseline.py")
    if prediction_payload.get("summary", {}).get("prediction_space") != "metric_axial_z_m":
        raise ValueError("prediction cache must contain metric axial z")

    sys.path.insert(0, str(THIS_DIR))
    from ray_events import RayEvents, single_depth_events

    predictions: dict[tuple[str, int], Path] = {}
    for item in prediction_payload["items"]:
        key = (str(item["scene_id"]), int(item["view_index"]))
        if key in predictions:
            raise ValueError(f"Duplicate prediction manifest key: {key}")
        predictions[key] = prediction_root / str(item["prediction_file"])

    gt_by_scene: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in gt_payload.get("items", []):
        if item.get("object_index") is not None:
            gt_by_scene[str(item["scene_id"])].append(item)
    if not gt_by_scene:
        raise ValueError("ground-truth manifest contains no per-object events")
    if args.scene_id:
        requested = set(args.scene_id)
        missing = requested - set(gt_by_scene)
        if missing:
            raise FileNotFoundError(f"Missing requested GT scene IDs: {sorted(missing)}")
        gt_by_scene = {scene: gt_by_scene[scene] for scene in sorted(requested)}

    events_dir = output_dir / "events"
    objects_dir = output_dir / "objects"
    events_dir.mkdir(parents=True, exist_ok=True)
    objects_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    counts = {
        "scenes": 0,
        "objects": 0,
        "object_views": 0,
        "object_hit_pixels": 0,
        "visible_object_pixels": 0,
        "valid_prediction_pixels": 0,
    }
    for scene, items in sorted(gt_by_scene.items()):
        source_files = {str(item["source_file"]) for item in items}
        if len(source_files) != 1:
            raise ValueError(f"Scene {scene} maps to inconsistent source files")
        source_file = next(iter(source_files))
        with (data_root / source_file).open("rb") as handle:
            data = pickle.load(handle)
        cameras = list(data["camera"])
        rendered = as_numpy(data["depth_imgs"]).astype(np.float32, copy=False)
        objects = unique_gt_objects(items)
        object_to_prediction = {int(item["object_index"]): index for index, item in enumerate(objects)}
        predicted_objects = [
            {
                "prediction_index": prediction_index,
                "class": item["class"],
                "pose_world": item["pose_world"],
                "params": item["params"],
                "association_protocol": "copied_from_GT_for_representation_only",
            }
            for prediction_index, item in enumerate(objects)
        ]
        object_file = objects_dir / f"{scene}.json"
        object_file.write_text(
            json.dumps(
                {
                    "scene_id": scene,
                    "source_file": source_file,
                    "input_protocol": "GT instance association and GT first-surface visibility oracle",
                    "predicted_objects": predicted_objects,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        for item in items:
            view = int(item["view_index"])
            object_index = int(item["object_index"])
            prediction_index = object_to_prediction[object_index]
            source_prediction = predictions.get((scene, view))
            if source_prediction is None or not source_prediction.is_file():
                raise FileNotFoundError(f"Missing prediction for {(scene, view)}")
            gt_events = RayEvents.load(gt_root / str(item["event_file"]))
            shape = gt_events.depths_m.shape[1:]
            prediction_axial = np.load(source_prediction).astype(np.float32, copy=False)
            if prediction_axial.shape != shape:
                prediction_axial = cv2.resize(prediction_axial, (shape[1], shape[0]), interpolation=cv2.INTER_LINEAR)
            intrinsics = as_numpy(cameras[view]["camera_intr"]).astype(np.float64)
            scale = ray_scale(intrinsics, shape)
            rendered_axial = clean_rendered_depth(rendered[view], float(as_numpy(cameras[view]["camera_z_far"])))
            visible = visible_object_mask(
                rendered_axial,
                gt_events.depths_m[0],
                gt_events.valid_mask[0],
                scale,
                args.visibility_tolerance_m,
            )
            valid = visible & np.isfinite(prediction_axial) & (prediction_axial > 0)
            prediction_range = np.where(valid, prediction_axial * scale, 0).astype(np.float32)
            output_path = events_dir / f"{scene}_prediction{prediction_index}_view{view}.npz"
            if args.overwrite or not output_path.is_file():
                single_depth_events(prediction_range, valid).save(output_path)
            else:
                cached = RayEvents.load(output_path)
                if cached.depths_m.shape != (1, *shape):
                    raise ValueError(f"Invalid cached event shape at {output_path}")
            counts["object_views"] += 1
            counts["object_hit_pixels"] += int(np.count_nonzero(gt_events.valid_mask[0]))
            counts["visible_object_pixels"] += int(np.count_nonzero(visible))
            counts["valid_prediction_pixels"] += int(np.count_nonzero(valid))

        counts["scenes"] += 1
        counts["objects"] += len(objects)
        manifest.append(
            {
                "scene_id": scene,
                "source_file": source_file,
                "objects_file": str(object_file.relative_to(output_dir)),
                "predicted_object_count": len(objects),
                "event_scope": "single_depth_on_GT_visible_pixels_per_object",
            }
        )

    method = str(source_metrics.get("method", prediction_payload["summary"].get("method", "single_depth")))
    summary = {
        "run_kind": "debug_subset_GT_instance_visibility_adapter" if args.scene_id else "full_GT_instance_visibility_adapter",
        "method": f"{method}_single_depth_GT_instance_visibility_oracle",
        "source_method": method,
        "source_prediction_root": str(prediction_root),
        "input_protocol": (
            f"{source_metrics.get('input_protocol', '')}; adapter uses GT object identity/association "
            "and GT rendered first-surface visibility; emits no back-side hypothesis"
        ),
        "prediction_space": "metric_euclidean_ray_range_m",
        "visibility_tolerance_m": args.visibility_tolerance_m,
        "camera_image_size_contract": "TablewareNet [height, width]",
        "adapter_oracles": ["GT object identity", "GT object association", "GT rendered first-surface visibility"],
        "counts": counts,
        "visible_fraction_of_isolated_object_front": (
            counts["visible_object_pixels"] / counts["object_hit_pixels"] if counts["object_hit_pixels"] else None
        ),
        "valid_fraction_on_visible_pixels": (
            counts["valid_prediction_pixels"] / counts["visible_object_pixels"] if counts["visible_object_pixels"] else None
        ),
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "metrics.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
