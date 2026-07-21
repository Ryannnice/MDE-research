#!/usr/bin/env python3
"""Unit tests for the LayeredDepth prediction evaluator."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np


MODULE_PATH = Path(__file__).with_name("evaluate_predictions.py")
SPEC = importlib.util.spec_from_file_location("evaluate_predictions", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TupleEvaluationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.layers = np.zeros((4, 2, 2), dtype=np.float32)
        self.layers[0] = 1.0
        self.layers[1] = 2.0
        self.valid = self.layers > 0

    def test_real_pair_uses_requested_layer(self) -> None:
        pair = {
            "p1": [0, 0, 1],
            "p2": [0, 0, 3],
            "is_real": True,
        }
        self.assertTrue(MODULE.tuple_correct(pair, self.layers, self.valid))

    def test_fake_tuple_requires_absent_layer(self) -> None:
        fake_third_layer = {
            "p1": [0, 0, 5],
            "p2": [1, 1, 5],
            "is_real": False,
        }
        self.assertTrue(
            MODULE.tuple_correct(fake_third_layer, self.layers, self.valid)
        )

    def test_single_depth_fails_real_second_layer(self) -> None:
        single_layer = self.layers[:1]
        single_valid = self.valid[:1]
        real_second_layer = {
            "p1": [0, 0, 3],
            "p2": [1, 1, 3],
            "is_real": True,
        }
        self.assertFalse(
            MODULE.tuple_correct(real_second_layer, single_layer, single_valid)
        )

    def test_inverse_depth_conversion(self) -> None:
        inverse = np.array([[2.0, 4.0], [0.0, np.nan]], dtype=np.float32)
        valid = np.isfinite(inverse) & (inverse > 0)
        depth = np.zeros_like(inverse)
        np.divide(1.0, inverse, out=depth, where=valid)
        np.testing.assert_allclose(depth, [[0.5, 0.25], [0.0, 0.0]])

    def test_depths_at_or_below_official_threshold_are_absent(self) -> None:
        layers = np.array([[[0.02]], [[0.03]]], dtype=np.float32)
        valid = np.ones_like(layers, dtype=bool)
        depths = MODULE.unique_sorted_depths(layers, valid, 0, 0)
        self.assertEqual(len(depths), 1)
        self.assertAlmostEqual(depths[0], 0.03)

    def test_loads_seegroup_npz_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "4.npz"
            np.savez_compressed(
                cache,
                layers_m=self.layers,
                valid_mask=self.valid,
            )
            layers, valid, files = MODULE.load_layers(
                Path(directory),
                "4",
                (2, 2),
                "depth",
                "odd",
                "seegroup-npz",
            )
        np.testing.assert_array_equal(layers, self.layers)
        np.testing.assert_array_equal(valid, self.valid)
        self.assertEqual(files, [cache.as_posix()])

    def test_official_protocol_drops_even_layer_labels(self) -> None:
        pair = {
            "p1": [0, 0, 2],
            "p2": [1, 1, 2],
            "is_real": False,
        }
        self.assertFalse(MODULE.tuple_in_official_protocol(pair, (2, 2)))


if __name__ == "__main__":
    unittest.main()
