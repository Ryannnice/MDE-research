# Agentic Robot / LIBERO 复现记录

日期：2026-07-04

## 结论

已完成到“OpenVLA executor baseline 可比较，并且 VLM verifier smoke 可运行”的状态：

1. 官方 Agentic Robot 代码已拉取：`Agentic-Robot/agentic-robot`，commit `cafb8d5`。
2. 已创建 conda 环境：`ar_agentic_libero`，Python 3.10。
3. 已补齐 OpenVLA / OpenVLA-OFT / LIBERO / robosuite / MuJoCo / FlashAttention 依赖。
4. 已通过 LIBERO 仿真 smoke test：`libero_spatial` task 0 reset、render、dummy action step 正常。
5. 已完成 7B OpenVLA 最小模型 smoke eval：加载 `openvla/openvla-7b-finetuned-libero-spatial`，跑 1 个 task、1 个 episode、2 个模型 action steps，按预期 timeout。
6. 已完成 `libero_spatial` 完整 OpenVLA executor baseline：10 tasks x 5 trials，成功率 `0.88 (44/50)`。
7. 已完成 `libero_object` 完整 OpenVLA executor baseline：10 tasks x 5 trials，成功率 `0.82 (41/50)`。
8. 已完成 `libero_goal` 完整 OpenVLA executor baseline：10 tasks x 5 trials，成功率 `0.76 (38/50)`。
9. 已完成 `libero_10` 完整 OpenVLA executor baseline：10 tasks x 5 trials，成功率 `0.42 (21/50)`。
10. 已创建独立 VLM verifier 环境：`ar_agentic_libero_vlm`，保留 baseline 环境 `ar_agentic_libero` 不变。
11. 已完成 `Qwen/Qwen2.5-VL-3B-Instruct` 加载 smoke，以及 `manual_plan + Qwen verifier + OpenVLA executor` 的 1-step 集成 smoke。
12. 已在 `ar_agentic_libero_vlm` 跑 `libero_spatial` task 0 对照：原始 OpenVLA executor 指令 `1/1` 成功；当前手写 `pick/place` 分解 + verifier `0/1`，说明后续 SAP ablation 需要调 planner 子任务粒度、verifier prompt/历史帧或切换策略。
13. 已把 LRM planner 的 API key env 做成可配置参数：默认仍是 `DASHSCOPE_API_KEY`，也可显式传 `--llm_planner_api_key_env OPENAI_API_KEY`；当前本机 `OPENAI_API_KEY` 为无效 token，只验证了 401 fallback 路径。

当前可比较指标仍是 OpenVLA executor baseline，不是论文完整 SAP 指标。本地已给 `main.py` 增加可选 planner / verifier 开关；默认仍保持 executor baseline 行为。VLM verifier 路径已跑通 smoke，但当前朴素手写分解会回归；完整 SAP 指标仍需要可用的 LRM planner API key 和完整 ablation。

## 目录

```text
agentic_robot_libero/
  README.md
  environment_ar_agentic_libero.yml
  environment_ar_agentic_libero_vlm.yml
  pip_freeze_ar_agentic_libero.txt
  pip_freeze_ar_agentic_libero_vlm.txt
  patches/agentic_robot_main_smoke.patch
  tools/smoke_libero_env.py
  data/libero_config/config.yaml
  data/logs/
  data/hf_cache/              # ignored, HF checkpoint cache
  data/libero_datasets/       # ignored
  repos/                      # ignored, cloned upstream repos
```

## 环境删除后的恢复命令

2026-07-05 已按下面流程重建并验证 `ar_agentic_libero`。不要只执行 `conda env create -f environment_ar_agentic_libero.yml`：该文件来自 `conda env export`，会把 Git 安装的 `dlimp` 记录成 PyPI 上不存在的 `dlimp==0.0.1`，导致 pip 阶段失败。

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"

apt-get update
apt-get install -y libosmesa6 libegl1 libopengl0 libgl1

conda env remove -n ar_agentic_libero || true
conda create -y -n ar_agentic_libero -c defaults -c conda-forge \
  python=3.10.20 pip=26.1.2 setuptools=82.0.1 wheel=0.47.0 \
  packaging=26.0 mesalib=25.3.5

