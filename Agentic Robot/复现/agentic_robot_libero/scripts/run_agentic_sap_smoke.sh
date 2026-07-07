#!/usr/bin/env bash
set -euo pipefail

REPRO_ROOT="${REPRO_ROOT:-/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero}"
AGENTIC_REPO="${AGENTIC_REPO:-$REPRO_ROOT/repos/agentic-robot}"

TASK_SUITE="${TASK_SUITE:-libero_10}"
CHECKPOINT="${CHECKPOINT:-openvla/openvla-7b-finetuned-libero-10}"
START_TASK_ID="${START_TASK_ID:-0}"
START_EPISODE_ID="${START_EPISODE_ID:-0}"
MAX_TASKS="${MAX_TASKS:-1}"
NUM_TRIALS_PER_TASK="${NUM_TRIALS_PER_TASK:-1}"
MAX_STEPS_OVERRIDE="${MAX_STEPS_OVERRIDE:-40}"
SAVE_FRAMES="${SAVE_FRAMES:-False}"
VERIFY_FREQUENCY="${VERIFY_FREQUENCY:-20}"
VLM_HISTORY_LENGTH="${VLM_HISTORY_LENGTH:-2}"
RUN_ID_NOTE="${RUN_ID_NOTE:-sap_smoke}"
MANUAL_PLAN="${MANUAL_PLAN:-}"
VLM_VERIFIER_BACKEND="${VLM_VERIFIER_BACKEND:-openai_api}"
STUCK_DETECTION_MODE="${STUCK_DETECTION_MODE:-heuristic}"
STUCK_NO_PROGRESS_CHECKS="${STUCK_NO_PROGRESS_CHECKS:-3}"
RECOVERY_MAX_ATTEMPTS="${RECOVERY_MAX_ATTEMPTS:-2}"
RECOVERY_LIFT_STEPS="${RECOVERY_LIFT_STEPS:-12}"
RECOVERY_LIFT_DELTA_Z="${RECOVERY_LIFT_DELTA_Z:-0.35}"
EXECUTOR_INSTRUCTION_MODE="${EXECUTOR_INSTRUCTION_MODE:-subtask}"
VERIFY_ON_ENV_SUCCESS="${VERIFY_ON_ENV_SUCCESS:-False}"
VLM_COMPLETION_CONFIRMATIONS="${VLM_COMPLETION_CONFIRMATIONS:-1}"
LLM_PLANNER_STYLE="${LLM_PLANNER_STYLE:-outcome}"

PRIMARY_MODEL="${OPENAI_MODEL:-gpt-5.4-mini}"
PRIMARY_BASE_URL="${OPENAI_BASE_URL:-https://Codex.hldragon.xyz/v1}"
FALLBACK_MODEL="${DASHSCOPE_MODEL:-qwen-plus}"
FALLBACK_BASE_URL="${DASHSCOPE_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
API_VLM_MODEL="${API_VLM_MODEL:-$PRIMARY_MODEL}"
API_VLM_BASE_URL="${API_VLM_BASE_URL:-$PRIMARY_BASE_URL}"
API_VLM_API_KEY_ENV="${API_VLM_API_KEY_ENV:-OPENAI_API_KEY}"

if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ "$VLM_VERIFIER_BACKEND" == "qwen_local" ]]; then
    PYTHON_BIN="/root/miniconda/envs/ar_agentic_libero_vlm/bin/python"
  else
    PYTHON_BIN="/root/miniconda/envs/ar_agentic_libero/bin/python"
  fi
fi

args=(
  experiments/robot/libero/main.py
  --model_family openvla
  --pretrained_checkpoint "$CHECKPOINT"
  --task_suite_name "$TASK_SUITE"
  --center_crop True
  --num_trials_per_task "$NUM_TRIALS_PER_TASK"
  --start_task_id "$START_TASK_ID"
  --start_episode_id "$START_EPISODE_ID"
  --max_tasks "$MAX_TASKS"
  --max_steps_override "$MAX_STEPS_OVERRIDE"
  --save_frames "$SAVE_FRAMES"
  --local_log_dir "$REPRO_ROOT/data/logs"
  --frames_save_root_dir "$REPRO_ROOT/data/saved_frames"
  --run_id_note "$RUN_ID_NOTE"
  --enable_vlm_verifier True
  --use_llm_planner True
  --llm_planner_style "$LLM_PLANNER_STYLE"
  --llm_planner_api_key_env OPENAI_API_KEY
  --llm_planner_base_url "$PRIMARY_BASE_URL"
  --llm_planner_model "$PRIMARY_MODEL"
  --vlm_verifier_backend "$VLM_VERIFIER_BACKEND"
  --api_vlm_api_key_env "$API_VLM_API_KEY_ENV"
  --api_vlm_base_url "$API_VLM_BASE_URL"
  --api_vlm_model "$API_VLM_MODEL"
  --verify_frequency "$VERIFY_FREQUENCY"
  --vlm_history_length "$VLM_HISTORY_LENGTH"
  --stuck_detection_mode "$STUCK_DETECTION_MODE"
  --stuck_no_progress_checks "$STUCK_NO_PROGRESS_CHECKS"
  --recovery_max_attempts "$RECOVERY_MAX_ATTEMPTS"
  --recovery_lift_steps "$RECOVERY_LIFT_STEPS"
  --recovery_lift_delta_z "$RECOVERY_LIFT_DELTA_Z"
  --executor_instruction_mode "$EXECUTOR_INSTRUCTION_MODE"
  --verify_on_env_success "$VERIFY_ON_ENV_SUCCESS"
  --vlm_completion_confirmations "$VLM_COMPLETION_CONFIRMATIONS"
)

if [[ -n "$MANUAL_PLAN" ]]; then
  args+=(
    --manual_plan "$MANUAL_PLAN"
  )
fi

if [[ -n "${DASHSCOPE_API_KEY:-}" ]]; then
  args+=(
    --llm_planner_fallback_api_key_env DASHSCOPE_API_KEY
    --llm_planner_fallback_base_url "$FALLBACK_BASE_URL"
    --llm_planner_fallback_model "$FALLBACK_MODEL"
  )
fi

cd "$AGENTIC_REPO"
HF_HOME="$REPRO_ROOT/data/hf_cache" \
LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config" \
PYTHONPATH="$REPRO_ROOT/repos/LIBERO" \
MUJOCO_GL=osmesa \
PYOPENGL_PLATFORM=osmesa \
TOKENIZERS_PARALLELISM=false \
TF_CPP_MIN_LOG_LEVEL=3 \
WANDB_MODE=disabled \
"$PYTHON_BIN" "${args[@]}"
