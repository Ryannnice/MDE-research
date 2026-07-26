#!/usr/bin/env python3
"""End-to-end test for the batch TablewareNet shell-oracle exporter."""

from __future__ import annotations

import json
import pickle
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import torch


THIS_DIR = Path(__file__).resolve().parent
TRANSPARENT_ROOT = THIS_DIR.parents[2]
T2_ROOT = TRANSPARENT_ROOT / "external" / "t2sqnet" / "official"
EXPORTER = THIS_DIR / "export_tablewarenet_shell_gt.py"


def test_batch_exporter_writes_one_hollow_object_frame() -> None:
    # A small camera looking along +x through the side wall of a Bowl.  The
    # pickle follows the official processed-scene field names used by the
    # exporter; only its image resolution is intentionally tiny.
    rotation_camera_to_world = np.asarray(
        [[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]], dtype=np.float64
    )
    pose = np.eye(4, dtype=np.float64)
    pose[:3, :3] = rotation_camera_to_world
    pose[:3, 3] = [-0.30, 0.0, 0.05]
    data = {
        "objects_class": ["Bowl"],
        "objects_pose": [torch.eye(4)],
        "objects_param": [torch.tensor([0.10, 0.10, 0.05, 0.10, 0.50, 0.0])],
        "camera": [
            {
                "camera_intr": np.asarray([[3.0, 0.0, 1.0], [0.0, 3.0, 0.0], [0.0, 0.0, 1.0]]),
                "camera_pose": pose,
                "camera_image_size": np.asarray([3, 1]),
            }
        ],
    }
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        data_root = root / "processed"
        data_root.mkdir()
        with (data_root / "scene.pkl").open("wb") as handle:
            pickle.dump(data, handle)
        output_dir = root / "out"
        subprocess.run(
            [
                sys.executable,
                str(EXPORTER),
                "--official-root",
                str(T2_ROOT),
                "--data-root",
                str(data_root),
                "--output-dir",
                str(output_dir),
                "--view-indices",
                "0",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        assert payload["summary"]["event_frames"] == 1
        event_path = output_dir / payload["items"][0]["event_file"]
        assert event_path.is_file()


if __name__ == "__main__":
    test_batch_exporter_writes_one_hollow_object_frame()
    print("TablewareNet batch shell-oracle export test: OK")