/root/miniconda/envs/ar_agentic_libero/bin/python -m pip install \
  --extra-index-url https://download.pytorch.org/whl/cu121 \
  "torch==2.2.0+cu121" "torchvision==0.17.0+cu121" "torchaudio==2.2.0+cu121"

REQ="$REPRO_ROOT/pip_freeze_ar_agentic_libero.txt"
/root/miniconda/envs/ar_agentic_libero/bin/python -m pip install \
  --extra-index-url https://download.pytorch.org/whl/cu121 \
  -r <(grep -v -E '^(torch==|torchvision==|torchaudio==|flash-attn==|-e git\+)' "$REQ")

/root/miniconda/envs/ar_agentic_libero/bin/python -m pip install --no-deps \
  -e "$REPRO_ROOT/repos/LIBERO" \
  -e "$REPRO_ROOT/repos/agentic-robot" \
  -e "$REPRO_ROOT/repos/openvla-oft"

/root/miniconda/envs/ar_agentic_libero/bin/python -m pip install \
  --no-build-isolation "flash-attn==2.5.5"
```

恢复后至少运行：

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"

/root/miniconda/envs/ar_agentic_libero/bin/python -m pip check

LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config" \
PYTHONPATH="$REPRO_ROOT/repos/LIBERO" \
MUJOCO_GL=osmesa \
PYOPENGL_PLATFORM=osmesa \
TOKENIZERS_PARALLELISM=false \
TF_CPP_MIN_LOG_LEVEL=3 \
WANDB_MODE=disabled \
/root/miniconda/envs/ar_agentic_libero/bin/python "$REPRO_ROOT/tools/smoke_libero_env.py"
```

本次恢复后已验证：

- `/root/miniconda/envs/ar_agentic_libero/bin/python -m pip check`：通过。
- `python -m py_compile experiments/robot/libero/main.py experiments/robot/libero/qwenvl.py experiments/robot/libero/ds.py`：通过。
- `tools/smoke_libero_env.py`：输出 `SMOKE_LIBERO_OK`。
- OpenVLA 7B 最小 smoke：`libero_spatial` task 0、1 trial、`--max_steps_override 1`，模型加载与 1 step 推理通过，按预期 timeout；日志为 `data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_05-06_08_30--restore_smoke_1task_1step.txt`。

### VLM verifier 环境

不要在 `ar_agentic_libero` 里直接升级 `transformers`。OpenVLA baseline 环境固定为 `transformers==4.40.1` / `tokenizers==0.19.1`；Qwen2.5-VL verifier 另用克隆环境：

```bash
conda create -y -n ar_agentic_libero_vlm --clone ar_agentic_libero
/root/miniconda/envs/ar_agentic_libero_vlm/bin/python -m pip install "transformers==4.51.3"
```

已导出环境记录：

```text
environment_ar_agentic_libero_vlm.yml
pip_freeze_ar_agentic_libero_vlm.txt
```

验证状态：

- `/root/miniconda/envs/ar_agentic_libero/bin/python`：`transformers 4.40.1`，`tokenizers 0.19.1`。
- `/root/miniconda/envs/ar_agentic_libero_vlm/bin/python`：`transformers 4.51.3`，`tokenizers 0.21.4`。
- `ar_agentic_libero_vlm` 可 import `Qwen2_5_VLForConditionalGeneration` 和 `qwen_vl_utils.process_vision_info`。
- `Qwen/Qwen2.5-VL-3B-Instruct` 已下载到 `data/hf_cache`，加载和最小 `check_completion_with_qwen_vl()` 生成路径通过。
- `ar_agentic_libero_vlm` 的 `pip check` 会报告 OpenVLA 元数据版本冲突，这是预期的：该环境只用于 verifier / SAP smoke；完整 executor baseline 仍使用 `ar_agentic_libero`。

## 已复现结果

### 1. LIBERO 环境 smoke test

命令：

```bash
conda run -n ar_agentic_libero python \
  "/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero/tools/smoke_libero_env.py"
```

关键输出：

