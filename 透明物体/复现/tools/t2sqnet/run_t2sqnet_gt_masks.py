#!/usr/bin/env python3
"""Run T²SQNet with official GT masks and cache physical-shell ray events.

This is deliberately a *GT-mask oracle* protocol: it bypasses LangSAM only
for the mask stage, while retaining the released DETR3D, voxel heads, dummy
batch handling and primitive reconstruction.  It must be reported separately
from a full RGB-segmentation T²SQNet result.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import types
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np


THIS_DIR = Path(__file__).resolve().parent
TRANSPARENT_ROOT = THIS_DIR.parents[2]
SHELLBENCH_ROOT = TRANSPARENT_ROOT / "复现" / "tools" / "shellbench"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True, help="TablewareNet processed .pkl root")
    parser.add_argument("--weights-root", type=Path, required=True, help="downloaded official pretrained/ directory")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--view-indices", default="15,16,17,18,19,20,21")
    parser.add_argument("--confidence-threshold", type=float, default=0.75)
    parser.add_argument("--max-events", type=int, default=6)
    parser.add_argument("--epsilon-m", type=float, default=1e-4)
    parser.add_argument("--max-scenes", type=int, help="debug-only prefix of sorted scene files")
    parser.add_argument("--device", default="cuda:0")
    return parser.parse_args()


def require(path: Path, description: str, directory: bool = False) -> Path:
    resolved = path.resolve()
    exists = resolved.is_dir() if directory else resolved.is_file()
    if not exists:
        raise FileNotFoundError(f"Missing {description}: {resolved}")
    return resolved


def parse_view_indices(value: str) -> list[int]:
    result = [int(item) for item in value.split(",") if item]
    if len(result) != 7 or len(set(result)) != 7 or min(result) < 0:
        raise ValueError("view-indices must be seven distinct non-negative indices")
    return result


def select_views(camera_count: int, requested: list[int]) -> list[int]:
    if max(requested) < camera_count:
        return requested
    # Some public TablewareNet releases contain exactly the seven selected
    # views, while the original DETR3D config indexes those views in a 36-view
    # source scene.  This is the only permitted fallback.
    if camera_count == 7:
        return list(range(7))
    raise IndexError(f"requested views {requested} unavailable for {camera_count} cameras")


def as_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value)


def camera_params_for_pipeline(data: dict[str, Any], indices: list[int]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build the exact seven-view relative-workspace input used by T²SQNet."""

    import torch

    origin = as_numpy(data["workspace_origin"]).astype(np.float64).reshape(3)
    cameras: list[dict[str, Any]] = []
    projections: list[Any] = []
    intrinsics: list[np.ndarray] = []
    for index in indices:
        camera = deepcopy(data["camera"][index])
        intrinsic = as_numpy(camera["camera_intr"]).astype(np.float64)
        pose = as_numpy(camera["camera_pose"]).astype(np.float64)
        pose[:3, 3] -= origin
        camera["camera_intr"] = intrinsic
        camera["camera_pose"] = pose
        cameras.append(camera)
        intrinsics.append(intrinsic)
        projections.append(torch.from_numpy(intrinsic @ np.linalg.inv(pose)[:3]).float())
    masks = as_numpy(data["mask_imgs"])[indices]
    if masks.ndim != 3:
        raise ValueError(f"mask_imgs must be [V,H,W], got {masks.shape}")
    return {
        "camera_image_size": torch.tensor(masks.shape[-2:]),
        "projection_matrices": torch.stack(projections),
        "camera_intr": intrinsics,
        "camera_pose": [camera["camera_pose"] for camera in cameras],
    }, cameras


def build_gt_mask_pipeline(
    bbox_model: Path,
    bbox_config: Path,
    param_models: list[Path],
    param_configs: list[Path],
    voxel_config: Path,
    dummy_paths: list[Path],
    device: str,
) -> Any:
    """Instantiate TSQPipeline without LangSAM; safe only with ``from_mask_imgs``."""

    # The upstream module imports LangSAM at module import time even though
    # this oracle never constructs a mask predictor.  A fail-fast placeholder
    # keeps the released geometry/model code intact while making the explicit
    # GT-mask protocol independent of unneeded SAM assets.
    if "lang_sam" not in sys.modules:
        placeholder = types.ModuleType("lang_sam")

        class UnusedLangSAM:  # pragma: no cover - construction would be a protocol violation
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                raise RuntimeError("LangSAM is unavailable in the GT-mask protocol")

        placeholder.LangSAM = UnusedLangSAM
        sys.modules["lang_sam"] = placeholder
    from models.pipelines import TSQPipeline

    pipeline = TSQPipeline.__new__(TSQPipeline)
    pipeline.device = device
    pipeline.load_models(str(bbox_model), str(bbox_config), [str(path) for path in param_models], [str(path) for path in param_configs])
    pipeline.load_voxel_infos(str(voxel_config))
    pipeline.load_dummy_data([str(path) for path in dummy_paths])
    pipeline.use_dummy_data = True
    pipeline.debug_mode = False
    pipeline.num_augs = 0
    return pipeline


