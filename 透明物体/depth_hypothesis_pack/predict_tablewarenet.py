#!/usr/bin/env python3
"""Run DepthHypothesisPack on every processed TablewareNet RGB view."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import pickle
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import torch

from dhp.inference import load_model, predict_image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--input-height", type=int, default=256)
    parser.add_argument("--max-scenes", type=int, help="debug-only sorted prefix")
    parser.add_argument(
        "--scene-id", action="append", default=[], help="debug-only exact scene id"
    )
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value)


def scene_id(path: Path, data_root: Path) -> str:
    return "__".join(path.relative_to(data_root).with_suffix("").parts)


def atomic_save_prediction(path: Path, prediction: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(
            handle,
            depth_m=np.asarray(prediction["depth"], dtype=np.float32),
            presence_probability=np.asarray(
                prediction["presence_probability"], dtype=np.float32
            ),
            uncertainty_m=np.asarray(prediction["uncertainty"], dtype=np.float32),
        )
    temporary.replace(path)


def validate_prediction(path: Path, expected_hw: tuple[int, int]) -> tuple[int, int, int]:
    with np.load(path) as payload:
        required = ("depth_m", "presence_probability", "uncertainty_m")
        if any(key not in payload for key in required):
            raise ValueError(f"Incomplete DHP prediction: {path}")
        shapes = {tuple(payload[key].shape) for key in required}
        if len(shapes) != 1:
            raise ValueError(f"Inconsistent arrays in {path}: {sorted(shapes)}")
        shape = next(iter(shapes))
        if len(shape) != 3 or shape[1:] != expected_hw:
            raise ValueError(f"Expected Kx{expected_hw} at {path}, got {shape}")
        if not all(np.all(np.isfinite(payload[key])) for key in required):
            raise ValueError(f"Non-finite DHP prediction: {path}")
    return shape


def main() -> int:
    args = parse_args()
    if args.input_height < 32:
        raise ValueError("input-height must be at least 32")
    checkpoint = args.checkpoint.expanduser().resolve()
    data_root = args.data_root.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    if not data_root.is_dir():
        raise NotADirectoryError(data_root)

    files = sorted(data_root.rglob("*.pkl"))
    if args.scene_id:
        requested = set(args.scene_id)
        files = [path for path in files if scene_id(path, data_root) in requested]
        found = {scene_id(path, data_root) for path in files}
        if found != requested:
            raise FileNotFoundError(f"Missing scene ids: {sorted(requested - found)}")
    if args.max_scenes is not None:
        if args.max_scenes < 1:
            raise ValueError("max-scenes must be positive")
        files = files[: args.max_scenes]
    if not files:
        raise FileNotFoundError(f"No TablewareNet pickle under {data_root}")

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    model = load_model(checkpoint, device)
    prediction_dir = output_dir / "predictions"
    prediction_dir.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, Any]] = []
    durations: list[float] = []
    reused_views = 0
    for order, path in enumerate(files):
        identifier = scene_id(path, data_root)
        with path.open("rb") as handle:
            data = pickle.load(handle)
        rgb = as_numpy(data["rgb_imgs"]).astype(np.uint8, copy=False)
        if rgb.ndim != 4 or rgb.shape[-1] != 3:
            raise ValueError(f"Expected VxHxWx3 RGB in {path}, got {rgb.shape}")
        for view, image in enumerate(rgb):
            destination = prediction_dir / f"{identifier}_view{view}.npz"
            reused = args.resume and destination.is_file()
            if reused:
                shape = validate_prediction(destination, image.shape[:2])
                reused_views += 1
            else:
                start = perf_counter()
                prediction = predict_image(model, image, device, args.input_height)
                durations.append(perf_counter() - start)
                atomic_save_prediction(destination, prediction)
                shape = validate_prediction(destination, image.shape[:2])
            items.append(
                {
                    "scene_id": identifier,
                    "scene_order": order,
                    "source_file": str(path.relative_to(data_root)),
                    "view_index": view,
                    "prediction_file": str(destination.relative_to(output_dir)),
                    "prediction_size_khw": list(shape),
                    "source_size_hw": list(image.shape[:2]),
                    "reused": reused,
                }
            )
        print(f"predicted scene {order + 1}/{len(files)}: {identifier}", flush=True)
        del data, rgb
        gc.collect()

    run_kind = (
        "full_tablewarenet_processed_test"
        if args.max_scenes is None and not args.scene_id
        else "debug_subset"
    )
    summary = {
        "run_kind": run_kind,
        "method": getattr(model, "method_name", type(model).__name__),
        "input_protocol": (
            "single RGB; LayeredDepth-Syn training only; direct synthetic-to-TablewareNet OOD transfer"
        ),
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256_file(checkpoint),
        "data_root": str(data_root),
        "device": str(device),
        "input_height": args.input_height,
        "prediction_space": "metric_axial_z_m",
        "output_contract": "four ordered depths + monotone presence + uncertainty",
        "scenes": len(files),
        "views": len(items),
        "reused_views": reused_views,
        "mean_inference_seconds_per_view": (
            float(np.mean(durations)) if durations else None
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps({"summary": summary, "items": items}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "metrics.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