```json
{
  "status": "SMOKE_LIBERO_OK",
  "suite": "libero_spatial",
  "task_id": 0,
  "agentview_image_shape": [128, 128, 3],
  "processed_image_shape": [128, 128, 3],
  "reward": 0.0,
  "done": false
}
```

### 2. OpenVLA 7B 最小模型 smoke eval

首次运行已下载 Hugging Face checkpoint 到：

```text
/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero/data/hf_cache
```

命令：

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"
AGENTIC_REPO="$REPRO_ROOT/repos/agentic-robot"

cd "$AGENTIC_REPO"
conda run -n ar_agentic_libero env \
  HF_HOME="$REPRO_ROOT/data/hf_cache" \
  LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config" \
  PYTHONPATH="$REPRO_ROOT/repos/LIBERO" \
  MUJOCO_GL=osmesa \
  PYOPENGL_PLATFORM=osmesa \
  TOKENIZERS_PARALLELISM=false \
  TF_CPP_MIN_LOG_LEVEL=3 \
  WANDB_MODE=disabled \
  python experiments/robot/libero/main.py \
    --model_family openvla \
    --pretrained_checkpoint openvla/openvla-7b-finetuned-libero-spatial \
    --task_suite_name libero_spatial \
    --center_crop True \
    --num_trials_per_task 1 \
    --start_task_id 0 \
    --max_tasks 1 \
    --max_steps_override 2 \
    --save_frames False \
    --run_id_note smoke_1task_2steps \
    --local_log_dir "$REPRO_ROOT/data/logs" \
    --frames_save_root_dir "$REPRO_ROOT/data/saved_frames"
```

实际结果：

```text
Loaded model: OpenVLAForActionPrediction
Task: pick up the black bowl between the plate and the ramekin and place it on the plate
[t=12] Episode TIMEOUT.
Total Success Rate: 0.00 (0/1)
eval_libero total_time: 905.43 seconds
```

这里的 timeout 是预期结果，因为 `--max_steps_override 2` 只用于验证模型推理和环境 step，不用于衡量成功率。

日志：

```text
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_04-08_37_38--smoke_1task_2steps.txt
```

### 3. OpenVLA 7B `libero_spatial` 完整 executor baseline

运行时间：2026-07-04 18:09:46 到 18:52:18 UTC
配置：`libero_spatial`，10 tasks，`--num_trials_per_task 5`，无 VLM verifier，`save_frames=False`
模型：`openvla/openvla-7b-finetuned-libero-spatial`

结果：

```text
Total Success Rate: 0.88 (44/50)
eval_libero total_time: 2551.87 seconds
```

逐 task 成功率：

| task_id | success | task |
|---:|---:|---|
| 0 | 5/5 | pick up the black bowl between the plate and the ramekin and place it on the plate |
| 1 | 5/5 | pick up the black bowl next to the ramekin and place it on the plate |
| 2 | 4/5 | pick up the black bowl from table center and place it on the plate |
| 3 | 4/5 | pick up the black bowl on the cookie box and place it on the plate |
| 4 | 3/5 | pick up the black bowl in the top drawer of the wooden cabinet and place it on the plate |
| 5 | 5/5 | pick up the black bowl on the ramekin and place it on the plate |
| 6 | 5/5 | pick up the black bowl next to the cookie box and place it on the plate |
| 7 | 5/5 | pick up the black bowl on the stove and place it on the plate |
| 8 | 3/5 | pick up the black bowl next to the plate and place it on the plate |
| 9 | 5/5 | pick up the black bowl on the wooden cabinet and place it on the plate |

日志：

```text
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_04-18_09_46--full_executor_baseline_5trials.txt
```

命令：

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"
AGENTIC_REPO="$REPRO_ROOT/repos/agentic-robot"

cd "$AGENTIC_REPO"
conda run -n ar_agentic_libero env \
  HF_HOME="$REPRO_ROOT/data/hf_cache" \
  LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config" \
  PYTHONPATH="$REPRO_ROOT/repos/LIBERO" \
  MUJOCO_GL=osmesa \
  PYOPENGL_PLATFORM=osmesa \
  TOKENIZERS_PARALLELISM=false \
  TF_CPP_MIN_LOG_LEVEL=3 \
  WANDB_MODE=disabled \
  python experiments/robot/libero/main.py \
    --model_family openvla \
    --pretrained_checkpoint openvla/openvla-7b-finetuned-libero-spatial \
    --task_suite_name libero_spatial \
    --center_crop True \
    --num_trials_per_task 5 \
    --save_frames False \
    --run_id_note full_executor_baseline_5trials \
    --local_log_dir "$REPRO_ROOT/data/logs" \
    --frames_save_root_dir "$REPRO_ROOT/data/saved_frames"
```