def allow_trusted_legacy_checkpoints(torch: Any, weights_root: Path) -> None:
    """Opt into legacy checkpoint loading only for the official asset root.

    T²SQNet's released ``.pkl`` checkpoints predate PyTorch 2.6.  They store
    training logger objects alongside ``model_state``, whereas PyTorch 2.6+
    defaults ``torch.load`` to ``weights_only=True`` and rejects that legacy
    payload.  We intentionally do *not* patch the upstream repository.  This
    process-local wrapper opts into the old behaviour only for files located
    under the explicit ``--weights-root`` supplied to this runner; all other
    ``torch.load`` calls keep their PyTorch default.
    """

    trusted_root = weights_root.resolve()
    original_load = torch.load

    def load_trusted(path: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(path, (str, Path)):
            resolved = Path(path).resolve()
            if resolved.is_relative_to(trusted_root):
                kwargs.setdefault("weights_only", False)
        return original_load(path, *args, **kwargs)

    torch.load = load_trusted


def shell_meshes(objects: list[Any]) -> list[Any]:
    meshes: list[Any] = []
    for obj in objects:
        for primitive in obj.quadrics:
            if primitive.type == "superparaboloid":
                meshes.append(primitive.get_mesh(resolution_radial=48, resolution_height=32))
    return meshes


def shell_meshes_by_object(objects: list[Any]) -> list[list[Any]]:
    """Retain object identity for the per-object GT shell comparison."""

    return [shell_meshes([obj]) for obj in objects]


def object_record(objects: list[Any], workspace_origin: np.ndarray) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for object_index, obj in enumerate(objects):
        pose = as_numpy(obj.SE3).astype(np.float64).copy()
        pose[:3, 3] += workspace_origin
        records.append(
            {
                "prediction_index": object_index,
                "class": str(obj.name),
                "pose_world": pose.tolist(),
                "params": as_numpy(obj.params).astype(np.float64).reshape(-1).tolist(),
                "primitive_types": [str(primitive.type) for primitive in obj.quadrics],
            }
        )
    return records


def main() -> None:
    args = parse_args()
    if not 0 <= args.confidence_threshold <= 1:
        raise ValueError("confidence-threshold must be in [0,1]")
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

    from ray_events import RayEvents
    from tablewarenet_shell_gt import cast_events, rays_from_camera

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    if device.type == "cuda" and device.index not in (None, 0):
        raise ValueError("The upstream voxel-carving implementation hard-codes cuda:0; use --device cuda:0")

    classes = ["WineGlass", "Bowl", "Bottle", "BeerBottle", "HandlessCup", "Mug", "Dish"]
    bbox_model = require(weights_root / "bbox" / "model_best.pkl", "T²SQNet bbox checkpoint")
    bbox_config = require(weights_root / "bbox" / "detr3d.yml", "T²SQNet bbox config")
    param_models = [require(weights_root / "voxel" / name / "model_best_chamfer_metric.pkl", f"{name} voxel checkpoint") for name in classes]
    param_configs = [require(weights_root / "voxel" / name / f"voxel_{name}.yml", f"{name} voxel config") for name in classes]
    voxel_config = require(official_root / "configs" / "voxelize_config.yml", "T²SQNet voxel config")
    dummy_paths = [require(weights_root / "dummy" / str(index), f"T²SQNet dummy scene {index}", directory=True) for index in range(1, 5)]
    allow_trusted_legacy_checkpoints(torch, weights_root)
    pipeline = build_gt_mask_pipeline(
        bbox_model, bbox_config, param_models, param_configs, voxel_config, dummy_paths, str(device)
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
    events_dir.mkdir(parents=True, exist_ok=True)
    objects_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    with torch.no_grad():
        for scene_index, path in enumerate(files):
            with path.open("rb") as handle:
                data = pickle.load(handle)
            indices = select_views(len(data["camera"]), requested_views)
            masks = as_numpy(data["mask_imgs"])[indices]
            pipeline_cameras, relative_cameras = camera_params_for_pipeline(data, indices)
            # ``TSQPipeline.mask2bbox`` moves its dummy padding batch to
            # ``self.device`` but leaves the caller-provided masks untouched.
            # The released RGB path obtains CUDA masks from LangSAM; our
            # GT-mask adapter must mirror that device placement explicitly.
            mask_tensor = torch.from_numpy((masks > 0).astype(np.float32)).to(device)
            _, predicted_classes, object_output = pipeline.forward(
                mask_tensor,
                pipeline_cameras,
                conf_thld=args.confidence_threshold,
                output_all=True,
                from_mask_imgs=True,
            )
            # ``infer_obj`` in the released pipeline returns both objects and
            # voxel metadata, and ``forward`` passes that pair through in the
            # GT-mask/output_all branch.
            objects = object_output[0] if isinstance(object_output, tuple) else object_output
            meshes = shell_meshes(objects)
            meshes_by_object = shell_meshes_by_object(objects)
            scene_id = "__".join(path.relative_to(data_root).with_suffix("").parts)
            origin = as_numpy(data["workspace_origin"]).astype(np.float64).reshape(3)
            object_payload = {
                "scene_id": scene_id,
                "source_file": str(path.relative_to(data_root)),
                "input_protocol": "official_GT_masks_only",
                "view_indices": indices,
                "confidence_threshold": args.confidence_threshold,
                "predicted_classes_from_bbox_head": [str(item) for item in predicted_classes],
                "predicted_objects": object_record(objects, origin),
            }
            object_path = objects_dir / f"{scene_id}.json"
            object_path.write_text(json.dumps(object_payload, indent=2) + "\n", encoding="utf-8")
            for local_view, (source_view, camera) in enumerate(zip(indices, relative_cameras)):
                rays, shape = rays_from_camera(camera)
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
                        "source_file": str(path.relative_to(data_root)),
                        "source_view_index": source_view,
                        "event_file": str(event_file.relative_to(output_dir)),
                        "objects_file": str(object_path.relative_to(output_dir)),
                        "predicted_object_count": len(objects),
                        "predicted_hollow_primitive_count": len(meshes),
                    }
                )
                # The aggregate event map is useful for a scene-level
                # visualization, but per-object maps are the only valid input
                # to the per-object TablewareNet oracle.  Do not silently
                # merge objects and then score their occlusion order as one
                # object's shell topology.
                for prediction_index, object_meshes in enumerate(meshes_by_object):
                    if not object_meshes:
                        continue
                    object_events = cast_events(
                        object_meshes,
                        rays,
                        shape,
                        args.max_events,
                        args.epsilon_m,
                    )
                    object_event_file = events_dir / f"{scene_id}_prediction{prediction_index}_view{source_view}.npz"
                    object_events.save(object_event_file)
                    manifest.append(
                        {
                            "scene_id": scene_id,
                            "scene_index": scene_index,
                            "source_file": str(path.relative_to(data_root)),
                            "source_view_index": source_view,
                            "event_file": str(object_event_file.relative_to(output_dir)),
                            "objects_file": str(object_path.relative_to(output_dir)),
                            "prediction_index": prediction_index,
                            "predicted_class": str(objects[prediction_index].name),
                            "event_scope": "single_predicted_hollow_object",
                            "predicted_hollow_primitive_count": len(object_meshes),
                        }
                    )
    summary = {
        "run_kind": "official_models_GT_mask_oracle" if args.max_scenes is None else "debug_subset_GT_mask_oracle",
        "method": "T2SQNet_released_models_with_official_GT_masks",
        "official_root": str(official_root),
        "data_root": str(data_root),
        "weights_root": str(weights_root),
        "device": str(device),
        "input_protocol": "GT mask; LangSAM segmentation bypassed",
        "checkpoint_loading": "legacy pickle enabled only for files under --weights-root",
        "views": requested_views,
        "scenes": len(files),
        "event_frames": len(manifest),
        "max_events": args.max_events,
        "epsilon_m": args.epsilon_m,
    }
    (output_dir / "metrics.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
