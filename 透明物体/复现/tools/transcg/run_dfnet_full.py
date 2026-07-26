#!/usr/bin/env python3
"""Run the released DFNet checkpoint on the official TransCG test split.

This is a thin adapter over the official `TransCG` dataset and `DFNet` model:
the preprocessing, per-image metric recorder, and checkpoint state dict remain
upstream.  In addition to the native aggregate metrics it saves metric-depth
predictions and a sample manifest, so the same fixed planner can later consume
the baseline output in the shell-failure diagnostic.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-root", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--checkpoint-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=24)
    parser.add_argument("--num-workers", type=int, default=8)
    parser.add_argument("--max-samples", type=int)
    parser.add_argument("--device", default=None, help="defaults to cuda:0 when available")
    parser.add_argument("--no-save-predictions", action="store_true")
    parser.add_argument(
        "--skip-integrity-audit",
        action="store_true",
        help="debug only; full release runs always audit every declared test asset",
    )
    return parser.parse_args()


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def require_complete_test_split(dataset_root: Path) -> None:
    """Make the runner and standalone TransCG audit use one denominator."""

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from audit_transcg import audit

    report = audit(dataset_root, "test")
    if not report["ready_for_full_split"]:
        raise RuntimeError(
            "TransCG test split is incomplete; run audit_transcg.py for details "
            "before launching a release baseline."
        )


def main() -> None:
    args = parse_args()
    official_root = args.official_root.resolve()
    dataset_root = args.dataset_root.resolve()
    checkpoint_path = args.checkpoint_path.resolve()
    if not (official_root / "models" / "DFNet.py").is_file():
        raise FileNotFoundError(f"Not a TransCG official checkout: {official_root}")
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Missing released DFNet checkpoint: {checkpoint_path}")
    if not (dataset_root / "metadata.json").is_file():
        raise FileNotFoundError(f"Missing TransCG metadata: {dataset_root / 'metadata.json'}")
    if args.max_samples is None and not args.skip_integrity_audit:
        require_complete_test_split(dataset_root)

    sys.path.insert(0, str(official_root))
    import torch
    from torch.utils.data import DataLoader, Subset

    from datasets.transcg import TransCG
    from models.DFNet import DFNet
    from utils.functions import to_device
    from utils.metrics import MetricsRecorder

    device_name = args.device or ("cuda:0" if torch.cuda.is_available() else "cpu")
    device = torch.device(device_name)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")

    dataset = TransCG(
        data_dir=str(dataset_root),
        split="test",
        image_size=(320, 240),
        use_augmentation=False,
        depth_min=0.0,
        depth_max=10.0,
        depth_norm=10.0,
        with_original=False,
    )
    sample_count = len(dataset) if args.max_samples is None else min(args.max_samples, len(dataset))
    if sample_count != len(dataset):
        dataset_for_run = Subset(dataset, list(range(sample_count)))
        run_kind = "debug_subset"
    else:
        dataset_for_run = dataset
        run_kind = "official_full_test"
    loader = DataLoader(
        dataset_for_run,
        batch_size=args.batch_size,
        shuffle=False,
        drop_last=False,
        num_workers=args.num_workers,
        pin_memory=device.type == "cuda",
    )

    model = DFNet(in_channels=4, hidden_channels=64, L=5, k=12).to(device)
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    metrics = MetricsRecorder(
        metrics_list=[
            "MSE", "MaskedMSE", "RMSE", "MaskedRMSE", "REL", "MaskedREL",
            "MAE", "MaskedMAE", "Threshold@1.05", "MaskedThreshold@1.05",
            "Threshold@1.10", "MaskedThreshold@1.10", "Threshold@1.25", "MaskedThreshold@1.25",
        ],
        epsilon=1e-8,
        depth_scale=10.0,
    )
    metrics.clear()

    output_dir = args.output_dir.resolve()
    prediction_dir = output_dir / "predictions_m"
    output_dir.mkdir(parents=True, exist_ok=True)
    if not args.no_save_predictions:
        prediction_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    intrinsics_by_camera = {
        "D435": np.load(dataset_root / "camera_intrinsics" / "1-camIntrinsics-D435.npy"),
        "L515": np.load(dataset_root / "camera_intrinsics" / "2-camIntrinsics-L515.npy"),
    }
    durations: list[float] = []
    offset = 0
    with torch.no_grad():
        for batch in loader:
            batch_size = int(batch["rgb"].shape[0])
            batch = to_device(batch, device)
            start = perf_counter()
            prediction = model(batch["rgb"], batch["depth"])
            durations.append(perf_counter() - start)
            depth_scale = batch["depth_max"] - batch["depth_min"]
            prediction = prediction * depth_scale.reshape(-1, 1, 1) + batch["depth_min"].reshape(-1, 1, 1)
            batch["pred"] = prediction
            metrics.evaluate_batch(batch, record=True)

            # The official test config uses depth_norm=10.  Its metrics multiply
            # by the same scale; the cached arrays here are therefore metric m.
            prediction_m = (prediction * 10.0).detach().cpu().numpy().astype(np.float32)
            for local_index, sample in enumerate(dataset.sample_info[offset : offset + batch_size]):
                sample_path, camera_type, scene_type, perspective_id = sample
                source_dir = Path(sample_path)
                scene_name = source_dir.parent.name
                camera_name = "D435" if camera_type == 1 else "L515"
                sample_id = f"{scene_name}_{perspective_id}_camera{camera_type}"
                relative_file = Path("predictions_m") / f"{sample_id}.npy"
                # The official dataset resizes the source image to 320x240.
                # Persist calibrated intrinsics so later geometry never has to
                # infer which resolution the depth map belongs to.
                from PIL import Image

                with Image.open(source_dir / f"rgb{camera_type}.png") as image:
                    source_width, source_height = image.size
                prediction_height, prediction_width = prediction_m[local_index].shape
                source_intrinsics = intrinsics_by_camera[camera_name].astype(float)
                prediction_intrinsics = source_intrinsics.copy()
                prediction_intrinsics[0, :] *= prediction_width / source_width
                prediction_intrinsics[1, :] *= prediction_height / source_height
                if not args.no_save_predictions:
                    np.save(output_dir / relative_file, prediction_m[local_index])
                manifest.append(
                    {
                        "sample_id": sample_id,
                        "scene": scene_name,
                        "perspective": int(perspective_id),
                        "camera": camera_name,
                        "scene_type": scene_type,
                        "prediction_m": None if args.no_save_predictions else str(relative_file),
                        "source_directory": str(source_dir.relative_to(dataset_root)),
                        "source_image_size_hw": [source_height, source_width],
                        "prediction_size_hw": [prediction_height, prediction_width],
                        "intrinsics_source": source_intrinsics.tolist(),
                        "intrinsics_prediction": prediction_intrinsics.tolist(),
                    }
                )
            offset += batch_size

    results = metrics.get_results()
    summary = {
        "run_kind": run_kind,
        "model": "TransCG_DFNet_release_checkpoint",
        "official_root": str(official_root),
        "dataset_root": str(dataset_root),
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_epoch": int(checkpoint.get("epoch", -1)),
        "device": str(device),
        "samples": offset,
        "batch_size": args.batch_size,
        "mean_model_forward_seconds_per_batch": float(np.mean(durations)) if durations else None,
        "native_metrics": jsonable(results),
        "prediction_space": "metric_depth_m",
        "preprocessing": "official TransCG dataset, image_size=(320,240), depth_norm=10",
    }
    (output_dir / "metrics.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
