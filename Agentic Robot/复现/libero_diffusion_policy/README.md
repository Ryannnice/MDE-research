# LIBERO + Diffusion Policy 复现记录

日期: 2026-07-04  
目标: 从 P0 推荐路线中优先落地 `Diffusion Policy` 的 PushT 低维基线，作为后续接 LIBERO / Agentic Robot executor 的低层策略复现起点。  
状态: 已完成环境、官方代码、PushT 数据、Dataset 读取、CPU/GPU smoke test、PushT lowdim GPU 训练、top checkpoint 独立 eval、官方 PushT checkpoint eval。

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
conda run -n ar_pusht_dp python -c "import torch, hydra, gym, pygame, pymunk, shapely, cv2, diffusers; from diffusion_policy.env.pusht.pusht_keypoints_env import PushTKeypointsEnv; env=PushTKeypointsEnv(render_size=96); obs=env.reset(); obs2,reward,done,info=env.step([256,256]); print('torch', torch.__version__); print('cuda_available', torch.cuda.is_available()); print('cuda_device', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none'); print('obs_shape', obs.shape); print('reward', float(reward), 'done', bool(done))"
```

结果:

```text
torch 2.2.0+cu121
cuda_available True
cuda_device NVIDIA H200 NVL
obs_shape (40,)
reward 0.01217234148030715 done False
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

### 2.5 GPU 最小训练闭环

Torch 已从 CPU wheel 升级为 CUDA wheel:

```text
torch 2.2.0+cu121
cuda 12.1
cuda_available True
gpu NVIDIA H200 NVL
```

命令:

```bash
cd "repos/diffusion_policy"
export LD_LIBRARY_PATH=/root/miniconda/envs/ar_pusht_dp/lib:${LD_LIBRARY_PATH:-}
WANDB_MODE=disabled conda run -n ar_pusht_dp python train.py \
  --config-name=train_diffusion_unet_lowdim_workspace \
  training.device=cuda:0 \
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
  hydra.run.dir=data/outputs/smoke_gpu_20260704
```

日志:

```json
{"train_loss": 0.9778574705123901, "global_step": 0, "epoch": 0, "lr": 2.0000000000000002e-07}
{"train_loss": 0.9778574705123901, "global_step": 0, "epoch": 0, "lr": 2.0000000000000002e-07, "test/sim_max_reward_100000": 0.0, "test/mean_score": 0.0, "val_loss": 0.8161196708679199, "train_action_mse_error": 36048.33984375}
```

### 2.6 PushT lowdim GPU 训练

使用官方 lowdim 配置、`seed=42`、`training.device=cuda:0` 训练。训练在 epoch 1028 处手动中断，因为 best score 已在 epoch 350/750 附近饱和，继续跑到 5000 epoch 的边际收益不高；checkpoint 已完整保留。

```bash
cd "repos/diffusion_policy"
export LD_LIBRARY_PATH=/root/miniconda/envs/ar_pusht_dp/lib:${LD_LIBRARY_PATH:-}
WANDB_MODE=disabled conda run -n ar_pusht_dp python train.py \
  --config-name=train_diffusion_unet_lowdim_workspace \
  training.device=cuda:0 \
  logging.mode=disabled \
  hydra.run.dir=data/outputs/pusht_lowdim_full_seed42_gpu_20260704
```

输出目录:

```text
repos/diffusion_policy/data/outputs/pusht_lowdim_full_seed42_gpu_20260704
```

训练中在线 rollout 最佳结果:

```text
best_epoch 350
best_test_mean_score 0.9012120767010411
best_val_loss 0.08325295895338058
best_train_mean_score 0.8651125491565067
```

最后一次完整在线 rollout:

```text
epoch 1000
test_mean_score 0.8646693129152462
val_loss 0.11207826435565948
```

保留的 checkpoint:

```text
epoch=0350-test_mean_score=0.901.ckpt
epoch=0750-test_mean_score=0.901.ckpt
epoch=0800-test_mean_score=0.882.ckpt
epoch=0900-test_mean_score=0.893.ckpt
epoch=0950-test_mean_score=0.882.ckpt
latest.ckpt
```

### 2.7 top checkpoint 独立 eval

`epoch=0350` 和 `epoch=0750` 的训练时分数非常接近，因此都单独跑了 `eval.py`。独立 eval 里 `epoch=0750` 更高。

命令模板:

```bash
cd "repos/diffusion_policy"
export LD_LIBRARY_PATH=/root/miniconda/envs/ar_pusht_dp/lib:${LD_LIBRARY_PATH:-}
conda run -n ar_pusht_dp python eval.py \
  --checkpoint data/outputs/pusht_lowdim_full_seed42_gpu_20260704/checkpoints/epoch=0750-test_mean_score=0.901.ckpt \
  --output_dir data/eval_outputs/pusht_lowdim_gpu_epoch0750_top_20260704 \
  --device cuda:0
```