### 4. OpenVLA 7B `libero_object` 完整 executor baseline

运行时间：2026-07-04 19:55:12 到 20:45:08 UTC
配置：`libero_object`，10 tasks，`--num_trials_per_task 5`，无 VLM verifier，`save_frames=False`
模型：`openvla/openvla-7b-finetuned-libero-object`

结果：

```text
Total Success Rate: 0.82 (41/50)
eval_libero total_time: 2995.33 seconds
```

逐 task 成功率：

| task_id | success | task |
|---:|---:|---|
| 0 | 3/5 | pick up the alphabet soup and place it in the basket |
| 1 | 4/5 | pick up the cream cheese and place it in the basket |
| 2 | 4/5 | pick up the salad dressing and place it in the basket |
| 3 | 3/5 | pick up the bbq sauce and place it in the basket |
| 4 | 4/5 | pick up the ketchup and place it in the basket |
| 5 | 4/5 | pick up the tomato sauce and place it in the basket |
| 6 | 4/5 | pick up the butter and place it in the basket |
| 7 | 5/5 | pick up the milk and place it in the basket |
| 8 | 5/5 | pick up the chocolate pudding and place it in the basket |
| 9 | 5/5 | pick up the orange juice and place it in the basket |

日志：

```text
data/logs/PEV_V1-EVAL-libero_object-openvla-2026_07_04-19_55_12--full_executor_baseline_5trials.txt
```

命令：

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"
AGENTIC_REPO="$REPRO_ROOT/repos/agentic-robot"

cd "$AGENTIC_REPO"
conda run -n ar_agentic_libero env \
  HF_HOME="$REPRO_ROOT/data/hf_cache" \
  LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config" \
  PYTHONPATH="$REPRO_ROOT/repos/LIBERO" \
  MUJOCO_GL=osmesa \
  PYOPENGL_PLATFORM=osmesa \
  TOKENIZERS_PARALLELISM=false \
  TF_CPP_MIN_LOG_LEVEL=3 \
  WANDB_MODE=disabled \
  python experiments/robot/libero/main.py \
    --model_family openvla \
    --pretrained_checkpoint openvla/openvla-7b-finetuned-libero-object \
    --task_suite_name libero_object \
    --center_crop True \
    --num_trials_per_task 5 \
    --save_frames False \
    --run_id_note full_executor_baseline_5trials \
    --local_log_dir "$REPRO_ROOT/data/logs" \
    --frames_save_root_dir "$REPRO_ROOT/data/saved_frames"
