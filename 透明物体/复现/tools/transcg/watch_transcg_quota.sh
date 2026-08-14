#!/usr/bin/env bash
# Low-frequency, resumable TransCG Drive-quota monitor.
# It tries one missing archive per interval, rotates through chunks 1..13,
# and delegates download, validation and extraction to the canonical script.
set -euo pipefail

workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
project_root="${workspace_root}/透明物体"
download_script="${project_root}/复现/tools/transcg/download_transcg.sh"
data_root="${TRANSCG_ROOT:-${project_root}/data/transcg}"
interval_seconds="${1:-1800}"

if ! [[ "$interval_seconds" =~ ^[0-9]+$ ]] || [[ "$interval_seconds" -lt 60 ]]; then
  echo "Usage: $0 [interval_seconds >= 60]" >&2
  exit 2
fi

chunks=(1 2 3 4 5 6 7 8 9 10 11 12 13)
index=0
while true; do
  chunk="${chunks[$index]}"
  archive="${data_root}/downloads/transcg-data-${chunk}.zip"
  timestamp="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  if [[ -f "$archive" && -f "${archive}.verified" ]]; then
    echo "${timestamp} chunk ${chunk}: archive already verified"
    index=$(( (index + 1) % ${#chunks[@]} ))
    continue
  else
    echo "${timestamp} chunk ${chunk}: testing Google Drive availability"
    if bash "$download_script" --continue-on-error "$chunk"; then
      echo "${timestamp} chunk ${chunk}: downloaded, verified and extracted"
    else
      echo "${timestamp} chunk ${chunk}: still unavailable or interrupted; will retry later"
    fi
  fi
  index=$(( (index + 1) % ${#chunks[@]} ))
  sleep "$interval_seconds"
done
