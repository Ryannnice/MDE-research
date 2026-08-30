#!/usr/bin/env python3
"""Run single-depth baselines on every processed TablewareNet test view.

The released TablewareNet pickle stores rendered axial camera depth.  This
runner keeps that convention in its cache and removes the far-plane value.
For completion models, the official union object mask is zeroed in the input
depth.  DFNet and ReMake retain their released checkpoints, model code, and
preprocessing; applying them to TablewareNet is explicitly an OOD diagnostic,
not a reproduction of their native TransCG paper score.
"""

from __future__ import annotations

import argparse
import gc
import json
import pickle
import sys
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import cv2
import numpy as np


THIS_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", choices=("rendered_front", "masked_raw", "dfnet", "remake"), required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--official-root", type=Path)
    parser.add_argument("--checkpoint-path", type=Path)
    parser.add_argument("--relative-depth-weights", type=Path)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--max-scenes", type=int, help="debug-only prefix of sorted scene files")
    parser.add_argument("--scene-id", action="append", default=[], help="debug-only exact scene identifier; repeatable")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def as_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value)


def scene_id(path: Path, data_root: Path) -> str:
    return "__".join(path.relative_to(data_root).with_suffix("").parts)


def require_file(path: Path | None, label: str) -> Path:
    if path is None or not path.expanduser().resolve().is_file():
        raise FileNotFoundError(f"Missing {label}: {path}")
    return path.expanduser().resolve()


def require_checkout(path: Path | None, relative_file: str, label: str) -> Path:
    if path is None:
        raise FileNotFoundError(f"Missing {label}: {path}")
    root = path.expanduser().resolve()
    if not (root / relative_file).is_file():
        raise FileNotFoundError(f"Invalid {label}: {root}")
    return root


def clean_rendered_depth(depth: np.ndarray, far_m: float) -> np.ndarray:
    result = np.asarray(depth, dtype=np.float32).copy()
    valid = np.isfinite(result) & (result > 0) & (result < far_m - 1e-4)
    result[~valid] = 0
    return result


def atomic_save_npy(path: Path, array: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, np.asarray(array, dtype=np.float32))
    temporary.replace(path)


def torch_batch(torch: Any, records: list[dict[str, Any]], device: Any) -> dict[str, Any]:
    from torch.utils.data import default_collate

    batch = default_collate(records)
    return {
        key: value.to(device, non_blocking=True) if torch.is_tensor(value) else value
        for key, value in batch.items()
    }


def build_dfnet(args: argparse.Namespace) -> tuple[Callable[..., np.ndarray], dict[str, Any]]:
    official_root = require_checkout(args.official_root, "models/DFNet.py", "TransCG checkout")
    checkpoint_path = require_file(args.checkpoint_path, "DFNet checkpoint")
    sys.path.insert(0, str(official_root))

    import torch
    from models.DFNet import DFNet
    from utils.data_preparation import process_data

    # The released preprocessing used NumPy's removed np.bool alias.
    if "bool" not in np.__dict__:
        np.bool = np.bool_  # type: ignore[attr-defined]
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    model = DFNet(in_channels=4, hidden_channels=64, L=5, k=12).to(device)
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval()

    def infer(rgb: np.ndarray, depth: np.ndarray, mask: np.ndarray, cameras: list[dict[str, Any]]) -> np.ndarray:
        records = []
        for view in range(len(rgb)):
            intrinsics = as_numpy(cameras[view]["camera_intr"]).astype(np.float32)
            records.append(
                process_data(
                    rgb[view].astype(np.float32),
                    depth[view],
                    depth[view],
                    mask[view].astype(np.uint8),
                    intrinsics,
                    scene_type="cluttered",
                    camera_type=0,
                    split="test",
                    image_size=(320, 240),
                    depth_min=0.0,
                    depth_max=10.0,
                    depth_norm=10.0,
                    use_aug=False,
                    inpainting=False,
                )
            )
        batch = torch_batch(torch, records, device)
        with torch.inference_mode():
            prediction = model(batch["rgb"], batch["depth"])
            scale = batch["depth_max"] - batch["depth_min"]
            prediction = prediction * scale[:, None, None] + batch["depth_min"][:, None, None]
        # Matches the released TransCG runner: preprocessing uses depth_norm=10.
        return (prediction * 10.0).detach().cpu().numpy().astype(np.float32)

    return infer, {
        "model": "TransCG_DFNet_release_checkpoint",
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_epoch": int(checkpoint.get("epoch", -1)),
        "official_root": str(official_root),
        "preprocessing": "released TransCG process_data; 320x240; depth_norm=10; GT union object mask zeroed before inference",
    }


