#!/usr/bin/env python3
"""Export physical multi-interface ray GT from a TablewareNet scene pickle.

TablewareNet's official superparaboloid generator explicitly builds an inner
and outer wall (`t=0.01`) for bowls/cups/dishes.  This adapter keeps that
generator as the source of geometry and casts camera rays against only those
hollow primitives.  It therefore produces a *model-induced physical-shell
oracle*, not a claim about real measured glass-wall thickness.

The output follows ``ray_events.py`` and is intended for the G0 representation
oracle and for evaluating cached predictions on a shared shell contract.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path
from typing import Any

import numpy as np

from ray_events import AIR_TO_SHELL, CAVITY_TO_SHELL, SHELL_TO_AIR, SHELL_TO_CAVITY, RayEvents


def as_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value)


def build_hollow_meshes(data: dict[str, Any], object_index: int | None) -> tuple[list[Any], list[dict[str, Any]]]:
    """Return official superparaboloid meshes and their object provenance."""

    from tablewarenet.tableware import name_to_class

    classes = list(data["objects_class"])
    poses = data["objects_pose"]
    params = data["objects_param"]
    indices = range(len(classes)) if object_index is None else [object_index]
    meshes: list[Any] = []
    provenance: list[dict[str, Any]] = []
    for index in indices:
        if index < 0 or index >= len(classes):
            raise IndexError(f"object index {index} not in [0, {len(classes) - 1}]")
        name = str(classes[index])
        pose = poses[index]
        param = params[index]
        object_model = name_to_class[name](pose, params=param, device="cpu", t=0.01, process_mesh=True)
        for primitive_index, primitive in enumerate(object_model.quadrics):
            if primitive.type != "superparaboloid":
                continue
            meshes.append(primitive.get_mesh(resolution_radial=48, resolution_height=32))
            provenance.append(
                {
                    "object_index": int(index),
                    "class": name,
                    "primitive_index": primitive_index,
                    "primitive_type": primitive.type,
                    "wall_parameter_t": 0.01,
                }
            )
    if not meshes:
        requested = "all objects" if object_index is None else f"object {object_index}"
        raise ValueError(f"{requested} contains no TablewareNet hollow superparaboloid primitive")
    return meshes, provenance


def rays_from_camera(camera: dict[str, Any]) -> tuple[np.ndarray, tuple[int, int]]:
    intrinsics = as_numpy(camera["camera_intr"]).astype(np.float64)
    pose = as_numpy(camera["camera_pose"]).astype(np.float64)
    width, height = [int(value) for value in as_numpy(camera["camera_image_size"]).reshape(-1)[:2]]
    col, row = np.meshgrid(np.arange(width, dtype=np.float64), np.arange(height, dtype=np.float64))
    directions_camera = np.stack(
        ((col - intrinsics[0, 2]) / intrinsics[0, 0], (row - intrinsics[1, 2]) / intrinsics[1, 1], np.ones_like(row)),
        axis=-1,
    )
    directions_world = directions_camera @ pose[:3, :3].T
    directions_world /= np.linalg.norm(directions_world, axis=-1, keepdims=True)
    origins = np.broadcast_to(pose[:3, 3], directions_world.shape)
    rays = np.concatenate((origins, directions_world), axis=-1).reshape(-1, 6).astype(np.float32)
    return rays, (height, width)


def cast_events(meshes: list[Any], rays: np.ndarray, shape: tuple[int, int], max_events: int, epsilon_m: float) -> RayEvents:
    """Iteratively ray-cast all visible interface crossings and label topology."""

    import open3d as o3d

    merged = meshes[0]
    for mesh in meshes[1:]:
        merged += mesh
    triangles = np.asarray(merged.triangles, dtype=np.int64)
    vertices = np.asarray(merged.vertices, dtype=np.float64)
    triangle_vertices = vertices[triangles]
    normals = np.cross(triangle_vertices[:, 1] - triangle_vertices[:, 0], triangle_vertices[:, 2] - triangle_vertices[:, 0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), np.finfo(np.float64).eps)

    scene = o3d.t.geometry.RaycastingScene()
    scene.add_triangles(o3d.t.geometry.TriangleMesh.from_legacy(merged))
    ray_origins = rays[:, :3].copy()
    ray_directions = rays[:, 3:].copy()
    ray_depth = np.zeros(len(rays), dtype=np.float32)
    depths = np.zeros((max_events, len(rays)), dtype=np.float32)
    valid = np.zeros((max_events, len(rays)), dtype=bool)
    entering = np.zeros((max_events, len(rays)), dtype=bool)

    for event_index in range(max_events):
        cast_rays = np.concatenate((ray_origins, ray_directions), axis=1)
        answer = scene.cast_rays(o3d.core.Tensor(cast_rays, dtype=o3d.core.Dtype.Float32))
        t_hit = answer["t_hit"].numpy()
        primitive_ids = answer["primitive_ids"].numpy()
        hit = np.isfinite(t_hit) & (t_hit > 0)
        if not np.any(hit):
            break
        hit_indices = np.flatnonzero(hit)
        depths[event_index, hit_indices] = ray_depth[hit_indices] + t_hit[hit_indices]
        valid[event_index, hit_indices] = True
        normal_dot_direction = np.einsum("ij,ij->i", normals[primitive_ids[hit_indices]], ray_directions[hit_indices])
        entering[event_index, hit_indices] = normal_dot_direction < 0
        step = t_hit[hit_indices] + epsilon_m
        ray_origins[hit_indices] += ray_directions[hit_indices] * step[:, None]
        ray_depth[hit_indices] += step

    transition = np.zeros_like(depths, dtype=np.int8)
    # A TablewareNet superparaboloid is an explicit pipe.  Along an isolated
    # ray, an outward-facing exit followed by another hit is a shell-to-cavity
    # transition; the final exit is shell-to-air.  Rays whose orientation does
    # not obey the state machine retain UNKNOWN rather than receiving invented
    # semantic labels.
    for ray_index in range(len(rays)):
        state = "air"
        for event_index in np.flatnonzero(valid[:, ray_index]):
            is_entering = bool(entering[event_index, ray_index])
            has_later_hit = bool(np.any(valid[event_index + 1 :, ray_index]))
            if is_entering and state == "air":
                transition[event_index, ray_index] = AIR_TO_SHELL
                state = "shell"
            elif is_entering and state == "cavity":
                transition[event_index, ray_index] = CAVITY_TO_SHELL
                state = "shell"
            elif not is_entering and state == "shell":
                transition[event_index, ray_index] = SHELL_TO_CAVITY if has_later_hit else SHELL_TO_AIR
                state = "cavity" if has_later_hit else "air"

    height, width = shape
    return RayEvents(
        depths.reshape(max_events, height, width),
        valid.reshape(max_events, height, width),
        transition.reshape(max_events, height, width),
    ).normalized()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-root", type=Path, required=True)
    parser.add_argument("--scene-pkl", type=Path, required=True)
    parser.add_argument("--view-index", type=int, default=0)
    parser.add_argument("--object-index", type=int, help="default: all hollow primitives in the scene")
    parser.add_argument("--max-events", type=int, default=6)
    parser.add_argument("--epsilon-m", type=float, default=1e-4)
    parser.add_argument("--output-npz", type=Path, required=True)
    args = parser.parse_args()
    if args.max_events < 1:
        raise ValueError("max-events must be positive")
    if args.epsilon_m <= 0:
        raise ValueError("epsilon-m must be positive")
    if not args.scene_pkl.is_file():
        raise FileNotFoundError(args.scene_pkl)
    if not (args.official_root / "tablewarenet" / "tableware.py").is_file():
        raise FileNotFoundError(f"Not a T²SQNet checkout: {args.official_root}")

    sys.path.insert(0, str(args.official_root.resolve()))
    with args.scene_pkl.open("rb") as handle:
        data = pickle.load(handle)
    cameras = data["camera"]
    if args.view_index < 0 or args.view_index >= len(cameras):
        raise IndexError(f"view index {args.view_index} not in [0, {len(cameras) - 1}]")
    meshes, provenance = build_hollow_meshes(data, args.object_index)
    rays, shape = rays_from_camera(cameras[args.view_index])
    events = cast_events(meshes, rays, shape, args.max_events, args.epsilon_m)
    args.output_npz.parent.mkdir(parents=True, exist_ok=True)
    events.save(args.output_npz)
    sidecar = {
        "scene_pkl": str(args.scene_pkl.resolve()),
        "view_index": args.view_index,
        "object_index": args.object_index,
        "shape_hw": list(shape),
        "max_events": args.max_events,
        "epsilon_m": args.epsilon_m,
        "geometry_source": "official TablewareNet superparaboloid mesh with wall_parameter_t=0.01",
        "scope": "model-induced physical-shell oracle; not measured real-wall GT",
        "hollow_primitives": provenance,
    }
    args.output_npz.with_suffix(".json").write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(sidecar, indent=2))


if __name__ == "__main__":
    main()
