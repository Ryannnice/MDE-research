#!/usr/bin/env python3
"""Run the released SeeGroup checkpoint on the Booster Table-2 image list.

The saved prediction is the closest valid raw SeeGroup depth head. SeeGroup's
training losses are normalization-aligned, so these values are not claimed to
be calibrated metric metres. Directory structure follows each Booster RGB
basename for explicit raw-as-metric and affine-aligned bridge diagnostics.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-root", type=Path, required=True)
    parser.add_argument("--checkpoint-path", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--dataset-txt", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Do not load the model; require every requested NPY to be reusable.",
    )
    return parser.parse_args()


def image_basenames(dataset_txt: Path) -> list[str]:
    basenames: list[str] = []
    for line_number, line in enumerate(
        dataset_txt.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        fields = line.split()
        if len(fields) not in (2, 3, 4):
            raise ValueError(
                f"Unexpected field count on line {line_number} of {dataset_txt}"
            )
        basenames.append(fields[0])
    return basenames


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
    input_root = args.input_root.expanduser().resolve()
    dataset_txt = args.dataset_txt.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Missing checkpoint: {checkpoint_path}")
    if not dataset_txt.is_file():
        raise FileNotFoundError(f"Missing dataset list: {dataset_txt}")
    sys.path.insert(0, official_root.as_posix())

    import cv2
    import numpy as np
    import torch
    from tqdm import tqdm

    from dataset import model_forward_unscale
    from model import init_model
    from util.config import get_config_from_path

    model = None
    if not args.cache_only:
        config = get_config_from_path((official_root / "config" / "val.py").as_posix())
        config["local_rank"] = 0
        config["rank"] = 0
        config["cli"] = "val"
        config["resumed_from"] = checkpoint_path.as_posix()
        model = init_model(config)
        model.eval()

    basenames = image_basenames(dataset_txt)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    mean = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)
    stop_index = len(basenames)
    if args.max_samples is not None:
        stop_index = min(stop_index, args.start_index + args.max_samples)
    basenames_to_process = basenames[args.start_index:stop_index]
    progress_total = len(basenames_to_process)

    with torch.inference_mode():
        for item, basename in enumerate(
            tqdm(basenames_to_process, total=progress_total, unit="sample"),
            start=args.start_index,
        ):
            source = input_root / basename
            if not source.is_file():
                raise FileNotFoundError(f"Missing Booster RGB image: {source}")
            relative = Path(basename).with_suffix(".npy")
            destination = output_dir / relative

            if destination.is_file() and not args.overwrite:
                prediction = np.load(destination).astype(np.float32, copy=False)
                manifest.append(
                    {
                        "sample": item,
                        "rgb": basename,
                        "prediction": relative.as_posix(),
                        "shape": list(prediction.shape),
                        "valid_ratio": float((prediction > 0.02).mean()),
                        "reused": True,
                    }
                )
                continue

            if args.cache_only:
                raise FileNotFoundError(
                    f"--cache-only requires a readable prediction for sample {item}: "
                    f"{destination}"
                )
            assert model is not None

            image_bgr = cv2.imread(source.as_posix(), cv2.IMREAD_COLOR)
            if image_bgr is None:
                raise ValueError(f"Could not decode Booster RGB image: {source}")
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            image_rgb = image_rgb.astype(np.float32) / 255.0
            normalized = (image_rgb - mean) / std
            tensor = torch.from_numpy(
                np.ascontiguousarray(normalized.transpose(2, 0, 1))
            )
            result = model_forward_unscale(
                model,
                {"image": tensor.unsqueeze(0).cuda(non_blocking=True)},
            )

            raw_depth = result["depth"][0]
            if "valid_mask" in result:
                raw_valid = result["valid_mask"][0] > 0.01
            elif "weight" in result:
                raw_valid = result["weight"][0] > 0.01
            else:
                raw_valid = torch.ones_like(raw_depth, dtype=torch.bool)
            raw_valid &= torch.isfinite(raw_depth) & (raw_depth > 0.02)

            candidates = raw_depth.masked_fill(~raw_valid, float("inf"))
            closest_depth = candidates.min(dim=0).values
            closest_valid = torch.isfinite(closest_depth)
            closest_depth = closest_depth.masked_fill(~closest_valid, 0)

            destination.parent.mkdir(parents=True, exist_ok=True)
            prediction = closest_depth.cpu().numpy().astype(np.float32)
            temporary = destination.with_suffix(".npy.tmp")
            with temporary.open("wb") as handle:
                np.save(handle, prediction)
            temporary.replace(destination)
            manifest.append(
                {
                    "sample": item,
                    "rgb": basename,
                    "prediction": relative.as_posix(),
                    "shape": list(prediction.shape),
                    "valid_ratio": float(closest_valid.float().mean().item()),
                    "reused": False,
                }
            )

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "method": "SeeGroup closest valid layer",
                "checkpoint": checkpoint_path.as_posix(),
                "prediction_space": "raw_depth_head_units_not_metric_calibrated",
                "start_index": args.start_index,
                "cache_only": args.cache_only,
                "samples": len(manifest),
                "items": manifest,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Saved {len(manifest)} Booster predictions in {output_dir}")


if __name__ == "__main__":
    main()
