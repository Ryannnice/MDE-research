#!/usr/bin/env python3
"""Integration test for T²SQNet per-object shell evaluation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np


THIS_DIR = Path(__file__).resolve().parent
SHELLBENCH_DIR = THIS_DIR.parent / "shellbench"
sys.path.insert(0, str(SHELLBENCH_DIR))
from ray_events import AIR_TO_SHELL, CAVITY_TO_SHELL, SHELL_TO_AIR, SHELL_TO_CAVITY, RayEvents  # noqa: E402


EVALUATOR = THIS_DIR / "evaluate_gt_mask_shell.py"


def events() -> RayEvents:
    depths = np.asarray([[[0.2]], [[0.21]], [[0.5]], [[0.51]]], dtype=np.float32)
    transitions = np.asarray(
        [[[AIR_TO_SHELL]], [[SHELL_TO_CAVITY]], [[CAVITY_TO_SHELL]], [[SHELL_TO_AIR]]],
        dtype=np.int8,
    )
    return RayEvents(depths, np.ones_like(depths, dtype=bool), transitions)


def pose(x: float) -> list[list[float]]:
    result = np.eye(4)
    result[0, 3] = x
    return result.tolist()


def test_per_object_evaluator_matches_and_scores() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        gt_root = root / "gt"
        prediction_root = root / "prediction"
        (gt_root / "events").mkdir(parents=True)
        (prediction_root / "events").mkdir(parents=True)
        (prediction_root / "objects").mkdir(parents=True)
        events().save(gt_root / "events" / "scene__object0__view0.npz")
        events().save(prediction_root / "events" / "scene_prediction0_view0.npz")
        (gt_root / "manifest.json").write_text(
            json.dumps(
                {
                    "summary": {},
                    "items": [
                        {
                            "scene_id": "scene",
                            "object_index": 0,
                            "view_index": 0,
                            "event_file": "events/scene__object0__view0.npz",
                            "ground_truth_object": {"class": "Bowl", "pose_world": pose(0.0), "params": []},
                        }
                    ],
                    "skipped": [],
                }
            ),
            encoding="utf-8",
        )
        (prediction_root / "objects" / "scene.json").write_text(
            json.dumps(
                {
                    "predicted_objects": [
                        {"prediction_index": 0, "class": "Bowl", "pose_world": pose(0.01), "params": []}
                    ]
                }
            ),
            encoding="utf-8",
        )
        (prediction_root / "manifest.json").write_text(
            json.dumps([{"scene_id": "scene", "objects_file": "objects/scene.json"}]), encoding="utf-8"
        )
        output = root / "metrics.json"
        subprocess.run(
            [
                sys.executable,
                str(EVALUATOR),
                "--ground-truth-root",
                str(gt_root),
                "--prediction-root",
                str(prediction_root),
                "--output-json",
                str(output),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        metrics = json.loads(output.read_text(encoding="utf-8"))
        assert metrics["matching"]["matched_objects"] == 1
        assert metrics["ray_event_metrics"]["interface_f1"] == 1.0
        assert metrics["ray_event_metrics"]["transition_f1"] == 1.0


if __name__ == "__main__":
    test_per_object_evaluator_matches_and_scores()
    print("T²SQNet GT-mask shell evaluation test: OK")
