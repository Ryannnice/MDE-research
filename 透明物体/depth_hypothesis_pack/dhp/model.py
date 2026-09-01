"""A small ordered multi-depth head used to test the representation gate."""

from __future__ import annotations

import math
import sys
from importlib import import_module
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F
from torchvision.models import ResNet18_Weights, resnet18


def inverse_softplus(value: float) -> float:
    return math.log(math.expm1(value))


class ResNet18Pyramid(nn.Module):
    def __init__(self, pretrained: bool = True) -> None:
        super().__init__()
        weights = ResNet18_Weights.DEFAULT if pretrained else None
        network = resnet18(weights=weights)
        self.stem = nn.Sequential(network.conv1, network.bn1, network.relu, network.maxpool)
        self.layer1 = network.layer1
        self.layer2 = network.layer2
        self.layer3 = network.layer3
        self.layer4 = network.layer4

    def forward(self, image: torch.Tensor) -> tuple[torch.Tensor, ...]:
        x = self.stem(image)
        layer1 = self.layer1(x)
        layer2 = self.layer2(layer1)
        layer3 = self.layer3(layer2)
        layer4 = self.layer4(layer3)
        return layer1, layer2, layer3, layer4


class DinoV2SmallPyramid(nn.Module):
    """Frozen-friendly four-level pyramid from official DINOv2-S/14 tokens."""

    model_name = "facebook/dinov2-small"
    hidden_state_indices = (3, 6, 9, 12)
    out_channels = 384

    def __init__(self, pretrained: bool = True) -> None:
        super().__init__()
        from transformers import Dinov2Config, Dinov2Model

        if pretrained:
            self.network = Dinov2Model.from_pretrained(self.model_name)
        else:
            self.network = Dinov2Model(
                Dinov2Config(
                    hidden_size=384,
                    num_hidden_layers=12,
                    num_attention_heads=6,
                    mlp_ratio=4,
                    patch_size=14,
                    image_size=518,
                    layerscale_value=1.0,
                    use_swiglu_ffn=False,
                    apply_layernorm=True,
                )
            )
        self.patch_size = int(self.network.config.patch_size)

    def forward(self, image: torch.Tensor) -> tuple[torch.Tensor, ...]:
        height, width = image.shape[-2:]
        padded_height = math.ceil(height / self.patch_size) * self.patch_size
        padded_width = math.ceil(width / self.patch_size) * self.patch_size
        padded = F.pad(image, (0, padded_width - width, 0, padded_height - height))
        output = self.network(pixel_values=padded, output_hidden_states=True)
        assert output.hidden_states is not None
        grid_height = padded_height // self.patch_size
        grid_width = padded_width // self.patch_size
        features = []
        for index in self.hidden_state_indices:
            tokens = self.network.layernorm(output.hidden_states[index])[:, 1:]
            features.append(
                tokens.transpose(1, 2).reshape(
                    image.shape[0], self.out_channels, grid_height, grid_width
                )
            )
        layer1 = F.interpolate(
            features[0],
            size=(grid_height * 4, grid_width * 4),
            mode="bilinear",
            align_corners=False,
        )
        layer2 = F.interpolate(
            features[1],
            size=(grid_height * 2, grid_width * 2),
            mode="bilinear",
            align_corners=False,
        )
        layer3 = features[2]
        layer4 = F.interpolate(
            features[3],
            size=(max(1, grid_height // 2), max(1, grid_width // 2)),
            mode="area",
        )
        return layer1, layer2, layer3, layer4


class DepthAnythingV2SmallPyramid(nn.Module):
    """Pyramid from the official DA-V2 DINO code and relative-depth weights."""

    hidden_layer_indices = (2, 5, 8, 11)
    out_channels = 384

    def __init__(
        self,
        source_root: str | Path,
        pretrained: bool = True,
        checkpoint_path: str | Path | None = None,
    ) -> None:
        super().__init__()
        source_root = Path(source_root).expanduser().resolve()
        expected_module = source_root / "depth_anything_v2" / "dinov2.py"
        if not expected_module.is_file():
            raise FileNotFoundError(f"Missing official Depth Anything source: {expected_module}")
        sys.path.insert(0, str(source_root))
        module = import_module("depth_anything_v2.dinov2")
        if Path(module.__file__).resolve() != expected_module:
            raise ImportError(
                "depth_anything_v2 was already imported from a different source: "
                f"{module.__file__}"
            )
        self.network = module.DINOv2(model_name="vits")
        self.patch_size = 14
        if pretrained:
            if checkpoint_path is None:
                raise ValueError(
                    "Depth Anything V2-S initialization requires encoder_checkpoint"
                )
            payload = torch.load(
                Path(checkpoint_path).expanduser().resolve(),
                map_location="cpu",
                weights_only=True,
            )
            state = {
                str(key)[len("pretrained.") :]: value
                for key, value in payload.items()
                if str(key).startswith("pretrained.")
            }
            self.network.load_state_dict(state, strict=True)

    def forward(self, image: torch.Tensor) -> tuple[torch.Tensor, ...]:
        height, width = image.shape[-2:]
        padded_height = math.ceil(height / self.patch_size) * self.patch_size
        padded_width = math.ceil(width / self.patch_size) * self.patch_size
        padded = F.pad(image, (0, padded_width - width, 0, padded_height - height))
        outputs = self.network.get_intermediate_layers(
            padded,
            self.hidden_layer_indices,
            return_class_token=True,
        )
        grid_height = padded_height // self.patch_size
        grid_width = padded_width // self.patch_size
        features = [
            tokens.transpose(1, 2).reshape(
                image.shape[0], self.out_channels, grid_height, grid_width
            )
            for tokens, _ in outputs
        ]
        return (
            F.interpolate(
                features[0],
                size=(grid_height * 4, grid_width * 4),
                mode="bilinear",
                align_corners=False,
            ),
            F.interpolate(
                features[1],
                size=(grid_height * 2, grid_width * 2),
                mode="bilinear",
                align_corners=False,
            ),
            features[2],
            F.interpolate(
                features[3],
                size=(max(1, grid_height // 2), max(1, grid_width // 2)),
                mode="area",
            ),
        )


class DepthHypothesisPackLite(nn.Module):
    """Predict ordered metric depths, monotone presence, and uncertainty."""

    def __init__(
        self,
        max_hypotheses: int = 4,
        decoder_channels: int = 96,
        encoder_name: str = "resnet18",
        pretrained_encoder: bool = True,
        freeze_encoder: bool = True,
        trainable_encoder_blocks: int = 0,
        encoder_checkpoint: str | Path | None = None,
        encoder_source_root: str | Path | None = None,
        min_depth_m: float = 0.02,
        min_gap_m: float = 0.005,
        min_uncertainty_m: float = 0.002,
        use_highres_refine: bool = True,
    ) -> None:
        super().__init__()
        if max_hypotheses < 1:
            raise ValueError("max_hypotheses must be positive")
        self.max_hypotheses = int(max_hypotheses)
        self.min_depth_m = float(min_depth_m)
        self.min_gap_m = float(min_gap_m)
        self.min_uncertainty_m = float(min_uncertainty_m)
        self.encoder_name = str(encoder_name)
        self.encoder_checkpoint = (
            str(Path(encoder_checkpoint).expanduser().resolve())
            if encoder_checkpoint is not None
            else None
        )
        self.encoder_source_root = (
            str(Path(encoder_source_root).expanduser().resolve())
            if encoder_source_root is not None
            else None
        )
        self.trainable_encoder_blocks = int(trainable_encoder_blocks)
        if self.trainable_encoder_blocks < 0:
            raise ValueError("trainable_encoder_blocks must be non-negative")
        if not freeze_encoder and self.trainable_encoder_blocks:
            raise ValueError(
                "Choose either the full encoder or the last encoder blocks to train"
            )
        self.encoder_frozen = bool(freeze_encoder)
        self.use_highres_refine = bool(use_highres_refine)

        if self.encoder_name == "resnet18":
            if self.encoder_checkpoint is not None or self.encoder_source_root is not None:
                raise ValueError("encoder source arguments are only used by Depth Anything V2")
            self.encoder = ResNet18Pyramid(pretrained=pretrained_encoder)
            lateral_channels = (64, 128, 256, 512)
            self.model_name = "DepthHypothesisPackLite"
            self.method_name = "DepthHypothesisPackLite_v0"
        elif self.encoder_name == "dinov2_small":
            if self.encoder_checkpoint is not None or self.encoder_source_root is not None:
                raise ValueError("encoder source arguments are only used by Depth Anything V2")
            self.encoder = DinoV2SmallPyramid(pretrained=pretrained_encoder)
            lateral_channels = (384, 384, 384, 384)
            if self.trainable_encoder_blocks:
                suffix = f"FT{self.trainable_encoder_blocks}"
                self.model_name = f"DepthHypothesisPackDINOv2S{suffix}"
                self.method_name = f"DepthHypothesisPackDINOv2S{suffix}_v1"
            else:
                self.model_name = "DepthHypothesisPackDINOv2S"
                self.method_name = "DepthHypothesisPackDINOv2S_v1"
        elif self.encoder_name == "depth_anything_v2_small":
            if self.encoder_source_root is None:
                raise ValueError("Depth Anything V2-S requires encoder_source_root")
            self.encoder = DepthAnythingV2SmallPyramid(
                source_root=self.encoder_source_root,
                pretrained=pretrained_encoder,
                checkpoint_path=self.encoder_checkpoint,
            )
            lateral_channels = (384, 384, 384, 384)
            if self.trainable_encoder_blocks:
                suffix = f"FT{self.trainable_encoder_blocks}"
                self.model_name = f"DepthHypothesisPackDAV2S{suffix}"
                self.method_name = f"DepthHypothesisPackDAV2S{suffix}_v1"
            else:
                self.model_name = "DepthHypothesisPackDAV2S"
                self.method_name = "DepthHypothesisPackDAV2S_v1"
        else:
            raise ValueError(f"Unsupported encoder_name: {self.encoder_name!r}")
        self.lateral = nn.ModuleList(
            nn.Conv2d(channels, decoder_channels, kernel_size=1)
            for channels in lateral_channels
        )
        self.smooth = nn.ModuleList(
            nn.Sequential(
                nn.Conv2d(decoder_channels, decoder_channels, kernel_size=3, padding=1),
                nn.GroupNorm(8, decoder_channels),
                nn.ReLU(inplace=True),
            )
            for _ in range(3)
        )
        self.highres_refine = (
            nn.Sequential(
                nn.Conv2d(decoder_channels + 3, decoder_channels, kernel_size=3, padding=1),
                nn.GroupNorm(8, decoder_channels),
                nn.ReLU(inplace=True),
            )
            if self.use_highres_refine
            else nn.Identity()
        )
        self.output = nn.Sequential(
            nn.Conv2d(decoder_channels, decoder_channels, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(decoder_channels, self.max_hypotheses * 3, kernel_size=1),
        )
        self._initialize_output_biases()
        self.set_encoder_trainable(not freeze_encoder)
        if self.trainable_encoder_blocks:
            self.set_dinov2_trainable_blocks(self.trainable_encoder_blocks)

    def _initialize_output_biases(self) -> None:
        final = self.output[-1]
        assert isinstance(final, nn.Conv2d)
        with torch.no_grad():
            final.weight.zero_()
            depth_bias = [inverse_softplus(2.0 - self.min_depth_m)]
            depth_bias.extend(
                [inverse_softplus(0.12 - self.min_gap_m)]
                * (self.max_hypotheses - 1)
            )
            presence_bias = [3.0] + [-0.5] * (self.max_hypotheses - 1)
            uncertainty_bias = [
                inverse_softplus(0.10 - self.min_uncertainty_m)
            ] * self.max_hypotheses
            final.bias.copy_(
                torch.tensor(depth_bias + presence_bias + uncertainty_bias)
            )

    def set_encoder_trainable(self, trainable: bool) -> None:
        self.encoder_frozen = not trainable
        for parameter in self.encoder.parameters():
            parameter.requires_grad = trainable

    def set_dinov2_trainable_blocks(self, blocks: int) -> None:
        if self.encoder_name not in ("dinov2_small", "depth_anything_v2_small"):
            raise ValueError("Partial block tuning requires a DINOv2-based encoder")
        layers = (
            self.encoder.network.blocks
            if self.encoder_name == "depth_anything_v2_small"
            else self.encoder.network.encoder.layer
        )
        if not 1 <= blocks <= len(layers):
            raise ValueError(f"blocks must be between 1 and {len(layers)}")
        self.set_encoder_trainable(False)
        for layer in layers[-blocks:]:
            for parameter in layer.parameters():
                parameter.requires_grad = True
        final_norm = (
            self.encoder.network.norm
            if self.encoder_name == "depth_anything_v2_small"
            else self.encoder.network.layernorm
        )
        for parameter in final_norm.parameters():
            parameter.requires_grad = True
        self.encoder_frozen = False

    def train(self, mode: bool = True) -> "DepthHypothesisPackLite":
        super().train(mode)
        if self.encoder_frozen:
            self.encoder.eval()
        return self

    def _decode(self, features: tuple[torch.Tensor, ...]) -> torch.Tensor:
        layer1, layer2, layer3, layer4 = features
        pyramid = self.lateral[3](layer4)
        outputs = [layer3, layer2, layer1]
        for index, feature in enumerate(outputs):
            pyramid = F.interpolate(
                pyramid,
                size=feature.shape[-2:],
                mode="bilinear",
                align_corners=False,
            )
            pyramid = self.smooth[index](pyramid + self.lateral[2 - index](feature))
        return pyramid

    def forward(self, image: torch.Tensor) -> dict[str, torch.Tensor]:
        output_size = image.shape[-2:]
        features = self.encoder(image)
        decoded = self._decode(features)
        decoded = F.interpolate(
            decoded,
            size=output_size,
            mode="bilinear",
            align_corners=False,
        )
        if self.use_highres_refine:
            decoded = self.highres_refine(torch.cat([decoded, image], dim=1))
        raw = self.output(decoded)
        depth_raw, presence_logits, uncertainty_raw = torch.split(
            raw,
            self.max_hypotheses,
            dim=1,
        )

        front = self.min_depth_m + F.softplus(depth_raw[:, :1])
        if self.max_hypotheses > 1:
            gaps = self.min_gap_m + F.softplus(depth_raw[:, 1:])
            depth = torch.cat([front, front + torch.cumsum(gaps, dim=1)], dim=1)
        else:
            depth = front

        gate_probability = torch.sigmoid(presence_logits)
        presence_probability = torch.cumprod(gate_probability, dim=1)
        uncertainty = self.min_uncertainty_m + F.softplus(uncertainty_raw)
        return {
            "depth": depth,
            "presence_probability": presence_probability,
            "presence_logits": presence_logits,
            "uncertainty": uncertainty,
        }
