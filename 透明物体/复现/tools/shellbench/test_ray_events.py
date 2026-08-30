#!/usr/bin/env python3
"""Unit tests for the ShellBench ray-event contract."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from ray_events import (
    AIR_TO_SHELL,
    CAVITY_TO_SHELL,
    SHELL_TO_AIR,
    SHELL_TO_CAVITY,
    RayEvents,
    _event_statistics_reference,
    event_statistics,
    single_depth_events,
    summarize_statistics,
)


class RayEventsTest(unittest.TestCase):
    def test_normalization_sorts_and_compacts(self) -> None:
        events = RayEvents(
            np.asarray([[[0.8]], [[0.0]], [[0.3]]], dtype=np.float32),
            np.asarray([[[True]], [[False]], [[True]]]),
            np.asarray([[[4]], [[0]], [[1]]], dtype=np.int8),
        ).normalized()
        self.assertTrue(np.array_equal(events.valid_mask[:, 0, 0], [True, True, False]))
        self.assertTrue(np.allclose(events.depths_m[:, 0, 0], [0.3, 0.8, 0.0]))
        self.assertTrue(np.array_equal(events.transition_type[:, 0, 0], [1, 4, 0]))

    def test_single_depth_has_unmatched_recall_penalty(self) -> None:
        gt = RayEvents(
            np.asarray([[[0.2]], [[0.3]], [[0.6]], [[0.7]]], dtype=np.float32),
            np.ones((4, 1, 1), dtype=bool),
        )
        pred = single_depth_events(np.asarray([[0.201]], dtype=np.float32))
        metrics = summarize_statistics(event_statistics(pred, gt, 0.01))
        self.assertAlmostEqual(metrics["interface_precision"], 1.0)
        self.assertAlmostEqual(metrics["interface_recall"], 0.25)
        self.assertAlmostEqual(metrics["interface_f1"], 0.4)
        self.assertEqual(metrics["interface_count_accuracy"], 0.0)

    def test_ordered_matching_skips_missing_middle_event(self) -> None:
        gt = RayEvents(
            np.asarray([[[0.2]], [[0.4]], [[0.6]]], dtype=np.float32),
            np.ones((3, 1, 1), dtype=bool),
        )
        pred = RayEvents(
            np.asarray([[[0.2]], [[0.6]]], dtype=np.float32),
            np.ones((2, 1, 1), dtype=bool),
        )
        metrics = summarize_statistics(event_statistics(pred, gt, 0.01))
        self.assertAlmostEqual(metrics["interface_recall"], 2 / 3)
        self.assertAlmostEqual(metrics["matched_interface_mae_m"], 0.0)

    def test_zero_overlap_reports_zero_f1(self) -> None:
        gt = single_depth_events(np.asarray([[0.2]], dtype=np.float32))
        pred = single_depth_events(np.asarray([[0.8]], dtype=np.float32))
        metrics = summarize_statistics(event_statistics(pred, gt, 0.01))
        self.assertEqual(metrics["interface_precision"], 0.0)
        self.assertEqual(metrics["interface_recall"], 0.0)
        self.assertEqual(metrics["interface_f1"], 0.0)

    def test_topology_metrics_require_explicit_types(self) -> None:
        valid = np.ones((4, 1, 1), dtype=bool)
        depths = np.asarray([[[0.2]], [[0.3]], [[0.6]], [[0.7]]], dtype=np.float32)
        transitions = np.asarray(
            [[[AIR_TO_SHELL]], [[SHELL_TO_CAVITY]], [[CAVITY_TO_SHELL]], [[SHELL_TO_AIR]]],
            dtype=np.int8,
        )
        gt = RayEvents(depths, valid, transitions)
        metrics = summarize_statistics(event_statistics(gt, gt, 0.001))
        self.assertEqual(metrics["topology_labeled_ray_rate"], 1.0)
        self.assertEqual(metrics["topology_valid_ray_rate"], 1.0)
        self.assertEqual(metrics["transition_f1"], 1.0)

    def test_unmatched_typed_event_is_a_transition_false_positive(self) -> None:
        gt = RayEvents(
            np.asarray([[[0.2]]], dtype=np.float32),
            np.ones((1, 1, 1), dtype=bool),
            np.asarray([[[AIR_TO_SHELL]]], dtype=np.int8),
        )
        pred = RayEvents(
            np.asarray([[[0.2]], [[0.6]]], dtype=np.float32),
            np.ones((2, 1, 1), dtype=bool),
            np.asarray([[[AIR_TO_SHELL]], [[SHELL_TO_AIR]]], dtype=np.int8),
        )
        metrics = summarize_statistics(event_statistics(pred, gt, 0.01))
        self.assertAlmostEqual(metrics["transition_precision"], 0.5)
        self.assertAlmostEqual(metrics["transition_recall"], 1.0)

    def test_npz_roundtrip(self) -> None:
        source = single_depth_events(np.asarray([[0.5, 0.0]], dtype=np.float32))
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "events.npz"
            source.save(path)
            target = RayEvents.load(path)
        self.assertTrue(np.array_equal(source.valid_mask, target.valid_mask))
        self.assertTrue(np.allclose(source.depths_m, target.depths_m))

    def test_accelerated_statistics_match_reference_randomized(self) -> None:
        rng = np.random.default_rng(7)
        transition_values = np.asarray(
            [0, AIR_TO_SHELL, SHELL_TO_CAVITY, CAVITY_TO_SHELL, SHELL_TO_AIR], dtype=np.int8
        )
        for _ in range(40):
            pred_shape = (int(rng.integers(1, 7)), 4, 5)
            gt_shape = (int(rng.integers(1, 7)), 4, 5)
            pred_valid = rng.random(pred_shape) > 0.35
            gt_valid = rng.random(gt_shape) > 0.35
            prediction = RayEvents(
                rng.uniform(0.1, 1.5, pred_shape).astype(np.float32),
                pred_valid,
                rng.choice(transition_values, pred_shape),
            )
            ground_truth = RayEvents(
                rng.uniform(0.1, 1.5, gt_shape).astype(np.float32),
                gt_valid,
                rng.choice(transition_values, gt_shape),
            )
            accelerated = event_statistics(prediction, ground_truth, 0.08)
            reference = _event_statistics_reference(prediction, ground_truth, 0.08)
            self.assertEqual(set(accelerated), set(reference))
            for key in reference:
                self.assertAlmostEqual(accelerated[key], reference[key], places=12, msg=key)


if __name__ == "__main__":
    unittest.main()
