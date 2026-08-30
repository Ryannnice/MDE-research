#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GROUNDING_ROOT="${1:?usage: apply_groundingdino_compat.sh /path/to/GroundingDINO}"
CUDA_ARCH="${TORCH_CUDA_ARCH_LIST:-9.0+PTX}"
PYTHON_BIN="${PYTHON_BIN:-python}"

SOURCE="$GROUNDING_ROOT/groundingdino/models/GroundingDINO/csrc/MsDeformAttn/ms_deform_attn_cuda.cu"
PATCH="$SCRIPT_DIR/groundingdino_pytorch28.patch"

if rg -q 'AT_DISPATCH_FLOATING_TYPES\(value\.scalar_type\(\)' "$SOURCE"; then
  echo "GroundingDINO PyTorch compatibility patch already present"
else
  git -C "$GROUNDING_ROOT" apply "$PATCH"
fi

CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}" \
TORCH_CUDA_ARCH_LIST="$CUDA_ARCH" \
MAX_JOBS="${MAX_JOBS:-8}" \
  "$PYTHON_BIN" -m pip install --no-deps --no-build-isolation -e "$GROUNDING_ROOT"
