#!/usr/bin/env python3
"""Canonical ray-event representation and evaluator for ShellBench.

The representation intentionally supports partial geometry.  A single-depth
method exports one valid event per ray; it must not invent deeper layers or
claim that unknown space is occupied.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

try:
    from numba import njit
except ImportError:  # pragma: no cover - the portable Python evaluator remains available
    njit = None


SCHEMA_VERSION = 1
UNKNOWN = 0
AIR_TO_SHELL = 1
SHELL_TO_CAVITY = 2
CAVITY_TO_SHELL = 3
SHELL_TO_AIR = 4


def _shape_error(name: str, array: np.ndarray, shape: tuple[int, ...]) -> ValueError:
    return ValueError(f"{name} has shape {array.shape}; expected {shape}")


@dataclass
class RayEvents:
    """Ordered metric intersections for one camera frame.

    ``depths_m`` and ``valid_mask`` have shape ``[layers, height, width]``.
    Transition labels use 0 for unsupported/unknown rather than fabricating a
    semantic event.  Valid events are normalized to ascending metric depth.
    """

    depths_m: np.ndarray
    valid_mask: np.ndarray
    transition_type: np.ndarray | None = None
    uncertainty_m: np.ndarray | None = None

    def __post_init__(self) -> None:
        self.depths_m = np.asarray(self.depths_m, dtype=np.float32)
        self.valid_mask = np.asarray(self.valid_mask, dtype=bool)
        if self.depths_m.ndim != 3:
            raise ValueError(f"depths_m must be [K,H,W], got {self.depths_m.shape}")
        if self.valid_mask.shape != self.depths_m.shape:
            raise _shape_error("valid_mask", self.valid_mask, self.depths_m.shape)
        if self.transition_type is None:
            self.transition_type = np.zeros_like(self.depths_m, dtype=np.int8)
        else:
            self.transition_type = np.asarray(self.transition_type, dtype=np.int8)
            if self.transition_type.shape != self.depths_m.shape:
                raise _shape_error("transition_type", self.transition_type, self.depths_m.shape)
        if self.uncertainty_m is not None:
            self.uncertainty_m = np.asarray(self.uncertainty_m, dtype=np.float32)
            if self.uncertainty_m.shape != self.depths_m.shape:
                raise _shape_error("uncertainty_m", self.uncertainty_m, self.depths_m.shape)
        if np.any(self.valid_mask & ~np.isfinite(self.depths_m)):
            raise ValueError("Valid events must have finite depths")
        if np.any(self.valid_mask & (self.depths_m <= 0)):
            raise ValueError("Valid events must have positive metric depths")

    @property
    def shape(self) -> tuple[int, int, int]:
        return tuple(self.depths_m.shape)

    @classmethod
    def empty(cls, layers: int, height: int, width: int) -> "RayEvents":
        shape = (layers, height, width)
        return cls(np.zeros(shape, dtype=np.float32), np.zeros(shape, dtype=bool))

    def normalized(self) -> "RayEvents":
        """Sort valid events and compact invalid entries to the trailing slots."""

        sort_depth = np.where(self.valid_mask, self.depths_m, np.inf)
        order = np.argsort(sort_depth, axis=0, kind="stable")
        depths = np.take_along_axis(self.depths_m, order, axis=0)
        valid = np.take_along_axis(self.valid_mask, order, axis=0)
        transition = np.take_along_axis(self.transition_type, order, axis=0)
        uncertainty = (
            None
            if self.uncertainty_m is None
            else np.take_along_axis(self.uncertainty_m, order, axis=0)
        )
        depths = np.where(valid, depths, 0).astype(np.float32)
        transition = np.where(valid, transition, UNKNOWN).astype(np.int8)
        if uncertainty is not None:
            uncertainty = np.where(valid, uncertainty, 0).astype(np.float32)
        return RayEvents(depths, valid, transition, uncertainty)

    def first_layers(self, count: int, keep_transitions: bool = True) -> "RayEvents":
        if count < 1:
            raise ValueError("count must be positive")
        source = self.normalized()
        count = min(count, source.depths_m.shape[0])
        transitions = source.transition_type[:count] if keep_transitions else None
        uncertainty = None if source.uncertainty_m is None else source.uncertainty_m[:count]
        return RayEvents(source.depths_m[:count], source.valid_mask[:count], transitions, uncertainty)

    def without_transitions(self) -> "RayEvents":
        source = self.normalized()
        return RayEvents(source.depths_m, source.valid_mask, None, source.uncertainty_m)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": np.asarray([SCHEMA_VERSION], dtype=np.int16),
            "depths_m": self.depths_m.astype(np.float32),
            "valid_mask": self.valid_mask.astype(bool),
            "transition_type": self.transition_type.astype(np.int8),
        }
        if self.uncertainty_m is not None:
            payload["uncertainty_m"] = self.uncertainty_m.astype(np.float32)
        np.savez_compressed(path, **payload)

    @classmethod
    def load(cls, path: str | Path) -> "RayEvents":
        with np.load(path) as payload:
            if "depths_m" not in payload or "valid_mask" not in payload:
                raise ValueError(f"{path} is not a ShellBench ray-event NPZ")
            return cls(
                payload["depths_m"],
                payload["valid_mask"],
                payload["transition_type"] if "transition_type" in payload else None,
                payload["uncertainty_m"] if "uncertainty_m" in payload else None,
            )


def single_depth_events(depth_m: np.ndarray, valid_mask: np.ndarray | None = None) -> RayEvents:
    """Convert a metric completed-depth map to one event per ray."""

    depth_m = np.asarray(depth_m, dtype=np.float32)
    if depth_m.ndim != 2:
        raise ValueError(f"depth_m must be [H,W], got {depth_m.shape}")
    if valid_mask is None:
        valid_mask = np.isfinite(depth_m) & (depth_m > 0)
    valid_mask = np.asarray(valid_mask, dtype=bool)
    if valid_mask.shape != depth_m.shape:
        raise _shape_error("valid_mask", valid_mask, depth_m.shape)
    return RayEvents(depth_m[None], valid_mask[None])


def _ordered_pairs(pred: np.ndarray, gt: np.ndarray, delta_m: float) -> list[tuple[int, int]]:
    """Maximum-cardinality, minimum-error order-constrained event matching."""

    rows, cols = len(pred), len(gt)
    matches = np.zeros((rows + 1, cols + 1), dtype=np.int16)
    costs = np.zeros((rows + 1, cols + 1), dtype=np.float64)
    choice = np.zeros((rows + 1, cols + 1), dtype=np.int8)
    for row in range(1, rows + 1):
        for col in range(1, cols + 1):
            candidates = [
                (matches[row - 1, col], costs[row - 1, col], 1),
                (matches[row, col - 1], costs[row, col - 1], 2),
            ]
            error = abs(float(pred[row - 1] - gt[col - 1]))
            if error <= delta_m:
                candidates.append((matches[row - 1, col - 1] + 1, costs[row - 1, col - 1] + error, 3))
            best = min(candidates, key=lambda item: (-item[0], item[1], item[2]))
            matches[row, col], costs[row, col], choice[row, col] = best
    result: list[tuple[int, int]] = []
    row, col = rows, cols
    while row and col:
        step = choice[row, col]
        if step == 3:
            result.append((row - 1, col - 1))
            row -= 1
            col -= 1
        elif step == 1:
            row -= 1
        else:
            col -= 1
    return list(reversed(result))


def _topology_valid(types: np.ndarray) -> bool:
    state = "air"
    for transition in types:
        if transition == AIR_TO_SHELL and state == "air":
            state = "shell"
        elif transition == SHELL_TO_CAVITY and state == "shell":
            state = "cavity"
        elif transition == CAVITY_TO_SHELL and state == "cavity":
            state = "shell"
        elif transition == SHELL_TO_AIR and state == "shell":
            state = "air"
        else:
            return False
    return state == "air"


def empty_statistics() -> dict[str, float]:
    return {
        "rays": 0,
        "count_correct": 0,
        "pred_events": 0,
        "gt_events": 0,
        "matched_events": 0,
        "abs_error_sum_m": 0.0,
        "squared_error_sum_m2": 0.0,
        "pred_typed_events": 0,
        "gt_typed_events": 0,
        "matched_typed_events": 0,
        "correct_typed_events": 0,
        "topology_labeled_rays": 0,
        "topology_valid_rays": 0,
    }


def add_statistics(target: dict[str, float], source: dict[str, float]) -> None:
    for key, value in source.items():
        target[key] = target.get(key, 0) + value


def _event_statistics_python(pred: RayEvents, gt: RayEvents, delta_m: float) -> dict[str, float]:
    """Portable reference implementation for an already-normalized pair."""

    stats = empty_statistics()
    _, height, width = gt.shape
    for row in range(height):
        for col in range(width):
            pred_valid = pred.valid_mask[:, row, col]
            gt_valid = gt.valid_mask[:, row, col]
            p_depth = pred.depths_m[pred_valid, row, col]
            g_depth = gt.depths_m[gt_valid, row, col]
            p_type = pred.transition_type[pred_valid, row, col]
            g_type = gt.transition_type[gt_valid, row, col]
            pairs = _ordered_pairs(p_depth, g_depth, delta_m)
            stats["rays"] += 1
            stats["count_correct"] += int(len(p_depth) == len(g_depth))
            stats["pred_events"] += len(p_depth)
            stats["gt_events"] += len(g_depth)
            # Count every labelled interface before matching.  Counting only
            # matched events would hide spurious labelled transitions from the
            # precision denominator.
            stats["pred_typed_events"] += int(np.count_nonzero(p_type != UNKNOWN))
            stats["gt_typed_events"] += int(np.count_nonzero(g_type != UNKNOWN))
            stats["matched_events"] += len(pairs)
            for p_index, g_index in pairs:
                error = abs(float(p_depth[p_index] - g_depth[g_index]))
                stats["abs_error_sum_m"] += error
                stats["squared_error_sum_m2"] += error * error
                if p_type[p_index] != UNKNOWN and g_type[g_index] != UNKNOWN:
                    stats["matched_typed_events"] += 1
                    stats["correct_typed_events"] += int(p_type[p_index] == g_type[g_index])
            if len(p_type) and np.all(p_type != UNKNOWN):
                stats["topology_labeled_rays"] += 1
                stats["topology_valid_rays"] += int(_topology_valid(p_type))
    return stats


if njit is not None:

    @njit(cache=True)
    def _event_statistics_kernel(
        pred_depths: np.ndarray,
        pred_valid: np.ndarray,
        pred_types: np.ndarray,
        gt_depths: np.ndarray,
        gt_valid: np.ndarray,
        gt_types: np.ndarray,
        delta_m: float,
    ) -> np.ndarray:
        """Numba equivalent of the order-constrained per-ray reference loop."""

        pred_layers, height, width = pred_depths.shape
        gt_layers = gt_depths.shape[0]
        result = np.zeros(13, dtype=np.float64)
        matches = np.zeros((pred_layers + 1, gt_layers + 1), dtype=np.int16)
        costs = np.zeros((pred_layers + 1, gt_layers + 1), dtype=np.float64)
        choice = np.zeros((pred_layers + 1, gt_layers + 1), dtype=np.int8)
        for image_row in range(height):
            for image_col in range(width):
                pred_count = 0
                gt_count = 0
                pred_typed = 0
                gt_typed = 0
                for layer in range(pred_layers):
                    if pred_valid[layer, image_row, image_col]:
                        pred_count += 1
                        if pred_types[layer, image_row, image_col] != UNKNOWN:
                            pred_typed += 1
                for layer in range(gt_layers):
                    if gt_valid[layer, image_row, image_col]:
                        gt_count += 1
                        if gt_types[layer, image_row, image_col] != UNKNOWN:
                            gt_typed += 1

                result[0] += 1
                if pred_count == gt_count:
                    result[1] += 1
                result[2] += pred_count
                result[3] += gt_count
                result[7] += pred_typed
                result[8] += gt_typed

                for row in range(pred_count + 1):
                    for col in range(gt_count + 1):
                        matches[row, col] = 0
                        costs[row, col] = 0.0
                        choice[row, col] = 0
                for row in range(1, pred_count + 1):
                    for col in range(1, gt_count + 1):
                        best_matches = matches[row - 1, col]
                        best_cost = costs[row - 1, col]
                        best_choice = 1

                        candidate_matches = matches[row, col - 1]
                        candidate_cost = costs[row, col - 1]
                        if candidate_matches > best_matches or (
                            candidate_matches == best_matches and candidate_cost < best_cost
                        ):
                            best_matches = candidate_matches
                            best_cost = candidate_cost
                            best_choice = 2

                        error = abs(
                            np.float64(
                                pred_depths[row - 1, image_row, image_col]
                                - gt_depths[col - 1, image_row, image_col]
                            )
                        )
                        if error <= delta_m:
                            candidate_matches = matches[row - 1, col - 1] + 1
                            candidate_cost = costs[row - 1, col - 1] + error
                            if candidate_matches > best_matches or (
                                candidate_matches == best_matches and candidate_cost < best_cost
                            ):
                                best_matches = candidate_matches
                                best_cost = candidate_cost
                                best_choice = 3
                        matches[row, col] = best_matches
                        costs[row, col] = best_cost
                        choice[row, col] = best_choice

                row = pred_count
                col = gt_count
                while row > 0 and col > 0:
                    step = choice[row, col]
                    if step == 3:
                        pred_type = pred_types[row - 1, image_row, image_col]
                        gt_type = gt_types[col - 1, image_row, image_col]
                        error = abs(
                            np.float64(
                                pred_depths[row - 1, image_row, image_col]
                                - gt_depths[col - 1, image_row, image_col]
                            )
                        )
                        result[4] += 1
                        result[5] += error
                        result[6] += error * error
                        if pred_type != UNKNOWN and gt_type != UNKNOWN:
                            result[9] += 1
                            if pred_type == gt_type:
                                result[10] += 1
                        row -= 1
                        col -= 1
                    elif step == 1:
                        row -= 1
                    else:
                        col -= 1

                if pred_count > 0 and pred_typed == pred_count:
                    result[11] += 1
                    state = 0  # 0=air, 1=shell, 2=cavity, 3=invalid
                    for layer in range(pred_count):
                        transition = pred_types[layer, image_row, image_col]
                        if transition == AIR_TO_SHELL and state == 0:
                            state = 1
                        elif transition == SHELL_TO_CAVITY and state == 1:
                            state = 2
                        elif transition == CAVITY_TO_SHELL and state == 2:
                            state = 1
                        elif transition == SHELL_TO_AIR and state == 1:
                            state = 0
                        else:
                            state = 3
                            break
                    if state == 0:
                        result[12] += 1
        return result

else:
    _event_statistics_kernel = None


_STATISTIC_KEYS = tuple(empty_statistics())


def _normalized_pair(
    prediction: RayEvents, ground_truth: RayEvents, delta_m: float
) -> tuple[RayEvents, RayEvents]:
    if delta_m <= 0:
        raise ValueError("delta_m must be positive")
    pred = prediction.normalized()
    gt = ground_truth.normalized()
    if pred.shape[1:] != gt.shape[1:]:
        raise ValueError(f"Image shapes differ: {pred.shape[1:]} vs {gt.shape[1:]}")
    return pred, gt


def _event_statistics_reference(
    prediction: RayEvents, ground_truth: RayEvents, delta_m: float
) -> dict[str, float]:
    """Test hook for exact comparison with the portable implementation."""

    pred, gt = _normalized_pair(prediction, ground_truth, delta_m)
    return _event_statistics_python(pred, gt, delta_m)


def event_statistics(prediction: RayEvents, ground_truth: RayEvents, delta_m: float) -> dict[str, float]:
    """Return additive event-matching statistics for one frame."""

    pred, gt = _normalized_pair(prediction, ground_truth, delta_m)
    if _event_statistics_kernel is None:
        return _event_statistics_python(pred, gt, delta_m)
    values = _event_statistics_kernel(
        pred.depths_m,
        pred.valid_mask,
        pred.transition_type,
        gt.depths_m,
        gt.valid_mask,
        gt.transition_type,
        delta_m,
    )
    return {key: float(value) for key, value in zip(_STATISTIC_KEYS, values)}


def summarize_statistics(stats: dict[str, float]) -> dict[str, float | None]:
    matched = stats["matched_events"]
    precision = matched / stats["pred_events"] if stats["pred_events"] else None
    recall = matched / stats["gt_events"] if stats["gt_events"] else None
    f1 = (
        None
        if precision is None or recall is None
        else 0.0
        if precision + recall == 0
        else 2 * precision * recall / (precision + recall)
    )
    typed_precision = (
        stats["correct_typed_events"] / stats["pred_typed_events"]
        if stats["pred_typed_events"]
        else None
    )
    typed_recall = (
        stats["correct_typed_events"] / stats["gt_typed_events"]
        if stats["gt_typed_events"]
        else None
    )
    typed_f1 = (
        None
        if typed_precision is None or typed_recall is None
        else 0.0
        if typed_precision + typed_recall == 0
        else 2 * typed_precision * typed_recall / (typed_precision + typed_recall)
    )
    return {
        "rays": int(stats["rays"]),
        "interface_precision": precision,
        "interface_recall": recall,
        "interface_f1": f1,
        "interface_count_accuracy": stats["count_correct"] / stats["rays"] if stats["rays"] else None,
        "matched_interface_mae_m": stats["abs_error_sum_m"] / matched if matched else None,
        "matched_interface_rmse_m": (stats["squared_error_sum_m2"] / matched) ** 0.5 if matched else None,
        "transition_precision": typed_precision,
        "transition_recall": typed_recall,
        "transition_f1": typed_f1,
        "transition_pair_coverage": stats["matched_typed_events"] / matched if matched else None,
        "topology_labeled_ray_rate": stats["topology_labeled_rays"] / stats["rays"] if stats["rays"] else None,
        "topology_valid_ray_rate": (
            stats["topology_valid_rays"] / stats["topology_labeled_rays"]
            if stats["topology_labeled_rays"]
            else None
        ),
    }


def iter_npz_pairs(ground_truth: str | Path, prediction: str | Path) -> Iterable[tuple[Path, Path]]:
    ground_truth = Path(ground_truth)
    prediction = Path(prediction)
    if ground_truth.is_file() and prediction.is_file():
        yield ground_truth, prediction
        return
    if not ground_truth.is_dir() or not prediction.is_dir():
        raise ValueError("Both inputs must be files or both must be directories")
    for gt_path in sorted(ground_truth.glob("*.npz")):
        pred_path = prediction / gt_path.name
        if not pred_path.is_file():
            raise FileNotFoundError(f"Missing prediction for {gt_path.name}: {pred_path}")
        yield gt_path, pred_path
