#!/usr/bin/env bash
# Execute ReMake's unmodified official test entrypoint after wiring its two
# hard-coded relative paths to the rehydrated artifacts.  The cache-producing
# Python adapter is the G0 entrypoint; this script is the native cross-check.
set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "usage: $0 <official-root> <transcg-root> <remake-checkpoint> <depth-anything-vits> <logname>" >&2
  exit 2
fi

official_root=$(realpath "$1")
dataset_root=$(realpath "$2")
checkpoint=$(realpath "$3")
depth_anything=$(realpath "$4")
logname=$5

ensure_link() {
  local target=$1
  local link=$2
  mkdir -p "$(dirname "$link")"
  if [[ -L "$link" || -e "$link" ]]; then
    [[ "$(realpath "$link")" == "$target" ]] || {
      echo "Refusing to replace existing path: $link" >&2
      exit 1
    }
  else
    ln -s "$target" "$link"
  fi
}

[[ -f "$official_root/main.py" ]] || { echo "invalid ReMake root: $official_root" >&2; exit 1; }
[[ -f "$dataset_root/metadata.json" ]] || { echo "missing TransCG metadata: $dataset_root" >&2; exit 1; }
[[ -f "$checkpoint" ]] || { echo "missing ReMake checkpoint: $checkpoint" >&2; exit 1; }
[[ -f "$depth_anything" ]] || { echo "missing Depth Anything weights: $depth_anything" >&2; exit 1; }

ensure_link "$dataset_root" "$official_root/datasets/transcg/transcg"
ensure_link "$depth_anything" "$official_root/checkpoints/depth_anything_v2_vits.pth"
cd "$official_root"
exec python main.py --mode test --cfg configs/test/transcg_remake.yaml \
  --checkpoints "$checkpoint" --reldepth_model depthanything --logname "$logname"
