# Goal2Skill / RMBench 复现记录

日期: 2026-07-05

## 1. 当前结论

第二篇目标论文已按 `Goal2Skill: Long-Horizon Manipulation with Adaptive Planning and Reflection` 重新对齐，不再把 PushT / Diffusion Policy 当作第二篇目标论文本身。

当前本地状态:

| 项 | 状态 |
|---|---|
| Goal2Skill 论文 | 本地 PDF 已核对，arXiv `2604.13942` |
| Goal2Skill 官方代码 | 未在论文或公开检索中找到明确官方仓库 |
| Benchmark | 使用官方 RMBench 仓库 |
| RMBench 仓库 | `repos/RMBench` |
| RMBench commit | `57ee09c` |
| conda 环境 | `ar_goal2skill_rmbench` 已创建并导出；Pi0.5 独立环境 `ar_goal2skill_pi05` 已创建并导出 |
| RMBench assets | 已下载，约 `1.3G` |
| Goal2Skill 5-task demo 数据 | 已下载，约 `14G` |
| 每任务 demo 数 | 5 个任务均为 `50/50` hdf5 |
| DP 数据预处理 | 5 个 Goal2Skill 任务均已生成 `50` demos zarr |
| DP 训练 | `observe_and_pickup` debug 训练 2 epochs、full-50 非 debug 短训 2 epochs、官方配置单任务 600 epochs 均已通过 |
| ACT 数据预处理 | 5 个 Goal2Skill 任务均已生成 `50` demos hdf5 |
| ACT 训练 smoke | 通过，full-50 官方训练入口跑完 1 epoch |
| Pi0.5 数据预处理 | 5 个 Goal2Skill 任务均已生成 `50` demos hdf5 |
| Pi0.5 训练 smoke | 通过，OpenPI / LeRobot / norm stats / Pi0.5 base restore / 1-step train checkpoint 均已打通 |
| X-VLA 数据预处理 | 5 个 Goal2Skill 任务均已写入 `language_instruction` 并生成 meta |
| X-VLA 训练 smoke | X-VLA-Pt base model 已下载；5-task 合并 meta 的 1-iter 训练 smoke 通过 |
| SAPIEN render smoke | 通过，使用局部 NVIDIA `570.124.06` runtime wrapper 后输出 `Render Well` |
| RMBench rollout smoke / eval | 通过，`observe_and_pickup` 上 DP 2-epoch 1-episode 为 `1/1`，ACT 1-episode 为 `0/1`；DP 300/600-epoch checkpoint 的 5-episode sanity eval 均为 `0/5`；DP 600-epoch checkpoint 的 100-episode 正式评估为 `1/100` |

这意味着：RMBench 的 Python 环境、assets、Goal2Skill 论文 5 个任务数据、DP/ACT/Pi0.5/X-VLA baseline 的数据入口已经恢复；DP/ACT/Pi0.5/X-VLA 训练入口已做 smoke；RMBench 真实 rollout 链路也已恢复；DP 已完成 `observe_and_pickup` 单任务官方 600-epoch 训练，并完成该任务 `100` episodes 正式评估，结果为 `1/100 = 1.0%`。当前仍不能正式报告 Goal2Skill/RMBench 的完整 5-task baseline success rate，因为还需要覆盖其余 4 个任务、每任务 `100` episodes 的论文协议评估。

## 2. 论文与 benchmark 口径

Goal2Skill 论文主实验使用 RMBench 5 个代表任务：

| 类型 | 任务 |
|---|---|
| M(1) | `observe_and_pickup`, `rearrange_blocks` |
| M(n) | `battery_try`, `blocks_ranking_try`, `press_button` |

论文协议：

- 每个任务 `50` expert demonstrations 训练。
- 每个任务 `100` rollout episodes 评估。
- 指标是 task success rate。
- baseline 为 `DP`、`ACT`、`Pi0.5`、`X-VLA`。

论文主表数值如下，当前只是论文报告值，不是本地复现实验结果：

| Method | Observe and Pick Up | Rearrange Blocks | Battery Try | Blocks Ranking Try | Press Button | M(1) Avg | M(n) Avg | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DP | 1% | 0% | 10% | 10% | 0% | 0.5% | 6.7% | 4.2% |
| ACT | 1% | 29% | 19% | 0% | 0% | 15.0% | 6.3% | 9.8% |
| Pi0.5 | 9% | 13% | 16% | 6% | 0% | 11.0% | 7.3% | 8.8% |
| X-VLA | 9% | 13% | 26% | 1% | 0% | 11.0% | 9.0% | 9.8% |
| Goal2Skill | 8% | 38% | 46% | 60% | 10% | 23.0% | 38.7% | 32.4% |

## 3. 环境恢复

