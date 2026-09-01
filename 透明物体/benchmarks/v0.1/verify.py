#!/usr/bin/env python3
"""Verify the frozen transparent-shell benchmark v0.1 contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = Path(__file__).with_name("benchmark.json")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nested_get(value: Any, dotted_path: str) -> Any:
    current = value
    for component in dotted_path.split("."):
        if not isinstance(current, dict) or component not in current:
            raise KeyError(dotted_path)
        current = current[component]
    return current


def verify_manifest(manifest_path: Path, project_root: Path) -> list[str]:
    errors: list[str] = []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("benchmark_id") != "transparent-shell-v0.1":
        errors.append("unexpected benchmark_id")

    frozen_files = manifest.get("frozen_files", [])
    if not frozen_files:
        errors.append("frozen_files is empty")

    for entry in frozen_files:
        relative_path = Path(entry["path"])
        if relative_path.is_absolute():
            errors.append(f"frozen path must be relative: {relative_path}")
            continue
        path = project_root / relative_path
        if not path.is_file():
            errors.append(f"missing frozen file: {relative_path}")
            continue
        actual = sha256_file(path)
        if actual != entry["sha256"]:
            errors.append(
                f"sha256 mismatch for {relative_path}: expected {entry['sha256']}, got {actual}"
            )

    summary_path = project_root / "透明物体/复现/baseline_results_2026-08-30.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        for invariant in manifest.get("frozen_result_invariants", []):
            dotted_path = invariant["path"]
            try:
                actual = nested_get(summary, dotted_path)
            except KeyError:
                errors.append(f"missing result invariant: {dotted_path}")
                continue
            if actual != invariant["value"]:
                errors.append(
                    f"result invariant mismatch for {dotted_path}: "
                    f"expected {invariant['value']!r}, got {actual!r}"
                )

    for split_name, split in manifest.get("evaluation_splits", {}).items():
        if split.get("role") != "evaluation_only" or split.get("allow_training") is not False:
            errors.append(f"evaluation split is not locked against training: {split_name}")

    for source_name, source in manifest.get("training_sources", {}).items():
        if source.get("role") != "training_only":
            errors.append(f"training source is not marked training_only: {source_name}")

    shell = manifest.get("evaluation_splits", {}).get("tablewarenet_shellbench", {})
    if shell.get("camera_image_size") != [240, 320]:
        errors.append("TablewareNet camera_image_size must be [height,width] = [240,320]")
    if shell.get("camera_image_size_order") != "height_width":
        errors.append("TablewareNet camera_image_size_order must be height_width")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--project-root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()

    errors = verify_manifest(args.manifest.resolve(), args.project_root.resolve())
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PASS: transparent-shell-v0.1 manifest and frozen artifacts verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
