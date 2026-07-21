#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "Usage: $0 <booster-train-balanced-root> [output-root]" >&2
    exit 2
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
workspace_root="$(cd -- "${script_dir}/../../../.." && pwd)"
official_root="${workspace_root}/透明物体/external/depth4tom/official"
weights_root="${workspace_root}/透明物体/weights/depth4tom/Base"
dataset_txt="${official_root}/datasets/booster/train_stereo.txt"
if [[ ! -d "$1" ]]; then
    echo "Missing Booster root: $1" >&2
    exit 1
fi
booster_root="$(realpath "$1")"
output_root="$(realpath -m "${2:-${workspace_root}/透明物体/runs/depth4tom/table2_base}")"

mkdir -p \
    "${output_root}/predictions" \
    "${output_root}/metrics" \
    "${output_root}/logs"

cd "${official_root}"
for model in midas_v21 dpt_large; do
    checkpoint="${weights_root}/${model}-base.pt"
    prediction_dir="${output_root}/predictions/${model}"
    metrics_file="${output_root}/metrics/${model}.txt"
    log_file="${output_root}/logs/${model}.log"

    if [[ ! -f "${checkpoint}" ]]; then
        echo "Missing Base checkpoint: ${checkpoint}" >&2
        exit 1
    fi

    python run.py \
        --model_type "${model}" \
        --model_weights "${checkpoint}" \
        --input_path "${booster_root}" \
        --dataset_txt "${dataset_txt}" \
        --output_path "${prediction_dir}" \
        2>&1 | tee "${log_file}"

    python evaluate_mono.py \
        --gt_root "${booster_root}" \
        --pred_root "${prediction_dir}" \
        --dataset_txt "${dataset_txt}" \
        --output_path "${metrics_file}" \
        2>&1 | tee -a "${log_file}"
done