环境名：

```bash
ar_goal2skill_rmbench
ar_goal2skill_pi05
```

导出文件：

```text
goal2skill_rmbench/environment_ar_goal2skill_rmbench.yml
goal2skill_rmbench/pip_freeze_ar_goal2skill_rmbench.txt
goal2skill_rmbench/environment_ar_goal2skill_pi05.yml
goal2skill_rmbench/pip_freeze_ar_goal2skill_pi05.txt
goal2skill_rmbench/uv_freeze_ar_goal2skill_pi05.txt
```

已执行的主流程：

```bash
conda create -n ar_goal2skill_rmbench python=3.10 -y
conda run -n ar_goal2skill_rmbench bash script/_install.sh
```

官方 `_install.sh` 有两个需要记录的坑：

1. `pytorch3d` 首次安装失败，因为 isolated build 环境内找不到 `torch`。已用以下命令补装：

```bash
TORCH_CUDA_ARCH_LIST="9.0" MAX_JOBS=8 \
conda run -n ar_goal2skill_rmbench python -m pip install \
  "git+https://github.com/facebookresearch/pytorch3d.git@stable" \
  --no-build-isolation
```

2. `sapien==3.0.0b1` 依赖 `pkg_resources`，而新 setuptools 已移除该模块。已固定：

```bash
conda run -n ar_goal2skill_rmbench python -m pip install "setuptools==80.9.0"
```

DP 训练入口额外补了官方子模块未随 `_install.sh` 安装的依赖：

```bash
cd repos/RMBench/policy/DP
conda run -n ar_goal2skill_rmbench python -m pip install -e . diffusers einops dill
conda run -n ar_goal2skill_rmbench python -m pip install "diffusers>=0.35.0" "huggingface-hub==0.36.2"
```

说明：早期曾用 `diffusers==0.11.1` 与 `huggingface-hub==0.25.0` 兼容 DP；但 X-VLA 训练依赖新版 `transformers/peft/huggingface-hub`。当前已升级到 `diffusers 0.39.0`、`huggingface-hub 0.36.2`，并给 `policy/DP/diffusion_policy/model/common/lr_scheduler.py` 做了小补丁：`Union` / `Optional` / `Optimizer` 改从 `typing` 和 `torch.optim` 导入，调度逻辑仍使用 `diffusers.optimization.SchedulerType` 和 `TYPE_TO_SCHEDULER_FUNCTION`。

ACT 官方训练入口额外需要 `dm_control`，否则 `imitate_episodes.py` 在 import `sim_env.py` 时失败：

```bash
conda run -n ar_goal2skill_rmbench python -m pip install dm_control
```

X-VLA dataloader smoke 额外补齐：

```bash
conda run -n ar_goal2skill_rmbench python -m pip install "mmengine==0.10.5" "pyarrow==20.0.0"
conda install -n ar_goal2skill_rmbench -c conda-forge av=14.4.0 -y
conda run -n ar_goal2skill_rmbench python -m pip install --no-cache-dir "numpy==1.26.4" "scipy==1.15.0"
conda run -n ar_goal2skill_rmbench python -m pip install \
  "transformers==4.51.3" "accelerate==1.2.1" "peft==0.17.1" \
  "timm==1.0.12" "tensorboard" "json_numpy==2.1.0" "mediapy==1.2.4" \
  "fastapi" "uvicorn==0.34.3"
```

说明：`av==14.4.0` 的 pip 源码构建需要 FFmpeg dev 包，当前用 conda-forge 预编译包解决。安装 `av` 时 conda 曾拉入 `numpy 2.2.6` 残留，已清理残留并固定实际 import 版本为 `numpy 1.26.4`、`scipy 1.15.0`。

Pi0.5 / OpenPI 单独使用 Python 3.11 + uv 环境，避免破坏 RMBench / DP / ACT 的 Python 3.10 依赖：

```bash
conda create -n ar_goal2skill_pi05 python=3.11 -y
conda run -n ar_goal2skill_pi05 python -m pip install uv
cd repos/RMBench/policy/pi05
/root/miniconda/envs/ar_goal2skill_pi05/bin/uv sync
```

本地 `policy/pi05/.venv` 约 `10G`。Pi0.5 base 权重已通过 OpenPI 官方 `gs://openpi-assets/checkpoints/pi05_base/params` 下载到本机缓存，`/root/.cache/openpi/openpi-assets/checkpoints/pi05_base/params` 约 `12G`。

Pi0.5 本地代码还补了两个兼容 patch：

| 文件 | 改动 |
|---|---|
| `policy/pi05/src/openpi/training/data_loader.py` | `create_data_loader()` 接受 `num_workers`，兼容当前 `scripts/train.py` 调用 |
| `policy/pi05/src/openpi/training/checkpoints.py` | `CallbackHandler.async_save()` 改为兼容 `orbax-checkpoint 0.11.1` 的 `NoopFuture` 路径 |

