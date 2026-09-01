"""Local LayeredDepth-Syn cache loading and target canonicalization."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import Dataset


IMAGENET_MEAN = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float32)[:, None, None]
IMAGENET_STD = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float32)[:, None, None]


def collapse_missing_front_layers(depth: np.ndarray) -> np.ndarray:
    """Match the released SeeGroup LayeredDepth-Syn missing-layer policy."""

    result = np.asarray(depth).copy()
    if result.ndim != 3:
        raise ValueError(f"Expected KxHxW depth, got {result.shape}")
    for current_layer in range(1, result.shape[0]):
        for target_layer in range(current_layer):
            valid_current = result[current_layer] > 0
            valid_target = result[target_layer] > 0
            collapse = valid_current & ~valid_target
            result[target_layer][collapse] = result[current_layer][collapse]
            result[current_layer][collapse] = 0
    return result


def sort_valid_depths(depth: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Sort present metric depths per pixel and move missing layers to the end."""

    depth = np.asarray(depth, dtype=np.float32)
    if depth.ndim != 3:
        raise ValueError(f"Expected KxHxW depth, got {depth.shape}")
    valid = np.isfinite(depth) & (depth > 0)
    sortable = np.where(valid, depth, np.inf)
    sorted_depth = np.sort(sortable, axis=0)
    sorted_valid = np.isfinite(sorted_depth)
    sorted_depth = np.where(sorted_valid, sorted_depth, 0).astype(np.float32)
    return sorted_depth, sorted_valid


def load_cache_manifest(cache_dir: Path) -> dict[str, Any]:
    manifest_path = cache_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing cache manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("dataset") != "princeton-vl/LayeredDepth-Syn":
        raise ValueError(f"Unexpected cache dataset in {manifest_path}")
    if manifest.get("depth_fields") != [
        "depth_1.png",
        "depth_3.png",
        "depth_5.png",
        "depth_7.png",
    ]:
        raise ValueError(f"Unexpected depth field contract in {manifest_path}")
    return manifest


class LayeredDepthCacheDataset(Dataset):
    def __init__(
        self,
        cache_dir: Path,
        indices: list[int] | None = None,
        crop_size: int = 256,
        augment: bool = True,
    ) -> None:
        self.cache_dir = cache_dir.expanduser().resolve()
        self.manifest = load_cache_manifest(self.cache_dir)
        self.samples = list(self.manifest["samples"])
        if indices is not None:
            self.samples = [self.samples[index] for index in indices]
        if not self.samples:
            raise ValueError("LayeredDepth cache selection is empty")
        self.crop_size = int(crop_size)
        self.augment = bool(augment)
        if self.crop_size <= 0:
            raise ValueError("crop_size must be positive")

    def __len__(self) -> int:
        return len(self.samples)

    def _crop(self, image: np.ndarray, depth: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        height, width = image.shape[:2]
        if height < self.crop_size or width < self.crop_size:
            raise ValueError(
                f"Cached sample {image.shape} is smaller than crop_size={self.crop_size}"
            )
        if self.augment:
            top = random.randint(0, height - self.crop_size)
            left = random.randint(0, width - self.crop_size)
        else:
            top = (height - self.crop_size) // 2
            left = (width - self.crop_size) // 2
        image = image[top : top + self.crop_size, left : left + self.crop_size]
        depth = depth[:, top : top + self.crop_size, left : left + self.crop_size]
        if self.augment and random.random() < 0.5:
            image = image[:, ::-1]
            depth = depth[:, :, ::-1]
        return np.ascontiguousarray(image), np.ascontiguousarray(depth)

    def __getitem__(self, index: int) -> dict[str, Any]:
        entry = self.samples[index]
        path = self.cache_dir / entry["file"]
        with np.load(path) as payload:
            image = payload["image"].astype(np.uint8, copy=False)
            depth_mm = payload["depth_mm"].astype(np.float32, copy=False)
            key = str(payload["key"].item())
        depth_mm = collapse_missing_front_layers(depth_mm)
        depth_m, valid = sort_valid_depths(depth_mm / 1000.0)
        image, depth_m = self._crop(image, depth_m)
        _, valid = sort_valid_depths(depth_m)

        image_tensor = torch.from_numpy(image.transpose(2, 0, 1)).float() / 255.0
        image_tensor = (image_tensor - IMAGENET_MEAN) / IMAGENET_STD
        depth_tensor = torch.from_numpy(depth_m)
        valid_tensor = torch.from_numpy(valid)
        return {
            "key": key,
            "image": image_tensor,
            "depth": depth_tensor,
            "valid_mask": valid_tensor,
        }