```

### 5. OpenVLA 7B `libero_goal` 完整 executor baseline

运行时间：2026-07-04 20:46:45 到 21:36:24 UTC
配置：`libero_goal`，10 tasks，`--num_trials_per_task 5`，无 VLM verifier，`save_frames=False`
模型：`openvla/openvla-7b-finetuned-libero-goal`

结果：

```text
Total Success Rate: 0.76 (38/50)
eval_libero total_time: 2978.27 seconds
```

逐 task 成功率：

| task_id | success | task |
|---:|---:|---|
| 0 | 2/5 | open the middle drawer of the cabinet |
| 1 | 5/5 | put the bowl on the stove |
| 2 | 5/5 | put the wine bottle on top of the cabinet |
| 3 | 3/5 | open the top drawer and put the bowl inside |
| 4 | 5/5 | put the bowl on top of the cabinet |
| 5 | 1/5 | push the plate to the front of the stove |
| 6 | 3/5 | put the cream cheese in the bowl |
| 7 | 5/5 | turn on the stove |
| 8 | 5/5 | put the bowl on the plate |
| 9 | 4/5 | put the wine bottle on the rack |

日志：

```text
data/logs/PEV_V1-EVAL-libero_goal-openvla-2026_07_04-20_46_45--full_executor_baseline_5trials.txt
```

命令：

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"
AGENTIC_REPO="$REPRO_ROOT/repos/agentic-robot"

cd "$AGENTIC_REPO"
conda run -n ar_agentic_libero env \
  HF_HOME="$REPRO_ROOT/data/hf_cache" \
  LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config" \
  PYTHONPATH="$REPRO_ROOT/repos/LIBERO" \
  MUJOCO_GL=osmesa \
  PYOPENGL_PLATFORM=osmesa \
  TOKENIZERS_PARALLELISM=false \
  TF_CPP_MIN_LOG_LEVEL=3 \
  WANDB_MODE=disabled \
  python experiments/robot/libero/main.py \
    --model_family openvla \
    --pretrained_checkpoint openvla/openvla-7b-finetuned-libero-goal \
    --task_suite_name libero_goal \
    --center_crop True \
    --num_trials_per_task 5 \
    --save_frames False \
    --run_id_note full_executor_baseline_5trials \
    --local_log_dir "$REPRO_ROOT/data/logs" \
	    --frames_save_root_dir "$REPRO_ROOT/data/saved_frames"
```

### 6. OpenVLA 7B `libero_10` 完整 executor baseline

运行时间：2026-07-04 21:37:39 到 23:22:25 UTC
配置：`libero_10`，10 tasks，`--num_trials_per_task 5`，无 VLM verifier，`save_frames=False`
模型：`openvla/openvla-7b-finetuned-libero-10`

结果：

```text
Total Success Rate: 0.42 (21/50)
eval_libero total_time: 6285.14 seconds
```

逐 task 成功率：

| task_id | success | task |
|---:|---:|---|
| 0 | 2/5 | put both the alphabet soup and the tomato sauce in the basket |
| 1 | 4/5 | put both the cream cheese box and the butter in the basket |
| 2 | 2/5 | turn on the stove and put the moka pot on it |
| 3 | 2/5 | put the black bowl in the bottom drawer of the cabinet and close it |
| 4 | 1/5 | put the white mug on the left plate and put the yellow and white mug on the right plate |
| 5 | 4/5 | pick up the book and place it in the back compartment of the caddy |
| 6 | 2/5 | put the white mug on the plate and put the chocolate pudding to the right of the plate |
| 7 | 2/5 | put both the alphabet soup and the cream cheese box in the basket |
| 8 | 2/5 | put both moka pots on the stove |
| 9 | 0/5 | put the yellow and white mug in the microwave and close it |

日志：

```text
data/logs/PEV_V1-EVAL-libero_10-openvla-2026_07_04-21_37_39--full_executor_baseline_5trials.txt
```

命令：

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"
AGENTIC_REPO="$REPRO_ROOT/repos/agentic-robot"

cd "$AGENTIC_REPO"
conda run -n ar_agentic_libero env \
  HF_HOME="$REPRO_ROOT/data/hf_cache" \
  LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config" \
  PYTHONPATH="$REPRO_ROOT/repos/LIBERO" \
  MUJOCO_GL=osmesa \
  PYOPENGL_PLATFORM=osmesa \
  TOKENIZERS_PARALLELISM=false \
  TF_CPP_MIN_LOG_LEVEL=3 \
  WANDB_MODE=disabled \
  python experiments/robot/libero/main.py \
    --model_family openvla \
    --pretrained_checkpoint openvla/openvla-7b-finetuned-libero-10 \
    --task_suite_name libero_10 \
    --center_crop True \
    --num_trials_per_task 5 \
    --save_frames False \
    --run_id_note full_executor_baseline_5trials \
    --local_log_dir "$REPRO_ROOT/data/logs" \
    --frames_save_root_dir "$REPRO_ROOT/data/saved_frames"
