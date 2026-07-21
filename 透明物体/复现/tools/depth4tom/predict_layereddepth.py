#!/usr/bin/env python3
"""Run a Depth4ToM monocular checkpoint on LayeredDepth validation images.

Outputs one inverse-depth hypothesis per image using the LayeredDepth odd-layer
naming convention: ``<sample_id>_1.npy``.
"""

from __future__ import annotations

import argparse
import json
import sys
from itertools import islice
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-root", type=Path, required=True)
    parser.add_argument("--checkpoint-path", type=Path, required=True)
    parser.add_argument(
        "--model-type",
        choices=("dpt_large", "midas_v21"),
        default="dpt_large",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument(
        "--local-validation-dir",
        type=Path,
        default=None,
        help="Optional directory containing validation-*.parquet for offline input.",
    )
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def normalized_index(value) -> str:
    text = str(value)
    return str(int(text)) if text.isdigit() else text


def main() -> None:
    args = parse_args()
    official_root = args.official_root.expanduser().resolve()
    checkpoint_path = args.checkpoint_path.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Missing checkpoint: {checkpoint_path}")
    sys.path.insert(0, official_root.as_posix())

    import cv2
    import numpy as np
    import torch
    from datasets import load_dataset
    from tqdm import tqdm
    from torchvision.transforms import Compose

    from midas.dpt_depth import DPTDepthModel
    from midas.midas_net import MidasNet
    from midas.transforms import NormalizeImage, PrepareForNet, Resize

    if args.model_type == "dpt_large":
        model = DPTDepthModel(
            path=None,
            backbone="vitl16_384",
            non_negative=True,
        )
        normalization = NormalizeImage(
            mean=[0.5, 0.5, 0.5],
            std=[0.5, 0.5, 0.5],
        )
        resize_method = "lower_bound"
    else:
        model = MidasNet(None, non_negative=True)
        normalization = NormalizeImage(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        )
        resize_method = "upper_bound"

    transform = Compose(
        [
            Resize(
                384,
                384,
                resize_target=True,
                keep_aspect_ratio=True,
                ensure_multiple_of=32,
                resize_method=resize_method,
                image_interpolation_method=cv2.INTER_CUBIC,
            ),
            normalization,
            PrepareForNet(),
        ]
    )

    checkpoint = torch.load(
        checkpoint_path,
        map_location="cpu",
        weights_only=True,
    )
    state_dict = checkpoint.get("model_state_dict", checkpoint)
    model.load_state_dict(state_dict)
    device = torch.device(args.device)
    model.eval().to(device)

    if args.local_validation_dir is not None:
        parquet_files = sorted(
            args.local_validation_dir.expanduser().resolve().glob(
                "validation-*.parquet"
            )
        )
        if not parquet_files:
            raise FileNotFoundError(
                f"No validation parquet files in {args.local_validation_dir}"
            )
        rows = load_dataset(
            "parquet",
            data_files={
                "validation": [path.as_posix() for path in parquet_files]
            },
            split="validation",
            streaming=True,
        )
        dataset_source = args.local_validation_dir.as_posix()
    else:
        rows = load_dataset(
            "princeton-vl/LayeredDepth",
            split="validation",
            streaming=True,
            cache_dir=args.cache_dir.as_posix() if args.cache_dir else None,
        )
        dataset_source = "princeton-vl/LayeredDepth"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    progress_total = args.max_samples
    rows_to_process = (
        rows
        if args.max_samples is None
        else islice(rows, args.max_samples)
    )

    with torch.inference_mode():
        for item, row in enumerate(
            tqdm(rows_to_process, total=progress_total, unit="sample")
        ):
            index = normalized_index(row["__key__"])
            destination = output_dir / f"{index}_1.npy"
            if destination.is_file() and not args.overwrite:
                prediction = np.load(destination).astype(np.float32, copy=False)
                manifest.append(
                    {
                        "sample_id": index,
                        "path": destination.name,
                        "shape": list(prediction.shape),
                        "valid_ratio": float((prediction > 0).mean()),
                        "reused": True,
                    }
                )
                continue

            image = np.asarray(row["image.png"].convert("RGB"), dtype=np.float32)
            image = image / 255.0
            transformed = transform({"image": image})["image"]
            sample = torch.from_numpy(transformed).unsqueeze(0).to(device)
            inverse_depth = model(sample)
            inverse_depth = torch.nn.functional.interpolate(
                inverse_depth.unsqueeze(1),
                size=image.shape[:2],
                mode="bicubic",
                align_corners=False,
            )[0, 0]
            prediction = inverse_depth.detach().cpu().numpy().astype(np.float32)
            prediction[~np.isfinite(prediction)] = 0
            prediction[prediction <= 0] = 0

            temporary = destination.with_suffix(".npy.tmp")
            with temporary.open("wb") as handle:
                np.save(handle, prediction)
            temporary.replace(destination)
            manifest.append(
                {
                    "sample_id": index,
                    "path": destination.name,
                    "shape": list(prediction.shape),
                    "valid_ratio": float((prediction > 0).mean()),
                    "reused": False,
                }
            )

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "method": f"Depth4ToM-{args.model_type}",
                "checkpoint": checkpoint_path.as_posix(),
                "dataset_source": dataset_source,
                "prediction_space": "inverse_depth",
                "layer_semantics": {"1": "single/front hypothesis"},
                "samples": len(manifest),
                "items": manifest,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Saved {len(manifest)} predictions in {output_dir}")


if __name__ == "__main__":
    main()