def build_remake(args: argparse.Namespace) -> tuple[Callable[..., np.ndarray], dict[str, Any]]:
    official_root = require_checkout(args.official_root, "models/remake.py", "ReMake checkout")
    checkpoint_path = require_file(args.checkpoint_path, "ReMake checkpoint")
    relative_weights = require_file(args.relative_depth_weights, "Depth Anything V2 vits weights")
    sys.path.insert(0, str(official_root))
    sys.path.insert(0, str(THIS_DIR.parent / "remake"))

    import torch
    import torch.nn.functional as functional
    from models.remake import ReMake
    from run_remake_full import load_depth_anything
    from utils.data_preparation import process_data

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    model = ReMake(lambda_val=1, res=True).to(device)
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval()
    relative_model = load_depth_anything(relative_weights, device)

    def infer(rgb: np.ndarray, depth: np.ndarray, mask: np.ndarray, cameras: list[dict[str, Any]]) -> np.ndarray:
        records = []
        for view in range(len(rgb)):
            resized_rgb = cv2.resize(rgb[view], (640, 480), interpolation=cv2.INTER_LINEAR).astype(np.float32)
            resized_depth = cv2.resize(depth[view], (640, 480), interpolation=cv2.INTER_NEAREST)
            resized_mask = cv2.resize(mask[view].astype(np.uint8), (640, 480), interpolation=cv2.INTER_NEAREST).astype(bool)
            intrinsics = as_numpy(cameras[view]["camera_intr"]).astype(np.float32).copy()
            intrinsics[0] *= 2.0
            intrinsics[1] *= 2.0
            records.append(
                process_data(
                    resized_rgb,
                    resized_depth,
                    resized_depth,
                    resized_mask,
                    intrinsics,
                    scene_type="cluttered",
                    camera_type=0,
                    split="test",
                    image_size=(640, 480),
                    depth_min=0.0,
                    depth_max=10.0,
                    depth_norm=1.0,
                    use_aug=False,
                    use_depth_aug=False,
                    no_mask_depth=False,
                    reldepth_model="depthanything",
                )
            )
        batch = torch_batch(torch, records, device)
        with torch.inference_mode():
            relative_depth = relative_model.forward(batch["rgb_relat"]).unsqueeze(1)
            relative_depth = functional.interpolate(relative_depth, size=(480, 640), mode="bilinear", align_corners=False)
            prediction = model(batch["rgb"], relative_depth, batch["depth"], batch["depth_gt_mask"])
        return prediction[:, 0].detach().cpu().numpy().astype(np.float32)

    return infer, {
        "model": "ReMake_release_checkpoint_with_DepthAnythingV2_vits",
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_epoch": int(checkpoint.get("epoch", -1)),
        "relative_depth_weights": str(relative_weights),
        "official_root": str(official_root),
        "preprocessing": "released ReMake process_data and DepthAnythingV2-vits; 640x480; GT union object mask zeroed in depth and supplied as mask channel",
    }