```

### 7. VLM verifier / manual plan 集成 smoke

运行时间：2026-07-05 08:26:43 UTC
配置：`libero_spatial` task 0，1 trial，`--max_steps_override 1`，启用 `--enable_vlm_verifier True`，使用手写 plan 避开缺失的 DashScope planner key。
模型：

- Executor：`openvla/openvla-7b-finetuned-libero-spatial`
- Verifier：`Qwen/Qwen2.5-VL-3B-Instruct`

结果：集成路径跑通，Qwen verifier 在 `t=10` 被调用并返回 `Not Complete`；episode 按预期 timeout。

```text
Plan Source: manual_plan
Plan: ['pick up the black bowl', 'place the black bowl on the plate']
[t=10] VLM Check Start: 'pick up the black bowl' (Queue size: 1)
[t=10] VLM Check Result: Not Complete
Total Success Rate: 0.00 (0/1)
```

日志：

```text
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_05-08_26_43--vlm_env_manual_plan_verifier_smoke_1step.txt
```

同环境下还验证了不启用 verifier 的 OpenVLA 1-step smoke：

```text
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_05-08_25_39--vlm_env_openvla_smoke_1step.txt
```

复跑命令：

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"
AGENTIC_REPO="$REPRO_ROOT/repos/agentic-robot"

cd "$AGENTIC_REPO"
HF_HOME="$REPRO_ROOT/data/hf_cache" \
LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config" \
PYTHONPATH="$REPRO_ROOT/repos/LIBERO" \
MUJOCO_GL=osmesa \
PYOPENGL_PLATFORM=osmesa \
TOKENIZERS_PARALLELISM=false \
TF_CPP_MIN_LOG_LEVEL=3 \
WANDB_MODE=disabled \
/root/miniconda/envs/ar_agentic_libero_vlm/bin/python experiments/robot/libero/main.py \
  --model_family openvla \
  --pretrained_checkpoint openvla/openvla-7b-finetuned-libero-spatial \
  --task_suite_name libero_spatial \
  --center_crop True \
  --num_trials_per_task 1 \
  --max_tasks 1 \
  --max_steps_override 1 \
  --save_frames False \
  --local_log_dir "$REPRO_ROOT/data/logs" \
  --run_id_note vlm_env_manual_plan_verifier_smoke_1step \
  --enable_vlm_verifier True \
  --manual_plan "pick up the black bowl||place the black bowl on the plate"
```

### 8. VLM 环境 task 0 对照

运行时间：2026-07-05 08:29:56 到 08:33:52 UTC
suite：`libero_spatial` task 0，1 trial。

结果：

| 配置 | 结果 | 说明 |
|---|---:|---|
| `ar_agentic_libero_vlm`，原始 task 指令，verifier 关闭 | `1/1` | `t=91` env success |
| `ar_agentic_libero_vlm`，原始 task 指令，verifier 开启 | `1/1` | Qwen 从 `t=10` 到 `t=90` 检查均为 `Not Complete`，但不改变 executor 指令，`t=91` env success |
| `ar_agentic_libero_vlm`，手写 `pick/place` plan，verifier 开启 | `0/1` | verifier 从 `t=10` 到 `t=225` 均为 `Not Complete`，未切换到 place |
| `ar_agentic_libero_vlm`，手写 `pick/place` plan，`--vlm_history_length 5 --verify_frequency 10` | `0/1` | verifier 从 `t=10` 到 `t=220` 均为 `Not Complete`，历史帧没有解决切换问题 |

关键日志：

```text
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_05-08_33_06--vlm_env_executor_task0_1trial.txt
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_05-09_00_06--vlm_env_original_instruction_verifier_task0_1trial.txt
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_05-08_29_56--vlm_env_manual_plan_verifier_task0_1trial.txt
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_05-09_05_27--vlm_env_manual_plan_verifier_task0_1trial_hist5_freq10.txt
```

结论：新版 `transformers` verifier 环境没有破坏 OpenVLA executor 的 task 0 行为；当前回归来自朴素手写 plan / verifier 判断策略。继续做 SAP ablation 前，应优先处理：

- planner 生成的 subtask 是否保留足够空间关系，例如 `between the plate and the ramekin`。
- verifier prompt 对 `pick up` 的完成条件是否过严；如果对象已经被放下，当前 prompt 仍可能判定 pick 未完成。
- 子任务切换时机和 verifier prompt。单独把 `--vlm_history_length` 从 1 提到 5、把 `--verify_frequency` 从 5 调到 10 仍未触发 `pick up` 完成。

