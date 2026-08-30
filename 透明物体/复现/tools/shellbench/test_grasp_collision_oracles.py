#!/usr/bin/env python3
"""Unit tests for the frozen ray-event collision policies."""

from __future__ import annotations

import unittest
import sys
from pathlib import Path

import numpy as np

THIS_DIR = Path(__file__).resolve().parent
T2_ROOT = THIS_DIR.parents[2] / "external" / "t2sqnet" / "official"
sys.path.insert(0, str(T2_ROOT))

from evaluate_grasp_collision_oracles import (
    POLICIES,
    bounded_uniform_sampling_2d,
    classify_depth_queries,
    collision_predictions,
    collision_predictions_batch,
)


class CollisionPolicyTests(unittest.TestCase):
    def test_bounded_sampler_preserves_regular_upstream_grid(self) -> None:
        import torch
        from tablewarenet.primitive_grasp_planner import delta_theta, sq_uniform_sampling_2D

        exponent = torch.tensor(0.8)
        axis_a = torch.tensor(0.10)
        axis_b = torch.tensor(0.08)
        expected = sq_uniform_sampling_2D(exponent, axis_a, axis_b, 0.005)
        actual, used_fallback = bounded_uniform_sampling_2d(
            torch, delta_theta, exponent, axis_a, axis_b, 0.005, 4096, 2048, 72
        )
        self.assertFalse(used_fallback)
        torch.testing.assert_close(actual, expected, rtol=0, atol=0)

    def test_bounded_sampler_terminates_pathological_grid(self) -> None:
        import torch
        from tablewarenet.primitive_grasp_planner import delta_theta

        actual, used_fallback = bounded_uniform_sampling_2d(
            torch,
            delta_theta,
            torch.tensor(0.12488148361444473),
            torch.tensor(0.10095225274562836),
            torch.tensor(0.04393069073557854),
            0.005,
            64,
            2048,
            72,
        )
        self.assertTrue(used_fallback)
        self.assertEqual(tuple(actual.shape), (72,))
        self.assertTrue(bool(torch.all(torch.isfinite(actual))))
        self.assertTrue(bool(torch.all(actual[:-1] < actual[1:])))

    def test_complete_shell_ray(self) -> None:
        depths = np.asarray([1.0, 1.01, 1.10, 1.11], dtype=np.float32)[:, None, None]
        valid = np.ones_like(depths, dtype=bool)
        transitions = np.asarray([1, 2, 3, 4], dtype=np.int8)[:, None, None]
        queries = np.asarray([0.9, 1.005, 1.05, 1.105, 1.2], dtype=np.float32)
        rows = np.zeros(len(queries), dtype=np.int64)
        columns = np.zeros(len(queries), dtype=np.int64)
        parity = classify_depth_queries(
            depths, valid, transitions, rows, columns, queries,
            "gt_events_fixed_parity", 0.002,
        )
        typed = classify_depth_queries(
            depths, valid, transitions, rows, columns, queries,
            "gt_events_shell_aware", 0.002,
        )
        np.testing.assert_array_equal(parity, [False, True, False, True, False])
        np.testing.assert_array_equal(typed, parity)

    def test_front_unknown_policies(self) -> None:
        depths = np.asarray([1.0], dtype=np.float32)[:, None, None]
        valid = np.ones_like(depths, dtype=bool)
        transitions = np.zeros_like(depths, dtype=np.int8)
        queries = np.asarray([0.99, 1.001, 1.02], dtype=np.float32)
        rows = np.zeros(len(queries), dtype=np.int64)
        columns = np.zeros(len(queries), dtype=np.int64)
        conservative = classify_depth_queries(
            depths, valid, transitions, rows, columns, queries,
            "gt_front_fixed_conservative", 0.002,
        )
        optimistic = classify_depth_queries(
            depths, valid, transitions, rows, columns, queries,
            "gt_front_fixed_optimistic", 0.002,
        )
        np.testing.assert_array_equal(conservative, [False, True, True])
        np.testing.assert_array_equal(optimistic, [False, True, False])

    def test_batch_matches_candidate_reference(self) -> None:
        rng = np.random.default_rng(12)
        candidate_points = rng.uniform(
            [-0.25, -0.20, 0.50], [0.25, 0.20, 1.40], size=(5, 37, 3)
        ).astype(np.float32)
        cameras = [
            {
                "camera_pose": np.eye(4, dtype=np.float32),
                "camera_intr": np.asarray(
                    [[70.0, 0.0, 9.5], [0.0, 70.0, 7.5], [0.0, 0.0, 1.0]],
                    dtype=np.float32,
                ),
            },
            {
                "camera_pose": np.asarray(
                    [[1.0, 0.0, 0.0, 0.03], [0.0, 1.0, 0.0, 0.0],
                     [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]],
                    dtype=np.float32,
                ),
                "camera_intr": np.asarray(
                    [[68.0, 0.0, 9.5], [0.0, 68.0, 7.5], [0.0, 0.0, 1.0]],
                    dtype=np.float32,
                ),
            },
        ]
        depths = np.broadcast_to(
            np.asarray([0.70, 0.75, 1.05, 1.10], dtype=np.float32)[:, None, None],
            (4, 16, 20),
        ).copy()
        valid = np.ones_like(depths, dtype=bool)
        transitions = np.broadcast_to(
            np.asarray([1, 2, 3, 4], dtype=np.int8)[:, None, None], depths.shape
        ).copy()
        events = [(depths, valid, transitions), (depths, valid, transitions)]

        batch_collision, batch_counts = collision_predictions_batch(
            candidate_points, cameras, events, 0.002
        )
        for candidate_index, points in enumerate(candidate_points):
            reference_collision, reference_counts = collision_predictions(
                points, cameras, events, 0.002
            )
            for policy in POLICIES:
                self.assertEqual(
                    bool(batch_collision[policy][candidate_index]), reference_collision[policy]
                )
                self.assertEqual(
                    int(batch_counts[policy][candidate_index]), reference_counts[policy]
                )
            self.assertEqual(
                int(batch_counts["projected_point_views"][candidate_index]),
                reference_counts["projected_point_views"],
            )


if __name__ == "__main__":
    unittest.main()
