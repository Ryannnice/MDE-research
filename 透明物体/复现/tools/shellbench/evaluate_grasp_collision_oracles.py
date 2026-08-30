#!/usr/bin/env python3
"""Evaluate frozen T²SQNet grasp candidates with shell-event oracles.

Candidates come only from cached T²SQNet objects and the released primitive
grasp planner.  TablewareNet GT events are used solely by the collision
checker and offline safety audit.  This is a target-shell collision gate, not
a robot task-success experiment: it does not model IK, furniture, or other
objects.
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


THIS_DIR = Path(__file__).resolve().parent
T2_TOOLS = THIS_DIR.parent / "t2sqnet"

POLICIES = (
    "gt_front_fixed_conservative",
    "gt_front_fixed_optimistic",
    "gt_events_fixed_parity",
    "gt_events_shell_aware",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--ground-truth-root", type=Path, required=True)
    parser.add_argument("--prediction-objects-root", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument(
        "--single-depth-root",
        action="append",
        default=[],
        metavar="LABEL=DIR",
        help=(
            "repeatable output of adapt_tablewarenet_depth_baseline.py; "
            "adds optimistic/conservative collision policies on the same candidates"
        ),
    )
    parser.add_argument("--max-centre-distance-m", type=float, default=0.10)
    parser.add_argument("--surface-band-m", type=float, default=0.002)
    parser.add_argument("--gripper-points", type=int, default=2048)
    parser.add_argument("--approach-distance-m", type=float, default=0.15)
    parser.add_argument("--approach-copies", type=int, default=5)
    parser.add_argument("--bootstrap-replicates", type=int, default=2000)
    parser.add_argument(
        "--max-uniform-sampling-steps",
        type=int,
        default=4096,
        help="per-direction cap before the released planner's pathological sampler fallback",
    )
    parser.add_argument("--fallback-grid-samples", type=int, default=8192)
    parser.add_argument("--fallback-return-samples", type=int, default=72)
    parser.add_argument("--seed", type=int, default=0)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_labeled_roots(values: list[str]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"single-depth-root must be LABEL=DIR, got {value!r}")
        label, raw_path = value.split("=", 1)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", label):
            raise ValueError(f"Invalid single-depth label: {label!r}")
        if label in roots:
            raise ValueError(f"Duplicate single-depth label: {label}")
        root = Path(raw_path).expanduser().resolve()
        if not (root / "manifest.json").is_file() or not (root / "metrics.json").is_file():
            raise FileNotFoundError(f"Not a completed single-depth ShellBench adapter: {root}")
        roots[label] = root
    return roots


def bounded_uniform_sampling_2d(
    torch: Any,
    delta_theta: Any,
    exponent: Any,
    axis_a: Any,
    axis_b: Any,
    spacing: float,
    max_steps: int,
    fallback_grid_samples: int,
    fallback_return_samples: int,
) -> tuple[Any, bool]:
    """Preserve the upstream sampler unless its iterative loop is pathological."""

    theta_forward: Any = 0.0
    theta_backward: Any = torch.pi / 2
    theta_list: list[Any] = []
    for _ in range(max_steps):
        theta_backward = theta_backward - delta_theta(
            theta_backward, exponent, axis_a, axis_b, spacing
        )
        if theta_backward < 0:
            break
        theta_list.append(theta_backward)
    else:
        return (
            arc_length_superellipse_angles(
                torch,
                exponent,
                axis_a,
                axis_b,
                fallback_grid_samples,
                fallback_return_samples,
            ),
            True,
        )

    for _ in range(max_steps):
        theta_forward = theta_forward + delta_theta(
            theta_forward, exponent, axis_a, axis_b, spacing
        )
        if theta_forward > torch.pi / 2:
            break
        theta_list.append(theta_forward)
    else:
        return (
            arc_length_superellipse_angles(
                torch,
                exponent,
                axis_a,
                axis_b,
                fallback_grid_samples,
                fallback_return_samples,
            ),
            True,
        )

    theta_list_sorted = torch.sort(torch.tensor(theta_list))[0]
    result = torch.cat(
        [
            torch.tensor([0.0]),
            theta_list_sorted,
            torch.tensor([torch.pi / 2]),
            theta_list_sorted + torch.pi / 2,
            torch.tensor([torch.pi]),
            theta_list_sorted + torch.pi,
            torch.tensor([torch.pi * 3 / 2]),
            theta_list_sorted + torch.pi * 3 / 2,
        ],
        dim=0,
    )
    return result, False


def arc_length_superellipse_angles(
    torch: Any,
    exponent: Any,
    axis_a: Any,
    axis_b: Any,
    grid_samples: int,
    return_samples: int,
) -> Any:
    """Deterministic arc-length approximation for the pathological fallback."""

    dtype = axis_a.dtype
    device = axis_a.device
    theta = torch.linspace(0.0, 2 * torch.pi, grid_samples + 1, dtype=dtype, device=device)
    cosine = torch.cos(theta)
    sine = torch.sin(theta)
    x = axis_a * torch.sign(cosine) * torch.abs(cosine) ** exponent
    y = axis_b * torch.sign(sine) * torch.abs(sine) ** exponent
    segment_length = torch.sqrt(torch.diff(x) ** 2 + torch.diff(y) ** 2)
    cumulative = torch.cat(
        [torch.zeros(1, dtype=dtype, device=device), torch.cumsum(segment_length, dim=0)]
    )
    targets = (
        torch.arange(return_samples, dtype=dtype, device=device)
        * cumulative[-1]
        / return_samples
    )
    upper = torch.searchsorted(cumulative, targets, right=True).clamp(1, grid_samples)
    lower = upper - 1
    denominator = (cumulative[upper] - cumulative[lower]).clamp_min(
        torch.finfo(dtype).eps
    )
    fraction = (targets - cumulative[lower]) / denominator
    return theta[lower] + fraction * (theta[upper] - theta[lower])


def install_bounded_uniform_sampler(
    torch: Any,
    primitive_grasp_planner: Any,
    max_steps: int,
    fallback_grid_samples: int,
    fallback_return_samples: int,
) -> list[dict[str, float]]:
    """Install a run-local compatibility guard and return its audit list."""

    fallback_calls: list[dict[str, float]] = []

    def sampler(exponent: Any, axis_a: Any, axis_b: Any, spacing: float) -> Any:
        angles, used_fallback = bounded_uniform_sampling_2d(
            torch,
            primitive_grasp_planner.delta_theta,
            exponent,
            axis_a,
            axis_b,
            spacing,
            max_steps,
            fallback_grid_samples,
            fallback_return_samples,
        )
        if used_fallback:
            fallback_calls.append(
                {
                    "exponent": float(exponent),
                    "axis_a_m": float(axis_a),
                    "axis_b_m": float(axis_b),
                    "spacing_m": float(spacing),
                }
            )
        return angles

    primitive_grasp_planner.sq_uniform_sampling_2D = sampler
    return fallback_calls


def classify_depth_queries(
    depths_m: np.ndarray,
    valid_mask: np.ndarray,
    transition_type: np.ndarray,
    rows: np.ndarray,
    columns: np.ndarray,
    query_depth_m: np.ndarray,
    policy: str,
    surface_band_m: float,
) -> np.ndarray:
    """Classify query points already projected onto one event image."""

    depths = depths_m[:, rows, columns]
    valid = valid_mask[:, rows, columns]
    transitions = transition_type[:, rows, columns]
    crossed = valid & (depths <= query_depth_m[None])
    if policy == "gt_front_fixed_conservative":
        return valid[0] & (query_depth_m >= depths[0] - surface_band_m)
    if policy == "gt_front_fixed_optimistic":
        return valid[0] & (np.abs(query_depth_m - depths[0]) <= surface_band_m)
    if policy == "gt_events_fixed_parity":
        return (np.count_nonzero(crossed, axis=0) % 2) == 1
    if policy != "gt_events_shell_aware":
        raise ValueError(f"Unknown collision policy: {policy}")

    # 0=air, 1=shell, 2=cavity, 3=unknown/fail-safe occupied.
    state = np.zeros(len(rows), dtype=np.int8)
    for layer in range(depths.shape[0]):
        active = crossed[layer]
        transition = transitions[layer]
        next_state = state.copy()
        next_state[active & (state == 0) & (transition == 1)] = 1
        next_state[active & (state == 1) & (transition == 2)] = 2
        next_state[active & (state == 2) & (transition == 3)] = 1
        next_state[active & (state == 1) & (transition == 4)] = 0
        recognized = (
            ((state == 0) & (transition == 1))
            | ((state == 1) & (transition == 2))
            | ((state == 2) & (transition == 3))
            | ((state == 1) & (transition == 4))
        )
        next_state[active & ~recognized] = 3
        state = next_state
    return (state == 1) | (state == 3)


def project_points(points_world: np.ndarray, camera: dict[str, Any], shape_hw: tuple[int, int]) -> tuple[np.ndarray, ...]:
    pose = np.asarray(camera["camera_pose"], dtype=np.float64)
    intrinsics = np.asarray(camera["camera_intr"], dtype=np.float64)
    points_camera = (points_world - pose[:3, 3]) @ pose[:3, :3]
    z = points_camera[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        columns = np.rint(intrinsics[0, 0] * points_camera[:, 0] / z + intrinsics[0, 2]).astype(np.int64)
        rows = np.rint(intrinsics[1, 1] * points_camera[:, 1] / z + intrinsics[1, 2]).astype(np.int64)
    height, width = shape_hw
    visible = (z > 0) & (rows >= 0) & (rows < height) & (columns >= 0) & (columns < width)
    indices = np.flatnonzero(visible)
    ray_depth = np.linalg.norm(points_world[indices] - pose[:3, 3], axis=1)
    return indices, rows[indices], columns[indices], ray_depth


def collision_predictions(
    points_world: np.ndarray,
    cameras: list[dict[str, Any]],
    events: list[tuple[np.ndarray, np.ndarray, np.ndarray]],
    surface_band_m: float,
) -> tuple[dict[str, bool], dict[str, int]]:
    occupied = {policy: np.zeros(len(points_world), dtype=bool) for policy in POLICIES}
    projected_point_views = 0
    for camera, (depths, valid, transitions) in zip(cameras, events):
        indices, rows, columns, ray_depth = project_points(points_world, camera, depths.shape[1:])
        projected_point_views += len(indices)
        for policy in POLICIES:
            occupied[policy][indices] |= classify_depth_queries(
                depths,
                valid,
                transitions,
                rows,
                columns,
                ray_depth,
                policy,
                surface_band_m,
            )
    return (
        {policy: bool(np.any(values)) for policy, values in occupied.items()},
        {policy: int(np.count_nonzero(values)) for policy, values in occupied.items()} | {
            "projected_point_views": projected_point_views
        },
    )


def collision_predictions_batch(
    points_world: np.ndarray,
    cameras: list[dict[str, Any]],
    events: list[tuple[np.ndarray, np.ndarray, np.ndarray]],
    surface_band_m: float,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Vectorized equivalent of ``collision_predictions`` for N candidates."""

    if points_world.ndim != 3 or points_world.shape[-1] != 3:
        raise ValueError(f"Expected candidate x point x xyz array, got {points_world.shape}")
    candidate_count, point_count, _ = points_world.shape
    occupied = {
        policy: np.zeros((candidate_count, point_count), dtype=bool)
        for policy in POLICIES
    }
    projected_point_views = np.zeros(candidate_count, dtype=np.int64)
    if candidate_count == 0 or point_count == 0:
        return (
            {policy: np.zeros(candidate_count, dtype=bool) for policy in POLICIES},
            {policy: np.zeros(candidate_count, dtype=np.int64) for policy in POLICIES}
            | {"projected_point_views": projected_point_views},
        )

    flattened = points_world.reshape(-1, 3)
    for camera, (depths, valid, transitions) in zip(cameras, events):
        indices, rows, columns, ray_depth = project_points(flattened, camera, depths.shape[1:])
        projected_point_views += np.bincount(indices // point_count, minlength=candidate_count)
        for policy in POLICIES:
            occupied[policy].reshape(-1)[indices] |= classify_depth_queries(
                depths,
                valid,
                transitions,
                rows,
                columns,
                ray_depth,
                policy,
                surface_band_m,
            )
    return (
        {policy: np.any(values, axis=1) for policy, values in occupied.items()},
        {policy: np.count_nonzero(values, axis=1) for policy, values in occupied.items()}
        | {"projected_point_views": projected_point_views},
    )


def empty_counts() -> dict[str, int]:
    return {
        "objects": 0,
        "objects_with_safe_candidate": 0,
        "candidates": 0,
        "tp": 0,
        "tn": 0,
        "fp": 0,
        "fn": 0,
        "selected": 0,
        "selected_safe": 0,
        "selected_collision": 0,
        "rejected": 0,
    }


def add_counts(target: dict[str, int], source: dict[str, int]) -> None:
    for key, value in source.items():
        target[key] += int(value)


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def summarize_counts(counts: dict[str, int]) -> dict[str, Any]:
    collision_gt = counts["tp"] + counts["fn"]
    safe_gt = counts["tn"] + counts["fp"]
    return {
        **counts,
        "candidate_collision_recall": ratio(counts["tp"], collision_gt),
        "candidate_through_wall_false_negative_rate": ratio(counts["fn"], collision_gt),
        "candidate_safe_recall": ratio(counts["tn"], safe_gt),
        "candidate_overblocking_false_positive_rate": ratio(counts["fp"], safe_gt),
        "selection_rate": ratio(counts["selected"], counts["objects"]),
        "selected_collision_free_rate": ratio(counts["selected_safe"], counts["selected"]),
        "selected_collision_rate": ratio(counts["selected_collision"], counts["selected"]),
        "collision_free_selection_rate_all_objects": ratio(counts["selected_safe"], counts["objects"]),
        "safe_candidate_recovery_rate": ratio(
            counts["selected_safe"], counts["objects_with_safe_candidate"]
        ),
    }


def bootstrap_ci(
    scene_counts: dict[str, dict[str, dict[str, int]]],
    policy: str,
    numerator: str,
    denominator: str,
    replicates: int,
    seed: int,
) -> list[float] | None:
    scenes = sorted(scene_counts)
    if not scenes or replicates < 1:
        return None
    rng = np.random.default_rng(seed)
    values: list[float] = []
    for _ in range(replicates):
        selected = rng.choice(scenes, size=len(scenes), replace=True)
        num = sum(scene_counts[scene][policy][numerator] for scene in selected)
        den = sum(scene_counts[scene][policy][denominator] for scene in selected)
        if den:
            values.append(num / den)
    if not values:
        return None
    return [float(value) for value in np.percentile(values, [2.5, 97.5])]


def main() -> None:
    args = parse_args()
    if args.surface_band_m <= 0 or args.max_centre_distance_m <= 0:
        raise ValueError("distance thresholds must be positive")
    if args.gripper_points < 1 or args.approach_copies < 2 or args.bootstrap_replicates < 1:
        raise ValueError("gripper-points, approach-copies, and bootstrap-replicates are invalid")
    if (
        args.max_uniform_sampling_steps < 1
        or args.fallback_grid_samples < 4
        or args.fallback_return_samples < 1
    ):
        raise ValueError("bounded primitive-sampling arguments are invalid")
    official_root = args.official_root.resolve()
    data_root = args.data_root.resolve()
    gt_root = args.ground_truth_root.resolve()
    objects_root = args.prediction_objects_root.resolve()
    output_json = args.output_json.resolve()
    single_depth_roots = parse_labeled_roots(args.single_depth_root)
    single_depth_metadata = {
        label: load_json(root / "metrics.json")
        for label, root in single_depth_roots.items()
    }
    single_depth_policies = [
        f"{label}_fixed_{unknown_policy}"
        for label in single_depth_roots
        for unknown_policy in ("conservative", "optimistic")
    ]
    evaluation_policies = [*POLICIES, *single_depth_policies]
    if not (official_root / "tablewarenet" / "tableware.py").is_file():
        raise FileNotFoundError(f"Not a T²SQNet checkout: {official_root}")
    gt_payload = load_json(gt_root / "manifest.json")
    if gt_payload.get("summary", {}).get("object_mode") != "per_hollow_object":
        raise ValueError("ground truth must use per_hollow_object mode")
    if {tuple(item.get("shape_hw", [])) for item in gt_payload["items"]} != {(240, 320)}:
        raise ValueError("ground truth does not use the corrected TablewareNet [H,W] ray grid")

    sys.path.insert(0, str(official_root))
    sys.path.insert(0, str(T2_TOOLS))
    import open3d as o3d
    import torch

    from control.gripper import Gripper
    from evaluate_gt_mask_shell import match_objects, unique_gt_objects
    from tablewarenet.tableware import name_to_class
    from tablewarenet import primitive_grasp_planner

    os.chdir(official_root)
    o3d.utility.random.seed(args.seed)
    sampling_fallbacks = install_bounded_uniform_sampler(
        torch,
        primitive_grasp_planner,
        args.max_uniform_sampling_steps,
        args.fallback_grid_samples,
        args.fallback_return_samples,
    )
    gripper = Gripper(
        np.eye(4),
        0.08,
        contain_camera=True,
        locked_joint_7=-0.25 * np.pi,
    )
    gripper_points = gripper.get_gripper_afterimage_pc(
        pc_dtype="numpy",
        number_of_points=args.gripper_points,
        distance=args.approach_distance_m,
        n_gripper=args.approach_copies,
    ).astype(np.float32)

    gt_by_scene: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in gt_payload["items"]:
        gt_by_scene[str(item["scene_id"])].append(item)
    totals = {policy: empty_counts() for policy in evaluation_policies}
    scene_counts: dict[str, dict[str, dict[str, int]]] = {}
    class_counts: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: {policy: empty_counts() for policy in evaluation_policies}
    )
    object_records: list[dict[str, Any]] = []
    matching_totals = {"gt_objects": 0, "predicted_objects": 0, "matched_objects": 0}

    for scene_id, gt_items in sorted(gt_by_scene.items()):
        scene_file = data_root / str(gt_items[0]["source_file"])
        with scene_file.open("rb") as handle:
            data = pickle.load(handle)
        object_payload = load_json(objects_root / f"{scene_id}.json")
        predicted_objects = list(object_payload.get("predicted_objects", []))
        gt_objects = unique_gt_objects(gt_items)
        matches, _, _ = match_objects(gt_objects, predicted_objects, args.max_centre_distance_m)
        matching_totals["gt_objects"] += len(gt_objects)
        matching_totals["predicted_objects"] += len(predicted_objects)
        matching_totals["matched_objects"] += len(matches)
        scene_counts[scene_id] = {policy: empty_counts() for policy in evaluation_policies}

        items_by_object: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for item in gt_items:
            items_by_object[int(item["object_index"])].append(item)
        for gt_list_index, prediction_index, centre_distance in matches:
            gt_object = gt_objects[gt_list_index]
            gt_object_index = int(gt_object["object_index"])
            prediction = predicted_objects[prediction_index]
            predicted_model = name_to_class[str(prediction["class"])](
                torch.as_tensor(prediction["pose_world"], dtype=torch.float32),
                torch.as_tensor(prediction["params"], dtype=torch.float32),
                device="cpu",
                process_mesh=False,
            )
            fallback_count_before = len(sampling_fallbacks)
            grasps = predicted_model.get_grasp_poses(
                desired_dir_sq=torch.tensor([1, 0, 0]),
                dir_angle_bound_sq=0.4 * np.pi,
                flip_sq=True,
                desired_dir_sp=torch.tensor([1, 0, 0]),
                dir_angle_bound_sp=0.4 * np.pi,
                flip_sp=False,
            )
            if grasps.ndim != 3:
                grasps = torch.empty((0, 4, 4), dtype=torch.float32)
            view_items = sorted(items_by_object[gt_object_index], key=lambda item: int(item["view_index"]))
            cameras = [data["camera"][int(item["view_index"])] for item in view_items]
            events: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
            for item in view_items:
                with np.load(gt_root / item["event_file"]) as payload:
                    events.append(
                        (
                            payload["depths_m"],
                            payload["valid_mask"],
                            payload["transition_type"],
                        )
                    )
            grasps_numpy = grasps.detach().cpu().numpy().astype(np.float32, copy=False)
            points_world = np.einsum(
                "nij,pj->npi", grasps_numpy[:, :3, :3], gripper_points, optimize=True
            )
            points_world += grasps_numpy[:, None, :3, 3]
            collision, counts = collision_predictions_batch(
                points_world, cameras, events, args.surface_band_m
            )
            candidate_predictions = {
                policy: collision[policy].tolist() for policy in POLICIES
            }
            for label, root in single_depth_roots.items():
                single_depth_events: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
                for item in view_items:
                    view_index = int(item["view_index"])
                    event_path = (
                        root
                        / "events"
                        / f"{scene_id}_prediction{gt_list_index}_view{view_index}.npz"
                    )
                    if not event_path.is_file():
                        raise FileNotFoundError(
                            f"Single-depth source {label} is missing {event_path}"
                        )
                    with np.load(event_path) as payload:
                        single_depth_events.append(
                            (
                                payload["depths_m"],
                                payload["valid_mask"],
                                payload.get(
                                    "transition_type",
                                    np.zeros_like(payload["depths_m"], dtype=np.int8),
                                ),
                            )
                        )
                single_collision, _ = collision_predictions_batch(
                    points_world,
                    cameras,
                    single_depth_events,
                    args.surface_band_m,
                )
                candidate_predictions[f"{label}_fixed_conservative"] = single_collision[
                    "gt_front_fixed_conservative"
                ].tolist()
                candidate_predictions[f"{label}_fixed_optimistic"] = single_collision[
                    "gt_front_fixed_optimistic"
                ].tolist()
            projected_views = counts["projected_point_views"].tolist()
            ground_truth_collision = candidate_predictions["gt_events_fixed_parity"]
            has_safe_candidate = any(not value for value in ground_truth_collision)
            per_policy_record: dict[str, Any] = {}
            for policy in evaluation_policies:
                counts = empty_counts()
                counts["objects"] = 1
                counts["objects_with_safe_candidate"] = int(has_safe_candidate)
                counts["candidates"] = len(ground_truth_collision)
                predictions = candidate_predictions[policy]
                for predicted_collision, actual_collision in zip(predictions, ground_truth_collision):
                    if predicted_collision and actual_collision:
                        counts["tp"] += 1
                    elif not predicted_collision and not actual_collision:
                        counts["tn"] += 1
                    elif predicted_collision and not actual_collision:
                        counts["fp"] += 1
                    else:
                        counts["fn"] += 1
                selected_index = next((index for index, collision in enumerate(predictions) if not collision), None)
                if selected_index is None:
                    counts["rejected"] = 1
                else:
                    counts["selected"] = 1
                    actual_collision = ground_truth_collision[selected_index]
                    counts["selected_collision"] = int(actual_collision)
                    counts["selected_safe"] = int(not actual_collision)
                add_counts(totals[policy], counts)
                add_counts(scene_counts[scene_id][policy], counts)
                add_counts(class_counts[str(gt_object["class"])][policy], counts)
                per_policy_record[policy] = {
                    "selected_candidate_index": selected_index,
                    "counts": counts,
                }
            object_records.append(
                {
                    "scene_id": scene_id,
                    "gt_object_index": gt_object_index,
                    "prediction_index": prediction_index,
                    "class": str(gt_object["class"]),
                    "centre_distance_m": centre_distance,
                    "candidate_count": len(ground_truth_collision),
                    "ground_truth_collision_candidates": int(sum(ground_truth_collision)),
                    "ground_truth_safe_candidates": int(len(ground_truth_collision) - sum(ground_truth_collision)),
                    "bounded_sampling_fallback_calls": len(sampling_fallbacks) - fallback_count_before,
                    "mean_projected_point_views_per_candidate": float(np.mean(projected_views)) if projected_views else None,
                    "policies": per_policy_record,
                }
            )

    summarized: dict[str, Any] = {}
    for policy in evaluation_policies:
        summary = summarize_counts(totals[policy])
        summary["bootstrap_95_ci"] = {
            "collision_free_selection_rate_all_objects": bootstrap_ci(
                scene_counts,
                policy,
                "selected_safe",
                "objects",
                args.bootstrap_replicates,
                args.seed,
            ),
            "safe_candidate_recovery_rate": bootstrap_ci(
                scene_counts,
                policy,
                "selected_safe",
                "objects_with_safe_candidate",
                args.bootstrap_replicates,
                args.seed + 1,
            ),
            "selected_collision_rate": bootstrap_ci(
                scene_counts,
                policy,
                "selected_collision",
                "selected",
                args.bootstrap_replicates,
                args.seed + 2,
            ),
        }
        summarized[policy] = summary

    output = {
        "benchmark": "TablewareNet target-shell grasp-collision oracle",
        "run_kind": (
            "oracle_and_single_depth_models_on_supplied_corrected_ground_truth_manifest"
            if single_depth_roots
            else "oracle_on_supplied_corrected_ground_truth_manifest"
        ),
        "scope": "offline collision gate only; no IK, furniture, other-object collision, execution, or robot task-success claim",
        "candidate_source": "cached T2SQNet GT-mask predicted objects + released primitive grasp planner with an audited pathological-sampling guard",
        "candidate_generation_reads_ground_truth": False,
        "single_depth_collision_adapters_use_ground_truth": bool(single_depth_roots),
        "single_depth_adapter_scope": (
            "GT object identity/association and GT rendered first-surface visibility; "
            "no back-side hypothesis is added"
            if single_depth_roots
            else None
        ),
        "single_depth_sources": {
            label: {
                "root": str(single_depth_roots[label]),
                "method": metadata.get("method"),
                "input_protocol": metadata.get("input_protocol"),
                "adapter_oracles": metadata.get("adapter_oracles"),
            }
            for label, metadata in single_depth_metadata.items()
        },
        "ground_truth_collision_definition": "odd parity of all corrected TablewareNet shell intersections, fused conservatively across seven views",
        "camera_image_size_contract": "TablewareNet [height, width]",
        "evaluation_denominator": {
            "scenes": len(scene_counts),
            "ground_truth_event_frames": len(gt_payload["items"]),
            "matched_objects": matching_totals["matched_objects"],
        },
        "unknown_space_policies": {
            "gt_front_fixed_conservative": "all space behind the first interface is occupied",
            "gt_front_fixed_optimistic": f"only a +/- {args.surface_band_m} m band around the first interface is occupied",
        }
        | {
            f"{label}_fixed_conservative": "all space behind this model's visible single-depth event is occupied"
            for label in single_depth_roots
        }
        | {
            f"{label}_fixed_optimistic": f"only a +/- {args.surface_band_m} m band around this model's visible single-depth event is occupied"
            for label in single_depth_roots
        },
        "frozen_planner": {
            "gripper_points": args.gripper_points,
            "approach_distance_m": args.approach_distance_m,
            "approach_copies": args.approach_copies,
            "gripper_width_m": 0.08,
            "contain_camera": True,
            "locked_joint_7_rad": -0.25 * np.pi,
            "angle_bound_rad": 0.4 * np.pi,
            "selection": "first released-planner candidate predicted collision-free; reject if none",
        },
        "candidate_generation_compatibility": {
            "normal_case": "released iterative sq_uniform_sampling_2D output retained exactly",
            "pathological_case": "after the per-direction step cap, return a deterministic arc-length-uniform superellipse grid; upstream then applies its original candidate filtering",
            "max_uniform_sampling_steps_per_direction": args.max_uniform_sampling_steps,
            "fallback_grid_samples": args.fallback_grid_samples,
            "fallback_return_samples": args.fallback_return_samples,
            "fallback_calls": len(sampling_fallbacks),
            "fallback_parameters": sampling_fallbacks,
        },
        "matching": matching_totals | {"max_centre_distance_m": args.max_centre_distance_m},
        "policies": summarized,
        "failure_slices_by_class": {
            class_name: {policy: summarize_counts(counts) for policy, counts in policies.items()}
            for class_name, policies in sorted(class_counts.items())
        },
        "bootstrap": {"unit": "scene", "replicates": args.bootstrap_replicates, "seed": args.seed},
        "objects": object_records,
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in output.items() if key != "objects"}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
