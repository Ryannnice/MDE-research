#!/usr/bin/env python3
"""Run released T²SQNet end to end from RGB with its official LangSAM path.

This is the deployable T²SQNet baseline.  Unlike the separate GT-mask oracle,
it preserves the upstream ``rgb2mask`` implementation, its ``tableware`` text
prompt, five hue augmentations by default, released DETR3D/voxel heads, and
the seven-view TablewareNet input.  Per-scene commits make a long run safely
resumable without mixing partial outputs into the final manifest.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path
from typing import Any

import numpy as np


THIS_DIR = Path(__file__).resolve().parent
TRANSPARENT_ROOT = THIS_DIR.parents[2]
SHELLBENCH_ROOT = TRANSPARENT_ROOT / "复现" / "tools" / "shellbench"
sys.path.insert(0, str(THIS_DIR))

from run_t2sqnet_gt_masks import (  # noqa: E402
    allow_trusted_legacy_checkpoints,
    as_numpy,
    camera_params_for_pipeline,
    object_record,
    parse_view_indices,
    require,
    select_views,
    shell_meshes,
    shell_meshes_by_object,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True, help="TablewareNet processed .pkl root")
    parser.add_argument("--weights-root", type=Path, required=True, help="downloaded official pretrained/ directory")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--view-indices", default="15,16,17,18,19,20,21")
    parser.add_argument("--text-prompt", default="tableware")
    parser.add_argument("--confidence-threshold", type=float, default=0.75)
    parser.add_argument("--num-augs", type=int, default=5)
    parser.add_argument("--max-events", type=int, default=6)
    parser.add_argument("--epsilon-m", type=float, default=1e-4)
    parser.add_argument("--max-scenes", type=int, help="debug-only prefix of sorted scene files")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def validate_scene_commit(output_dir: Path, payload: dict[str, Any]) -> None:
    required = [payload.get("objects_file"), payload.get("masks_file")]
    required.extend(item.get("event_file") for item in payload.get("manifest", []))
    missing = [str(value) for value in required if not value or not (output_dir / str(value)).is_file()]
    if missing:
        raise FileNotFoundError(f"Incomplete committed scene {payload.get('scene_id')}: {missing[:5]}")


def main() -> None:
    args = parse_args()
    if not 0 <= args.confidence_threshold <= 1:
        raise ValueError("confidence-threshold must be in [0,1]")
    if args.num_augs < 2:
        raise ValueError("num-augs must be at least 2 for the unchanged upstream hue schedule")
    if args.max_events < 1 or args.epsilon_m <= 0:
        raise ValueError("max-events and epsilon-m must be positive")
    requested_views = parse_view_indices(args.view_indices)
    official_root = require(args.official_root, "T²SQNet checkout", directory=True)
    data_root = require(args.data_root, "TablewareNet processed root", directory=True)
    weights_root = require(args.weights_root, "T²SQNet pretrained root", directory=True)
    require(official_root / "models" / "pipelines.py", "T²SQNet pipeline source")
    sys.path.insert(0, str(official_root))
    sys.path.insert(0, str(SHELLBENCH_ROOT))

    import torch
    from models.pipelines import TSQPipeline
    from ray_events import RayEvents
    from tablewarenet_shell_gt import cast_events, rays_from_camera

    device = torch.device(args.device)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("The released RGB baseline requires CUDA")
    if device.index not in (None, 0):
        raise ValueError("Launch with CUDA_VISIBLE_DEVICES and use --device cuda:0; upstream voxel carving hard-codes cuda:0")

    classes = ["WineGlass", "Bowl", "Bottle", "BeerBottle", "HandlessCup", "Mug", "Dish"]
    bbox_model = require(weights_root / "bbox" / "model_best.pkl", "T²SQNet bbox checkpoint")
    bbox_config = require(weights_root / "bbox" / "detr3d.yml", "T²SQNet bbox config")
    param_models = [require(weights_root / "voxel" / name / "model_best_chamfer_metric.pkl", f"{name} voxel checkpoint") for name in classes]
    param_configs = [require(weights_root / "voxel" / name / f"voxel_{name}.yml", f"{name} voxel config") for name in classes]
    voxel_config = require(official_root / "configs" / "voxelize_config.yml", "T²SQNet voxel config")
    dummy_paths = [require(weights_root / "dummy" / str(index), f"T²SQNet dummy scene {index}", directory=True) for index in range(1, 5)]

    allow_trusted_legacy_checkpoints(torch, weights_root)
    pipeline = TSQPipeline(
        str(bbox_model),
        str(bbox_config),
        [str(path) for path in param_models],
        [str(path) for path in param_configs],
        str(voxel_config),
        device=str(device),
        dummy_data_paths=[str(path) for path in dummy_paths],
        num_augs=args.num_augs,
        debug_mode=False,
    )

    files = sorted(data_root.rglob("*.pkl"))
    if args.max_scenes is not None:
        if args.max_scenes < 1:
            raise ValueError("max-scenes must be positive")
        files = files[: args.max_scenes]
    if not files:
        raise FileNotFoundError(f"No .pkl scenes under {data_root}")

    output_dir = args.output_dir.resolve()
    events_dir = output_dir / "events"
    objects_dir = output_dir / "objects"
    masks_dir = output_dir / "masks"
    scenes_dir = output_dir / "scenes"
    for directory in (events_dir, objects_dir, masks_dir, scenes_dir):
        directory.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, Any]] = []
    resumed_scenes = 0
    with torch.no_grad():
        for scene_index, path in enumerate(files):
            scene_id = "__".join(path.relative_to(data_root).with_suffix("").parts)
            scene_commit_path = scenes_dir / f"{scene_id}.json"
            if args.resume and scene_commit_path.is_file():
                scene_payload = json.loads(scene_commit_path.read_text(encoding="utf-8"))
                validate_scene_commit(output_dir, scene_payload)
                manifest.extend(scene_payload["manifest"])
                resumed_scenes += 1
                print(f"[{scene_index + 1}/{len(files)}] resumed {scene_id}", flush=True)
                continue

            with path.open("rb") as handle:
                data = pickle.load(handle)
            indices = select_views(len(data["camera"]), requested_views)
            camera_params, relative_cameras = camera_params_for_pipeline(data, indices)
            rgb = as_numpy(data["rgb_imgs"])[indices]
            if rgb.ndim != 4 or rgb.shape[-1] != 3:
                raise ValueError(f"rgb_imgs must be [V,H,W,3], got {rgb.shape}")
            rgb_tensor = torch.from_numpy(rgb).float().permute(0, 3, 1, 2)
            mask_tensor, _, predicted_classes, object_output = pipeline.forward(
                rgb_tensor,
                camera_params,
                text_prompt=args.text_prompt,
                conf_thld=args.confidence_threshold,
                output_all=True,
                from_mask_imgs=False,
            )
            objects = object_output[0] if isinstance(object_output, tuple) else object_output
            meshes = shell_meshes(objects)
            meshes_by_object = shell_meshes_by_object(objects)
            origin = as_numpy(data["workspace_origin"]).astype(np.float64).reshape(3)
            object_payload = {
                "scene_id": scene_id,
                "source_file": str(path.relative_to(data_root)),
                "input_protocol": "RGB through unchanged official LangSAM rgb2mask",
                "view_indices": indices,
                "text_prompt": args.text_prompt,
                "num_augs": args.num_augs,
                "confidence_threshold": args.confidence_threshold,
                "predicted_classes_from_bbox_head": [str(item) for item in predicted_classes],
                "predicted_objects": object_record(objects, origin),
            }
            object_path = objects_dir / f"{scene_id}.json"
            object_path.write_text(json.dumps(object_payload, indent=2) + "\n", encoding="utf-8")
            mask_path = masks_dir / f"{scene_id}.npz"
            np.savez_compressed(
                mask_path,
                mask_imgs=as_numpy(mask_tensor).astype(bool),
                view_indices=np.asarray(indices, dtype=np.int16),
            )

            scene_manifest: list[dict[str, Any]] = []
            for source_view, camera in zip(indices, relative_cameras):
                rays, shape = rays_from_camera(camera)
                events = (
                    cast_events(meshes, rays, shape, args.max_events, args.epsilon_m)
                    if meshes
                    else RayEvents.empty(args.max_events, *shape)
                )
                event_file = events_dir / f"{scene_id}_view{source_view}.npz"
                events.save(event_file)
                scene_manifest.append(
                    {
                        "scene_id": scene_id,
                        "scene_index": scene_index,
                        "source_file": str(path.relative_to(data_root)),
                        "source_view_index": source_view,
                        "shape_hw": list(shape),
                        "event_file": str(event_file.relative_to(output_dir)),
                        "objects_file": str(object_path.relative_to(output_dir)),
                        "masks_file": str(mask_path.relative_to(output_dir)),
                        "predicted_object_count": len(objects),
                        "predicted_hollow_primitive_count": len(meshes),
                    }
                )
                for prediction_index, object_meshes in enumerate(meshes_by_object):
                    if not object_meshes:
                        continue
                    object_events = cast_events(object_meshes, rays, shape, args.max_events, args.epsilon_m)
                    object_event_file = events_dir / f"{scene_id}_prediction{prediction_index}_view{source_view}.npz"
                    object_events.save(object_event_file)
                    scene_manifest.append(
                        {
                            "scene_id": scene_id,
                            "scene_index": scene_index,
                            "source_file": str(path.relative_to(data_root)),
                            "source_view_index": source_view,
                            "shape_hw": list(shape),
                            "event_file": str(object_event_file.relative_to(output_dir)),
                            "objects_file": str(object_path.relative_to(output_dir)),
                            "masks_file": str(mask_path.relative_to(output_dir)),
                            "prediction_index": prediction_index,
                            "predicted_class": str(objects[prediction_index].name),
                            "event_scope": "single_predicted_hollow_object",
                            "predicted_hollow_primitive_count": len(object_meshes),
                        }
                    )
            scene_payload = {
                "scene_id": scene_id,
                "objects_file": str(object_path.relative_to(output_dir)),
                "masks_file": str(mask_path.relative_to(output_dir)),
                "manifest": scene_manifest,
            }
            scene_commit_path.write_text(json.dumps(scene_payload, indent=2) + "\n", encoding="utf-8")
            manifest.extend(scene_manifest)
            print(
                f"[{scene_index + 1}/{len(files)}] {scene_id}: masks={tuple(mask_tensor.shape)}, objects={len(objects)}",
                flush=True,
            )

    summary = {
        "run_kind": "official_RGB_full" if args.max_scenes is None else "debug_subset_official_RGB",
        "method": "T2SQNet_released_models_with_official_LangSAM",
        "official_root": str(official_root),
        "data_root": str(data_root),
        "weights_root": str(weights_root),
        "device": str(device),
        "input_protocol": "RGB; upstream LangSAM rgb2mask unchanged",
        "text_prompt": args.text_prompt,
        "num_augs": args.num_augs,
        "confidence_threshold": args.confidence_threshold,
        "checkpoint_loading": "legacy pickle enabled only for files under --weights-root",
        "views": requested_views,
        "scenes": len(files),
        "resumed_scenes": resumed_scenes,
        "event_frames": len(manifest),
        "max_events": args.max_events,
        "epsilon_m": args.epsilon_m,
        "camera_image_size_contract": "TablewareNet [height, width]",
    }
    (output_dir / "metrics.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
