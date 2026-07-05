# Agentic Robot / LIBERO 复现记录

日期：2026-07-04

## 结论

已完成到“OpenVLA executor baseline 可比较”的状态：

1. 官方 Agentic Robot 代码已拉取：`Agentic-Robot/agentic-robot`，commit `cafb8d5`。
2. 已创建 conda 环境：`ar_agentic_libero`，Python 3.10。
3. 已补齐 OpenVLA / OpenVLA-OFT / LIBERO / robosuite / MuJoCo / FlashAttention 依赖。
4. 已通过 LIBERO 仿真 smoke test：`libero_spatial` task 0 reset、render、dummy action step 正常。
5. 已完成 7B OpenVLA 最小模型 smoke eval：加载 `openvla/openvla-7b-finetuned-libero-spatial`，跑 1 个 task、1 个 episode、2 个模型 action steps，按预期 timeout。
6. 已完成 `libero_spatial` 完整 OpenVLA executor baseline：10 tasks x 5 trials，成功率 `0.88 (44/50)`。
7. 已完成 `libero_object` 完整 OpenVLA executor baseline：10 tasks x 5 trials，成功率 `0.82 (41/50)`。
8. 已完成 `libero_goal` 完整 OpenVLA executor baseline：10 tasks x 5 trials，成功率 `0.76 (38/50)`。
9. 已完成 `libero_10` 完整 OpenVLA executor baseline：10 tasks x 5 trials，成功率 `0.42 (21/50)`。

当前结果是 OpenVLA executor baseline，不是论文完整 SAP / VLM verifier 闭环。本地已给 `main.py` 增加可选 planner / verifier 开关；默认仍保持 executor baseline 行为。

## 目录

```text
agentic_robot_libero/
  README.md
  environment_ar_agentic_libero.yml
  pip_freeze_ar_agentic_libero.txt
  patches/agentic_robot_main_smoke.patch
  tools/smoke_libero_env.py
  data/libero_config/config.yaml
  data/logs/
  data/hf_cache/              # ignored, HF checkpoint cache
  data/libero_datasets/       # ignored
  repos/                      # ignored, cloned upstream repos
```

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
3. 增加显式 SAP 控制参数：`--enable_vlm_verifier`、`--use_llm_planner`、`--manual_plan`、`--vlm_model_id`、`--vlm_attn_implementation`、`--vlm_history_length` 等。默认不启用 planner / verifier，因此已完成的 baseline 仍是纯 OpenVLA executor。
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

也就是说，原始默认 eval 更接近 OpenVLA executor 评估，而不是论文完整的 Planner-Executor-Verifier 闭环。本地 patch 已把 planner / verifier 做成显式可开关路径，但完整 SAP 指标还未完成，剩余条件是：

- `DASHSCOPE_API_KEY` 或等价 LRM 接口，用于批量生成 task-level plan。
- 一个与 Qwen2.5-VL 兼容的 verifier 环境；当前 `ar_agentic_libero` 是 `transformers==4.40.1`，可 import `qwenvl.py`，但不能加载 `Qwen2_5_VLForConditionalGeneration`。
- 在启用 verifier 后，跑 `libero_10` 或指定 task 的 SAP ablation，对比 executor baseline。

## 参考源

- Agentic Robot: https://github.com/Agentic-Robot/agentic-robot
- Paper: https://arxiv.org/abs/2505.23450
- Project page: https://agentic-robot.github.io/
- OpenVLA-OFT: https://github.com/moojink/openvla-oft
- LIBERO setup notes: https://github.com/moojink/openvla-oft/blob/main/LIBERO.md
