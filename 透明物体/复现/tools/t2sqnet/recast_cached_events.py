#!/usr/bin/env python3
"""Recast cached T²SQNet objects into corrected TablewareNet ray events.

This does not rerun the recognition network.  It reuses the auditable object
records produced by ``run_t2sqnet_gt_masks.py`` and changes only the derived
ray grid after fixing TablewareNet's [height, width] camera-size convention.
"""

from __future__ import annotations

import argparse
import json
import pickle
import shutil
import sys
from pathlib import Path
from typing import Any


THIS_DIR = Path(__file__).resolve().parent
TRANSPARENT_ROOT = THIS_DIR.parents[2]
SHELLBENCH_ROOT = TRANSPARENT_ROOT / "复现" / "tools" / "shellbench"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--objects-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-events", type=int, default=6)
    parser.add_argument("--epsilon-m", type=float, default=1e-4)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    args = parse_args()
    official_root = args.official_root.resolve()
    data_root = args.data_root.resolve()
    objects_root = args.objects_root.resolve()
    output_dir = args.output_dir.resolve()
    if args.max_events < 1 or args.epsilon_m <= 0:
        raise ValueError("max-events and epsilon-m must be positive")
    if not (official_root / "tablewarenet" / "tableware.py").is_file():
        raise FileNotFoundError(f"Not a T²SQNet checkout: {official_root}")
    if not data_root.is_dir() or not objects_root.is_dir():
        raise NotADirectoryError("data-root and objects-root must be directories")

    sys.path.insert(0, str(official_root))
    sys.path.insert(0, str(SHELLBENCH_ROOT))
    import torch

    from ray_events import RayEvents
    from tablewarenet.tableware import name_to_class
    from tablewarenet_shell_gt import cast_events, rays_from_camera

    # Import only geometry helpers; this module does not instantiate LangSAM
    # or load any recognition checkpoint.
    from run_t2sqnet_gt_masks import shell_meshes, shell_meshes_by_object

    object_files = sorted(objects_root.glob("*.json"))
    if not object_files:
        raise FileNotFoundError(f"No cached object records under {objects_root}")
    events_dir = output_dir / "events"
    copied_objects_dir = output_dir / "objects"
    events_dir.mkdir(parents=True, exist_ok=True)
    copied_objects_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []

    for scene_index, object_file in enumerate(object_files):
        payload = load_json(object_file)
        scene_id = str(payload["scene_id"])
        source_file = str(payload["source_file"])
        scene_path = data_root / source_file
        with scene_path.open("rb") as handle:
            data = pickle.load(handle)
        indices = [int(value) for value in payload["view_indices"]]
        records = list(payload.get("predicted_objects", []))
        objects = [
            name_to_class[str(record["class"])](
                torch.as_tensor(record["pose_world"], dtype=torch.float32),
                torch.as_tensor(record["params"], dtype=torch.float32),
                device="cpu",
                t=0.01,
                process_mesh=True,
            )
            for record in records
        ]
        meshes = shell_meshes(objects)
        meshes_by_object = shell_meshes_by_object(objects)
        copied_object_file = copied_objects_dir / object_file.name
        shutil.copy2(object_file, copied_object_file)

        for source_view in indices:
            rays, shape = rays_from_camera(data["camera"][source_view])
            events = (
                cast_events(meshes, rays, shape, args.max_events, args.epsilon_m)
                if meshes
                else RayEvents.empty(args.max_events, *shape)
            )
            event_file = events_dir / f"{scene_id}_view{source_view}.npz"
            events.save(event_file)
            manifest.append(
                {
                    "scene_id": scene_id,
                    "scene_index": scene_index,
                    "source_file": source_file,
                    "source_view_index": source_view,
                    "event_file": str(event_file.relative_to(output_dir)),
                    "objects_file": str(copied_object_file.relative_to(output_dir)),
                    "predicted_object_count": len(objects),
                    "predicted_hollow_primitive_count": len(meshes),
                    "ray_grid_shape_hw": list(shape),
                }
            )
            for prediction_index, object_meshes in enumerate(meshes_by_object):
                if not object_meshes:
                    continue
                object_events = cast_events(
                    object_meshes, rays, shape, args.max_events, args.epsilon_m
                )
                object_event_file = events_dir / (
                    f"{scene_id}_prediction{prediction_index}_view{source_view}.npz"
                )
                object_events.save(object_event_file)
                manifest.append(
                    {
                        "scene_id": scene_id,
                        "scene_index": scene_index,
                        "source_file": source_file,
                        "source_view_index": source_view,
                        "event_file": str(object_event_file.relative_to(output_dir)),
                        "objects_file": str(copied_object_file.relative_to(output_dir)),
                        "prediction_index": prediction_index,
                        "predicted_class": str(objects[prediction_index].name),
                        "event_scope": "single_predicted_hollow_object",
                        "predicted_hollow_primitive_count": len(object_meshes),
                        "ray_grid_shape_hw": list(shape),
                    }
                )

    summary = {
        "run_kind": "cached_GT_mask_objects_corrected_ray_grid",
        "method": "T2SQNet_released_models_with_official_GT_masks",
        "input_protocol": "GT mask; cached released-model objects; LangSAM bypassed",
        "source_objects_root": str(objects_root),
        "official_root": str(official_root),
        "data_root": str(data_root),
        "camera_image_size_contract": "TablewareNet [height, width]",
        "scenes": len(object_files),
        "event_frames": len(manifest),
        "max_events": args.max_events,
        "epsilon_m": args.epsilon_m,
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
