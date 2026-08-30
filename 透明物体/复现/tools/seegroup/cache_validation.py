#!/usr/bin/env python3
"""Cache SeeGroup teacher predictions for LayeredDepth validation images."""

from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile
from pathlib import Path


TARGET_LAYERS = (1, 3, 5, 7)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-root", type=Path, required=True)
    parser.add_argument("--checkpoint-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument(
        "--local-validation-dir",
        type=Path,
        default=None,
        help="Optional directory containing validation-*.parquet for offline input.",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Skip this many validation samples before caching a shard.",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Maximum number of samples to process after --start-index.",
    )
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Recompute samples whose NPZ cache already exists.",
    )
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Do not load the model; require every requested NPZ to be reusable.",
    )
    return parser.parse_args()


def normalized_index(value, fallback: int) -> str:
    if isinstance(value, (list, tuple)):
        value = value[0] if value else fallback
    if hasattr(value, "numel"):
        value = value.flatten()[0].item() if value.numel() else fallback
    text = str(value)
    return str(int(text)) if text.isdigit() else text.replace(os.sep, "_")


def main() -> None:
    args = parse_args()
    if args.start_index < 0:
        raise ValueError("--start-index must be non-negative")
    if args.max_samples is not None and args.max_samples <= 0:
        raise ValueError("--max-samples must be positive")
    if args.cache_only and args.overwrite:
        raise ValueError("--cache-only and --overwrite are mutually exclusive")
    official_root = args.official_root.expanduser().resolve()
    checkpoint_path = args.checkpoint_path.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Missing checkpoint: {checkpoint_path}")
    sys.path.insert(0, official_root.as_posix())

    import numpy as np
    import torch
    from torch.utils.data import DataLoader
    from tqdm import tqdm

    from dataset import (
        MetricTracker,
        StreamingDatasetAdapter,
        collate_bypass_tuples,
        model_forward_unscale,
    )
    from dataset.layereddepth import (
        LayeredDepth,
        get_is_fake,
        get_layer_name,
        layereddepth_tuple_correct,
    )
    from model import init_model
    from util.config import get_config_from_path
    from util.train import to_cuda

    model = None
    if not args.cache_only:
        config = get_config_from_path(
            (official_root / "config" / "val.py").as_posix()
        )
        config["local_rank"] = 0
        config["rank"] = 0
        config["cli"] = "val"
        config["resumed_from"] = checkpoint_path.as_posix()
        model = init_model(config)
        model.eval()

    dataset_class = LayeredDepth
    if args.local_validation_dir is not None:
        from datasets import load_dataset

        parquet_files = sorted(
            args.local_validation_dir.expanduser().resolve().glob(
                "validation-*.parquet"
            )
        )
        if not parquet_files:
            raise FileNotFoundError(
                f"No validation parquet files in {args.local_validation_dir}"
            )
        local_data_files = [path.as_posix() for path in parquet_files]

        class LocalLayeredDepth(LayeredDepth):
            def _load_hf_dataset(self):
                return load_dataset(
                    "parquet",
                    data_files={"validation": local_data_files},
                    split="validation",
                    streaming=True,
                )

        dataset_class = LocalLayeredDepth

    dataset = dataset_class(
        mode="val",
        hf_dataset="princeton-vl/LayeredDepth",
        hf_split="validation",
        streaming=True,
        cache_dir=args.cache_dir.as_posix() if args.cache_dir else None,
        tuple_layer="layer_all",
        num_examples=300,
    )
    loader = DataLoader(
        StreamingDatasetAdapter(dataset),
        batch_size=1,
        pin_memory=True,
        num_workers=args.num_workers,
        collate_fn=collate_bypass_tuples,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    metric_tracker = MetricTracker()

    def record_metrics(sample, layers_np, valid_np) -> None:
        for tuple_name in ("pairs", "trips", "quads"):
            if tuple_name not in sample or not sample[tuple_name]:
                continue
            for single_tuple in sample[tuple_name][0]:
                correctness = int(
                    layereddepth_tuple_correct(
                        single_tuple,
                        layers_np,
                        valid_np,
                    )
                )
                layer = get_layer_name(single_tuple)
                is_fake = get_is_fake(single_tuple)
                metric_tracker.update({f"{tuple_name}/acc": correctness})
                metric_tracker.update({f"{tuple_name}/{layer}": correctness})
                validity = "fake" if is_fake else "real"
                metric_tracker.update({f"{tuple_name}/{validity}": correctness})
                metric_tracker.update(
                    {f"{tuple_name}/{layer}_{validity}": correctness}
                )

    with torch.no_grad():
        for batch_index, sample in enumerate(tqdm(loader, unit="sample")):
            if batch_index < args.start_index:
                continue
            if (
                args.max_samples is not None
                and batch_index >= args.start_index + args.max_samples
            ):
                break
            index = normalized_index(sample.get("index"), batch_index)
            destination = output_dir / f"{index}.npz"

            if destination.is_file() and not args.overwrite:
                try:
                    with np.load(destination) as payload:
                        layers_np = payload["layers_m"].astype(np.float32)
                        valid_np = payload["valid_mask"].astype(bool)
                except (
                    EOFError,
                    KeyError,
                    OSError,
                    ValueError,
                    zipfile.BadZipFile,
                ) as error:
                    print(
                        f"Recomputing unreadable cache {destination}: {error}",
                        file=sys.stderr,
                    )
                else:
                    if layers_np.shape != valid_np.shape or layers_np.ndim != 3:
                        raise ValueError(
                            f"Invalid existing cache shapes at {destination}: "
                            f"{layers_np.shape}, {valid_np.shape}"
                        )
                    record_metrics(sample, layers_np, valid_np)
                    manifest.append(
                        {
                            "sample_id": index,
                            "path": destination.name,
                            "shape": list(layers_np.shape),
                            "valid_ratio": float(valid_np.mean()),
                            "reused": True,
                        }
                    )
                    continue

            if args.cache_only:
                raise FileNotFoundError(
                    f"--cache-only requires a readable cache for validation sample {index}: "
                    f"{destination}"
                )
            assert model is not None
            sample = to_cuda(sample)
            result = model_forward_unscale(model, {"image": sample["image"]})

            raw_depth = result["depth"][0]
            raw_valid = result["valid_mask"][0] > 0.01
            sort_source = raw_depth.masked_fill(~raw_valid, float("inf"))
            layers, order = sort_source.sort(dim=0)
            valid_mask = torch.gather(raw_valid, 0, order)
            layers = layers.masked_fill(~valid_mask, 0)

            beta = result.get("b1")
            if beta is not None:
                beta = torch.gather(beta[0], 0, order)
                beta = beta.masked_fill(~valid_mask, 0)

            layers_np = layers.detach().cpu().numpy().astype(np.float32)
            valid_np = valid_mask.detach().cpu().numpy().astype(bool)
            record_metrics(sample, layers_np, valid_np)
            temporary = destination.with_suffix(".npz.tmp")
            with temporary.open("wb") as handle:
                np.savez_compressed(
                    handle,
                    layers_m=layers_np,
                    valid_mask=valid_np,
                    beta=(
                        beta.detach().cpu().numpy().astype(np.float32)
                        if beta is not None
                        else np.empty((0,), dtype=np.float32)
                    ),
                    layer_labels=np.asarray(TARGET_LAYERS, dtype=np.int8),
                )
            temporary.replace(destination)
            manifest.append(
                {
                    "sample_id": index,
                    "path": destination.name,
                    "shape": list(layers.shape),
                    "valid_ratio": float(valid_mask.float().mean().item()),
                    "reused": False,
                }
            )

    manifest_path = output_dir / "manifest.json"
    metrics = metric_tracker.get_average()
    metrics_path = output_dir / "metrics_layer_all.json"
    metrics_path.write_text(
        json.dumps(
            {
                "method": "SeeGroup",
                "checkpoint": checkpoint_path.as_posix(),
                "dataset": "princeton-vl/LayeredDepth",
                "dataset_source": (
                    args.local_validation_dir.expanduser().resolve().as_posix()
                    if args.local_validation_dir is not None
                    else "princeton-vl/LayeredDepth"
                ),
                "split": "validation",
                "subset": "layer_all",
                "start_index": args.start_index,
                "cache_only": args.cache_only,
                "samples": len(manifest),
                "metrics": metrics,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "method": "SeeGroup",
                "checkpoint": checkpoint_path.as_posix(),
                "start_index": args.start_index,
                "cache_only": args.cache_only,
                "samples": len(manifest),
                "metrics": metrics_path.name,
                "items": manifest,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Cached {len(manifest)} samples in {output_dir}")


if __name__ == "__main__":
    main()
