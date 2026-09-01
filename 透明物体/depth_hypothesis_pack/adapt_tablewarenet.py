#!/usr/bin/env python3
"""Adapt TablewareNet DHP predictions to per-object ShellBench events.

GT object identity and rendered-front visibility are used only to isolate the
representation diagnostic, matching the frozen single-depth adapter protocol.
No transition type is fabricated by DepthHypothesisPack v0.
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

from dhp.calibration import load_presence_thresholds


THIS_DIR = Path(__file__).resolve().parent
SHELLBENCH_DIR = THIS_DIR.parent / "复现" / "tools" / "shellbench"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--ground-truth-root", type=Path, required=True)
    parser.add_argument("--prediction-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--presence-threshold", type=float, default=0.5)
    parser.add_argument("--presence-calibration", type=Path)
    parser.add_argument("--visibility-tolerance-m", type=float, default=0.003)
    parser.add_argument("--scene-id", action="append", default=[])
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def as_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value)


def resize_layers(value: np.ndarray, shape_hw: tuple[int, int]) -> np.ndarray:
    value = np.asarray(value, dtype=np.float32)
    if value.ndim != 3:
        raise ValueError(f"Expected KxHxW array, got {value.shape}")
    if value.shape[1:] == shape_hw:
        return value
    height, width = shape_hw
    return np.stack(
        [cv2.resize(layer, (width, height), interpolation=cv2.INTER_LINEAR) for layer in value]
    ).astype(np.float32)


def prediction_events(
    depth_axial_m: np.ndarray,
    presence_probability: np.ndarray,
    uncertainty_axial_m: np.ndarray,
    visible: np.ndarray,
    scale: np.ndarray,
    thresholds: list[float] | np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert ordered axial hypotheses to ordered Euclidean ray events."""

    depth = np.asarray(depth_axial_m, dtype=np.float32)
    presence = np.asarray(presence_probability, dtype=np.float32)
    uncertainty = np.asarray(uncertainty_axial_m, dtype=np.float32)
    if depth.shape != presence.shape or depth.shape != uncertainty.shape:
        raise ValueError("DHP prediction arrays must share one KxHxW shape")
    if depth.shape[1:] != visible.shape or visible.shape != scale.shape:
        raise ValueError("DHP prediction, visibility, and ray scale shapes differ")
    valid = (
        visible[None]
        & np.isfinite(depth)
        & (depth > 0)
        & np.isfinite(presence)
        & (presence >= np.asarray(thresholds, dtype=np.float32)[:, None, None])
    )
    # Monotone presence is part of the model contract, but enforce trailing
    # validity here as a defensive adapter invariant after interpolation.
    valid = np.logical_and.accumulate(valid, axis=0)
    depths_range = np.where(valid, depth * scale[None], 0).astype(np.float32)
    uncertainty_range = np.where(valid, uncertainty * scale[None], 0).astype(
        np.float32
    )
    return depths_range, valid, uncertainty_range


