#!/usr/bin/env python3
"""Run the released ReMake checkpoint on the complete official TransCG test set.

The implementation keeps ReMake's official dataset, preprocessing, model,
relative-depth backbone, trainer, and metric recorder.  Its only additions are
strict sample ordering and a per-frame metric-depth cache for the shared G0
reader.  A value of ``--max-samples`` is explicitly marked as a debug subset
and must not be copied into the baseline table.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np


METRICS = [
    "MSE",
    "RMSE",
    "REL",
    "MAE",
    "Threshold@1.01",
    "Threshold@1.03",
    "Threshold@1.05",
    "Threshold@1.10",
    "Threshold@1.25",
    "MaskedMSE",
    "MaskedRMSE",
    "MaskedREL",
    "MaskedMAE",
    "MaskedThreshold@1.01",
    "MaskedThreshold@1.02",
    "MaskedThreshold@1.03",
    "MaskedThreshold@1.05",
    "MaskedThreshold@1.10",
    "MaskedThreshold@1.25",
    "ssim",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-root", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--checkpoint-path", type=Path, required=True)
    parser.add_argument("--relative-depth-weights", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--num-workers", type=int, default=8)
    parser.add_argument("--max-samples", type=int, help="debug-only prefix of official test ordering")
    parser.add_argument("--device", default=None, help="defaults to cuda:0 when available")
    parser.add_argument("--no-save-predictions", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="reuse complete cached batches while recomputing aggregate metrics",
    )
    parser.add_argument(
        "--skip-integrity-audit",
        action="store_true",
        help="debug only; a full release run audits every declared TransCG test asset",
    )
    return parser.parse_args()


def require_file(path: Path, message: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{message}: {resolved}")
    return resolved


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def load_depth_anything(weights: Path, device: Any) -> Any:
    """Build exactly ReMake's hard-coded vits relative-depth backbone."""

    import torch
    from relat_depth_models import DepthAnythingV2

    model = DepthAnythingV2(
        encoder="vits",
        features=64,
        out_channels=[48, 96, 192, 384],
    )
    state = torch.load(weights, map_location="cpu", weights_only=False)
    if isinstance(state, dict) and "model_state_dict" in state:
        state = state["model_state_dict"]
    if isinstance(state, dict) and "state_dict" in state:
        state = state["state_dict"]
    if not isinstance(state, dict):
        raise TypeError(f"Unsupported Depth Anything checkpoint payload: {type(state)!r}")
    model.load_state_dict(state, strict=True)
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    return model.to(device).eval()


def sample_id(sample: list[Any]) -> tuple[str, dict[str, Any]]:
    sample_path, camera_type, scene_type = sample
    path = Path(sample_path)
    scene = path.parent.name
    perspective = path.name
    camera = "D435" if int(camera_type) == 1 else "L515"
    identifier = f"{scene}_{perspective}_{camera}"
    return identifier, {
        "sample_id": identifier,
        "scene": scene,
        "perspective": int(perspective),
        "camera": camera,
        "scene_type": str(scene_type),
    }


