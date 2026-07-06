#!/usr/bin/env python3
"""Prepare RMBench Goal2Skill data for the X-VLA dataloader.

This script adds a scalar ``language_instruction`` dataset to each RMBench
HDF5 episode and writes X-VLA meta JSON files for the five Goal2Skill tasks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import h5py


TASKS = (
    "observe_and_pickup",
    "rearrange_blocks",
    "battery_try",
    "blocks_ranking_try",
    "press_button",
)


def default_rmbench_root() -> Path:
    return Path(__file__).resolve().parents[1] / "repos" / "RMBench"


def load_instruction(task_root: Path, episode_idx: int) -> str:
    instruction_path = task_root / "instructions" / f"episode{episode_idx}.json"
    if instruction_path.exists():
        payload = json.loads(instruction_path.read_text(encoding="utf-8"))
        seen = payload.get("seen") or []
        if seen:
            return str(seen[0])

    annotations_path = task_root / "language_annotation.json"
    annotations = json.loads(annotations_path.read_text(encoding="utf-8"))
    parts = annotations.get(f"episode_{episode_idx}", [])
    deduped = []
    for item in parts:
        text = item[0] if isinstance(item, list) and item else str(item)
        if text not in deduped:
            deduped.append(text)
    if not deduped:
        raise ValueError(f"No instruction found for {task_root.name} episode {episode_idx}")
    return " ".join(deduped)


def write_language_instruction(hdf5_path: Path, instruction: str) -> None:
    string_dtype = h5py.string_dtype(encoding="utf-8")
    with h5py.File(hdf5_path, "r+") as handle:
        if "language_instruction" in handle:
            del handle["language_instruction"]
        handle.create_dataset("language_instruction", data=instruction, dtype=string_dtype)


def task_root(rmbench_root: Path, task: str, setting: str) -> Path:
    root = rmbench_root / "data" / task / setting
    if root.exists():
        return root.resolve()

    root = rmbench_root / "data" / "data" / task / setting
    if root.exists():
        return root.resolve()

    raise FileNotFoundError(f"Cannot find RMBench data for {task}/{setting}")


def build_meta(datalist: list[str]) -> dict:
    return {
        "dataset_name": "rmbench_abs_ee",
        "language_instruction_key": "language_instruction",
        "observation_key": ["observation/head_camera/rgb"],
        "datalist": datalist,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rmbench-root", type=Path, default=default_rmbench_root())
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--setting", default="demo_clean")
    parser.add_argument("--num-episodes", type=int, default=50)
    parser.add_argument("--skip-hdf5-write", action="store_true")
    args = parser.parse_args()

    rmbench_root = args.rmbench_root.resolve()
    output_dir = args.output_dir or (rmbench_root / "policy" / "X-VLA" / "meta_rmbench")
    output_dir.mkdir(parents=True, exist_ok=True)

    combined: list[str] = []
    for task in TASKS:
        root = task_root(rmbench_root, task, args.setting)
        datalist: list[str] = []
        for episode_idx in range(args.num_episodes):
            hdf5_path = root / "data" / f"episode{episode_idx}.hdf5"
            if not hdf5_path.exists():
                raise FileNotFoundError(hdf5_path)

            instruction = load_instruction(root, episode_idx)
            if not args.skip_hdf5_write:
                write_language_instruction(hdf5_path, instruction)
            datalist.append(str(hdf5_path.resolve()))

        meta_path = output_dir / f"{task}_{args.setting}_{args.num_episodes}.json"
        meta_path.write_text(
            json.dumps(build_meta(datalist), indent=2) + "\n",
            encoding="utf-8",
        )
        combined.extend(datalist)
        print(f"{task}: wrote {len(datalist)} episodes -> {meta_path}")

    combined_path = output_dir / f"goal2skill_5task_{args.setting}_{args.num_episodes}.json"
    combined_path.write_text(
        json.dumps(build_meta(combined), indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"combined: wrote {len(combined)} episodes -> {combined_path}")


if __name__ == "__main__":
    main()
