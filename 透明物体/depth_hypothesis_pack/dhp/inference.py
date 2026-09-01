"""Checkpoint loading and full-image inference helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.nn import functional as F

from .data import IMAGENET_MEAN, IMAGENET_STD
from .model import DepthHypothesisPackLite


def load_model(checkpoint_path: Path, device: torch.device) -> nn.Module:
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    config = dict(checkpoint["model_config"])
    config.setdefault("use_highres_refine", False)
    config.setdefault("encoder_name", "resnet18")
    # The checkpoint already contains every encoder tensor. Avoid network or
    # source-checkpoint dependencies while reconstructing the architecture.
    config["pretrained_encoder"] = False
    config["encoder_checkpoint"] = None
    model = DepthHypothesisPackLite(**config)
    model.load_state_dict(checkpoint["model"], strict=True)
    model.to(device).eval()
    return model


def prepare_image(
    image: Image.Image | np.ndarray,
    input_height: int,
) -> tuple[torch.Tensor, tuple[int, int]]:
    if isinstance(image, Image.Image):
        image = np.asarray(image.convert("RGB")).copy()
    else:
        image = np.asarray(image)
        if image.ndim != 3 or image.shape[2] not in (3, 4):
            raise ValueError(f"Expected HxWx3 RGB image, got {image.shape}")
        image = image[..., :3].astype(np.uint8, copy=False)
    original_hw = (int(image.shape[0]), int(image.shape[1]))
    input_width = max(32, int(round(image.shape[1] * input_height / image.shape[0] / 32)) * 32)
    resized = Image.fromarray(image).resize((input_width, input_height), Image.Resampling.BICUBIC)
    tensor = torch.from_numpy(np.asarray(resized).copy().transpose(2, 0, 1)).float() / 255.0
    tensor = (tensor - IMAGENET_MEAN) / IMAGENET_STD
    return tensor[None], original_hw


@torch.inference_mode()
def predict_image(
    model: nn.Module,
    image: Image.Image | np.ndarray,
    device: torch.device,
    input_height: int = 256,
) -> dict[str, np.ndarray]:
    tensor, original_hw = prepare_image(image, input_height)
    output = model(tensor.to(device))
    result: dict[str, np.ndarray] = {}
    for key in ("depth", "presence_probability", "uncertainty"):
        # Some LayeredDepth images exceed 10 MP. Upsampling all K hypotheses
        # at that resolution on a shared GPU can require hundreds of MiB even
        # though the model forward itself is small. Move the compact output to
        # CPU first; this preserves the interpolation contract and bounds GPU
        # memory by the network input size.
        value = F.interpolate(
            output[key].float().cpu(),
            size=original_hw,
            mode="bilinear",
            align_corners=False,
        )[0]
        result[key] = value.numpy()
    return result
