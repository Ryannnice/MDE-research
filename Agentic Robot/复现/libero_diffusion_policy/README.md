# LIBERO + Diffusion Policy 复现记录

日期: 2026-07-04  
目标: 从 P0 推荐路线中优先落地 `Diffusion Policy` 的 PushT 低维基线，作为后续接 LIBERO / Agentic Robot executor 的低层策略复现起点。  
状态: 已完成环境、官方代码、PushT 数据、Dataset 读取、最小训练闭环、最小 eval 闭环。

## 1. 代码与环境

仓库:

| 组件 | 路径 | commit |
|---|---|---|
| LIBERO | `repos/LIBERO` | `8f1084e` |
| Diffusion Policy | `repos/diffusion_policy` | `5ba07ac` |

Conda 环境:

```bash
conda activate ar_pusht_dp
```

环境导出:

- `environment_ar_pusht_dp.yml`
- `pip_freeze_ar_pusht_dp.txt`

运行 `diffusion_policy` 里涉及 `av/ffmpeg` 的脚本时，需要优先使用 conda runtime:

```bash
export LD_LIBRARY_PATH=/root/miniconda/envs/ar_pusht_dp/lib:${LD_LIBRARY_PATH:-}
```

否则会触发系统 `libstdc++` 的 `CXXABI_1.3.15` 缺失问题。

## 2. 已完成验收

### 2.1 PushT 仿真环境 sanity check

命令:

```bash
conda run -n ar_pusht_dp python -c "import torch, hydra, gym, pygame, pymunk, shapely, cv2, diffusers; from diffusion_policy.env.pusht.pusht_keypoints_env import PushTKeypointsEnv; env=PushTKeypointsEnv(render_size=96); obs=env.reset(); obs2,reward,done,info=env.step([256,256]); print('torch', torch.__version__); print('cuda_available', torch.cuda.is_available()); print('obs_shape', obs.shape); print('reward', float(reward), 'done', bool(done))"
```

结果:

```text
torch 1.13.1+cpu
cuda_available False
obs_shape (40,)
reward 0.0 done False
```

### 2.2 官方 PushT 数据下载与 Dataset 读取

单连接下载被 Columbia 源限速到十几 KB/s，因此使用 HTTP range 并行分片下载了 `pusht.zip`。

数据路径:

```text
repos/diffusion_policy/data/pusht/pusht_cchi_v7_replay.zarr
```

Dataset 读取结果:

```text
dataset_len 10726
obs_shape (16, 20) action_shape (16, 2)
obs_mean 173.7696990966797 action_mean 177.8125
```

### 2.3 最小训练闭环

目标不是复现论文分数，而是验证官方训练链路可跑通: dataloader -> model -> loss/backward -> 1-step rollout -> validation -> checkpoint。

命令:

```bash
cd "repos/diffusion_policy"
export LD_LIBRARY_PATH=/root/miniconda/envs/ar_pusht_dp/lib:${LD_LIBRARY_PATH:-}
WANDB_MODE=disabled conda run -n ar_pusht_dp python train.py \
  --config-name=train_diffusion_unet_lowdim_workspace \
  training.device=cpu \
  training.seed=42 \
  training.num_epochs=1 \
  training.max_train_steps=1 \
  training.max_val_steps=1 \
  training.debug=false \
  training.use_ema=false \
  dataloader.batch_size=2 \
  dataloader.num_workers=0 \
  dataloader.pin_memory=false \
  val_dataloader.batch_size=2 \
  val_dataloader.num_workers=0 \
  val_dataloader.pin_memory=false \
  policy.num_inference_steps=2 \
  task.env_runner.n_train=0 \
  task.env_runner.n_train_vis=0 \
  task.env_runner.n_test=1 \
  task.env_runner.n_test_vis=0 \
  task.env_runner.n_envs=1 \
  task.env_runner.max_steps=1 \
  logging.mode=disabled \
  hydra.run.dir=data/outputs/smoke_cpu_20260704
```

输出文件:

