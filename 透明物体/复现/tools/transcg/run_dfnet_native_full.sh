#!/usr/bin/env bash
# Run TransCG's unmodified test.py with only its two hard-coded paths wired to
# the downloaded release artifacts.  The cache-producing Python adapter is the
# shared-G0 entrypoint; this script is the native aggregate-metric cross-check.
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 <official-root> <transcg-root> <dfnet-checkpoint>" >&2
  exit 2
fi

official_root=$(realpath "$1")
dataset_root=$(realpath "$2")
checkpoint=$(realpath "$3")
config="${official_root}/configs/320x240/train_transcg_val_transcg.yaml"

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

[[ -f "${official_root}/test.py" ]] || { echo "invalid TransCG root: ${official_root}" >&2; exit 1; }
[[ -f "${dataset_root}/metadata.json" ]] || { echo "missing TransCG metadata: ${dataset_root}" >&2; exit 1; }
[[ -f "$checkpoint" ]] || { echo "missing DFNet checkpoint: ${checkpoint}" >&2; exit 1; }
[[ -f "$config" ]] || { echo "missing official TransCG test config: ${config}" >&2; exit 1; }

ensure_link "$dataset_root" "${official_root}/data"
ensure_link "$checkpoint" "${official_root}/stats/train-tg-val-tg/checkpoint.tar"
cd "$official_root"
exec python test.py --cfg "${config}"
