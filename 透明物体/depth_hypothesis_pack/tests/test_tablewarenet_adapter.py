from __future__ import annotations

import unittest

import numpy as np

from anchor_tablewarenet import fit_robust_affine

from adapt_tablewarenet import prediction_events


class TablewareNetAdapterTest(unittest.TestCase):
    def test_background_affine_is_robust_to_outliers(self):
        prediction = np.linspace(0.5, 2.0, 1000)
        anchor = 0.4 * prediction + 0.3
        anchor[::50] += 5.0
        slope, offset, points = fit_robust_affine(prediction, anchor)
        self.assertGreater(points, 900)
        self.assertAlmostEqual(slope, 0.4, places=3)
        self.assertAlmostEqual(offset, 0.3, places=3)

    def test_axial_depth_and_uncertainty_are_converted_to_ray_range(self) -> None:
        depth = np.array([[[1.0]], [[2.0]], [[3.0]], [[4.0]]], dtype=np.float32)
        presence = np.array([[[0.9]], [[0.8]], [[0.4]], [[0.3]]], dtype=np.float32)
        uncertainty = np.full_like(depth, 0.1)
        values, valid, sigma = prediction_events(
            depth,
            presence,
            uncertainty,
            visible=np.array([[True]]),
            scale=np.array([[1.25]], dtype=np.float32),
            thresholds=[0.5, 0.5, 0.5, 0.5],
        )
        np.testing.assert_array_equal(valid[:, 0, 0], [True, True, False, False])
        np.testing.assert_allclose(values[:, 0, 0], [1.25, 2.5, 0.0, 0.0])
        np.testing.assert_allclose(sigma[:, 0, 0], [0.125, 0.125, 0.0, 0.0])

    def test_invisible_pixel_has_no_events(self) -> None:
        depth = np.ones((4, 1, 1), dtype=np.float32)
        presence = np.ones_like(depth)
        _, valid, _ = prediction_events(
            depth,
            presence,
            np.ones_like(depth),
            visible=np.array([[False]]),
            scale=np.array([[1.0]], dtype=np.float32),
            thresholds=[0.5, 0.5, 0.5, 0.5],
        )
        self.assertFalse(valid.any())


if __name__ == "__main__":
    unittest.main()