def main() -> None:
    args = parse_args()
    data_root = args.data_root.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    if not data_root.is_dir():
        raise NotADirectoryError(data_root)
    files = sorted(data_root.rglob("*.pkl"))
    if args.scene_id:
        requested = set(args.scene_id)
        files = [path for path in files if scene_id(path, data_root) in requested]
        found = {scene_id(path, data_root) for path in files}
        if found != requested:
            raise FileNotFoundError(f"Missing requested scene IDs: {sorted(requested - found)}")
    if args.max_scenes is not None:
        if args.max_scenes < 1:
            raise ValueError("max-scenes must be positive")
        files = files[: args.max_scenes]
    if not files:
        raise FileNotFoundError(f"No TablewareNet pickle under {data_root}")

    if args.method == "dfnet":
        infer, model_metadata = build_dfnet(args)
    elif args.method == "remake":
        infer, model_metadata = build_remake(args)
    else:
        infer = None
        model_metadata = {
            "model": args.method,
            "preprocessing": "TablewareNet rendered axial z with far plane removed; official union object mask zeroed only for masked_raw",
        }

    prediction_dir = output_dir / "predictions_m"
    prediction_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    durations: list[float] = []
    reused = 0
    for order, path in enumerate(files):
        identifier = scene_id(path, data_root)
        with path.open("rb") as handle:
            data = pickle.load(handle)
        rgb = as_numpy(data["rgb_imgs"]).astype(np.uint8, copy=False)
        rendered_depth = as_numpy(data["depth_imgs"]).astype(np.float32, copy=False)
        mask = as_numpy(data["mask_imgs"]).astype(bool, copy=False)
        cameras = list(data["camera"])
        if rgb.shape[:3] != rendered_depth.shape or mask.shape != rendered_depth.shape:
            raise ValueError(f"Inconsistent TablewareNet arrays in {path}")
        clean_depth = np.stack(
            [clean_rendered_depth(rendered_depth[view], float(as_numpy(cameras[view]["camera_z_far"]))) for view in range(len(cameras))]
        )
        masked_depth = np.where(mask, 0.0, clean_depth).astype(np.float32)
        destinations = [prediction_dir / f"{identifier}_view{view}.npy" for view in range(len(cameras))]
        can_reuse = args.resume and all(destination.is_file() for destination in destinations)
        if can_reuse:
            predictions = [np.load(destination, mmap_mode="r") for destination in destinations]
            if any(prediction.ndim != 2 or not np.all(np.isfinite(prediction)) for prediction in predictions):
                raise ValueError(f"Invalid cached predictions for {identifier}")
            reused += len(destinations)
        else:
            start = perf_counter()
            if args.method == "rendered_front":
                predictions = clean_depth
            elif args.method == "masked_raw":
                predictions = masked_depth
            else:
                assert infer is not None
                predictions = infer(rgb, masked_depth, mask, cameras)
            durations.append(perf_counter() - start)
            if len(predictions) != len(cameras):
                raise ValueError(f"Expected {len(cameras)} predictions, got {len(predictions)}")
            for destination, prediction in zip(destinations, predictions):
                prediction = np.asarray(prediction, dtype=np.float32)
                prediction[~np.isfinite(prediction)] = 0
                prediction[prediction < 0] = 0
                atomic_save_npy(destination, prediction)

        for view, destination in enumerate(destinations):
            prediction = np.load(destination, mmap_mode="r")
            manifest.append(
                {
                    "scene_id": identifier,
                    "scene_order": order,
                    "source_file": str(path.relative_to(data_root)),
                    "view_index": view,
                    "prediction_file": str(destination.relative_to(output_dir)),
                    "prediction_size_hw": list(prediction.shape),
                    "source_size_hw": list(rendered_depth[view].shape),
                    "prediction_space": "metric_axial_z_m",
                    "union_object_mask_ratio": float(mask[view].mean()),
                }
            )
        del data, rgb, rendered_depth, mask, clean_depth, masked_depth
        gc.collect()

    run_kind = (
        "full_tablewarenet_processed_test"
        if args.max_scenes is None and not args.scene_id
        else "debug_subset"
    )
    input_protocol = {
        "rendered_front": "TablewareNet rendered front axial depth; model-free upper bound",
        "masked_raw": "TablewareNet rendered front depth with official union object mask set to zero",
        "dfnet": "RGB + mask-zeroed rendered depth; released DFNet checkpoint; OOD TablewareNet",
        "remake": "RGB + mask-zeroed rendered depth + official union object mask; released ReMake checkpoint; OOD TablewareNet",
    }[args.method]
    summary = {
        "run_kind": run_kind,
        "method": args.method,
        "input_protocol": input_protocol,
        "data_root": str(data_root),
        "device": args.device if args.method in {"dfnet", "remake"} else "cpu",
        "scenes": len(files),
        "views": len(manifest),
        "reused_views": reused,
        "mean_inference_seconds_per_scene": float(np.mean(durations)) if durations else None,
        "prediction_space": "metric_axial_z_m",
        "camera_image_size_contract": "TablewareNet [height, width]",
        "model_metadata": model_metadata,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps({"summary": summary, "items": manifest}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "metrics.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
