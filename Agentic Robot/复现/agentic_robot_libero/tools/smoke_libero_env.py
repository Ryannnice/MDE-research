#!/usr/bin/env python
"""Smoke test for the Agentic Robot LIBERO reproduction environment."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REPRO_ROOT = Path(__file__).resolve().parents[1]
AGENTIC_REPO = REPRO_ROOT / "repos" / "agentic-robot"
LIBERO_REPO = REPRO_ROOT / "repos" / "LIBERO"
OPENVLA_OFT_REPO = REPRO_ROOT / "repos" / "openvla-oft"

os.environ.setdefault("LIBERO_CONFIG_PATH", str(REPRO_ROOT / "data" / "libero_config"))
os.environ.setdefault("MUJOCO_GL", "osmesa")
os.environ.setdefault("PYOPENGL_PLATFORM", "osmesa")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

sys.path[:0] = [str(AGENTIC_REPO), str(LIBERO_REPO), str(OPENVLA_OFT_REPO)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="libero_spatial")
    parser.add_argument("--task-id", type=int, default=0)
    parser.add_argument("--resolution", type=int, default=128)
    args = parser.parse_args()

    from libero.libero import benchmark
    from experiments.robot.libero.libero_utils import (
        get_libero_dummy_action,
        get_libero_env,
        get_libero_image,
    )

    benchmark_dict = benchmark.get_benchmark_dict()
    task_suite = benchmark_dict[args.suite]()
    task = task_suite.get_task(args.task_id)
    initial_states = task_suite.get_task_init_states(args.task_id)

    env = None
    try:
        env, task_description = get_libero_env(task, "openvla", resolution=args.resolution)
        obs = env.set_init_state(initial_states[0])
        processed_image = get_libero_image(obs, args.resolution)
        obs, reward, done, info = env.step(get_libero_dummy_action("openvla"))

        payload = {
            "status": "SMOKE_LIBERO_OK",
            "suite": args.suite,
            "task_id": args.task_id,
            "n_tasks": task_suite.n_tasks,
            "task_language": task_description,
            "init_states_shape": list(initial_states.shape),
            "agentview_image_shape": list(obs["agentview_image"].shape),
            "processed_image_shape": list(processed_image.shape),
            "reward": float(reward),
            "done": bool(done),
            "info_keys": sorted(info.keys()),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    finally:
        if env is not None:
            env.close()


if __name__ == "__main__":
    main()
