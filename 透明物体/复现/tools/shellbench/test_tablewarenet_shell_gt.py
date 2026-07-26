#!/usr/bin/env python3
"""Integration test for the TablewareNet physical-shell ray caster.

This test intentionally uses the upstream superparaboloid mesh constructor,
rather than a hand-made proxy.  A horizontal ray through the wall of an open
cup must encounter the outer shell, the cavity, the far shell, then air.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


THIS_DIR = Path(__file__).resolve().parent
TRANSPARENT_ROOT = THIS_DIR.parents[2]
T2_ROOT = TRANSPARENT_ROOT / "external" / "t2sqnet" / "official"
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(T2_ROOT))

from ray_events import AIR_TO_SHELL, CAVITY_TO_SHELL, SHELL_TO_AIR, SHELL_TO_CAVITY  # noqa: E402
from tablewarenet.primitives import mesh_superparaboloid  # noqa: E402
from tablewarenet_shell_gt import cast_events  # noqa: E402


def test_cup_side_ray_has_four_interfaces() -> None:
    mesh = mesh_superparaboloid(
        np.asarray([0.10, 0.10, 0.12, 1.0, 1.0, 0.0], dtype=np.float64),
        resolution_radial=64,
        resolution_height=32,
        t=0.01,
        process_mesh=True,
    )
    # The ray passes through the side wall below the rim and therefore avoids
    # the open top.  Distances are in metres and positive in camera-ray space.
    rays = np.asarray([[-0.30, 0.0, -0.05, 1.0, 0.0, 0.0]], dtype=np.float32)
    events = cast_events([mesh], rays, shape=(1, 1), max_events=6, epsilon_m=1e-4)
    valid_depths = events.depths_m[events.valid_mask[:, 0, 0], 0, 0]
    valid_types = events.transition_type[events.valid_mask[:, 0, 0], 0, 0]
    assert len(valid_depths) == 4, valid_depths
    assert np.all(np.diff(valid_depths) > 0), valid_depths
    assert valid_types.tolist() == [
        AIR_TO_SHELL,
        SHELL_TO_CAVITY,
        CAVITY_TO_SHELL,
        SHELL_TO_AIR,
    ], valid_types


if __name__ == "__main__":
    test_cup_side_ray_has_four_interfaces()
    print("TablewareNet shell ray-caster integration test: OK")