环境内还补了两个 SAPIEN 兼容 patch：

| 文件 | 改动 |
|---|---|
| `/root/miniconda/envs/ar_goal2skill_rmbench/lib/python3.10/site-packages/sapien/wrapper/urdf_loader.py` | `urdf_file[:-4] + "srdf"` 改为 `urdf_file[:-4] + ".srdf"` |
| `/root/miniconda/envs/ar_goal2skill_rmbench/lib/python3.10/site-packages/sapien/_vulkan_tricks.py` | EGL ICD 目录不存在时跳过，避免 `FileNotFoundError` |

系统层面已安装通用 Vulkan/Mesa 包：

```bash
apt-get install -y libvulkan1 mesa-vulkan-drivers libegl1
```

这些包只能补齐 Mesa/lavapipe，不能替代 NVIDIA Vulkan/EGL runtime。当前已通过局部提取匹配宿主驱动 `570.124.06` 的 NVIDIA 用户态库解决，见第 6 节。

## 4. Assets 与数据

assets 下载命令：

```bash
conda run -n ar_goal2skill_rmbench bash script/_download_assets.sh
```

结果：

| 路径 | 大小 |
|---|---:|
| `repos/RMBench/assets` | `1.3G` |

Goal2Skill 5-task 数据下载使用 Hugging Face 断点续传，并限制为论文 5 个任务：

```bash
cd repos/RMBench/data
conda run -n ar_goal2skill_rmbench python - <<'PY'
from huggingface_hub import snapshot_download
patterns = [
    "data/observe_and_pickup/demo_clean/**",
    "data/rearrange_blocks/demo_clean/**",
    "data/battery_try/demo_clean/**",
    "data/blocks_ranking_try/demo_clean/**",
    "data/press_button/demo_clean/**",
]
snapshot_download(
    repo_id="TianxingChen/RMBench",
    repo_type="dataset",
    local_dir=".",
    allow_patterns=patterns,
    resume_download=True,
    max_workers=4,
)
PY
```

官方下载结构会落成 `repos/RMBench/data/data/<task>/...`，而代码读取 `repos/RMBench/data/<task>/...`。已创建相对符号链接：

```text
data/battery_try -> data/battery_try
data/blocks_ranking_try -> data/blocks_ranking_try
data/observe_and_pickup -> data/observe_and_pickup
data/press_button -> data/press_button
data/rearrange_blocks -> data/rearrange_blocks
```

这些链接位于 `repos/RMBench/data/` 下，实际解析到 `repos/RMBench/data/data/<task>`。

数据完整性：

| Task | hdf5 | `language_annotation.json` |
|---|---:|---|
| `observe_and_pickup` | `50/50` | yes |
| `rearrange_blocks` | `50/50` | yes |
| `battery_try` | `50/50` | yes |
| `blocks_ranking_try` | `50/50` | yes |
| `press_button` | `50/50` | yes |

样例 hdf5 key 已验证：

```text
['endpose', 'joint_action', 'observation', 'pointcloud', 'third_view_rgb']
```

## 5. 已完成验证

### 5.1 Python 依赖

已通过：

```bash
conda run -n ar_goal2skill_rmbench python -m pip check
```

结果：

```text
No broken requirements found.
```

核心导入已通过：

```text
torch 2.4.1+cu121
cuda 12.1
cuda_available True
sapien 3.0.0b1
pytorch3d 0.7.8
```

### 5.2 DP 数据预处理 smoke

命令：

```bash
cd repos/RMBench/policy/DP
conda run -n ar_goal2skill_rmbench bash process_data.sh observe_and_pickup demo_clean 1
```

结果：

```text
processing episode: 1 / 1
```

生成：

```text
repos/RMBench/policy/DP/data/observe_and_pickup-demo_clean-1.zarr
```

### 5.3 DP 论文 5-task 50-demo 数据与训练 smoke

已为 Goal2Skill 论文 5 个 RMBench 任务全部生成 DP zarr 输入：

```bash
cd repos/RMBench/policy/DP
for task in observe_and_pickup rearrange_blocks battery_try blocks_ranking_try press_button; do
  conda run -n ar_goal2skill_rmbench bash process_data.sh "$task" demo_clean 50
done
```

结果：

| Task | zarr shape | episodes | 大小 |
|---|---|---:|---:|
| `observe_and_pickup` | action/state/head_camera: `7473` steps | `50` | `670M` |
| `rearrange_blocks` | action/state/head_camera: `20085` steps | `50` | `1.6G` |
| `battery_try` | action/state/head_camera: `33512` steps | `50` | `3.0G` |
| `blocks_ranking_try` | action/state/head_camera: `73739` steps | `50` | `6.8G` |
| `press_button` | action/state/head_camera: `26302` steps | `50` | `2.5G` |

