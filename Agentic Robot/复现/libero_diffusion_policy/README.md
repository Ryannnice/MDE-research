# LIBERO + Diffusion Policy 复现记录

日期: 2026-07-04  
目标: 从 P0 推荐路线中优先落地 `Diffusion Policy` 的 PushT 低维基线，作为后续接 LIBERO / Agentic Robot executor 的低层策略复现起点。  
状态: 已完成环境、官方代码、PushT 数据、Dataset 读取、CPU/GPU smoke test、PushT lowdim GPU 完整训练、top checkpoint 独立 eval、官方 PushT checkpoint eval。

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

### 环境删除后的恢复命令

2026-07-05 已按下面流程重建并验证 `ar_pusht_dp`。不要只执行 `conda env create -f environment_ar_pusht_dp.yml`：该文件的 pip 段包含 `torch==2.2.0+cu121`，默认 PyPI 无法直接解析 CUDA wheel；同时 `av/pillow` 应保留为 conda runtime，避免 ffmpeg/libstdc++ 兼容问题。

```bash
REPRO_ROOT="/renyuanliu/MDE-research/Agentic Robot/复现/libero_diffusion_policy"
DP_REPO="$REPRO_ROOT/repos/diffusion_policy"
PY=/root/miniconda/envs/ar_pusht_dp/bin/python

conda env remove -n ar_pusht_dp || true
conda create -y -n ar_pusht_dp -c defaults -c conda-forge \
  python=3.9.25 pip=22.2.2 setuptools=65.5.0 wheel=0.38.4 \
  av=10.0.0 ffmpeg=6.1.2 pillow=11.3.0

WHEELHOUSE=/tmp/ar_pusht_wheelhouse
mkdir -p "$WHEELHOUSE"
$PY -m pip download --no-deps \
  --extra-index-url https://download.pytorch.org/whl/cu121 \
  -d "$WHEELHOUSE" "torch==2.2.0+cu121"

$PY -m pip install --index-url https://pypi.org/simple --timeout 60 \
  filelock==3.19.1 fsspec==2025.10.0 Jinja2==3.1.6 networkx==3.2.1 \
  sympy==1.14.0 typing_extensions==4.16.0 triton==2.2.0 \
  nvidia-cuda-nvrtc-cu12==12.1.105 nvidia-cuda-runtime-cu12==12.1.105 \
  nvidia-cuda-cupti-cu12==12.1.105 nvidia-cudnn-cu12==8.9.2.26 \
  nvidia-cublas-cu12==12.1.3.1 nvidia-cufft-cu12==11.0.2.54 \
  nvidia-curand-cu12==10.3.2.106 nvidia-cusolver-cu12==11.4.5.107 \
  nvidia-cusparse-cu12==12.1.0.106 nvidia-nccl-cu12==2.19.3 \
  nvidia-nvtx-cu12==12.1.105 nvidia-nvjitlink-cu12==12.9.86

$PY -m pip install --no-deps "$WHEELHOUSE"/torch-2.2.0+cu121-cp39-cp39-linux_x86_64.whl
rm -f /root/miniconda/envs/ar_pusht_dp/lib/python3.9/site-packages/torch-2.2.0+cu121.dist-info/direct_url.json

REQ="$REPRO_ROOT/pip_freeze_ar_pusht_dp.txt"
$PY -m pip install --index-url https://pypi.org/simple --timeout 60 \
  -r <(grep -v -E '^(torch==|triton==|nvidia-|-e git\+|av @|pillow @)' "$REQ")

$PY -m pip install --no-deps -e "$DP_REPO"
```

本次恢复后已验证：

- `/root/miniconda/envs/ar_pusht_dp/bin/python -m pip check`：通过。
- PushT 仿真环境 reset/step：通过，`obs_shape (40,)`，`done False`。
- PushT lowdim dataset 读取：`dataset_len 10726`，`obs_shape [16, 20]`，`action_shape [16, 2]`。
- 1-step CPU train/eval/validation smoke：通过，输出在 `repos/diffusion_policy/data/outputs/restore_smoke_cpu_20260705`。

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

使用官方 lowdim 配置、`seed=42`、`training.device=cuda:0` 训练。初次运行曾在 epoch 1028 左右中断；环境恢复后从 `latest.ckpt` 的 epoch 1000 继续补跑 `training.num_epochs=4000` 个本地 epoch。官方 workspace 的 resume 逻辑会从 checkpoint 中的 `self.epoch` 继续累加，因此本次完整跑到 epoch 5000；脚本在 epoch 4950 保存最后一个 `latest.ckpt`，这与从零训练时的保存节奏一致。