```text
data/outputs/smoke_cpu_20260704/.hydra/config.yaml
data/outputs/smoke_cpu_20260704/.hydra/overrides.yaml
data/outputs/smoke_cpu_20260704/checkpoints/latest.ckpt
data/outputs/smoke_cpu_20260704/checkpoints/epoch=0000-test_mean_score=0.000.ckpt
data/outputs/smoke_cpu_20260704/logs.json.txt
```

日志:

```json
{"train_loss": 1.027917504310608, "global_step": 0, "epoch": 0, "lr": 2.0000000000000002e-07}
{"train_loss": 1.027917504310608, "global_step": 0, "epoch": 0, "lr": 2.0000000000000002e-07, "test/sim_max_reward_100000": 0.0, "test/mean_score": 0.0, "val_loss": 1.2539448738098145, "train_action_mse_error": 36940.26953125}
```

### 2.4 最小 eval 闭环

命令:

```bash
cd "repos/diffusion_policy"
export LD_LIBRARY_PATH=/root/miniconda/envs/ar_pusht_dp/lib:${LD_LIBRARY_PATH:-}
conda run -n ar_pusht_dp python eval.py \
  --checkpoint data/outputs/smoke_cpu_20260704/checkpoints/latest.ckpt \
  --output_dir data/eval_outputs/smoke_cpu_latest \
  --device cpu
```

结果:

```json
{
  "test/mean_score": 0.0,
  "test/sim_max_reward_100000": 0.0
}
```

## 3. 当前限制

1. GPU 当前被其它训练占用约 73GB，且利用率接近 99%。本次只跑 CPU smoke test。
2. 官方预训练 checkpoint `epoch=0550-test_mean_score=0.969.ckpt` 大约 996MB，Columbia 源单连接只有十几 KB/s。已放弃单连接下载，避免留下误用的半截 checkpoint。
3. Smoke test 的 `test/mean_score=0.0` 是预期结果，因为只训练 1 个 batch、1 个 rollout step，不能代表论文性能。
4. `LD_LIBRARY_PATH` 会让 bash 输出 `libtinfo.so.6: no version information available` 警告，目前不影响 Python/av/训练/评估运行。

## 4. 下一步完整复现

### 4.1 完整训练低维 PushT

等 GPU 空闲后，先跑低维官方配置。建议先把 rollout 降低到小规模，确认 GPU 训练速度和显存:

```bash
cd "repos/diffusion_policy"
export LD_LIBRARY_PATH=/root/miniconda/envs/ar_pusht_dp/lib:${LD_LIBRARY_PATH:-}
WANDB_MODE=disabled conda run -n ar_pusht_dp python train.py \
  --config-name=train_diffusion_unet_lowdim_workspace \
  training.device=cuda:0 \
  logging.mode=disabled \
  hydra.run.dir=data/outputs/pusht_lowdim_full_seed42
```

### 4.2 评估官方预训练 checkpoint

如果继续从 Columbia 源下载，建议用 range 分片下载，不要用单连接 `wget`。下载完成后运行:

```bash
cd "repos/diffusion_policy"
export LD_LIBRARY_PATH=/root/miniconda/envs/ar_pusht_dp/lib:${LD_LIBRARY_PATH:-}
conda run -n ar_pusht_dp python eval.py \
  --checkpoint data/checkpoints/pusht_lowdim_dp_epoch0550_score0969.ckpt \
  --output_dir data/eval_outputs/pusht_lowdim_official_epoch0550 \
  --device cuda:0
```

预期官方 README 示例中的同类结果约为 `test/mean_score ~= 0.915`，但需要以实际下载的 checkpoint 和 eval seeds 为准。

### 4.3 接 LIBERO

LIBERO 仓库已 clone，但尚未安装环境。建议等 Diffusion Policy 低维 PushT 完整训练或官方 checkpoint eval 跑通后，再做 LIBERO:

1. 创建 `libero` 官方 Python 3.8.13 环境。
2. 下载 `libero_spatial` 或 `libero_goal` 小套件。
3. 先跑 LIBERO 官方 BC/Transformer baseline。
4. 再考虑把 DP-style policy 或 OpenVLA executor 接入 LIBERO。
