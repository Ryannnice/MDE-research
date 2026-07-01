# TransCG / DFNet 最小复现记录

日期: 2026-07-01

目标: 先复现一个透明物体深度补全方法的可执行闭环。这里选择 [TransCG / DFNet](https://github.com/galaxies99/transcg)，因为它是透明 RGB-D depth completion 的基础数据集和经典机器人抓取基线。

## 论文工作讲解

TransCG 的问题设定是透明物体 RGB-D depth completion。输入不是单 RGB，而是 RGB 图像加原始深度图。透明物体会让 RealSense 这类 RGB-D 传感器出现空洞、背景错深度或局部噪声；论文目标是在透明区域把 raw depth 修成更接近真实表面的稠密深度，供抓取、点云和碰撞检查使用。

论文主要贡献有三点:

1. 发布 TransCG 数据集。它包含 57,715 张真实 RGB-D 图像，覆盖 51 个透明物体、130 个真实场景，并提供相机内参、透明物体 mesh、pose、mask、surface normal 和 refined ground-truth depth。
2. 提出 DFNet 作为 depth filler baseline。DFNet 输入 RGB 和原始 depth，使用多尺度卷积/稠密块结构补全透明区域深度。它本质上是一个透明物体 RGB-D depth restoration 网络，不是单目深度模型。
3. 用机器人抓取展示下游价值。补全后的深度可以生成更完整点云，减少透明区域深度缺失对 suction/parallel-jaw grasp 的影响。

它的关键边界:

- 优点: 数据集真实、任务定义清楚、代码和 checkpoint 公开，适合作为透明物体复现第一基线。
- 限制: 输入依赖 RGB-D raw depth；如果原始深度完全不可用或机器人只有单 RGB，不能直接等同于单目 MDE。
- 对后续工作的威胁: 任何透明 depth 方法都至少要解释自己相对 raw depth、DFNet、TODE、ReMake 这类 RGB-D completion baseline 的优势。

## 当前状态

已完成:

- 官方代码已克隆到 `data/external/transcg/official/`，提交为 `135f9e0ad20592cb40b288c152aff5eda033a765`。
- conda 环境 `transcg` 已创建，Python 3.10。
- 已安装 CPU 版 PyTorch 和最小 inference 依赖。
- 官方 checkpoint 已下载到 `weights/transparent/transcg/checkpoint.tar`，文件大小约 5.2MB，checkpoint epoch 为 12。
- 已添加无 GUI 最小脚本 `tools/repro/transparent/transcg/run_dfnet_minimal.py`。
- 已跑通一次合成 RGB-D smoke test，输出在 `runs/transparent/transcg/minimal_synthetic/`。

未完成:

- 未下载官方真实 TransCG 数据分块。官方 `scene21-30` 分块为 `transcg-data-3.zip`，约 15.1GB；完整 TransCG 数据由 13 个大分块组成。
- 当前 smoke test 的 MAE/RMSE 只验证代码闭环，不代表论文或官方 TransCG test split 结果。

## 文件夹结构

```text
data/
  external/transcg/official/        # 官方 TransCG 代码，git clone，忽略入库

weights/
  transparent/transcg/checkpoint.tar # 官方 DFNet checkpoint，忽略入库

runs/
  transparent/transcg/minimal_synthetic/
    input_rgb.png
    input_depth_raw_mm.png
    dfnet_depth_mm.png
    dfnet_depth_vis.png
    summary.json

tools/
  repro/transparent/transcg/run_dfnet_minimal.py

docs/
  复现/透明物体/TransCG_DFNet.md
```

这个结构遵守仓库 README: 真实数据放 `data/`，权重放 `weights/`，实验输出放 `runs/`。这些目录已被 `.gitignore` 忽略。

## 环境

```bash
conda create -y -n transcg python=3.10
conda run -n transcg python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
conda run -n transcg python -m pip install numpy scipy pillow pyyaml tqdm einops opencv-python gdown
```

smoke test 环境版本:

```text
torch 2.12.1+cpu
numpy 2.2.6
opencv-python 4.13.0
```

说明: 第一次只跑单样本 inference，所以使用 CPU 版 PyTorch，避免 RTX 5090 与老 PyTorch/CUDA 组合的兼容问题。后续跑全量评测时可以单独建 GPU 环境。

## 已执行命令

```bash
mkdir -p data/external/transcg weights/transparent/transcg runs/transparent/transcg
git clone https://github.com/galaxies99/transcg.git data/external/transcg/official

conda run -n transcg gdown 1oZi9zdOg0WYuTHM10xlyq5FRlfoKDKzU \
  -O weights/transparent/transcg/checkpoint.tar

conda run -n transcg python tools/repro/transparent/transcg/run_dfnet_minimal.py \
  --out-dir runs/transparent/transcg/minimal_synthetic
```

输出摘要:

```json
{
  "source": "synthetic",
  "checkpoint_epoch": 12,
  "input_shape_hwc": [480, 640, 3],
  "official_inference_size_wh": [320, 240],
  "raw_valid_ratio": 0.8985611979166667,
  "pred_min_m": 0.6216562986373901,
  "pred_max_m": 0.7883589267730713,
  "pred_mean_m": 0.7043432593345642,
  "gt_available": true,
  "mae_m": 0.001014457899145782,
  "rmse_m": 0.0018889900529757142
}
```

## 接真实 TransCG 数据

官方数据页: [https://graspnet.net/transcg](https://graspnet.net/transcg)

官方页面说明 TransCG 提供 RGB-D 原图、refined GT depth、transparent object pose、mask、surface normals 和模型；数据结构为 `scene1/ ... scene130/`，并提供 `camera_intrinsics/`、`models/` 和 `metadata.json`。

若要复现官方 `sample_inference.py` 中的 `scene21/1`，需要下载:

- `transcg-info.zip`: 149.3MB，Google Drive id `18LkbelKNTURF-8f8N-ykzs79FJ013knH`
- `transcg-data-3.zip`: scene 21-30，15.1GB，Google Drive id `19tXZ9lzpW2gUk1ibkij76I_-oknCbqyP`

建议真实数据放:

```text
data/transparent/transcg/
```

下载命令:

```bash
mkdir -p data/transparent/transcg
conda run -n transcg gdown 18LkbelKNTURF-8f8N-ykzs79FJ013knH \
  -O data/transparent/transcg/transcg-info.zip
conda run -n transcg gdown 19tXZ9lzpW2gUk1ibkij76I_-oknCbqyP \
  -O data/transparent/transcg/transcg-data-3.zip
```

解压后按实际根目录调整路径。若得到 `scene21/1/rgb1.png`、`depth1.png`、`depth1-gt.png`，可直接运行:

```bash
conda run -n transcg python tools/repro/transparent/transcg/run_dfnet_minimal.py \
  --rgb data/transparent/transcg/scene21/1/rgb1.png \
  --depth data/transparent/transcg/scene21/1/depth1.png \
  --gt data/transparent/transcg/scene21/1/depth1-gt.png \
  --out-dir runs/transparent/transcg/scene21_1_dfnet
```

## 结论

TransCG / DFNet 的代码、checkpoint、最小 inference 链路已经跑通。下一步如果要做真实复现，应下载 `transcg-data-3.zip`，先跑 `scene21/1`，再扩展到固定小子集，最后才跑完整 test split。
