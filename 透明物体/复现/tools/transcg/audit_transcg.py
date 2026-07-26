#!/usr/bin/env python3
"""Audit the exact TransCG split before an evaluation is allowed to start.

The public TransCG download is split by scene ranges, while the official test
split is interleaved across all thirteen ranges.  This checker is deliberately
strict: it prevents a partial download from being presented as a full test
result and records the expected sample denominator for a run manifest.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_FILES = {
    1: ("rgb1.png", "depth1.png", "depth1-gt.png", "depth1-gt-mask.png"),
    2: ("rgb2.png", "depth2.png", "depth2-gt.png", "depth2-gt-mask.png"),
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def audit(dataset_root: Path, split: str) -> dict[str, Any]:
    metadata_path = dataset_root / "metadata.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Missing TransCG metadata: {metadata_path}")
    metadata = load_json(metadata_path)
    if split not in {"train", "test"}:
        raise ValueError(f"Unsupported split: {split}")

    scene_ids = [int(scene_id) for scene_id in metadata[split]]
    expected_samples = int(metadata[f"{split}_samples"])
    missing_scene_metadata: list[int] = []
    missing_samples: list[dict[str, Any]] = []
    present_samples = 0
    expected_by_camera = {"D435": 0, "L515": 0}
    present_by_camera = {"D435": 0, "L515": 0}

    for scene_id in scene_ids:
        scene_root = dataset_root / f"scene{scene_id}"
        scene_metadata_path = scene_root / "metadata.json"
        if not scene_metadata_path.is_file():
            missing_scene_metadata.append(scene_id)
            continue
        scene_metadata = load_json(scene_metadata_path)
        if scene_metadata.get("split") != split:
            raise ValueError(
                f"scene{scene_id} declares split={scene_metadata.get('split')!r}, expected {split!r}"
            )
        for camera_name, camera_type, key in (
            ("D435", 1, "D435_valid_perspective_list"),
            ("L515", 2, "L515_valid_perspective_list"),
        ):
            for perspective_id in scene_metadata[key]:
                expected_by_camera[camera_name] += 1
                sample_root = scene_root / str(perspective_id)
                absent = [name for name in REQUIRED_FILES[camera_type] if not (sample_root / name).is_file()]
                if absent:
                    if len(missing_samples) < 100:
                        missing_samples.append(
                            {
                                "scene": scene_id,
                                "perspective": int(perspective_id),
                                "camera": camera_name,
                                "missing": absent,
                            }
                        )
                    continue
                present_samples += 1
                present_by_camera[camera_name] += 1

    expected_from_scene_metadata = sum(expected_by_camera.values())
    return {
        "dataset_root": str(dataset_root.resolve()),
        "split": split,
        "total_scenes": int(metadata["total_scenes"]),
        "split_scene_count": len(scene_ids),
        "split_scenes": scene_ids,
        "expected_samples_from_root_metadata": expected_samples,
        "expected_samples_from_scene_metadata": expected_from_scene_metadata,
        "present_complete_samples": present_samples,
        "expected_by_camera": expected_by_camera,
        "present_by_camera": present_by_camera,
        "missing_scene_metadata_count": len(missing_scene_metadata),
        "missing_scene_metadata": missing_scene_metadata,
        # Root metadata remains the only trustworthy denominator until every
        # scene metadata file is present.  Reporting zero here for a metadata-
        # only download would otherwise be actively misleading.
        "missing_sample_count": expected_samples - present_samples,
        "missing_sample_examples": missing_samples,
        "ready_for_full_split": (
            not missing_scene_metadata
            and expected_samples == expected_from_scene_metadata == present_samples
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "test"), default="test")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="write/report an incomplete audit without returning a non-zero status",
    )
    args = parser.parse_args()

    report = audit(args.dataset_root, args.split)
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    if not report["ready_for_full_split"] and not args.allow_incomplete:
        raise SystemExit("TransCG audit is incomplete; refusing a full-split baseline claim.")


if __name__ == "__main__":
    main()
