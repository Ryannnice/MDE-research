# Agentic Robot / LIBERO 复现记录

日期：2026-07-04

## 结论

已完成到“可第一时间继续复现”的状态：

1. 官方 Agentic Robot 代码已拉取：`Agentic-Robot/agentic-robot`，commit `cafb8d5`。
2. 已创建 conda 环境：`ar_agentic_libero`，Python 3.10。
3. 已补齐 OpenVLA / OpenVLA-OFT / LIBERO / robosuite / MuJoCo / FlashAttention 依赖。
4. 已通过 LIBERO 仿真 smoke test：`libero_spatial` task 0 reset、render、dummy action step 正常。
5. 已完成 7B OpenVLA 最小模型 smoke eval：加载 `openvla/openvla-7b-finetuned-libero-spatial`，跑 1 个 task、1 个 episode、2 个模型 action steps，按预期 timeout。

当前没有跑完整论文指标。完整指标需要去掉 smoke 参数，按 task suite 跑完整 rollouts。

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

## 完整评估命令

去掉 smoke 限制即可跑完整 task suite。示例：

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

1. `qwenvl.py` 依赖 `Qwen2_5_VLForConditionalGeneration`，但 OpenVLA 推荐的 `transformers==4.40.1` 不支持该类。由于官方 `main.py` 当前实际禁用了 VLM，已改成可选导入，避免不用 VLM 时直接崩溃。
2. 增加 `--start_task_id`、`--max_tasks`、`--max_steps_override`，用于最小 smoke eval。默认值不改变完整评估行为。

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

当前开源版 `main.py` 不能完整代表论文里的 SAP + VLM verifier 闭环：

1. 代码中明确设置了 `VLM_ENABLED_EFFECTIVELY = False`，并打印 `No VLM`。
2. 虽然有 `hardcoded_plan`，但实际执行时设置的是：

```python
current_subtask_instruction = original_task_description
```

也就是说，当前 smoke eval 和默认 eval 更接近 OpenVLA executor 评估，而不是论文完整的 Planner-Executor-Verifier 闭环。若要复现论文声称的 Agentic Robot 增益，需要进一步修复/实现：

- LRM 规划阶段批量接入，而不是手动 hard-coded plan。
- Qwen2.5-VL verifier 与 OpenVLA 环境的 transformers 版本冲突。
- verifier completion 后的 subtask 切换逻辑。

## 参考源

- Agentic Robot: https://github.com/Agentic-Robot/agentic-robot
- Paper: https://arxiv.org/abs/2505.23450
- Project page: https://agentic-robot.github.io/
- OpenVLA-OFT: https://github.com/moojink/openvla-oft
- LIBERO setup notes: https://github.com/moojink/openvla-oft/blob/main/LIBERO.md