### 9. LRM planner API key env smoke

运行时间：2026-07-05 09:03:12 UTC
配置：`ar_agentic_libero`，`libero_spatial` task 0，1 trial，`--max_steps_override 1`，启用 `--use_llm_planner True`，显式传 `--llm_planner_api_key_env OPENAI_API_KEY`、`--llm_planner_base_url https://api.openai.com/v1`、`--llm_planner_model gpt-4o-mini`。

结果：当前 `OPENAI_API_KEY` 为无效 token，planner 返回空 plan，主流程按预期 fallback 到原始任务指令并完成 1-step timeout。

```text
LLM Planner Enabled: True
LLM Planner API Key Env: OPENAI_API_KEY
Warning: LLM planner returned no steps.
Plan Source: original_task
Total Success Rate: 0.00 (0/1)
```

日志：

```text
data/logs/PEV_V1-EVAL-libero_spatial-openvla-2026_07_05-09_03_12--planner_openai_invalid_key_fallback_smoke_1step.txt
```

复跑命令：

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"
AGENTIC_REPO="$REPRO_ROOT/repos/agentic-robot"

cd "$AGENTIC_REPO"
HF_HOME="$REPRO_ROOT/data/hf_cache" \
LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config" \
PYTHONPATH="$REPRO_ROOT/repos/LIBERO" \
MUJOCO_GL=osmesa \
PYOPENGL_PLATFORM=osmesa \
TOKENIZERS_PARALLELISM=false \
TF_CPP_MIN_LOG_LEVEL=3 \
WANDB_MODE=disabled \
/root/miniconda/envs/ar_agentic_libero/bin/python experiments/robot/libero/main.py \
  --model_family openvla \
  --pretrained_checkpoint openvla/openvla-7b-finetuned-libero-spatial \
  --task_suite_name libero_spatial \
  --center_crop True \
  --num_trials_per_task 1 \
  --max_tasks 1 \
  --max_steps_override 1 \
  --save_frames False \
  --local_log_dir "$REPRO_ROOT/data/logs" \
  --run_id_note planner_openai_invalid_key_fallback_smoke_1step \
  --use_llm_planner True \
  --llm_planner_api_key_env OPENAI_API_KEY \
  --llm_planner_base_url https://api.openai.com/v1 \
  --llm_planner_model gpt-4o-mini
```

## 完整评估命令

已用以下形式跑通 `libero_spatial`、`libero_object`、`libero_goal` 和 `libero_10`。要复跑或切 suite，只需替换 checkpoint 和 `--task_suite_name`：

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/agentic_robot_libero"
AGENTIC_REPO="$REPRO_ROOT/repos/agentic-robot"

cd "$AGENTIC_REPO"
conda run -n ar_agentic_libero env \
  HF_HOME="$REPRO_ROOT/data/hf_cache" \
  LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config" \
  PYTHONPATH="$REPRO_ROOT/repos/LIBERO" \
  MUJOCO_GL=osmesa \
  PYOPENGL_PLATFORM=osmesa \
  TOKENIZERS_PARALLELISM=false \
  TF_CPP_MIN_LOG_LEVEL=3 \
  WANDB_MODE=disabled \
  python experiments/robot/libero/main.py \
    --model_family openvla \
    --pretrained_checkpoint openvla/openvla-7b-finetuned-libero-spatial \
    --task_suite_name libero_spatial \
    --center_crop True \
    --num_trials_per_task 5 \
    --save_frames False \
    --local_log_dir "$REPRO_ROOT/data/logs"
```

要跑论文级指标，建议按官方默认 suite 分别跑：

- `libero_spatial`: `openvla/openvla-7b-finetuned-libero-spatial`
- `libero_object`: `openvla/openvla-7b-finetuned-libero-object`
- `libero_goal`: `openvla/openvla-7b-finetuned-libero-goal`
- `libero_10`: `openvla/openvla-7b-finetuned-libero-10`