def require_complete_test_split(dataset_root: Path) -> None:
    """Use the same exact-denominator check as the DFNet release runner."""

    audit_module_dir = Path(__file__).resolve().parents[1] / "transcg"
    sys.path.insert(0, str(audit_module_dir))
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
    checkpoint_path = require_file(args.checkpoint_path, "Missing released ReMake checkpoint")
    relative_depth_weights = require_file(args.relative_depth_weights, "Missing Depth Anything V2 vits weights")
    if not (official_root / "models" / "remake.py").is_file():
        raise FileNotFoundError(f"Not a ReMake official checkout: {official_root}")
    if not (dataset_root / "metadata.json").is_file():
        raise FileNotFoundError(f"Missing TransCG metadata: {dataset_root / 'metadata.json'}")
    if args.batch_size < 1 or args.num_workers < 0:
        raise ValueError("batch-size must be positive and num-workers non-negative")
    if args.resume and args.no_save_predictions:
        raise ValueError("--resume requires prediction caching")
    if args.max_samples is None and not args.skip_integrity_audit:
        require_complete_test_split(dataset_root)

    sys.path.insert(0, str(official_root))
    # ReMake's checkout also uses a local ``datasets`` directory without an
    # __init__.py.  Import the module directly so an installed Hugging Face
    # package named datasets cannot shadow it.
    sys.path.insert(0, str(official_root / "datasets"))
    import torch
    from torch.utils.data import DataLoader, Subset

    from transcg import TransCG
    from models.remake import ReMake
    from run_utils.trainer import remake_trainer
    from utils.metrics import MetricsRecorder
    from utils.tools import to_device

    device_name = args.device or ("cuda:0" if torch.cuda.is_available() else "cpu")
    device = torch.device(device_name)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")

    dataset = TransCG(
        data_dir=str(dataset_root),
        split="test",
        image_size=(640, 480),
        use_augmentation=False,
        depth_min=0.0,
        depth_max=10.0,
        depth_norm=1.0,
        reldepth_model="depthanything",
    )
    sample_count = len(dataset) if args.max_samples is None else min(args.max_samples, len(dataset))
    if sample_count < 1:
        raise ValueError("max-samples must leave at least one sample")
    dataset_for_run = dataset if sample_count == len(dataset) else Subset(dataset, range(sample_count))
    loader = DataLoader(
        dataset_for_run,
        batch_size=args.batch_size,
        shuffle=False,
        drop_last=False,
        num_workers=args.num_workers,
        pin_memory=device.type == "cuda",
    )

    model = ReMake(lambda_val=1, res=True).to(device)
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval()
    relative_depth_model = load_depth_anything(relative_depth_weights, device)
    metrics = MetricsRecorder(logger_name="remake_full", metrics_list=METRICS, epsilon=1e-8, depth_scale=1.0)
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
    resumed_samples = 0
    offset = 0
    with torch.no_grad():
        for batch in loader:
            current_batch = int(batch["rgb"].shape[0])
            source_samples = dataset.sample_info[offset : offset + current_batch]
            relative_files = [
                Path("predictions_m") / f"{sample_id(source_sample)[0]}.npy"
                for source_sample in source_samples
            ]
            cached_batch = args.resume and all((output_dir / path).is_file() for path in relative_files)
            batch = to_device(batch, device)
            if cached_batch:
                predictions_m = np.stack(
                    [np.load(output_dir / path).astype(np.float32) for path in relative_files]
                )
                if predictions_m.shape != (current_batch, 480, 640):
                    raise ValueError(f"Invalid cached ReMake batch shape: {predictions_m.shape}")
                if not np.all(np.isfinite(predictions_m)):
                    raise ValueError("Cached ReMake predictions contain non-finite values")
                batch["pred"] = torch.from_numpy(predictions_m).to(device)
                resumed_samples += current_batch
            else:
                start = perf_counter()
                relative_depth = relative_depth_model.forward(batch["rgb_relat"]).unsqueeze(1)
                remake_trainer(model, batch, relative_depth)
                durations.append(perf_counter() - start)
                predictions_m = batch["pred"].detach().cpu().numpy().astype(np.float32)
            metrics.evaluate_batch(batch, record=True)
            for local_index, source_sample in enumerate(source_samples):
                identifier, record = sample_id(source_sample)
                relative_file = relative_files[local_index]
                source_dir = Path(source_sample[0])
                camera_type = int(source_sample[1])
                camera_name = record["camera"]
                # ReMake's official dataset resizes to 640x480.  Preserve the
                # scaled calibration with every cached output for a later
                # common shell/planner reader.
                from PIL import Image

                with Image.open(source_dir / f"rgb{camera_type}.png") as image:
                    source_width, source_height = image.size
                prediction_height, prediction_width = predictions_m[local_index].shape
                source_intrinsics = intrinsics_by_camera[camera_name].astype(float)
                prediction_intrinsics = source_intrinsics.copy()
                prediction_intrinsics[0, :] *= prediction_width / source_width
                prediction_intrinsics[1, :] *= prediction_height / source_height
                if not args.no_save_predictions and not cached_batch:
                    np.save(output_dir / relative_file, predictions_m[local_index])
                if not args.no_save_predictions:
                    record["prediction_m"] = str(relative_file)
                else:
                    record["prediction_m"] = None
                record.update(
                    {
                        "source_directory": str(source_dir.relative_to(dataset_root)),
                        "source_image_size_hw": [source_height, source_width],
                        "prediction_size_hw": [prediction_height, prediction_width],
                        "intrinsics_source": source_intrinsics.tolist(),
                        "intrinsics_prediction": prediction_intrinsics.tolist(),
                    }
                )
                manifest.append(record)
            offset += current_batch

    native_metrics = metrics.get_results()
    summary = {
        "run_kind": "official_full_test" if sample_count == len(dataset) else "debug_subset",
        "model": "ReMake_release_checkpoint_with_DepthAnythingV2_vits",
        "official_root": str(official_root),
        "dataset_root": str(dataset_root),
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_epoch": int(checkpoint.get("epoch", -1)),
        "relative_depth_weights": str(relative_depth_weights),
        "device": str(device),
        "samples": offset,
        "resumed_cached_samples": resumed_samples,
        "model_batches_executed": len(durations),
        "batch_size": args.batch_size,
        "mean_model_plus_relative_depth_seconds_per_batch": float(np.mean(durations)) if durations else None,
        "native_metrics": jsonable(native_metrics),
        "prediction_space": "metric_depth_m",
        "preprocessing": "official ReMake TransCG dataset, image_size=(640,480), depth_norm=1, DepthAnythingV2-vits",
    }
    (output_dir / "metrics.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