DP debug 训练 smoke：

```bash
cd repos/RMBench/policy/DP
conda run -n ar_goal2skill_rmbench python train.py --config-name=robot_dp_14.yaml \
  task.name=observe_and_pickup \
  task.dataset.zarr_path="data/observe_and_pickup-demo_clean-50.zarr" \
  training.debug=True \
  training.seed=42 \
  training.device="cuda:0" \
  exp_name=observe_and_pickup-robot_dp-smoke \
  logging.mode=offline \
  setting=demo_clean \
  expert_data_num=50 \
  head_camera_type=D435 \
  hydra.run.dir=data/outputs/smoke_observe_and_pickup_seed42
```

结果：2 个 debug epochs 完成，日志 `policy/DP/data/outputs/smoke_observe_and_pickup_seed42/logs.json.txt`，最后一条记录：

```text
train_loss=1.1599180698394775
val_loss=1.1415990591049194
train_action_mse_error=0.8883101940155029
```

DP full-50 非 debug 短训：

```bash
cd repos/RMBench/policy/DP
conda run -n ar_goal2skill_rmbench python train.py --config-name=robot_dp_14.yaml \
  task.name=observe_and_pickup \
  task.dataset.zarr_path="data/observe_and_pickup-demo_clean-50.zarr" \
  training.debug=False \
  training.seed=42 \
  training.device="cuda:0" \
  training.num_epochs=2 \
  training.checkpoint_every=2 \
  training.val_every=1 \
  training.sample_every=1 \
  exp_name=observe_and_pickup-robot_dp-full50-short2ep \
  logging.mode=offline \
  setting=demo_clean \
  expert_data_num=50 \
  head_camera_type=D435 \
  hydra.run.dir=data/outputs/short_observe_and_pickup_seed42_2ep
```

结果：

```text
epoch 0: 57 train batches, 1 val batch
epoch 1: 57 train batches, 1 val batch
final train_loss=0.9256509416981747
final val_loss=0.7713891863822937
final train_action_mse_error=0.7673165798187256
```

生成并验证可由部署侧 loader 读取：

```text
policy/DP/checkpoints/observe_and_pickup-demo_clean-50-42/1.ckpt
policy/DP/checkpoints/observe_and_pickup-demo_clean-50-42/2.ckpt
```

升级 `diffusers` 后又补跑了 1-step 训练 smoke，确认当前环境仍可训练：

```text
policy/DP/data/outputs/smoke_observe_and_pickup_postdiffusers/logs.json.txt
train_loss=1.1681005954742432
val_loss=1.1899713277816772
train_action_mse_error=0.8868616819381714
```

DP `observe_and_pickup` 官方配置单任务 600-epoch 训练：

```bash
cd repos/RMBench/policy/DP
WANDB_MODE=offline CUDA_VISIBLE_DEVICES=0 conda run --no-capture-output -n ar_goal2skill_rmbench \
  python train.py --config-name=robot_dp_14.yaml \
  task.name=observe_and_pickup \
  task.dataset.zarr_path=data/observe_and_pickup-demo_clean-50.zarr \
  training.debug=False \
  training.seed=42 \
  training.device=cuda:0 \
  training.num_epochs=600 \
  training.checkpoint_every=300 \
  training.val_every=1 \
  training.sample_every=50 \
  exp_name=observe_and_pickup-robot_dp-full600 \
  setting=demo_clean \
  expert_data_num=50 \
  head_camera_type=D435 \
  logging.mode=offline \
  hydra.run.dir=data/outputs/full_observe_and_pickup_seed42_600ep
```

结果：

```text
checkpoint: policy/DP/checkpoints/observe_and_pickup-demo_clean-50-42/300.ckpt
checkpoint: policy/DP/checkpoints/observe_and_pickup-demo_clean-50-42/600.ckpt
log: policy/DP/data/outputs/full_observe_and_pickup_seed42_600ep/logs.json.txt
final epoch=599
final global_step=34199
final train_loss=0.00042442281566061927
final val_loss=0.023543836548924446
```

说明：这是 DP baseline 的 `observe_and_pickup` 单任务、50 demos、seed 42、600 epochs 训练，配置接近官方 DP 训练入口；但它仍不是 Goal2Skill 论文完整 baseline，因为论文协议需要 5 个任务各自训练/评估，并且每任务 `100` rollout episodes。

### 5.4 ACT 数据预处理与训练 smoke

命令：