```bash
cd "repos/diffusion_policy"
export LD_LIBRARY_PATH=/root/miniconda/envs/ar_pusht_dp/lib:${LD_LIBRARY_PATH:-}
WANDB_MODE=disabled conda run -n ar_pusht_dp python train.py \
  --config-name=train_diffusion_unet_lowdim_workspace \
  training.device=cuda:0 \
  logging.mode=disabled \
  hydra.run.dir=data/outputs/pusht_lowdim_full_seed42_gpu_20260704
```

恢复后补跑命令:

```bash
cd "repos/diffusion_policy"
export LD_LIBRARY_PATH=/root/miniconda/envs/ar_pusht_dp/lib:${LD_LIBRARY_PATH:-}
WANDB_MODE=disabled /root/miniconda/envs/ar_pusht_dp/bin/python train.py \
  --config-name=train_diffusion_unet_lowdim_workspace \
  training.device=cuda:0 \
  training.num_epochs=4000 \
  logging.mode=disabled \
  hydra.run.dir=data/outputs/pusht_lowdim_full_seed42_gpu_20260704
```

输出目录:

```text
repos/diffusion_policy/data/outputs/pusht_lowdim_full_seed42_gpu_20260704
```

完整训练后 checkpoint 元数据:

```text
latest.ckpt global_step 207982
latest.ckpt epoch 4950
```

完整训练中在线 rollout 最佳结果:

```text
best_epoch 2350
best_test_mean_score 0.9057693529859826
best_val_loss 0.14871586859226227
```

最后一次完整在线 rollout:

```text
epoch 4950
test_mean_score 0.8770879795016302
val_loss 0.19117677211761475
```

保留的 checkpoint:

```text
epoch=0350-test_mean_score=0.901.ckpt
epoch=0750-test_mean_score=0.901.ckpt
epoch=0800-test_mean_score=0.882.ckpt
epoch=0900-test_mean_score=0.893.ckpt
epoch=0950-test_mean_score=0.882.ckpt
epoch=1900-test_mean_score=0.904.ckpt
epoch=2100-test_mean_score=0.902.ckpt
epoch=2350-test_mean_score=0.906.ckpt
epoch=2500-test_mean_score=0.900.ckpt
epoch=2850-test_mean_score=0.905.ckpt
latest.ckpt
```

### 2.7 top checkpoint 独立 eval

`epoch=0350` 和 `epoch=0750` 的训练时分数非常接近，因此都单独跑了 `eval.py`。补跑完整 5000 epoch 后，在线最佳点是 `epoch=2350`，也单独跑了 `eval.py`。独立 eval 里 `epoch=0750` 更高，并且环境恢复后复跑结果一致。

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
| `epoch=0750-test_mean_score=0.901.ckpt` | `data/eval_outputs/pusht_lowdim_gpu_epoch0750_top_full_rerun_20260705/eval_log.json` | `0.9067247098960688` | `0.9174882088267978` |
| `epoch=2350-test_mean_score=0.906.ckpt` | `data/eval_outputs/pusht_lowdim_gpu_epoch2350_top_full_20260705/eval_log.json` | `0.8858753866558553` | `0.8035799682933433` |

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

1. 当前本地 PushT 训练结果是 `seed=42` 单次完整训练，独立 eval 最佳 `test/mean_score=0.9067247098960688`，已经是可比较 baseline，但还不是论文级多 seed 统计。
2. 官方 checkpoint 在当前环境下独立 eval 为 `test/mean_score=0.9091062879409345`，略低于 checkpoint 文件名中的训练期 `0.969`，与官方 README 示例约 `0.915` 接近；最终报告应明确区分 checkpoint 文件名、训练时在线 rollout 和本地 `eval.py` 结果。
3. 训练时在线 rollout 和 `eval.py` 独立 eval 的分数会有采样差异，README 中以 `eval.py` 独立 eval 作为最终本地分数。
4. 还没有把 Diffusion Policy 接到 LIBERO；当前完成的是 PushT lowdim 官方基线。
5. `LD_LIBRARY_PATH` 会让 bash 输出 `libtinfo.so.6: no version information available` 警告，目前不影响 Python/av/训练/评估运行。

## 4. 下一步完整复现

### 4.1 继续追 PushT 官方分数

如果目标是尽量接近官方 checkpoint / 论文数字，可以继续做:

1. 补 2-3 个随机种子，报告 mean/std；当前 `seed=42` 最佳独立 eval `0.9067247098960688`，官方 checkpoint 独立 eval `0.9091062879409345`。
2. 若要严格对齐官方日志，复核 eval seed / `n_test` / runner 配置差异。
3. 如需继续训练策略层面的 ablation，优先从 `epoch=0750` 或官方 checkpoint 分支，而不是使用 full run 后段 checkpoint。

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