结果:

| checkpoint | eval output | test/mean_score | train/mean_score |
|---|---|---:|---:|
| `epoch=0350-test_mean_score=0.901.ckpt` | `data/eval_outputs/pusht_lowdim_gpu_epoch0350_best_20260704/eval_log.json` | `0.8815358536610566` | `0.9950847996718665` |
| `epoch=0750-test_mean_score=0.901.ckpt` | `data/eval_outputs/pusht_lowdim_gpu_epoch0750_top_20260704/eval_log.json` | `0.9067247098960688` | `0.9174882088267978` |

当前本地训练出的最佳独立 eval checkpoint:

```text
repos/diffusion_policy/data/outputs/pusht_lowdim_full_seed42_gpu_20260704/checkpoints/epoch=0750-test_mean_score=0.901.ckpt
```

### 2.8 官方 PushT checkpoint eval

官方 checkpoint 已通过 HTTP range 分片并行下载并合并，避免单连接限速。

checkpoint:

```text
repos/diffusion_policy/data/checkpoints/epoch=0550-test_mean_score=0.969.ckpt
```

文件校验:

```text
size 1044185793 bytes
sha256 f804e16575e261fa0b7e981da3f67741fc8517817734320d550e43a4182bf876
```

命令:

```bash
cd "repos/diffusion_policy"
export LD_LIBRARY_PATH=/root/miniconda/envs/ar_pusht_dp/lib:${LD_LIBRARY_PATH:-}
conda run -n ar_pusht_dp python eval.py \
  --checkpoint data/checkpoints/epoch=0550-test_mean_score=0.969.ckpt \
  --output_dir data/eval_outputs/pusht_lowdim_official_epoch0550_20260704 \
  --device cuda:0
```

结果:

```json
{
  "test/mean_score": 0.9091062879409345,
  "train/mean_score": 0.9958690138323644
}
```

完整日志:

```text
repos/diffusion_policy/data/eval_outputs/pusht_lowdim_official_epoch0550_20260704/eval_log.json
```

## 3. 当前限制

1. 当前本地 PushT 训练结果是 `seed=42` 单次训练，独立 eval `test/mean_score=0.9067247098960688`，已经是可比较 baseline，但还不是论文级多 seed 统计。
2. 官方 checkpoint 在当前环境下独立 eval 为 `test/mean_score=0.9091062879409345`，略低于 checkpoint 文件名中的训练期 `0.969`，与官方 README 示例约 `0.915` 接近；最终报告应明确区分 checkpoint 文件名、训练时在线 rollout 和本地 `eval.py` 结果。
3. 训练时在线 rollout 和 `eval.py` 独立 eval 的分数会有采样差异，README 中以 `eval.py` 独立 eval 作为最终本地分数。
4. 还没有把 Diffusion Policy 接到 LIBERO；当前完成的是 PushT lowdim 官方基线。
5. `LD_LIBRARY_PATH` 会让 bash 输出 `libtinfo.so.6: no version information available` 警告，目前不影响 Python/av/训练/评估运行。

## 4. 下一步完整复现

### 4.1 继续追 PushT 官方分数

如果目标是尽量接近官方 checkpoint / 论文数字，可以继续做:

1. 跑满 5000 epoch，或以 `epoch=0750` 为当前本地最佳点继续训练观察；当前本地最佳独立 eval `0.9067247098960688`，官方 checkpoint 独立 eval `0.9091062879409345`。
2. 补 2-3 个随机种子，报告 mean/std。
3. 若要严格对齐官方日志，复核 eval seed / `n_test` / runner 配置差异。

### 4.2 官方预训练 checkpoint 复跑

官方 checkpoint 已下载到 `data/checkpoints/epoch=0550-test_mean_score=0.969.ckpt`。复跑命令:

```bash
cd "repos/diffusion_policy"
export LD_LIBRARY_PATH=/root/miniconda/envs/ar_pusht_dp/lib:${LD_LIBRARY_PATH:-}
conda run -n ar_pusht_dp python eval.py \
  --checkpoint data/checkpoints/epoch=0550-test_mean_score=0.969.ckpt \
  --output_dir data/eval_outputs/pusht_lowdim_official_epoch0550_rerun \
  --device cuda:0
```

本次实际结果为 `test/mean_score=0.9091062879409345`。

### 4.3 接 LIBERO

LIBERO 仓库已 clone。建议先把当前 PushT lowdim checkpoint 固化成可复现实验资产，再做 LIBERO:

1. 创建 `libero` 官方 Python 3.8.13 环境。
2. 下载 `libero_spatial` 或 `libero_goal` 小套件。
3. 先跑 LIBERO 官方 BC/Transformer baseline。
4. 再考虑把 DP-style policy 或 OpenVLA executor 接入 LIBERO。
