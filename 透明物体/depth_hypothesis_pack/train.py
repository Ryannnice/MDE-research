#!/usr/bin/env python3
"""Train the minimal ordered DepthHypothesisPack head."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import torch
from torch.nn.utils import clip_grad_norm_
from torch.utils.data import DataLoader

from dhp.data import LayeredDepthCacheDataset
from dhp.losses import DepthHypothesisLoss
from dhp.model import DepthHypothesisPackLite


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--crop-size", type=int, default=256)
    parser.add_argument("--decoder-channels", type=int, default=96)
    parser.add_argument(
        "--encoder",
        choices=("resnet18", "dinov2_small", "depth_anything_v2_small"),
        default="resnet18",
    )
    parser.add_argument(
        "--encoder-checkpoint",
        type=Path,
        help="Official Depth Anything V2-S checkpoint used only for initialization",
    )
    parser.add_argument(
        "--encoder-source-root",
        type=Path,
        help="Directory containing the official depth_anything_v2 Python package",
    )
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--encoder-learning-rate", type=float, default=1e-5)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--overfit-samples", type=int)
    parser.add_argument("--max-steps-per-epoch", type=int)
    parser.add_argument("--train-encoder", action="store_true")
    parser.add_argument(
        "--encoder-trainable-blocks",
        type=int,
        default=0,
        help="Fine-tune only the last N DINOv2 blocks (0 keeps them frozen)",
    )
    parser.add_argument("--no-pretrained-encoder", action="store_true")
    parser.add_argument("--resume", type=Path)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def split_indices(count: int, val_fraction: float, seed: int) -> tuple[list[int], list[int]]:
    if count < 2:
        raise ValueError("At least two cached samples are required")
    if not 0 < val_fraction < 1:
        raise ValueError("val_fraction must be in (0,1)")
    generator = np.random.default_rng(seed)
    indices = generator.permutation(count).tolist()
    val_count = max(1, int(round(count * val_fraction)))
    return indices[val_count:], indices[:val_count]


def batch_metrics(
    prediction: dict[str, torch.Tensor],
    depth: torch.Tensor,
    valid: torch.Tensor,
) -> dict[str, float]:
    predicted_valid = prediction["presence_probability"] >= 0.5
    true_positive = (predicted_valid & valid).sum().item()
    false_positive = (predicted_valid & ~valid).sum().item()
    false_negative = (~predicted_valid & valid).sum().item()
    valid_count = max(1, int(valid.sum().item()))
    absolute_error = torch.abs(prediction["depth"] - depth)
    result = {
        "absolute_error_sum": float((absolute_error * valid).sum().item()),
        "front_absolute_error_sum": float((absolute_error[:, :1] * valid[:, :1]).sum().item()),
        "valid_count": float(valid_count),
        "front_valid_count": float(max(1, int(valid[:, :1].sum().item()))),
        "true_positive": float(true_positive),
        "false_positive": float(false_positive),
        "false_negative": float(false_negative),
    }
    for layer in range(valid.shape[1]):
        layer_prediction = predicted_valid[:, layer]
        layer_target = valid[:, layer]
        result[f"layer_{layer + 1}_true_positive"] = float(
            (layer_prediction & layer_target).sum().item()
        )
        result[f"layer_{layer + 1}_false_positive"] = float(
            (layer_prediction & ~layer_target).sum().item()
        )
        result[f"layer_{layer + 1}_false_negative"] = float(
            (~layer_prediction & layer_target).sum().item()
        )
    return result


def reduce_metrics(sums: dict[str, float]) -> dict[str, float]:
    precision = sums["true_positive"] / max(
        1.0, sums["true_positive"] + sums["false_positive"]
    )
    recall = sums["true_positive"] / max(
        1.0, sums["true_positive"] + sums["false_negative"]
    )
    result = {
        "depth_mae_m": sums["absolute_error_sum"] / sums["valid_count"],
        "front_mae_m": sums["front_absolute_error_sum"] / sums["front_valid_count"],
        "presence_precision": precision,
        "presence_recall": recall,
        "presence_f1": 2.0 * precision * recall / max(1e-12, precision + recall),
    }
    for layer in range(1, 5):
        true_positive = sums[f"layer_{layer}_true_positive"]
        false_positive = sums[f"layer_{layer}_false_positive"]
        false_negative = sums[f"layer_{layer}_false_negative"]
        layer_precision = true_positive / max(1.0, true_positive + false_positive)
        layer_recall = true_positive / max(1.0, true_positive + false_negative)
        result[f"presence_layer_{layer}_precision"] = layer_precision
        result[f"presence_layer_{layer}_recall"] = layer_recall
        result[f"presence_layer_{layer}_f1"] = (
            2.0
            * layer_precision
            * layer_recall
            / max(1e-12, layer_precision + layer_recall)
        )
    return result


def move_batch(batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
    return {
        key: value.to(device, non_blocking=True) if torch.is_tensor(value) else value
        for key, value in batch.items()
    }


def evaluate(
    model: DepthHypothesisPackLite,
    criterion: DepthHypothesisLoss,
    loader: DataLoader,
    device: torch.device,
) -> dict[str, float]:
    model.eval()
    loss_total = 0.0
    batches = 0
    metric_keys = [
        "absolute_error_sum",
        "front_absolute_error_sum",
        "valid_count",
        "front_valid_count",
        "true_positive",
        "false_positive",
        "false_negative",
    ]
    for layer in range(1, 5):
        metric_keys.extend(
            [
                f"layer_{layer}_true_positive",
                f"layer_{layer}_false_positive",
                f"layer_{layer}_false_negative",
            ]
        )
    sums = {key: 0.0 for key in metric_keys}
    with torch.inference_mode():
        for batch in loader:
            batch = move_batch(batch, device)
            prediction = model(batch["image"])
            loss = criterion(prediction, batch["depth"], batch["valid_mask"])
            loss_total += float(loss["total"].item())
            batches += 1
            for key, value in batch_metrics(
                prediction, batch["depth"], batch["valid_mask"]
            ).items():
                sums[key] += value
    metrics = reduce_metrics(sums)
    metrics["loss"] = loss_total / max(1, batches)
    return metrics


def save_checkpoint(
    path: Path,
    model: DepthHypothesisPackLite,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    best_val_loss: float,
    args: argparse.Namespace,
) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(
        {
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "epoch": epoch,
            "best_val_loss": best_val_loss,
            "model_config": {
                "max_hypotheses": 4,
                "decoder_channels": args.decoder_channels,
                "encoder_name": args.encoder,
                "encoder_checkpoint": (
                    str(args.encoder_checkpoint.expanduser().resolve())
                    if args.encoder_checkpoint is not None
                    else None
                ),
                "encoder_source_root": (
                    str(args.encoder_source_root.expanduser().resolve())
                    if args.encoder_source_root is not None
                    else None
                ),
                "pretrained_encoder": not args.no_pretrained_encoder,
                "freeze_encoder": not args.train_encoder,
                "trainable_encoder_blocks": args.encoder_trainable_blocks,
                "use_highres_refine": True,
            },
        },
        temporary,
    )
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    seed_everything(args.seed)
    cache_dir = args.cache_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.epochs < 1 or args.batch_size < 1:
        raise ValueError("epochs and batch-size must be positive")
    if args.encoder_trainable_blocks < 0:
        raise ValueError("encoder-trainable-blocks must be non-negative")
    if args.train_encoder and args.encoder_trainable_blocks:
        raise ValueError(
            "Choose either --train-encoder or --encoder-trainable-blocks, not both"
        )
    if args.encoder_trainable_blocks and args.encoder not in (
        "dinov2_small",
        "depth_anything_v2_small",
    ):
        raise ValueError("encoder-trainable-blocks requires a DINOv2-based encoder")
    if args.encoder == "depth_anything_v2_small":
        if args.encoder_source_root is None:
            raise ValueError("Depth Anything V2-S requires --encoder-source-root")
        if not args.no_pretrained_encoder and args.encoder_checkpoint is None:
            raise ValueError(
                "Depth Anything V2-S requires --encoder-checkpoint unless "
                "--no-pretrained-encoder is set"
            )
    elif args.encoder_checkpoint is not None or args.encoder_source_root is not None:
        raise ValueError("encoder source arguments are only valid for Depth Anything V2-S")

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    cache_manifest_path = cache_dir / "manifest.json"
    cache_manifest = json.loads(cache_manifest_path.read_text(encoding="utf-8"))
    sample_count = int(cache_manifest["samples_count"])
    if args.overfit_samples is not None:
        if not 1 < args.overfit_samples <= sample_count:
            raise ValueError("overfit-samples must be between 2 and cache size")
        train_indices = list(range(args.overfit_samples))
        val_indices = list(train_indices)
        augment = False
        run_kind = "overfit"
    else:
        train_indices, val_indices = split_indices(sample_count, args.val_fraction, args.seed)
        augment = True
        run_kind = "pilot"

    train_dataset = LayeredDepthCacheDataset(
        cache_dir, train_indices, crop_size=args.crop_size, augment=augment
    )
    val_dataset = LayeredDepthCacheDataset(
        cache_dir, val_indices, crop_size=args.crop_size, augment=False
    )
    loader_kwargs = {
        "batch_size": args.batch_size,
        "num_workers": args.num_workers,
        "pin_memory": device.type == "cuda",
    }
    train_loader = DataLoader(train_dataset, shuffle=True, **loader_kwargs)
    val_loader = DataLoader(val_dataset, shuffle=False, **loader_kwargs)

    model = DepthHypothesisPackLite(
        decoder_channels=args.decoder_channels,
        encoder_name=args.encoder,
        pretrained_encoder=not args.no_pretrained_encoder,
        freeze_encoder=not args.train_encoder,
        trainable_encoder_blocks=args.encoder_trainable_blocks,
        encoder_checkpoint=args.encoder_checkpoint,
        encoder_source_root=args.encoder_source_root,
    ).to(device)
    criterion = DepthHypothesisLoss().to(device)
    decoder_parameters = [
        parameter
        for name, parameter in model.named_parameters()
        if parameter.requires_grad and not name.startswith("encoder.")
    ]
    parameter_groups: list[dict[str, Any]] = [
        {"params": decoder_parameters, "lr": args.learning_rate}
    ]
    trainable_encoder_parameters = [
        parameter for parameter in model.encoder.parameters() if parameter.requires_grad
    ]
    if trainable_encoder_parameters:
        parameter_groups.append(
            {
                "params": trainable_encoder_parameters,
                "lr": args.encoder_learning_rate,
            }
        )
    optimizer = torch.optim.AdamW(parameter_groups, weight_decay=args.weight_decay)
    start_epoch = 0
    best_val_loss = float("inf")
    if args.resume is not None:
        checkpoint = torch.load(args.resume, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        start_epoch = int(checkpoint["epoch"]) + 1
        best_val_loss = float(checkpoint["best_val_loss"])

    run_manifest = {
        "run_kind": run_kind,
        "cache_dir": str(cache_dir),
        "cache_manifest_sha256": sha256_file(cache_manifest_path),
        "cache_revision": cache_manifest["revision"],
        "train_indices": train_indices,
        "val_indices": val_indices,
        "evaluation_leakage": False,
        "args": vars(args),
    }
    if args.encoder_checkpoint is not None:
        encoder_checkpoint = args.encoder_checkpoint.expanduser().resolve()
        run_manifest["encoder_initialization"] = {
            "checkpoint": str(encoder_checkpoint),
            "checkpoint_sha256": sha256_file(encoder_checkpoint),
            "source_root": str(args.encoder_source_root.expanduser().resolve()),
        }
    run_manifest["args"] = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in run_manifest["args"].items()
    }
    (output_dir / "run_manifest.json").write_text(
        json.dumps(run_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    history_path = output_dir / "history.jsonl"
    start_time = perf_counter()
    best_record: dict[str, float] | None = None
    for epoch in range(start_epoch, args.epochs):
        model.train()
        train_loss = 0.0
        train_batches = 0
        for step, batch in enumerate(train_loader):
            if args.max_steps_per_epoch is not None and step >= args.max_steps_per_epoch:
                break
            batch = move_batch(batch, device)
            optimizer.zero_grad(set_to_none=True)
            prediction = model(batch["image"])
            loss = criterion(prediction, batch["depth"], batch["valid_mask"])
            loss["total"].backward()
            clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            train_loss += float(loss["total"].item())
            train_batches += 1

        validation = evaluate(model, criterion, val_loader, device)
        record = {
            "epoch": epoch,
            "train_loss": train_loss / max(1, train_batches),
            "elapsed_seconds": perf_counter() - start_time,
            **{f"val_{key}": value for key, value in validation.items()},
        }
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        print(json.dumps(record, sort_keys=True), flush=True)
        improved = validation["loss"] < best_val_loss
        if improved:
            best_val_loss = validation["loss"]
            best_record = record
        save_checkpoint(
            output_dir / "last.pt", model, optimizer, epoch, best_val_loss, args
        )
        if improved:
            save_checkpoint(
                output_dir / "best.pt", model, optimizer, epoch, best_val_loss, args
            )

    summary = {
        "run_kind": run_kind,
        "epochs_completed": args.epochs - start_epoch,
        "best_val_loss": best_val_loss,
        "best_validation": best_record,
        "best_checkpoint": "best.pt",
        "elapsed_seconds": perf_counter() - start_time,
        "device": str(device),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
