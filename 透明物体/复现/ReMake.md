# ReMake 最小复现记录

日期: 2026-07-01

目标: 复现第二个透明物体深度方法的可执行闭环。这里选择 [ReMake](https://github.com/ChengYaofeng/ReMake)，因为它把 monocular depth estimation、instance mask 和 RGB-D depth completion 结合起来，是 TransCG/DFNet 之后更贴近当前透明物体 MDE 威胁的路线。

## 论文工作讲解

ReMake 的完整题目是 *Rethinking Transparent Object Grasping: Depth Completion with Monocular Depth Estimation and Instance Mask*。它关注透明物体抓取中的深度补全问题。

它和 TransCG / DFNet 的关键区别是:

- TransCG / DFNet 主要输入 RGB + raw depth，让网络从 RGB-D 里学习补全透明区域。
- ReMake 额外引入两个强先验: 单目相对深度和实例 mask。相对深度来自 Depth Anything / LeReS 这类 MDE 模型，mask 告诉网络哪里是透明物体。

方法直觉:

1. raw depth 提供可信的米制尺度，但透明区域常缺失或错误。
2. MDE relative depth 对透明区域可能更连续，但通常没有可靠米制尺度。
3. instance mask 明确指出需要重点修复的透明区域。
4. ReMake 网络融合 RGB、raw depth、relative depth 和 mask，输出补全后的 metric depth。

它的研究意义在于把 foundation MDE 当作透明 depth completion 的先验，而不是单独相信 MDE 输出。这也是它对后续透明物体单目/少传感方法的主要威胁。

## 当前状态

已完成:

- 官方代码已克隆到 `data/external/remake/official/`，提交为 `4f568148c8421544136bf49bb941149e0c990a34`。
- conda 环境 `remake` 已创建，Python 3.10。
- 已安装 CPU 版 PyTorch/torchvision 和最小前向依赖。
- 官方 checkpoint 已下载到 `weights/transparent/remake/checkpoint.tar`，文件大小约 35MB，checkpoint epoch 为 39。
- 已添加无 GUI 最小脚本 `tools/repro/transparent/remake/run_remake_minimal.py`。
- 已跑通一次合成输入 smoke test，输出在 `runs/transparent/remake/minimal_synthetic/`。

未完成:

- 未下载完整 TransCG 数据。
- 未下载 `DepthAnythingV2` 官方权重 `depth_anything_v2_vits.pth`。
- 当前 smoke test 使用合成 relative depth，只验证 ReMake 主网络和 checkpoint 能运行，不代表官方论文指标。

## 文件夹结构

```text
data/
  external/remake/official/          # 官方 ReMake 代码，git clone，忽略入库

weights/
  transparent/remake/checkpoint.tar  # 官方 ReMake checkpoint，忽略入库

runs/
  transparent/remake/minimal_synthetic/
    input_rgb.png
    input_depth_raw_mm.png
    input_mask.png
    input_relative_depth_u16.png
    remake_depth_mm.png
    remake_depth_vis.png
    summary.json

tools/
  repro/transparent/remake/run_remake_minimal.py

docs/
  复现/透明物体/ReMake.md
```

## 环境

```bash
conda create -y -n remake python=3.10
conda run -n remake python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
conda run -n remake python -m pip install numpy scipy pillow pyyaml tqdm einops opencv-python gdown timm matplotlib
```

smoke test 环境版本:

```text
torch 2.12.1+cpu
torchvision 0.27.1+cpu
numpy 2.2.6
opencv-python 4.13.0
timm 1.0.27
```

说明: 第一次只验证单样本前向，所以使用 CPU 版 PyTorch。官方 env 包含 Open3D、RealSense、SAM、Depth Anything 和真实机器人链路依赖；这些不适合第一步最小复现。

## 已执行命令

```bash
mkdir -p data/external/remake weights/transparent/remake runs/transparent/remake
git clone https://github.com/ChengYaofeng/ReMake.git data/external/remake/official

conda run -n remake gdown \
  'https://drive.google.com/file/d/1AF9sWyhEoNHnAlJ_y1AXsoxgrXq44333/view?usp=drive_link' \
  -O weights/transparent/remake/checkpoint.tar

conda run -n remake python tools/repro/transparent/remake/run_remake_minimal.py \
  --out-dir runs/transparent/remake/minimal_synthetic
```

输出摘要:

```json
{
  "source": "synthetic",
  "checkpoint_epoch": 39,
  "input_shape_hwc": [480, 640, 3],
  "network_size_wh": [640, 480],
  "raw_valid_ratio": 0.857265625,
  "mask_ratio": 0.142734375,
  "pred_min_m": 0.4421382546424866,
  "pred_max_m": 0.8198965787887573,
  "pred_mean_m": 0.6624274849891663,
  "uses_depthanything": false,
  "gt_available": true,
  "mae_m": 0.03773219510912895,
  "rmse_m": 0.09120184928178787
}
```

## 真实数据与完整推理阻塞

官方 `run_tools/runner_inference.py` 里有作者本地硬编码路径:

```text
/home/cyf/remake/datasets/transcg/transcg/...
```

完整官方链路还需要:

- TransCG 真实数据，按 README 放成 `datasets/transcg/transcg/...` 的结构。
- `DepthAnythingV2` 权重，官方代码期望路径为 `checkpoints/depth_anything_v2_vits.pth`。

本仓库建议放置:

```text
data/transparent/transcg/
weights/transparent/remake/depth_anything_v2_vits.pth
```

下一步如果跑真实 ReMake inference，应把最小脚本扩展为:

```bash
conda run -n remake python tools/repro/transparent/remake/run_remake_minimal.py \
  --rgb data/transparent/transcg/scene21/1/rgb1.png \
  --depth data/transparent/transcg/scene21/1/depth1.png \
  --mask data/transparent/transcg/scene21/1/depth1-gt-mask.png \
  --gt data/transparent/transcg/scene21/1/depth1-gt.png \
  --out-dir runs/transparent/remake/scene21_1_smoke
```

这条命令仍使用合成/派生 relative depth；若要完全复现论文链路，还要接入 Depth Anything V2 生成 relative depth。

## 结论

ReMake 的官方代码、checkpoint、主网络前向已经跑通。当前复现层级是“模型/权重 smoke test”，不是官方 benchmark。要进入真实复现，下一步应先下载一块 TransCG 真实数据，再补 Depth Anything V2 权重。
