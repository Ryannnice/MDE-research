#!/usr/bin/env bash
# Download and verify the official TransCG scene archives.
#
# The default is intentionally the complete public dataset because the official
# test split spans all thirteen scene ranges.  A subset may be requested only
# for an explicitly labelled debugging run, for example: `... 3`.  Pass
# `--continue-on-error` before the chunk list to retain/attempt later chunks
# when an upstream Drive quota affects only part of a release.
set -euo pipefail

workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
project_root="${workspace_root}/透明物体"
data_root="${TRANSCG_ROOT:-${project_root}/data/transcg}"
download_root="${TRANSCG_DOWNLOAD_ROOT:-${data_root}/downloads}"
gdown_bin="${GDOWN:-gdown}"

declare -A archive_ids=(
  [info]="18LkbelKNTURF-8f8N-ykzs79FJ013knH"
  [1]="1rDgbMrzyO8GvTwEyPDbyx6pS9TVVDJLI"
  [2]="10etZWFV5r_wJRCR3Q38eq9WaRY8qWBFp"
  [3]="19tXZ9lzpW2gUk1ibkij76I_-oknCbqyP"
  [4]="13JFpSXd8d7vkVJvAUT1E6JOL6ZGC9B5f"
  [5]="1sMt8pbiVTU4J2YCdN31ZV3BY6m4ywX9O"
  [6]="1Uc2UDALZRG2NDZJt9CXMRLw1y6gpa_sT"
  [7]="1NXCGDzC2MrWktR9HcUddtRpajeg2JMEf"
  [8]="11MK-7_eX5oRNTdJPcOUXmvMaL3_cmFVh"
  [9]="1oSMxQ0O9UD38Tu8w16BOhi8sPKMp6UQf"
  [10]="1usAWlEJ0PE9gdgQb7CKo9CgkWOFr-Ms0"
  [11]="1M-QQcEGFcTw2SJrr-Z_Gg1-fyA0PZrcb"
  [12]="1KxpeNNOEOlv0t6PSNYWg0PoQ37OizDhR"
  [13]="1FaZX6eWGYuMKu6riX-su3es3_XzoTawC"
)

continue_on_error=false
if [[ "${1:-}" == "--continue-on-error" ]]; then
  continue_on_error=true
  shift
fi

if [[ $# -eq 0 || "${1:-}" == "--all" ]]; then
  requested=(1 2 3 4 5 6 7 8 9 10 11 12 13)
  [[ "${1:-}" == "--all" ]] && shift
else
  requested=("$@")
fi

for chunk in "${requested[@]}"; do
  [[ -v "archive_ids[$chunk]" && "$chunk" != "info" ]] || {
    echo "Unknown TransCG chunk: $chunk (expected 1..13)" >&2
    exit 2
  }
done

mkdir -p "$data_root" "$download_root"

fetch_and_extract() {
  local label="$1"
  local filename
  if [[ "$label" == "info" ]]; then
    filename="transcg-info.zip"
  else
    filename="transcg-data-${label}.zip"
  fi
  local archive="${download_root}/${filename}"
  echo "==> ${filename}"
  "$gdown_bin" --continue "${archive_ids[$label]}" -O "$archive"
  unzip -tq "$archive"
  unzip -nq "$archive" -d "$data_root"
}

if [[ ! -f "${data_root}/transcg/metadata.json" ]]; then
  fetch_and_extract info
fi
failed_chunks=()
for chunk in "${requested[@]}"; do
  if ! fetch_and_extract "$chunk"; then
    if [[ "$continue_on_error" != true ]]; then
      exit 1
    fi
    failed_chunks+=("$chunk")
    echo "WARNING: TransCG chunk ${chunk} failed; continuing with remaining requested chunks." >&2
  fi
done

if [[ ${#failed_chunks[@]} -gt 0 ]]; then
  echo "Incomplete download; failed chunks: ${failed_chunks[*]}" >&2
  echo "Existing archives remain resumable. Re-run this command after the upstream quota clears." >&2
  exit 1
fi

echo "TransCG download/extract completed. Audit before declaring a full result:"
echo "  python ${project_root}/复现/tools/transcg/audit_transcg.py --dataset-root ${data_root}/transcg --split test"
