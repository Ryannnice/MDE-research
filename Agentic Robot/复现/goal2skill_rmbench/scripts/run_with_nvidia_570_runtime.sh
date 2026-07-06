#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root_dir="$(cd "$script_dir/.." && pwd)"
runtime_dir="$root_dir/nvidia_runtime_570.124.06/libs"
lib_dir="$runtime_dir/usr/lib/x86_64-linux-gnu"

if [[ ! -d "$lib_dir" ]]; then
  echo "Missing NVIDIA 570.124.06 runtime libs: $lib_dir" >&2
  exit 1
fi

export LD_LIBRARY_PATH="$lib_dir:${LD_LIBRARY_PATH:-}"
export VK_ICD_FILENAMES="$runtime_dir/usr/share/vulkan/icd.d/nvidia_icd.json"
export __EGL_VENDOR_LIBRARY_FILENAMES="$runtime_dir/usr/share/glvnd/egl_vendor.d/10_nvidia.json"
export LANG="${LANG:-C.UTF-8}"
export LC_ALL="${LC_ALL:-C.UTF-8}"
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"

exec "$@"
