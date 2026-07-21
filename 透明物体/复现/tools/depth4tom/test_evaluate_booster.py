#!/usr/bin/env python3
"""Unit tests for explicit Booster prediction semantics."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import cv2
import numpy as np


MODULE_PATH = Path(__file__).with_name("evaluate_booster.py")
SPEC = importlib.util.spec_from_file_location("evaluate_booster", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def least_squares(prediction, target, mask):
    selected_prediction = prediction[mask > 0]
    selected_target = target[mask > 0]
    design = np.stack(
        [selected_prediction, np.ones_like(selected_prediction)],
        axis=1,
    )
    scale, shift = np.linalg.lstsq(design, selected_target, rcond=None)[0]
    return float(scale), float(shift)


class BoosterEvaluationTest(unittest.TestCase):
    def test_raw_metric_depth_is_converted_to_millimetres(self) -> None:
        prediction = np.array([[1.0, 2.0]], dtype=np.float32)
        depth = MODULE.prediction_depth_mm(
            prediction,
            "depth",
            "none",
            np.ones_like(prediction),
            np.ones_like(prediction, dtype=bool),
            100.0,
            10.0,
            1.0,
            10000.0,
            least_squares,
        )
        np.testing.assert_allclose(depth, [[1000.0, 2000.0]])

    def test_affine_alignment_operates_in_inverse_depth(self) -> None:
        depth_m = np.array([[1.0, 0.5, 0.25]], dtype=np.float32)
        target_disparity = np.array([[3.0, 5.0, 9.0]], dtype=np.float32)
        aligned = MODULE.align_inverse_depth(
            depth_m,
            "depth",
            target_disparity,
            np.ones_like(depth_m, dtype=bool),
            least_squares,
        )
        np.testing.assert_allclose(aligned, target_disparity, atol=1e-5)

    def test_perfect_prediction_has_perfect_metrics(self) -> None:
        target = np.array([[100.0, 200.0]], dtype=np.float32)
        metrics = MODULE.booster_metrics(
            target,
            target,
            np.ones_like(target, dtype=bool),
        )
        self.assertEqual(metrics["rmse"], 0.0)
        self.assertEqual(metrics["absrel"], 0.0)
        self.assertEqual(metrics["delta1.05"], 100.0)

    def test_upstream_positional_resize_is_effectively_bilinear(self) -> None:
        prediction = np.array(
            [[0.0, 1.0], [2.0, 4.0]],
            dtype=np.float32,
        )
        upstream_style = cv2.resize(
            prediction,
            (7, 7),
            cv2.INTER_CUBIC,
        )
        explicit_linear = cv2.resize(
            prediction,
            (7, 7),
            interpolation=cv2.INTER_LINEAR,
        )
        explicit_cubic = cv2.resize(
            prediction,
            (7, 7),
            interpolation=cv2.INTER_CUBIC,
        )
        np.testing.assert_array_equal(upstream_style, explicit_linear)
        self.assertFalse(np.array_equal(upstream_style, explicit_cubic))


if __name__ == "__main__":
    unittest.main()
