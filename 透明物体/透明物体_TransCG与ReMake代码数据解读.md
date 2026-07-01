# TransCG 与 ReMake: 透明物体深度补全代码/数据解读

日期: 2026-07-01

本文只整理两个已开始复现的透明物体深度补全工作:

- [TransCG / DFNet](https://github.com/galaxies99/transcg): 透明物体 RGB-D depth completion 的经典数据集与基线。
- [ReMake](https://github.com/ChengYaofeng/ReMake): 融合 monocular relative depth、instance mask 和 raw depth 的透明 depth completion 方法。

当前复现层级是 `smoke test`: 已验证官方代码、checkpoint、模型前向和输出保存能跑通；还没有下载完整 TransCG 真实数据块，因此官方 test split 指标仍为 `待跑`。

## 总览对比

| 项 | TransCG / DFNet | ReMake |
|---|---|---|
| 任务 | RGB-D 透明物体 depth completion | RGB-D + MDE + mask 透明物体 depth completion |
| 输入 | RGB + raw depth | RGB + raw depth + relative depth + instance mask |
| 输出 | completed metric depth | completed metric depth |
| 主网络 | Dense CNN encoder-decoder | Swin encoder + ResNet18 depth encoder + decoder |
| 是否依赖 MDE | 否 | 是，Depth Anything / LeReS |
| 是否依赖 mask | 训练/评测使用 GT mask 指标，模型输入不显式用 mask | 是，mask 是模型输入 |
| 主要数据 | TransCG | TransCG、ClearGrasp |
| 当前 checkpoint | `weights/transparent/transcg/checkpoint.tar`, epoch 12 | `weights/transparent/remake/checkpoint.tar`, epoch 39 |
| 当前复现 | `tools/repro/transparent/transcg/run_dfnet_minimal.py` | `tools/repro/transparent/remake/run_remake_minimal.py` |
| 官方测试状态 | 待跑 | 待跑 |

## 1. TransCG / DFNet

### 工作目标

TransCG 的问题设定是透明物体 RGB-D depth completion。它不是单目深度估计。输入是 RGB 图像和原始深度图，目标是在透明物体区域修复 RGB-D 传感器的空洞、背景错深度和噪声，输出可用于点云、抓取和碰撞检测的稠密深度。

透明物体对 RealSense / ToF / active stereo 传感器的典型破坏包括:

- 透明区域返回 0 或 invalid depth。
- 传感器读到透明物体后方背景深度。
- 边界、折射、反射处出现局部噪声。

论文贡献可以概括为三点:

1. 发布 TransCG 数据集: 57,715 张真实 RGB-D 图像，51 个透明物体，130 个真实场景。
2. 提出 DFNet 作为 depth filler baseline。
3. 用机器人抓取展示补全后的 depth 对透明物体抓取有帮助。

### 核心代码

| 模块 | 本地路径 | 作用 |
|---|---|---|
| DFNet 模型 | `data/external/transcg/official/models/DFNet.py` | RGB + depth 到 completed depth 的主网络 |
| 数据集类 | `data/external/transcg/official/datasets/transcg.py` | 读取 TransCG metadata、scene、RGB/depth/GT/mask |
| 推理类 | `data/external/transcg/official/inference.py` | checkpoint 加载、depth 预处理、模型前向、反归一化 |
| 默认配置 | `data/external/transcg/official/configs/default.yaml` | 模型参数、数据路径、训练/测试指标 |
| 最小复现脚本 | `tools/repro/transparent/transcg/run_dfnet_minimal.py` | 无 GUI smoke test，支持合成输入或真实 RGB-D 路径 |

### 模型结构

DFNet 配置:

```yaml
model:
  type: DFNet
  params:
    in_channels: 4
    hidden_channels: 64
    L: 5
    k: 12
```

输入 4 通道来自:

```text
RGB 3 通道 + raw depth 1 通道
```

模型 forward 的关键流程:

1. `torch.cat((rgb, depth), dim=1)` 合并成 4 通道输入。
2. 多级 dense block 下采样。
3. 每一级都把缩放后的 depth 重新注入特征。
4. 用 dense upsampling convolution 逐级上采样。
5. 输出单通道 depth。

这说明 DFNet 的核心假设是: raw depth 中仍有足够多可信区域，可以通过 RGB 纹理和空间上下文补全透明区域。

### 推理流程

官方 `Inferencer.inference()` 的逻辑:

1. RGB 和 depth resize 到配置尺寸，默认 `320x240`。
2. depth 按 `depth_min/depth_max` 裁剪。
3. 用全图 depth 均值和标准差过滤异常深度。
4. 可选最近邻插值补洞。
5. depth 归一化到网络输入范围。
6. 前向 `self.model(rgb, depth)`。
7. 输出反归一化，并 resize 回目标尺寸。

注意: 这里的插值补洞是模型前处理，不是最终结果；DFNet 输出才是 completed depth。

### 数据集与测试集

TransCG 官方数据结构由 `metadata.json` 控制 split，而不是在代码里硬编码。

核心读取逻辑:

- 根目录 `metadata.json` 包含:
  - `total_scenes`
  - `perspective_num`
  - `train`
  - `test`
  - `train_samples`
  - `test_samples`
- 每个 `scene*/metadata.json` 包含:
  - scene 类型
  - scene split
  - `D435_valid_perspective_list`
  - `L515_valid_perspective_list`

每个样本路径格式:

```text
scene{scene_id}/{perspective_id}/
  rgb1.png
  depth1.png
  depth1-gt.png
  depth1-gt-mask.png
  rgb2.png
  depth2.png
  depth2-gt.png
  depth2-gt-mask.png
```

其中:

- `1` 表示 RealSense D435。
- `2` 表示 RealSense L515。
- `depth*-gt-mask.png` 是 transparent / GT mask，用于 masked metric。

官方 test split 是 `metadata.json` 中的 `test` scenes。当前我们还没有下载真实数据，所以 test split 指标是 `待跑`。

### 当前复现状态

已完成:

```bash
conda run -n transcg python tools/repro/transparent/transcg/run_dfnet_minimal.py \
  --out-dir runs/transparent/transcg/minimal_synthetic_verify2
```

输出摘要:

```json
{
  "checkpoint_epoch": 12,
  "raw_valid_ratio": 0.8985611979166667,
  "pred_min_m": 0.6216562986373901,
  "pred_max_m": 0.7883589267730713,
  "pred_mean_m": 0.7043432593345642,
  "mae_m": 0.001014457899145782,
  "rmse_m": 0.0018889900529757142
}
```

这个结果只说明模型、checkpoint、前向和输出保存可用；输入是合成 RGB-D，不代表 TransCG 官方 test split。

## 2. ReMake

### 工作目标

ReMake 的完整题目是 *Rethinking Transparent Object Grasping: Depth Completion with Monocular Depth Estimation and Instance Mask*。它仍然是透明物体 depth completion，而不是纯单目 MDE。

ReMake 的输入比 DFNet 多两个强先验:

```text
RGB + raw depth + monocular relative depth + instance mask
```

方法直觉:

1. raw depth 有米制尺度，但透明区域常失败。
2. MDE relative depth 在透明区域可能更连续，但通常没有可靠米制尺度。
3. instance mask 告诉网络哪里是透明物体、哪里需要重点补全。
4. ReMake 融合三路几何/语义信息，输出 metric completed depth。

因此，ReMake 是当前透明物体方向的重要威胁: 它不是只训练一个 RGB-D completion 网络，而是把 foundation MDE 的相对几何先验接进了机器人 depth completion。

### 核心代码

| 模块 | 本地路径 | 作用 |
|---|---|---|
| ReMake 模型 | `data/external/remake/official/models/remake.py` | RGB/mask、relative depth、raw depth 三路融合网络 |
| TransCG 数据集类 | `data/external/remake/official/datasets/transcg.py` | 读取 TransCG RGB/depth/GT/mask，并生成训练输入 |
| 推理类 | `data/external/remake/official/run_utils/inferencer.py` | 加载 checkpoint、生成 relative depth、调用 ReMake |
| 测试配置 | `data/external/remake/official/configs/test/transcg_remake.yaml` | TransCG 测试配置、指标、MDE 模型设置 |
| 推理配置 | `data/external/remake/official/configs/inference/remake.yaml` | 单样本 inference 设置 |
| 最小复现脚本 | `tools/repro/transparent/remake/run_remake_minimal.py` | 无 GUI smoke test，绕开完整 Depth Anything 链路 |

### 模型结构

ReMake 主网络由三路 encoder 加一个 decoder 组成:

```text
RGB + mask       -> SwinTransformer encoder_img
relative depth   -> SwinTransformer encoder_rel
raw depth        -> ResNet18 encoder_depth

三路多尺度特征相加 -> decoder -> completed depth
```

关键代码:

- `encoder_img = SwinTransformer(patch_size=2, in_chans=4, embed_dim=24)`
- `encoder_rel = SwinTransformer(patch_size=2, in_chans=1, embed_dim=24)`
- `resnet = resnet18(pretrained=False)`
- forward 中把三路 encoder 特征逐层相加。

这和 DFNet 的差异很大:

- DFNet 只把 RGB 和 raw depth 作为网络输入。
- ReMake 把 mask 直接拼到 RGB 分支，并单独用一个 encoder 处理 relative depth。

### 推理流程

官方 `Inferencer.inference()` 的逻辑:

1. resize RGB/depth/mask 到配置尺寸，通常 `640x480`。
2. 清理 raw depth 的无效值。
3. 如果 `reldepth_model == depthanything`，对 RGB 做 Depth Anything 的预处理。
4. 加载 relative depth 模型，生成 relative depth。
5. relative depth resize 到 `(480, 640)`。
6. 调用:

```python
depth_res = self.model(rgb, relative_depth, depth, rgb_mask)
```

完整官方推理依赖:

- ReMake checkpoint。
- Depth Anything V2 权重: 代码期望 `checkpoints/depth_anything_v2_vits.pth`。
- TransCG 或 ClearGrasp 格式的数据。

当前最小复现使用合成 relative depth 验证 ReMake 主网络和 checkpoint，不代表完整官方 pipeline。

### 数据集与测试集

ReMake 的 TransCG 数据类同样读取 TransCG 官方结构:

```text
metadata.json
scene*/metadata.json
scene*/{perspective}/rgb{camera_type}.png
scene*/{perspective}/depth{camera_type}.png
scene*/{perspective}/depth{camera_type}-gt.png
scene*/{perspective}/depth{camera_type}-gt-mask.png
```

ReMake 配置中测试集路径:

```yaml
dataset:
  test:
    type: transcg
    data_dir: datasets/transcg/transcg
    image_size: [640, 480]
    use_augmentation: False
    depth_min: 0.0
    depth_max: 10.0
    depth_norm: 1.0
    reldepth_model: depthanything
```

测试指标包括:

- `MSE`
- `RMSE`
- `REL`
- `MAE`
- `Threshold@1.01/1.03/1.05/1.10/1.25`
- masked 版本指标
- `ssim`

其中 masked 指标更重要，因为透明物体 depth completion 的关键是透明区域，而不是背景全图平均。

### 当前复现状态

已完成:

```bash
conda run -n remake python tools/repro/transparent/remake/run_remake_minimal.py \
  --out-dir runs/transparent/remake/minimal_synthetic_verify
```

输出摘要:

```json
{
  "checkpoint_epoch": 39,
  "raw_valid_ratio": 0.857265625,
  "mask_ratio": 0.142734375,
  "pred_min_m": 0.4421382546424866,
  "pred_max_m": 0.8198965787887573,
  "pred_mean_m": 0.6624274849891663,
  "uses_depthanything": false,
  "mae_m": 0.03773219510912895,
  "rmse_m": 0.09120184928178787
}
```

这个结果只验证 ReMake 主网络、checkpoint 和输入输出链路。因为 relative depth 是合成输入，不是 Depth Anything 生成结果，所以不能写成论文复现指标。

## 后续真实复现路线

下一步建议按这个顺序推进:

1. 下载 TransCG `transcg-info.zip` 和 `transcg-data-3.zip`，先获得 `scene21/1` 这类真实样本。
2. 用 DFNet 跑真实 `scene21/1`，验证 RGB、raw depth、GT depth、mask 路径全部正确。
3. 用 ReMake 最小脚本跑同一个真实样本，但先使用派生 relative depth，确认 mask/depth/GT 对齐。
4. 下载 `depth_anything_v2_vits.pth`，接入 ReMake 完整 relative depth pipeline。
5. 固定一个小 test subset，统一导出:
   - raw depth
   - DFNet depth
   - ReMake depth
   - GT depth
   - transparent mask
   - full-image metrics
   - transparent-mask metrics

在真实 CSV 生成前，所有官方 test split 结论都保持 `待跑`。
