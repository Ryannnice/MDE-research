#!/usr/bin/env python3
"""Audit a TablewareNet processed split before T²SQNet evaluation.

The audit records the actual pickle schema, selected-view availability and
class mix without pretending that any object class is a physical shell.  Shell
eligibility is decided later by the official primitive geometry in
``tablewarenet_shell_gt.py``.
"""

from __future__ import annotations

import argparse
import json
import pickle
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np


REQUIRED_KEYS = {
    "mask_imgs",
    "camera",
    "objects_pose",
    "objects_class",
    "objects_param",
    "workspace_origin",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True, help="directory containing processed .pkl scenes")
    parser.add_argument("--view-indices", default="15,16,17,18,19,20,21")
    parser.add_argument("--max-scenes", type=int)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def as_shape(value: Any) -> list[int]:
    if hasattr(value, "shape"):
        return [int(item) for item in value.shape]
    return list(np.asarray(value).shape)


def main() -> None:
    args = parse_args()
    root = args.data_root.resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    views = [int(item) for item in args.view_indices.split(",") if item]
    if not views or min(views) < 0:
        raise ValueError("view-indices must contain non-negative comma-separated integers")
    files = sorted(root.rglob("*.pkl"))
    if args.max_scenes is not None:
        if args.max_scenes < 1:
            raise ValueError("max-scenes must be positive")
        files = files[: args.max_scenes]
    if not files:
        raise FileNotFoundError(f"No .pkl scenes under {root}")

    class_counts: Counter[str] = Counter()
    bad_files: list[dict[str, Any]] = []
    valid_records: list[dict[str, Any]] = []
    for path in files:
        try:
            with path.open("rb") as handle:
                data = pickle.load(handle)
            missing = sorted(REQUIRED_KEYS - set(data))
            if missing:
                raise KeyError(f"missing required keys: {missing}")
            classes = [str(name) for name in data["objects_class"]]
            camera_count = len(data["camera"])
            mask_shape = as_shape(data["mask_imgs"])
            selected_available = all(index < camera_count for index in views)
            seven_view_fallback = camera_count == 7 and len(views) == 7
            if len(data["objects_pose"]) != len(classes) or len(data["objects_param"]) != len(classes):
                raise ValueError("objects_pose / objects_param lengths do not agree with objects_class")
            class_counts.update(classes)
            valid_records.append(
                {
                    "file": str(path.relative_to(root)),
                    "objects": len(classes),
                    "classes": classes,
                    "camera_count": camera_count,
                    "mask_shape": mask_shape,
                    "configured_views_available": selected_available,
                    "seven_view_fallback": seven_view_fallback,
                    "has_rgb": "rgb_imgs" in data,
                    "has_depth": "depth_imgs" in data,
                    "has_tsdf": "tsdf" in data,
                }
            )
        except Exception as error:  # audit must list corrupt files rather than silently skip them
            bad_files.append({"file": str(path.relative_to(root)), "error": f"{type(error).__name__}: {error}"})

    summary = {
        "data_root": str(root),
        "requested_view_indices": views,
        "scenes_discovered": len(files),
        "scenes_valid": len(valid_records),
        "scenes_invalid": len(bad_files),
        "class_counts": dict(sorted(class_counts.items())),
        "all_configured_views_available": bool(valid_records) and all(
            record["configured_views_available"] or record["seven_view_fallback"] for record in valid_records
        ),
        "records": valid_records,
        "invalid": bad_files,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key not in {"records", "invalid"}}, indent=2))
    if bad_files:
        raise RuntimeError(f"TablewareNet audit found {len(bad_files)} invalid scenes; see {args.output}")


if __name__ == "__main__":
    main()
