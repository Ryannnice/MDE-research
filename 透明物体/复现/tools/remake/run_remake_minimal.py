#!/usr/bin/env python
"""Minimal, headless ReMake inference.

This script verifies the ReMake core network and released checkpoint without
requiring the full TransCG dataset, Open3D, RealSense, SAM, or Depth Anything
weights. It supplies a synthetic relative-depth map to the ReMake model.
"""

from __future__ import annotations

import argparse
import json
import sys
import types
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="data/external/remake/official")
    parser.add_argument("--checkpoint", default="weights/transparent/remake/checkpoint.tar")
    parser.add_argument("--out-dir", default="runs/transparent/remake/minimal")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--rgb", default=None, help="Optional RGB image path.")
    parser.add_argument("--depth", default=None, help="Optional raw depth path.")
    parser.add_argument("--mask", default=None, help="Optional transparent mask path; nonzero means transparent.")
    parser.add_argument("--relative-depth", default=None, help="Optional relative depth path.")
    parser.add_argument("--gt", default=None, help="Optional GT depth path.")
    parser.add_argument("--depth-scale", type=float, default=1000.0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    return parser.parse_args()


def install_visualization_stub() -> None:
    """Avoid importing Open3D/pandas from the upstream visualization module."""

    module = types.ModuleType("utils.visualization")
    module.plot_realat_depth = lambda *args, **kwargs: None
    module.run_gradcam_on_encoder_img = lambda *args, **kwargs: None
    sys.modules["utils.visualization"] = module


def load_depth(path: str | Path, scale: float) -> np.ndarray:
    depth = np.asarray(Image.open(path), dtype=np.float32)
    if depth.max(initial=0.0) > 10.0:
        depth = depth / scale
    return depth.astype(np.float32)


def load_mask(path: str | Path) -> np.ndarray:
    mask = np.asarray(Image.open(path), dtype=np.float32)
    if mask.ndim == 3:
        mask = mask[..., 0]
    if mask.max(initial=0.0) > 1.0:
        mask = mask / 255.0
    return (mask > 0.5).astype(np.float32)


def make_synthetic_inputs(width: int, height: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x = np.linspace(0.0, 1.0, width, dtype=np.float32)
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)

    gt_depth = 0.58 + 0.20 * xx + 0.04 * yy
    relative_depth = (gt_depth - gt_depth.min()) / max(float(gt_depth.max() - gt_depth.min()), 1e-6)

    cx, cy = 0.52, 0.50
    mask = (((xx - cx) / 0.19) ** 2 + ((yy - cy) / 0.24) ** 2 < 1.0).astype(np.float32)

    raw_depth = gt_depth.copy()
    raw_depth[mask > 0] = 0.0

    rgb = np.zeros((height, width, 3), dtype=np.float32)
    rgb[..., 0] = 70 + 90 * xx
    rgb[..., 1] = 90 + 120 * yy
    rgb[..., 2] = 170 + 45 * (1.0 - yy)
    rgb[mask > 0, 0] = 155
    rgb[mask > 0, 1] = 220
    rgb[mask > 0, 2] = 235
    return np.clip(rgb, 0, 255).astype(np.uint8), raw_depth.astype(np.float32), mask, relative_depth.astype(np.float32), gt_depth.astype(np.float32)


def resize_inputs(
    rgb: np.ndarray,
    depth: np.ndarray,
    mask: np.ndarray,
    relative_depth: np.ndarray,
    size_wh: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rgb = cv2.resize(rgb, size_wh, interpolation=cv2.INTER_NEAREST)
    depth = cv2.resize(depth, size_wh, interpolation=cv2.INTER_NEAREST)
    mask = cv2.resize(mask, size_wh, interpolation=cv2.INTER_NEAREST)
    relative_depth = cv2.resize(relative_depth, size_wh, interpolation=cv2.INTER_NEAREST)
    return rgb, depth, mask, relative_depth


def depth_to_u16_mm(depth_m: np.ndarray) -> np.ndarray:
    return np.clip(depth_m * 1000.0, 0, np.iinfo(np.uint16).max).astype(np.uint16)


def save_depth_vis(path: Path, depth_m: np.ndarray, vmin: float = 0.3, vmax: float = 1.2) -> None:
    norm = np.clip((depth_m - vmin) / max(vmax - vmin, 1e-6), 0.0, 1.0)
    image = (norm * 255).astype(np.uint8)
    color = cv2.applyColorMap(image, cv2.COLORMAP_TURBO)
    color[depth_m <= 0] = (0, 0, 0)
    cv2.imwrite(str(path), color)


def main() -> None:
    args = parse_args()
    install_visualization_stub()
    sys.path.insert(0, str(Path(args.repo).resolve()))

    from models.remake import ReMake  # pylint: disable=import-error,import-outside-toplevel

    device = torch.device(args.device)
    model = ReMake(lambda_val=1, res=True)
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device).eval()

    if args.rgb and args.depth and args.mask:
        rgb = np.asarray(Image.open(args.rgb).convert("RGB"), dtype=np.uint8)
        depth = load_depth(args.depth, args.depth_scale)
        mask = load_mask(args.mask)
        if args.relative_depth:
            relative_depth = load_depth(args.relative_depth, args.depth_scale)
        else:
            valid = depth > 0
            relative_depth = depth.copy()
            if valid.any():
                relative_depth = (relative_depth - relative_depth[valid].min()) / max(float(np.ptp(relative_depth[valid])), 1e-6)
            relative_depth[~valid] = relative_depth[valid].mean() if valid.any() else 0.5
        gt = load_depth(args.gt, args.depth_scale) if args.gt else None
        source = "file"
    else:
        rgb, depth, mask, relative_depth, gt = make_synthetic_inputs(args.width, args.height)
        source = "synthetic"

    rgb_net, depth_net, mask_net, rel_net = resize_inputs(rgb, depth, mask, relative_depth, (640, 480))
    rgb_tensor = torch.from_numpy((rgb_net / 255.0).transpose(2, 0, 1)).float().unsqueeze(0).to(device)
    depth_tensor = torch.from_numpy(depth_net).float().unsqueeze(0).to(device)
    mask_tensor = torch.from_numpy(mask_net).float().unsqueeze(0).to(device)
    rel_tensor = torch.from_numpy(rel_net).float().unsqueeze(0).unsqueeze(0).to(device)

    with torch.no_grad():
        pred = model(rgb_tensor, rel_tensor, depth_tensor, mask_tensor)

    pred_np = pred.squeeze(0).squeeze(0).cpu().numpy()
    pred_np = cv2.resize(pred_np, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_NEAREST)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb).save(out_dir / "input_rgb.png")
    cv2.imwrite(str(out_dir / "input_depth_raw_mm.png"), depth_to_u16_mm(depth))
    cv2.imwrite(str(out_dir / "input_mask.png"), (mask * 255).astype(np.uint8))
    cv2.imwrite(str(out_dir / "input_relative_depth_u16.png"), depth_to_u16_mm(relative_depth))
    cv2.imwrite(str(out_dir / "remake_depth_mm.png"), depth_to_u16_mm(pred_np))
    np.save(out_dir / "input_depth_raw_m.npy", depth)
    np.save(out_dir / "input_mask.npy", mask)
    np.save(out_dir / "input_relative_depth.npy", relative_depth)
    np.save(out_dir / "remake_depth_m.npy", pred_np)
    save_depth_vis(out_dir / "input_depth_raw_vis.png", depth)
    save_depth_vis(out_dir / "input_relative_depth_vis.png", relative_depth, 0.0, 1.0)
    save_depth_vis(out_dir / "remake_depth_vis.png", pred_np)

    summary = {
        "source": source,
        "repo": args.repo,
        "checkpoint": args.checkpoint,
        "checkpoint_epoch": int(checkpoint.get("epoch", -1)),
        "input_shape_hwc": list(rgb.shape),
        "network_size_wh": [640, 480],
        "raw_valid_ratio": float((depth > 0).mean()),
        "mask_ratio": float((mask > 0).mean()),
        "pred_min_m": float(pred_np.min()),
        "pred_max_m": float(pred_np.max()),
        "pred_mean_m": float(pred_np.mean()),
        "uses_depthanything": False,
        "note": "Synthetic relative depth is used in this minimal smoke test; this is not an official benchmark result.",
    }

    if gt is not None:
        np.save(out_dir / "gt_depth_m.npy", gt)
        cv2.imwrite(str(out_dir / "gt_depth_mm.png"), depth_to_u16_mm(gt))
        save_depth_vis(out_dir / "gt_depth_vis.png", gt)
        valid = gt > 0
        abs_err = np.abs(pred_np - gt)
        summary.update(
            {
                "gt_available": True,
                "mae_m": float(abs_err[valid].mean()) if valid.any() else None,
                "rmse_m": float(np.sqrt((abs_err[valid] ** 2).mean())) if valid.any() else None,
            }
        )
        save_depth_vis(out_dir / "abs_error_vis.png", abs_err, 0.0, 0.5)
    else:
        summary["gt_available"] = False

    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
