#!/usr/bin/env python3
"""Dependency-light tests for the TablewareNet axial-depth adapter."""

from __future__ import annotations

import unittest

import numpy as np

from adapt_tablewarenet_depth_baseline import ray_scale, visible_object_mask


class TablewareNetDepthAdapterTest(unittest.TestCase):
    def test_axial_to_euclidean_ray_scale(self) -> None:
        intrinsics = np.asarray([[2.0, 0.0, 1.0], [0.0, 2.0, 0.0], [0.0, 0.0, 1.0]])
        scale = ray_scale(intrinsics, (1, 3))
        self.assertTrue(np.allclose(scale, [[np.sqrt(1.25), 1.0, np.sqrt(1.25)]]))

    def test_visibility_uses_axial_depth_not_ray_range(self) -> None:
        scale = np.asarray([[2.0, 1.0]], dtype=np.float32)
        rendered_axial = np.asarray([[0.5, 0.5]], dtype=np.float32)
        object_range = np.asarray([[1.0, 0.7]], dtype=np.float32)
        valid = np.ones((1, 2), dtype=bool)
        visible = visible_object_mask(rendered_axial, object_range, valid, scale, 0.01)
        self.assertTrue(np.array_equal(visible, [[True, False]]))

    def test_invalid_object_ray_is_never_visible(self) -> None:
        visible = visible_object_mask(
            np.asarray([[0.5]], dtype=np.float32),
            np.asarray([[0.5]], dtype=np.float32),
            np.asarray([[False]]),
            np.asarray([[1.0]], dtype=np.float32),
            0.01,
        )
        self.assertFalse(bool(visible[0, 0]))


if __name__ == "__main__":
    unittest.main()