```bash
cd repos/RMBench/policy/ACT
conda run -n ar_goal2skill_rmbench bash process_data.sh observe_and_pickup demo_clean 1
```

结果：

```text
proccess 0 success!
```

生成：

```text
repos/RMBench/policy/ACT/processed_data/sim-observe_and_pickup/demo_clean-1/episode_0.hdf5
```

官方脚本会临时向 `policy/ACT/SIM_TASK_CONFIGS.json` 追加 `sim-observe_and_pickup-demo_clean-1` 配置；smoke 后已把该源码改动还原，保留生成的 1-episode processed 数据作为验证产物。

为避免再次修改 `SIM_TASK_CONFIGS.json`，ACT 训练 smoke 直接调用 `process_data.py` 内部的 `data_transform()` 生成 2-episode 数据：

```text
repos/RMBench/policy/ACT/processed_data/smoke-observe_and_pickup/demo_clean-2/
```

随后用 `utils.load_data + ACTPolicy` 完成 1 个 batch 的 forward / backward / optimizer step。结果：

```text
device cuda:0
batch_image (1, 3, 3, 480, 640)
qpos (1, 14)
action (1, 149, 14)
loss 53.686729431152344
l1 0.6912587881088257
kl 5.29954719543457
```

已为 Goal2Skill 论文 5 个 RMBench 任务全部生成 ACT full-50 processed 数据，并把对应配置写入 `policy/ACT/SIM_TASK_CONFIGS.json`：

| Task | processed episodes | 大小 |
|---|---:|---:|
| `observe_and_pickup` | `50/50` | `20G` |
| `rearrange_blocks` | `50/50` | `52G` |
| `battery_try` | `50/50` | `87G` |
| `blocks_ranking_try` | `50/50` | `190G` |
| `press_button` | `50/50` | `68G` |

full-50 dataloader smoke：

```text
Data from: processed_data/sim-observe_and_pickup/demo_clean-50
train_batches 20
val_batches 5
image (2, 3, 3, 480, 640)
qpos (2, 14)
action (2, 154, 14)
is_pad (2, 154)
```

ACT 官方训练入口 1-epoch smoke：

```bash
cd repos/RMBench/policy/ACT
conda run -n ar_goal2skill_rmbench python imitate_episodes.py \
  --task_name sim-observe_and_pickup-demo_clean-50 \
  --ckpt_dir ./act_ckpt/smoke-observe_and_pickup/demo_clean-50-epoch1 \
  --policy_class ACT \
  --kl_weight 10 \
  --chunk_size 50 \
  --hidden_dim 512 \
  --batch_size 2 \
  --dim_feedforward 3200 \
  --num_epochs 1 \
  --lr 1e-5 \
  --save_freq 1 \
  --state_dim 14 \
  --seed 42
```

结果：

```text
Val loss:   65.89836
Train loss: 33.92073
Best ckpt, val loss 65.898361 @ epoch0
```

生成：

```text
policy/ACT/act_ckpt/smoke-observe_and_pickup/demo_clean-50-epoch1/
```

其中包含 `dataset_stats.pkl`、`policy_last.ckpt`、`policy_best.ckpt`、`policy_epoch_0_seed_42.ckpt`、`policy_epoch_1_seed_42.ckpt` 和训练曲线 png。

### 5.5 Pi0.5 数据预处理

Pi0.5 的 1-episode smoke 已通过，输出结构包含 `action`、三路相机 JPEG bytes、`qpos` 和 `instructions.json`。

已为 Goal2Skill 论文 5 个 RMBench 任务全部生成 Pi0.5 full-50 processed 数据：

```bash
cd repos/RMBench/policy/pi05
for task in observe_and_pickup rearrange_blocks battery_try blocks_ranking_try press_button; do
  conda run -n ar_goal2skill_rmbench bash process_data_pi05.sh "$task" demo_clean 50
done
```

结果：

| Task | processed episodes | episode0 action | episode0 cam_high | 大小 |
|---|---:|---:|---:|---:|
| `observe_and_pickup` | `50/50` | `(148, 14)` | `(148,)` | `696M` |
| `rearrange_blocks` | `50/50` | `(404, 14)` | `(404,)` | `2.0G` |
| `battery_try` | `50/50` | `(668, 14)` | `(668,)` | `3.8G` |
| `blocks_ranking_try` | `50/50` | `(1030, 14)` | `(1030,)` | `7.1G` |
| `press_button` | `50/50` | `(573, 14)` | `(573,)` | `2.7G` |

Pi0.5 独立 OpenPI 环境和训练入口也已做 smoke：