## 对官方代码的必要修正

已在本地 `repos/agentic-robot/experiments/robot/libero/main.py` 做了最小 patch，并保存到：

```text
patches/agentic_robot_main_smoke.patch
```

修正内容：

1. `qwenvl.py` 依赖 `Qwen2_5_VLForConditionalGeneration`，但 OpenVLA 推荐的 `transformers==4.40.1` 不支持该类。已改为延迟到 `load_qwen_vl_model()` 内部导入，使当前 OpenVLA executor 环境可以正常 import；真正启用 VLM verifier 时仍需要更新版 `transformers`。
2. 增加 `--start_task_id`、`--max_tasks`、`--max_steps_override`，用于最小 smoke eval。默认值不改变完整评估行为。
3. 增加显式 SAP 控制参数：`--enable_vlm_verifier`、`--use_llm_planner`、`--manual_plan`、`--llm_planner_api_key_env`、`--vlm_model_id`、`--vlm_attn_implementation`、`--vlm_history_length` 等。默认不启用 planner / verifier，因此已完成的 baseline 仍是纯 OpenVLA executor。
4. 当 multi-step plan 存在但 VLM verifier 未启用时，本地代码会回退到原始任务指令，避免只执行第一个 subtask 后无法推进。

## 关键依赖坑

1. 官方 Agentic Robot repo 不是 standalone，缺少 `prismatic` 源码。这里额外 clone 并 editable 安装了 `moojink/openvla-oft`。
2. LIBERO 当前 checkout 的 `setup.py` 没有正确暴露 `libero.libero`，运行时必须设置：

```bash
PYTHONPATH="$REPRO_ROOT/repos/LIBERO"
LIBERO_CONFIG_PATH="$REPRO_ROOT/data/libero_config"
```

3. `robosuite==1.4.1` 与新 `mujoco==3.10.0` API 不兼容，已固定为：

```text
mujoco==2.3.7
```

4. headless 渲染需要系统 GL 库，已安装：

```bash
apt-get install -y libosmesa6 libegl1 libopengl0 libgl1
```

5. TensorFlow 2.15 / TFDS 4.9.3 组合需要较旧 metadata/protobuf 组合：

```text
tensorflow-metadata==1.14.0
protobuf==3.20.3
wandb==0.16.6
```

6. 官方模型加载硬编码 `flash_attention_2`，已安装：

```text
flash-attn==2.5.5
```

## 重要代码审计发现

原始开源版 `main.py` 不能完整代表论文里的 SAP + VLM verifier 闭环：

1. 代码中明确设置了 `VLM_ENABLED_EFFECTIVELY = False`，并打印 `No VLM`。
2. 虽然有 `hardcoded_plan`，但实际执行时设置的是：

```python
current_subtask_instruction = original_task_description
```

也就是说，原始默认 eval 更接近 OpenVLA executor 评估，而不是论文完整的 Planner-Executor-Verifier 闭环。本地 patch 已把 planner / verifier 做成显式可开关路径，且 verifier 集成 smoke 已通过；完整 SAP 指标还未完成，剩余条件是：

- 有效的 `DASHSCOPE_API_KEY` 或等价 LRM 接口 key，用于批量生成 task-level plan；当前本机 `OPENAI_API_KEY` 对 `https://api.openai.com/v1` 返回 401。
- 使用 `ar_agentic_libero_vlm` 跑 `libero_10` 或指定 task 的 SAP ablation，对比 executor baseline。
- 若继续追求论文完整设置，需要确认 LRM planner、manual plan、verifier 频率和历史帧长度等 ablation 配置。
- 当前手写 `pick/place` 分解在 `libero_spatial` task 0 上使 executor 从对照 `1/1` 变成 `0/1`，因此不能直接用该朴素分解代表论文 SAP。

## 参考源

- Agentic Robot: https://github.com/Agentic-Robot/agentic-robot
- Paper: https://arxiv.org/abs/2505.23450
- Project page: https://agentic-robot.github.io/
- OpenVLA-OFT: https://github.com/moojink/openvla-oft
- LIBERO setup notes: https://github.com/moojink/openvla-oft/blob/main/LIBERO.md
