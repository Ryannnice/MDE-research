#!/usr/bin/env bash
# Download the public Depth Anything V2 Small/VITS checkpoint required by
# ReMake's released relative-depth branch. The URL is the official model card
# repository; the command is resumable and prints a content hash for the run
# manifest.
set -euo pipefail

workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
project_root="${workspace_root}/透明物体"
output="${DEPTH_ANYTHING_V2_VITS_PATH:-${project_root}/weights/depth-anything-v2/depth_anything_v2_vits.pth}"
url="${DEPTH_ANYTHING_V2_VITS_URL:-https://huggingface.co/depth-anything/Depth-Anything-V2-Small/resolve/main/depth_anything_v2_vits.pth}"

mkdir -p "$(dirname "$output")"
curl --fail --location --retry 3 --retry-delay 3 --continue-at - --output "$output" "$url"
sha256sum "$output"