| 项 | 结果 |
|---|---|
| Python / uv 环境 | `ar_goal2skill_pi05` + `policy/pi05/.venv`，JAX CUDA 可用 |
| import smoke | `jax 0.5.0`，`torch 2.6.0+cu124`，`openpi` / `lerobot` import 通过 |
| LeRobot 转换 | `observe_and_pickup` episode 0 已转为本地 repo `rmbench/observe_and_pickup_demo_clean_1` |
| LeRobot 数据 | `len=148`，三路图像 `(3,480,640)`，`observation.state=(14,)`，`action=(14,)` |
| OpenPI dataloader | `actions=(1,50,32)`，三路图像 `(1,224,224,3)`，`state=(1,32)`，`tokenized_prompt=(1,200)` |
| norm stats | 已写入 `policy/pi05/assets/pi05_aloha_full_base/rmbench/observe_and_pickup_demo_clean_1/norm_stats.json` |
| Pi0.5 base | 官方 `pi05_base/params` 已下载并 restore 成功 |
| 训练 smoke | `pi05_aloha_full_base`，1 step，`loss=0.1976`，checkpoint 成功 finalize |

LeRobot 转换命令：

```bash
cd repos/RMBench/policy/pi05
/root/miniconda/envs/ar_goal2skill_pi05/bin/uv run python \
  examples/aloha_real/convert_aloha_data_to_lerobot_robotwin.py \
  --raw-dir processed_data/observe_and_pickup-demo_clean-50 \
  --repo-id rmbench/observe_and_pickup_demo_clean_1 \
  --episodes 0 \
  --mode image \
  --dataset-config.no-use-videos
```

Pi0.5 1-step 训练 smoke 命令：

```bash
cd repos/RMBench/policy/pi05
XLA_PYTHON_CLIENT_PREALLOCATE=false \
XLA_PYTHON_CLIENT_MEM_FRACTION=0.60 \
/root/miniconda/envs/ar_goal2skill_pi05/bin/uv run python scripts/train.py \
  pi05_aloha_full_base \
  --exp-name smoke_rmbench_observe_1step \
  --overwrite \
  --num-train-steps 1 \
  --batch-size 1 \
  --no-wandb-enabled \
  --data.repo-id rmbench/observe_and_pickup_demo_clean_1 \
  --checkpoint-base-dir ./checkpoints_pi05_smoke
```

输出 checkpoint：

```text
policy/pi05/checkpoints_pi05_smoke/pi05_aloha_full_base/smoke_rmbench_observe_1step/1
```

该 smoke 只验证 Pi0.5 / OpenPI 训练链路，不等同于论文 baseline 的完整训练或 100-episode rollout 评估。

### 5.6 X-VLA 数据预处理与训练 smoke

X-VLA 官方 `hdf5_add_language_instruction.py` 是硬编码示例脚本。为复现 Goal2Skill 5-task，本地新增了可重建脚本：

```text
goal2skill_rmbench/scripts/prepare_xvla_rmbench_meta.py
```

用途：

1. 从 `data/<task>/demo_clean/instructions/episode*.json` 读取自然语言 instruction。
2. 向每个 RMBench hdf5 写入顶层 `language_instruction`。
3. 生成 X-VLA meta JSON。

复现命令：

```bash
conda run -n ar_goal2skill_rmbench python \
  goal2skill_rmbench/scripts/prepare_xvla_rmbench_meta.py
```

已生成：

| Meta | datalist |
|---|---:|
| `policy/X-VLA/meta_rmbench/observe_and_pickup_demo_clean_50.json` | `50` |
| `policy/X-VLA/meta_rmbench/rearrange_blocks_demo_clean_50.json` | `50` |
| `policy/X-VLA/meta_rmbench/battery_try_demo_clean_50.json` | `50` |
| `policy/X-VLA/meta_rmbench/blocks_ranking_try_demo_clean_50.json` | `50` |
| `policy/X-VLA/meta_rmbench/press_button_demo_clean_50.json` | `50` |
| `policy/X-VLA/meta_rmbench/goal2skill_5task_demo_clean_50.json` | `250` |

每个 meta 均使用：

```json
{
  "dataset_name": "rmbench_abs_ee",
  "language_instruction_key": "language_instruction",
  "observation_key": ["observation/head_camera/rgb"]
}
```

本地还补了 X-VLA domain registry，让 `rmbench_abs_ee` 走已有 `RobotWin2Handler`：

```text
repos/RMBench/policy/X-VLA/datasets/domain_handler/registry.py
```

X-VLA-Pt base model 已下载：

```bash
cd repos/RMBench/policy/X-VLA
conda run -n ar_goal2skill_rmbench huggingface-cli download \
  --repo-type model 2toINF/X-VLA-Pt \
  --local-dir ./checkpoints/X-VLA-Pt
```

结果：

```text
policy/X-VLA/checkpoints/X-VLA-Pt/model.safetensors 3519068172 bytes
policy/X-VLA/checkpoints/X-VLA-Pt/ 约 3.3G
```