def unique_gt_objects(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    objects: dict[int, dict[str, Any]] = {}
    for item in items:
        object_index = item.get("object_index")
        metadata = item.get("ground_truth_object")
        if object_index is not None and metadata is not None:
            objects[int(object_index)] = {"object_index": int(object_index), **metadata}
    return [objects[index] for index in sorted(objects)]


def main() -> int:
    args = parse_args()
    if not 0 < args.presence_threshold < 1:
        raise ValueError("presence-threshold must be in (0,1)")
    thresholds = (
        load_presence_thresholds(args.presence_calibration)
        if args.presence_calibration is not None
        else [args.presence_threshold] * 4
    )
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
    if prediction_payload.get("summary", {}).get("prediction_space") != "metric_axial_z_m":
        raise ValueError("DHP cache must contain metric axial z")

    sys.path.insert(0, str(SHELLBENCH_DIR))
    from adapt_tablewarenet_depth_baseline import (  # type: ignore
        clean_rendered_depth,
        ray_scale,
        visible_object_mask,
    )
    from ray_events import RayEvents  # type: ignore

    predictions: dict[tuple[str, int], Path] = {}
    for item in prediction_payload.get("items", []):
        key = (str(item["scene_id"]), int(item["view_index"]))
        if key in predictions:
            raise ValueError(f"Duplicate prediction manifest key: {key}")
        predictions[key] = prediction_root / str(item["prediction_file"])

    gt_by_scene: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in gt_payload.get("items", []):
        if item.get("object_index") is not None:
            gt_by_scene[str(item["scene_id"])].append(item)
    if args.scene_id:
        requested = set(args.scene_id)
        missing = requested - set(gt_by_scene)
        if missing:
            raise FileNotFoundError(f"Missing requested GT scene ids: {sorted(missing)}")
        gt_by_scene = {key: gt_by_scene[key] for key in sorted(requested)}

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
        "predicted_events": 0,
        "predicted_rays": 0,
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
        object_to_prediction = {
            int(item["object_index"]): index for index, item in enumerate(objects)
        }
        predicted_objects = [
            {
                "prediction_index": index,
                "class": item["class"],
                "pose_world": item["pose_world"],
                "params": item["params"],
                "association_protocol": "copied_from_GT_for_representation_only",
            }
            for index, item in enumerate(objects)
        ]
        object_file = objects_dir / f"{scene}.json"
        object_file.write_text(
            json.dumps(
                {
                    "scene_id": scene,
                    "source_file": source_file,
                    "input_protocol": (
                        "GT instance association and GT rendered first-surface visibility"
                    ),
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
                raise FileNotFoundError(f"Missing DHP prediction for {(scene, view)}")
            gt_events = RayEvents.load(gt_root / str(item["event_file"]))
            shape = gt_events.depths_m.shape[1:]
            intrinsics = as_numpy(cameras[view]["camera_intr"]).astype(np.float64)
            scale = ray_scale(intrinsics, shape)
            rendered_axial = clean_rendered_depth(
                rendered[view], float(as_numpy(cameras[view]["camera_z_far"]))
            )
            visible = visible_object_mask(
                rendered_axial,
                gt_events.depths_m[0],
                gt_events.valid_mask[0],
                scale,
                args.visibility_tolerance_m,
            )
            with np.load(source_prediction) as payload:
                depth = resize_layers(payload["depth_m"], shape)
                presence = resize_layers(payload["presence_probability"], shape)
                uncertainty = resize_layers(payload["uncertainty_m"], shape)
            depths_range, valid, uncertainty_range = prediction_events(
                depth,
                presence,
                uncertainty,
                visible,
                scale,
                thresholds,
            )
            output_path = (
                events_dir / f"{scene}_prediction{prediction_index}_view{view}.npz"
            )
            events = RayEvents(
                depths_range,
                valid,
                transition_type=None,
                uncertainty_m=uncertainty_range,
            ).normalized()
            if args.overwrite or not output_path.is_file():
                events.save(output_path)
            else:
                cached = RayEvents.load(output_path)
                if cached.depths_m.shape != events.depths_m.shape:
                    raise ValueError(f"Invalid cached event shape at {output_path}")
            counts["object_views"] += 1
            counts["object_hit_pixels"] += int(np.count_nonzero(gt_events.valid_mask[0]))
            counts["visible_object_pixels"] += int(np.count_nonzero(visible))
            counts["predicted_events"] += int(np.count_nonzero(valid))
            counts["predicted_rays"] += int(np.count_nonzero(valid[0]))

        counts["scenes"] += 1
        counts["objects"] += len(objects)
        manifest.append(
            {
                "scene_id": scene,
                "source_file": source_file,
                "objects_file": str(object_file.relative_to(output_dir)),
                "predicted_object_count": len(objects),
                "event_scope": "DHP_K4_on_GT_visible_pixels_per_object",
            }
        )

    source_method = str(source_metrics.get("method") or "DepthHypothesisPack")
    summary = {
        "run_kind": (
            "debug_subset_GT_instance_visibility_adapter"
            if args.scene_id
            else "full_GT_instance_visibility_adapter"
        ),
        "method": f"{source_method}_GT_instance_visibility_oracle",
        "source_method": source_method,
        "source_prediction_root": str(prediction_root),
        "input_protocol": (
            f"{source_metrics.get('input_protocol', '')}; adapter uses GT object identity, "
            "association, and rendered first-surface visibility"
        ),
        "prediction_space": "metric_euclidean_ray_range_m",
        "presence_thresholds": thresholds,
        "presence_calibration": (
            str(args.presence_calibration.expanduser().resolve())
            if args.presence_calibration is not None
            else None
        ),
        "visibility_tolerance_m": args.visibility_tolerance_m,
        "transition_semantics": "unsupported_all_labels_UNKNOWN",
        "adapter_oracles": [
            "GT object identity",
            "GT object association",
            "GT rendered first-surface visibility",
        ],
        "counts": counts,
        "visible_fraction_of_isolated_object_front": (
            counts["visible_object_pixels"] / counts["object_hit_pixels"]
            if counts["object_hit_pixels"]
            else None
        ),
        "mean_events_per_predicted_ray": (
            counts["predicted_events"] / counts["predicted_rays"]
            if counts["predicted_rays"]
            else None
        ),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "metrics.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
