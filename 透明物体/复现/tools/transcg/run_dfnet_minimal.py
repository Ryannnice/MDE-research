#!/usr/bin/env python
"""Minimal, headless DFNet inference for TransCG reproduction.

This script intentionally does not modify the upstream TransCG repository.
It imports the official model code, loads the official checkpoint, and writes
depth outputs under runs/.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
import yaml
from PIL import Image
from scipy.interpolate import NearestNDInterpolator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="data/external/transcg/official")
    parser.add_argument("--config", default="data/external/transcg/official/configs/inference.yaml")
    parser.add_argument("--checkpoint", default="weights/transparent/transcg/checkpoint.tar")
    parser.add_argument("--out-dir", default="runs/transparent/transcg/minimal")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--rgb", default=None, help="Optional RGB image path.")
    parser.add_argument("--depth", default=None, help="Optional raw depth image path.")
    parser.add_argument("--gt", default=None, help="Optional ground-truth depth image path.")
    parser.add_argument("--depth-scale", type=float, default=1000.0, help="Input depth divisor for integer PNG depth.")
    parser.add_argument("--synthetic-width", type=int, default=640)
    parser.add_argument("--synthetic-height", type=int, default=480)
    return parser.parse_args()


def load_depth(path: str | Path, scale: float) -> np.ndarray:
    depth = np.asarray(Image.open(path), dtype=np.float32)
    if depth.max(initial=0.0) > 10.0:
        depth = depth / scale
    return depth


def make_synthetic_rgbd(width: int, height: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = np.linspace(0.0, 1.0, width, dtype=np.float32)
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)

    rgb = np.zeros((height, width, 3), dtype=np.float32)
    rgb[..., 0] = 80 + 100 * xx
    rgb[..., 1] = 90 + 120 * yy
    rgb[..., 2] = 150 + 80 * (1.0 - xx)

    gt_depth = 0.62 + 0.12 * xx + 0.05 * yy
    cx, cy = 0.52, 0.48
    radius = 0.18
    transparent_mask = (xx - cx) ** 2 + (yy - cy) ** 2 < radius**2
    raw_depth = gt_depth.copy()
    raw_depth[transparent_mask] = 0.0

    rgb[transparent_mask, 0] = 170
    rgb[transparent_mask, 1] = 220
    rgb[transparent_mask, 2] = 230
    return np.clip(rgb, 0, 255).astype(np.uint8), raw_depth.astype(np.float32), gt_depth.astype(np.float32)


def depth_to_u16_mm(depth_m: np.ndarray) -> np.ndarray:
    return np.clip(depth_m * 1000.0, 0, np.iinfo(np.uint16).max).astype(np.uint16)


def save_depth_vis(path: Path, depth_m: np.ndarray, vmin: float = 0.3, vmax: float = 1.0) -> None:
    denom = max(vmax - vmin, 1e-6)
    norm = np.clip((depth_m - vmin) / denom, 0.0, 1.0)
    image = (norm * 255).astype(np.uint8)
    color = cv2.applyColorMap(image, cv2.COLORMAP_TURBO)
    invalid = depth_m <= 0
    color[invalid] = (0, 0, 0)
    cv2.imwrite(str(path), color)


def official_preprocess(
    rgb: np.ndarray,
    depth: np.ndarray,
    image_size: tuple[int, int],
    depth_min: float,
    depth_max: float,
    depth_norm: float,
    depth_coefficient: float = 3.0,
    inpainting: bool = True,
) -> tuple[torch.Tensor, torch.Tensor, tuple[float, float]]:
    rgb_small = cv2.resize(rgb, image_size, interpolation=cv2.INTER_NEAREST)
    depth_small = cv2.resize(depth, image_size, interpolation=cv2.INTER_NEAREST)
    depth_small = np.where(depth_small < depth_min, 0, depth_small)
    depth_small = np.where(depth_small > depth_max, 0, depth_small)
    depth_small[np.isnan(depth_small)] = 0

    valid = depth_small[depth_small > 0]
    depth_mu = valid.mean() if valid.shape[0] != 0 else 0
    depth_std = valid.std() if valid.shape[0] != 0 else 1
    depth_small = np.where(depth_small < depth_mu - depth_coefficient * depth_std, 0, depth_small)
    depth_small = np.where(depth_small > depth_mu + depth_coefficient * depth_std, 0, depth_small)

    if inpainting:
        mask = np.where(depth_small > 0)
        if mask[0].shape[0] != 0:
            interp = NearestNDInterpolator(np.transpose(mask), depth_small[mask])
            depth_small = interp(*np.indices(depth_small.shape))

    depth_small = depth_small / depth_norm
    d_min = float(depth_small.min() - 0.5 * depth_small.std() - 1e-6)
    d_max = float(depth_small.max() + 0.5 * depth_small.std() + 1e-6)
    depth_small = (depth_small - d_min) / (d_max - d_min)

    rgb_tensor = torch.from_numpy((rgb_small / 255.0).transpose(2, 0, 1)).float().unsqueeze(0)
    depth_tensor = torch.from_numpy(depth_small).float().unsqueeze(0)
    return rgb_tensor, depth_tensor, (d_min, d_max)


def main() -> None:
    args = parse_args()
    repo = Path(args.repo)
    sys.path.insert(0, str(repo.resolve()))

    from utils.builder import ConfigBuilder  # pylint: disable=import-error,import-outside-toplevel

    config = yaml.load(open(args.config, "r", encoding="utf-8"), Loader=yaml.FullLoader)
    builder = ConfigBuilder(**config)
    model = builder.get_model()

    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    device = torch.device(args.device)
    model.to(device)

    if args.rgb and args.depth:
        rgb = np.asarray(Image.open(args.rgb).convert("RGB"), dtype=np.uint8)
        depth = load_depth(args.depth, args.depth_scale)
        gt = load_depth(args.gt, args.depth_scale) if args.gt else None
        source = "file"
    else:
        rgb, depth, gt = make_synthetic_rgbd(args.synthetic_width, args.synthetic_height)
        source = "synthetic"

    image_size = tuple(builder.get_inference_image_size())
    depth_min, depth_max = builder.get_inference_depth_min_max()
    depth_norm = builder.get_inference_depth_norm()
    rgb_tensor, depth_tensor, (d_min, d_max) = official_preprocess(
        rgb=rgb,
        depth=depth,
        image_size=image_size,
        depth_min=depth_min,
        depth_max=depth_max,
        depth_norm=depth_norm,
    )

    with torch.no_grad():
        pred = model(rgb_tensor.to(device), depth_tensor.to(device))

    pred_np = pred.squeeze(0).cpu().numpy()
    pred_np = pred_np * (d_max - d_min) + d_min
    pred_np = pred_np * depth_norm
    target_size = (rgb.shape[1], rgb.shape[0])
    pred_np = cv2.resize(pred_np, target_size, interpolation=cv2.INTER_NEAREST)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb).save(out_dir / "input_rgb.png")
    cv2.imwrite(str(out_dir / "input_depth_raw_mm.png"), depth_to_u16_mm(depth))
    cv2.imwrite(str(out_dir / "dfnet_depth_mm.png"), depth_to_u16_mm(pred_np))
    np.save(out_dir / "input_depth_raw_m.npy", depth)
    np.save(out_dir / "dfnet_depth_m.npy", pred_np)
    save_depth_vis(out_dir / "input_depth_raw_vis.png", depth, depth_min, depth_max)
    save_depth_vis(out_dir / "dfnet_depth_vis.png", pred_np, depth_min, depth_max)

    summary = {
        "source": source,
        "repo": str(repo),
        "checkpoint": str(args.checkpoint),
        "checkpoint_epoch": int(checkpoint.get("epoch", -1)),
        "input_shape_hwc": list(rgb.shape),
        "official_inference_size_wh": list(image_size),
        "depth_min_m": float(depth_min),
        "depth_max_m": float(depth_max),
        "raw_valid_ratio": float((depth > 0).mean()),
        "pred_min_m": float(pred_np.min()),
        "pred_max_m": float(pred_np.max()),
        "pred_mean_m": float(pred_np.mean()),
    }

    if gt is not None:
        np.save(out_dir / "gt_depth_m.npy", gt)
        cv2.imwrite(str(out_dir / "gt_depth_mm.png"), depth_to_u16_mm(gt))
        save_depth_vis(out_dir / "gt_depth_vis.png", gt, depth_min, depth_max)
        valid = gt > 0
        abs_err = np.abs(pred_np - gt)
        summary.update(
            {
                "gt_available": True,
                "mae_m": float(abs_err[valid].mean()) if valid.any() else None,
                "rmse_m": float(np.sqrt((abs_err[valid] ** 2).mean())) if valid.any() else None,
            }
        )
        save_depth_vis(out_dir / "abs_error_vis.png", abs_err, 0.0, 0.1)
    else:
        summary["gt_available"] = False

    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