模型加载 smoke：

```text
xvla_load_ok XVLA XVLAProcessor
num_params 879482456
num_actions 30
action_mode ee6d
```

5-task 合并 meta 的 dataloader smoke 已通过：

```bash
cd repos/RMBench/policy/X-VLA
conda run -n ar_goal2skill_rmbench python - <<'PY'
from datasets.dataset import InfiniteDataReader

ds = InfiniteDataReader(
    "meta_rmbench/goal2skill_5task_demo_clean_50.json",
    num_actions=10,
    training=False,
    action_mode="ee6d",
)
sample = next(iter(ds))
print(sample["image_input"].shape, sample["proprio"].shape, sample["action"].shape)
PY
```

结果：

```text
== dataset rmbench_abs_ee with 250 trajs
image_input (3, 3, 224, 224) torch.float32
proprio (20,) torch.float32
action (10, 20) torch.float32
```

1-iteration 训练 smoke 已通过：

```bash
cd repos/RMBench/policy/X-VLA
conda run -n ar_goal2skill_rmbench python train.py \
  --models ./checkpoints/X-VLA-Pt \
  --train_metas_path meta_rmbench/goal2skill_5task_demo_clean_50.json \
  --learning_rate 1e-4 \
  --learning_coef 0.1 \
  --iters 1 \
  --freeze_steps 1000 \
  --warmup_steps 10 \
  --batch_size 1 \
  --save_interval 1 \
  --log_interval 1 \
  --output_dir runnings/smoke_goal2skill_5task_1iter_seed42 \
  --seed 42
```

结果：

```text
== dataset rmbench_abs_ee with 250 trajs
loss=355.3592
lr_core=0.00e+00
lr_vlm=0.00e+00
Saving model to runnings/smoke_goal2skill_5task_1iter_seed42/ckpt-1
```

生成：

```text
policy/X-VLA/runnings/smoke_goal2skill_5task_1iter_seed42/ckpt-1/model.safetensors
```

当前 X-VLA 的数据、模型加载和训练入口已通；正式 baseline 还需要按论文/官方脚本扩大到完整训练步数，并在渲染 runtime 修复后接 server/client rollout 评估链路。

## 6. NVIDIA runtime 与 rollout smoke

官方 render smoke：

```bash
conda run -n ar_goal2skill_rmbench python script/test_render.py
```

最初失败原因：

```text
RuntimeError: failed to find a rendering device
```

补齐 `dm_control` 后再次执行 `script/test_render.py`，仍输出：

```text
Render Error
```

安装 Mesa Vulkan 后，强制使用 lavapipe：

```bash
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.x86_64.json \
conda run -n ar_goal2skill_rmbench python script/test_render.py
```

等价 traceback 显示：

```text
RuntimeError: vk::PhysicalDevice::createDeviceUnique: ErrorExtensionNotPresent
```

判断：

1. Python 依赖、CUDA、PyTorch、PyTorch3D、CuRobo 都已经恢复。
2. 最初不能跑 RMBench rollout 的原因是系统没有 NVIDIA Vulkan/EGL/GLX 用户态渲染库。
3. Mesa/lavapipe 缺 SAPIEN 所需 Vulkan 扩展，不能替代真实 GPU renderer。
4. Ubuntu 当前 apt 源里的 `libnvidia-gl-570` 候选版本是 `570.211.01`，和宿主 `570.124.06` 不一致，所以没有安装系统 apt 包。

本地修复方式：

1. 从 NVIDIA data center driver `570.124.06` 的 Ubuntu 22.04 local repo 包中局部提取用户态库。
2. 不执行 `dpkg -i`，不修改系统 GL/Vulkan 库。
3. 用 wrapper 在命令级设置 `LD_LIBRARY_PATH`、`VK_ICD_FILENAMES`、`__EGL_VENDOR_LIBRARY_FILENAMES`。

下载来源：

```text
https://developer.download.nvidia.com/compute/nvidia-driver/570.124.06/local_installers/nvidia-driver-local-repo-ubuntu2204-570.124.06_1.0-1_amd64.deb
```

局部 runtime 目录：

```text
goal2skill_rmbench/nvidia_runtime_570.124.06/
```

当前只保留运行必需的 `libs/`，约 `739M`；原始 local repo `.deb` 与展开的 `repo_extract/` 已删除，可用上面的 URL 重建。

关键文件：

```text
nvidia_runtime_570.124.06/libs/usr/lib/x86_64-linux-gnu/libEGL_nvidia.so.570.124.06
nvidia_runtime_570.124.06/libs/usr/lib/x86_64-linux-gnu/libGLX_nvidia.so.570.124.06
nvidia_runtime_570.124.06/libs/usr/share/glvnd/egl_vendor.d/10_nvidia.json
nvidia_runtime_570.124.06/libs/usr/share/vulkan/icd.d/nvidia_icd.json
```

