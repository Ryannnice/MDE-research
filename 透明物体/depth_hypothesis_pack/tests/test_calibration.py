from __future__ import annotations

import unittest

import numpy as np

from calibrate_presence import best_threshold


class PresenceCalibrationTest(unittest.TestCase):
    def test_best_threshold_separates_histograms(self) -> None:
        positive = np.array([0, 0, 1, 4], dtype=np.int64)
        negative = np.array([4, 1, 0, 0], dtype=np.int64)
        result = best_threshold(positive, negative)
        self.assertEqual(result["f1"], 1.0)
        self.assertGreaterEqual(result["threshold"], 0.5)


if __name__ == "__main__":
    unittest.main()
