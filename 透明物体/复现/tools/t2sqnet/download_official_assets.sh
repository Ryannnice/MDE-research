#!/usr/bin/env bash
# Download the two release assets required for a reproducible T^2SQNet run.
#
# The upstream project publishes Google Drive *folders*, rather than immutable
# archive files.  This script deliberately does not guess a file layout: it
# keeps each download in an explicit raw directory and prints an inventory for
# the post-download audit.  The evaluator accepts an explicit --data-root and
# --weights-root, so a later layout change cannot silently select stale assets.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "${script_dir}/../../.." && pwd)"

data_url="${TABLEWARENET_DATA_URL:-https://drive.google.com/drive/folders/1d9K7xZU8Z4RnEMgOCBAw3ilTztowcJm7?usp=drive_link}"
weights_url="${T2SQNET_WEIGHTS_URL:-https://drive.google.com/drive/folders/18gaogv8NOEbxskADN7dGahi6N_MXcEuS?usp=sharing}"
data_destination="${TABLEWARENET_DOWNLOAD_DIR:-${project_root}/data/tablewarenet/release}"
weights_destination="${T2SQNET_WEIGHTS_DOWNLOAD_DIR:-${project_root}/weights/t2sqnet/release}"
gdown_bin="${GDOWN:-gdown}"

usage() {
  cat <<'USAGE'
Usage: bash download_official_assets.sh {data|weights|all}

Downloads the official Google Drive folders with gdown.  Google Drive folders
may contain at most 50 files when listed by gdown; this script uses
--remaining-ok but does not claim completeness.  Always run
audit_tablewarenet.py and check the printed inventory before evaluation.

Environment overrides:
  GDOWN=/path/to/gdown
  TABLEWARENET_DATA_URL=<official folder URL>
  T2SQNET_WEIGHTS_URL=<official folder URL>
  TABLEWARENET_DOWNLOAD_DIR=<destination>
  T2SQNET_WEIGHTS_DOWNLOAD_DIR=<destination>
USAGE
}

if [[ $# -ne 1 || "${1}" == "-h" || "${1}" == "--help" ]]; then
  usage
  [[ $# -eq 1 ]] && exit 0
  exit 2
fi
if ! command -v "${gdown_bin}" >/dev/null 2>&1; then
  echo "gdown is required; install it or set GDOWN=/path/to/gdown" >&2
  exit 127
fi

download_folder() {
  local label="$1"
  local url="$2"
  local destination="$3"
  mkdir -p "${destination}"
  echo "Downloading official ${label} folder to: ${destination}"
  "${gdown_bin}" --folder --remaining-ok --continue --fuzzy "${url}" -O "${destination}/"
  echo "${label} inventory (first 200 paths):"
  find "${destination}" -type f -printf '%P\t%s bytes\n' | sort | sed -n '1,200p'
}

extract_tablewarenet_archives() {
  local archive
  local archive_found=false
  while IFS= read -r -d '' archive; do
    archive_found=true
    echo "Testing and extracting: ${archive}"
    tar -tzf "${archive}" >/dev/null
    # The upstream data release consists of independent tarballs.  Keeping
    # their top-level folders under the download destination makes extraction
    # resumable and avoids pretending that a partial archive is a valid split.
    tar --skip-old-files -xzf "${archive}" -C "${data_destination}"
  done < <(find "${data_destination}" -type f \( -name '*.tar.gz' -o -name '*.tgz' \) -print0 | sort -z)
  if [[ "${archive_found}" == false ]]; then
    echo "No TablewareNet tar archives found under ${data_destination}; inspect the release inventory." >&2
    return 1
  fi
  echo "Detected processed directories:"
  find "${data_destination}" -type d \( -name 'test_processed' -o -name 'train_processed' \) -print | sort
}

case "$1" in
  data)
    download_folder "TablewareNet data" "${data_url}" "${data_destination}"
    extract_tablewarenet_archives
    ;;
  weights)
    download_folder "T2SQNet pretrained weights" "${weights_url}" "${weights_destination}"
    ;;
  all)
    download_folder "TablewareNet data" "${data_url}" "${data_destination}"
    extract_tablewarenet_archives
    download_folder "T2SQNet pretrained weights" "${weights_url}" "${weights_destination}"
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