运行 wrapper：

```bash
goal2skill_rmbench/scripts/run_with_nvidia_570_runtime.sh \
  conda run -n ar_goal2skill_rmbench python script/test_render.py
```

结果：

```text
Render Well
```

为跑通 rollout 还补了几个本地兼容 patch：

| 文件 | 改动 |
|---|---|
| `script/eval_policy.py` | 增加可选 `test_num` / `topk` override，默认仍为论文协议 `100` episodes |
| `envs/robot/planner.py` | YAML 读取显式 `encoding="utf-8"` |
| `envs/_base_task.py` | `_eval_step_limit.yml` 读取显式 `encoding="utf-8"` |
| `envs/curobo/src/curobo/util_file.py` | Curobo YAML loader 显式 `encoding="utf-8"` |
| `envs/curobo/src/curobo/__init__.py` | 兼容 `warp-lang 1.14.0`，把 `warp._src.torch` 暴露为旧代码需要的 `warp.torch` |
| `goal2skill_rmbench/scripts/run_with_nvidia_570_runtime.sh` | 设置局部 NVIDIA runtime 和 UTF-8 locale |

已完成真实 RMBench rollout smoke / sanity eval：

| Policy | Checkpoint | Task | Episodes | Result | `_result.txt` |
|---|---|---|---:|---:|---|
| DP | `policy/DP/checkpoints/observe_and_pickup-demo_clean-50-42/2.ckpt` | `observe_and_pickup` | `1` | `1/1` | `eval_result/observe_and_pickup/DP/demo_clean/demo_clean/2026-07-05 19:45:22/_result.txt` |
| ACT | `policy/ACT/act_ckpt/smoke-observe_and_pickup/demo_clean-50-epoch1/policy_last.ckpt` | `observe_and_pickup` | `1` | `0/1` | `eval_result/observe_and_pickup/ACT/demo_clean/smoke_epoch1/2026-07-05 19:46:37/_result.txt` |
| DP | `policy/DP/checkpoints/observe_and_pickup-demo_clean-50-42/300.ckpt` | `observe_and_pickup` | `5` | `0/5` | `eval_result/observe_and_pickup/DP/demo_clean/demo_clean/2026-07-05 21:30:53/_result.txt` |
| DP | `policy/DP/checkpoints/observe_and_pickup-demo_clean-50-42/600.ckpt` | `observe_and_pickup` | `5` | `0/5` | `eval_result/observe_and_pickup/DP/demo_clean/demo_clean/2026-07-05 22:32:36/_result.txt` |
| DP | `policy/DP/checkpoints/observe_and_pickup-demo_clean-50-42/600.ckpt` | `observe_and_pickup` | `100` | `1/100` (`0.01`) | `eval_result/observe_and_pickup/DP/demo_clean/demo_clean/2026-07-05 23:03:31/_result.txt` |

这些结果证明 rollout 链路已通，并给出 DP `observe_and_pickup` 单任务 300/600-epoch checkpoint 的小样本 sanity eval，以及 DP 600-epoch checkpoint 的单任务 `100` episodes 正式评估。DP 2-epoch checkpoint 和 ACT 1-epoch checkpoint 仍只是 smoke；DP `observe_and_pickup` 的 `1/100 = 1.0%` 与论文表中 DP 该任务 `1%` 对齐，但仍没有覆盖其余 4 个 Goal2Skill 任务。

## 7. Baseline 复现路线

当前优先顺序：

1. 用 `run_with_nvidia_570_runtime.sh` 包住所有 RMBench eval 命令。
2. 将 DP / ACT / Pi0.5 / X-VLA 从 smoke 训练扩大到完整训练配置；DP 已完成 `observe_and_pickup` 单任务 600 epochs 和 100-episode eval，仍需补其余 4 个任务。
3. 按论文协议复现 Goal2Skill baseline：
   - `DP`
   - `ACT`
   - `Pi0.5`
   - `X-VLA`
4. 每个任务跑 `100` rollout episodes，报告 task success rate。
5. 再搭 Goal2Skill-style 方法：
   - VLM planner 输出 subtask tuple。
   - structured memory: episodic history、working memory、error register。
   - verifier 判断 post-condition。
   - reflection 输出 retry / adjust-param / replan。
   - low-level executor 先复用 RMBench policy 或 Mem-0 execution module。

当前不建议直接声称复现 Goal2Skill full system，因为论文未公开完整 Goal2Skill 代码，本地也还没有跑出论文协议下的 5-task、100-episode success rate。
