import unittest

import numpy as np

from dhp.data import collapse_missing_front_layers, sort_valid_depths


class LayeredDepthTargetTest(unittest.TestCase):
    def test_missing_front_layer_is_collapsed(self):
        depth = np.zeros((4, 2, 2), dtype=np.float32)
        depth[2, 0, 0] = 3.0
        collapsed = collapse_missing_front_layers(depth)
        self.assertEqual(collapsed[0, 0, 0], 3.0)
        self.assertEqual(np.count_nonzero(collapsed[:, 0, 0]), 1)

    def test_valid_depths_are_sorted_and_missing_is_last(self):
        depth = np.asarray([[[2.0]], [[0.0]], [[1.0]], [[4.0]]], dtype=np.float32)
        sorted_depth, valid = sort_valid_depths(depth)
        np.testing.assert_allclose(sorted_depth[:, 0, 0], [1.0, 2.0, 4.0, 0.0])
        np.testing.assert_array_equal(valid[:, 0, 0], [True, True, True, False])


if __name__ == "__main__":
    unittest.main()
