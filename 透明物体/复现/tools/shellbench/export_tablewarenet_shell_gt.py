#!/usr/bin/env python3
"""Batch-export TablewareNet's model-induced physical-shell ray events.

The source is only the official TablewareNet superparaboloid mesh generator.
It has explicit inner and outer walls (``t=0.01``), so this script provides a
controlled physical-shell oracle for G0.  It is *not* a measured real-glass
thickness annotation.  Non-hollow primitives remain outside this initial
oracle rather than being relabelled as cavity geometry.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path
from typing import Any


THIS_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True, help="directory containing TablewareNet processed .pkl scenes")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--object-mode",
        choices=("per_hollow_object", "all_hollow"),
        default="per_hollow_object",
        help="per-object avoids ambiguous topology when objects occlude each other",
    )
    parser.add_argument(
        "--view-indices",
        default="",
        help="comma-separated source camera indices; empty selects every available camera",
    )
    parser.add_argument("--max-events", type=int, default=6)
    parser.add_argument("--epsilon-m", type=float, default=1e-4)
    parser.add_argument("--max-scenes", type=int, help="debug-only prefix of the sorted scene list")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def parse_views(value: str, camera_count: int) -> list[int]:
    if not value.strip():
        return list(range(camera_count))
    indices = [int(item) for item in value.split(",") if item.strip()]
    if not indices or len(set(indices)) != len(indices):
        raise ValueError("view-indices must be distinct comma-separated integers")
    if min(indices) < 0 or max(indices) >= camera_count:
        raise IndexError(f"view-indices must be in [0, {camera_count - 1}]")
    return indices


def scene_id(path: Path, data_root: Path) -> str:
    return "__".join(path.relative_to(data_root).with_suffix("").parts)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def object_metadata(data: dict[str, Any], object_index: int | None, as_numpy: Any) -> dict[str, Any] | None:
    if object_index is None:
        return None
    return {
        "class": str(data["objects_class"][object_index]),
        "pose_world": as_numpy(data["objects_pose"][object_index]).astype(float).tolist(),
        "params": as_numpy(data["objects_param"][object_index]).astype(float).reshape(-1).tolist(),
    }


def main() -> None:
    args = parse_args()
    if args.max_events < 1 or args.epsilon_m <= 0:
        raise ValueError("max-events and epsilon-m must be positive")
    official_root = args.official_root.resolve()
    data_root = args.data_root.resolve()
    output_dir = args.output_dir.resolve()
    if not (official_root / "tablewarenet" / "tableware.py").is_file():
        raise FileNotFoundError(f"Not a T²SQNet official checkout: {official_root}")
    if not data_root.is_dir():
        raise NotADirectoryError(data_root)
    sys.path.insert(0, str(THIS_DIR))
    sys.path.insert(0, str(official_root))
    from tablewarenet_shell_gt import as_numpy, build_hollow_meshes, cast_events, rays_from_camera

    files = sorted(data_root.rglob("*.pkl"))
    if args.max_scenes is not None:
        if args.max_scenes < 1:
            raise ValueError("max-scenes must be positive")
        files = files[: args.max_scenes]
    if not files:
        raise FileNotFoundError(f"No .pkl scenes under {data_root}")
    events_dir = output_dir / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for order, path in enumerate(files):
        with path.open("rb") as handle:
            data = pickle.load(handle)
        identifier = scene_id(path, data_root)
        cameras = data.get("camera")
        if cameras is None:
            skipped.append({"source_file": str(path.relative_to(data_root)), "reason": "missing camera"})
            continue
        try:
            views = parse_views(args.view_indices, len(cameras))
            if args.object_mode == "all_hollow":
                candidates: list[tuple[str, int | None]] = [("all_hollow", None)]
            else:
                candidates = [(f"object{index}", index) for index in range(len(data["objects_class"]))]
            for object_label, object_index in candidates:
                try:
                    meshes, provenance = build_hollow_meshes(data, object_index)
                except ValueError:
                    # Solid components are intentionally not made into a fake
                    # shell GT.  Retaining the skip in the manifest makes the
                    # exact evaluation slice explicit.
                    continue
                gt_object = object_metadata(data, object_index, as_numpy)
                for view_index in views:
                    filename = f"{identifier}__{object_label}__view{view_index}.npz"
                    event_path = events_dir / filename
                    if event_path.is_file() and not args.overwrite:
                        manifest.append(
                            {
                                "scene_id": identifier,
                                "scene_order": order,
                                "source_file": str(path.relative_to(data_root)),
                                "object_label": object_label,
                                "object_index": object_index,
                                "view_index": view_index,
                                "event_file": str(event_path.relative_to(output_dir)),
                                "hollow_primitives": provenance,
                                "ground_truth_object": gt_object,
                                "reused": True,
                            }
                        )
                        continue
                    rays, shape = rays_from_camera(cameras[view_index])
                    events = cast_events(meshes, rays, shape, args.max_events, args.epsilon_m)
                    events.save(event_path)
                    manifest.append(
                        {
                            "scene_id": identifier,
                            "scene_order": order,
                            "source_file": str(path.relative_to(data_root)),
                            "object_label": object_label,
                            "object_index": object_index,
                            "view_index": view_index,
                            "event_file": str(event_path.relative_to(output_dir)),
                            "shape_hw": list(shape),
                            "hollow_primitives": provenance,
                            "ground_truth_object": gt_object,
                            "reused": False,
                        }
                    )
        except Exception as error:
            skipped.append(
                {
                    "source_file": str(path.relative_to(data_root)),
                    "reason": f"{type(error).__name__}: {error}",
                }
            )

    summary: dict[str, Any] = {
        "geometry_source": "official TablewareNet superparaboloid mesh with wall_parameter_t=0.01",
        "scope": "model-induced physical-shell oracle; not measured real-wall GT",
        "official_root": str(official_root),
        "data_root": str(data_root),
        "object_mode": args.object_mode,
        "view_indices": args.view_indices or "all_available",
        "max_events": args.max_events,
        "epsilon_m": args.epsilon_m,
        "scenes_discovered": len(files),
        "event_frames": len(manifest),
        "skipped_scenes": len(skipped),
    }
    write_json(output_dir / "manifest.json", {"summary": summary, "items": manifest, "skipped": skipped})
    print(json.dumps(summary, indent=2, sort_keys=True))
    if skipped:
        raise RuntimeError(f"Skipped {len(skipped)} TablewareNet scenes; see {output_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
