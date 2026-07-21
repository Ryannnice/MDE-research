# 透明物体深度方法骨架与代码 I/O 调研

> **状态：工程背景与支撑资料。** 当前总项目主线及方法边界见 [统一 Idea v2](Shell-Aware-Multi-Layer-Transparent-Grasping-Idea-v2.md)；本文中的旧“第一选择 / 主线”表述按 2026-07-10 历史上下文理解。

日期: 2026-07-10

本文仿照 `Agent_Research/literature-search-20260707-conflict-aware-agent-memory/方法骨架与代码IO调研.md` 的写法，记录透明/镜面/非朗伯物体深度方向中最相关工作的 **方法骨架、benchmark / 代码 I/O、依赖框架、创新点、对我们课题的直接用途**。

本文不是重新写综述，而是服务两个工程目标:

1. 判断哪些代码、数据、benchmark 可以直接作为我们的 robust backbone / baseline / eval。
2. 判断哪些接口和协议值得仿造，避免从 0 到 1 自造数据、模型和评测。

核心结论: 透明物体 depth correction 已经不是空白。我们的第一选择应是复用 `Depth4ToM + Booster + LayeredDepth + SeeGroup` 建立 CCF-A 视觉主线，复用 `TransCG + ClearPose + ReMake + MOMA-style alignment` 建立 A2 / robot failure slice。自己真正需要写的是统一 adapter、layer-aware head、selector / confidence 和 ablation。

## 0. 本轮落地资产

### 0.1 PDF

本目录已保留的高相关 PDF:

| 工作 | 本地文件 | 角色 |
|---|---|---|
| ClearGrasp | `pdfs/2019_2020_cleargrasp_transparent_objects_manipulation.pdf` | 经典 RGB-D completion / manipulation 背景 |
| LIDF | `pdfs/2021_cvpr_lidf_transparent_depth_completion_arxiv_backup.pdf` | CVPR RGB-D local implicit depth completion baseline |
| TransCG | `pdfs/2022_ral_transcg_dataset_depth_completion_grasping.pdf` | 真实透明 RGB-D 数据集和 DFNet baseline |
| ClearPose | `pdfs/2022_eccv_clearpose_dataset_benchmark.pdf` | 透明 depth / normal / pose benchmark |
| DREDS | `pdfs/2022_eccv_dreds_swindrnet_specular_transparent.pdf` | sim2real RGB-D restoration 路线 |
| Booster | `pdfs/2023_booster_specular_transparent_depth_benchmark.pdf` | 高分辨率 ToM benchmark 和协议资源 |
| Depth4ToM | `pdfs/2023_iccv_depth4tom_transparent_mirror_surfaces_arxiv.pdf` | 单目/双目透明镜面 ToM depth 主基线 |
| Diffusion4RobustDepth | `pdfs/2024_robust_mde_non_lambertian_surfaces.pdf` | 非朗伯/困难条件通用 MDE baseline |
| MODEST | `pdfs/2025_modest_monocular_depth_segmentation_transparent.pdf` | 单 RGB 透明分割+深度直接近邻 |
| LayeredDepth | `pdfs/2025_layereddepth_multilayer_transparent_depth.pdf` | 多层透明深度 benchmark 和任务定义 |
| MOMA | `pdfs/2025_moma_metric_depth_alignment_robot_grasping.pdf` | 单 RGB + sparse metric alignment + grasping 威胁 |
| ReMake | `pdfs/2026_remake_mde_mask_transparent_grasping.pdf` | MDE + mask + RGB-D completion 强基线 |
| SeeClear | `pdfs/2026_seeclear_generative_opacification_transparent_depth.pdf` | 生成式 opacification 强威胁 |
| SeeGroup | `pdfs/2026_seegroup_multilayer_transparent_depth.pdf` | CVPR 2026 multi-layer transparent depth 强基线 |
| AISPO | `pdfs/2026_aispo_affine_invariant_shape_prior_non_lambertian_robotics.pdf` | affine-invariant shape prior / reliability 威胁 |
| ASGrasp | `pdfs/2024_asgrasp_transparent_reconstruction_grasp_detection.pdf` | active stereo / 6-DoF grasp system upper bound |

### 0.2 本地代码与复现记录

| 工作 | 本地路径 | 上游 | 当前状态 |
|---|---|---|---|
| TransCG / DFNet | `external/transcg/official/` | https://github.com/Galaxies99/TransCG | 官方代码已克隆；checkpoint 已下载；合成 smoke test 跑通；完整真实 test split 待跑 |
| TransCG minimal runner | `复现/tools/transcg/run_dfnet_minimal.py` | 本地脚本 | 无 GUI 单样本前向，支持合成输入或真实 RGB-D 路径 |
| TransCG 复现记录 | `复现/TransCG_DFNet.md` | 本地记录 | 记录环境、checkpoint、数据下载入口和 smoke 输出 |
| ReMake | `external/remake/official/` | https://github.com/ChengYaofeng/ReMake | 官方代码已克隆；checkpoint 已下载；主网络合成 smoke test 跑通；完整 Depth Anything 链路待补 |
| ReMake minimal runner | `复现/tools/remake/run_remake_minimal.py` | 本地脚本 | 无 GUI 单样本前向，绕开完整 Depth Anything 链路 |
| ReMake 复现记录 | `复现/ReMake.md` | 本地记录 | 记录环境、checkpoint、真实数据阻塞和下一步 |
| 代码数据解读 | `透明物体_TransCG与ReMake代码数据解读.md` | 本地文档 | 对 TransCG / ReMake 的模型、数据、I/O 做二次解读 |

### 0.3 尚未本地克隆但应优先复用

| 优先级 | 工作 | 上游 | 直接价值 |
|---|---|---|---|
| P0 | Depth4ToM | https://github.com/CVLAB-Unibo/Depth4ToM-code | ToM single-depth 主基线；官方数据、权重、评测脚本 |
| P0 | LayeredDepth | https://github.com/princeton-vl/LayeredDepth | multi-layer transparent depth benchmark、HF 数据、eval |
| P0 | SeeGroup | https://github.com/princeton-vl/SeeGroup | LayeredDepth 上的 multi-layer teacher / SOTA baseline |
| P1 | MODEST | https://github.com/D-Robotics-AI-Lab/MODEST | 单 RGB 透明 segmentation + depth 辅助 baseline |
| P1 | Diffusion4RobustDepth | https://github.com/fabiotosi92/Diffusion4RobustDepth | 非朗伯/困难条件通用 MDE baseline |
| P1 | MDA | https://github.com/biansy000/MDA | mixture-density / multi-hypothesis head 威胁与参考 |
| P2 | SeeClear | https://github.com/YumengHe/SeeClear | demo checkpoint / opacification pipeline；完整训练待 SeeClear-396k |
| P2 | DepthFocus | https://github.com/junhong-3dv/DepthFocus | controllable see-through depth monitor；代码未完整释放时不依赖 |

## 1. 总览矩阵

| 工作 | 方法骨架 | Benchmark / 代码 I/O | 基于什么框架 | 自己的创新 | 对我们课题的用途 |
|---|---|---|---|---|---|
| Depth4ToM | ToM 区域 inpainting / virtual depth 生成，再微调 MiDaS/DPT 做透明/镜面 single-depth。 | 输入 RGB、ToM mask/proxy、virtual depth / Booster；输出 single-depth map 和 ToM/Other 指标；官方有 weights、dataset、`table2/table3` 风格脚本。 | MiDaS/DPT、Trans10K/MSD virtual depth、Booster benchmark。 | 把透明/镜面区域的目标定义为 closest/front surface，而不是背景或反射内容。 | P0 single-depth teacher / warm start / Booster 主表基线。 |
| Booster / NTIRE | 高分辨率透明/镜面 depth benchmark，提供 ToM material mask 和 mono/stereo 协议。 | 输入预测 depth/disparity；输出 ToM/Other 的 MAE/RMSE/AbsRel/delta 或 challenge 指标；2026 mono metric track 强调 cm depth。 | 数据集和 challenge server / dev kit。 | 把透明、镜面、普通区域分片评测，暴露全图均值掩盖的问题。 | P0 metric protocol；约束我们必须报 metric vs affine、ToM mask、boundary。 |
| LayeredDepth | 将透明物体沿一条 camera ray 的多个 medium transition 定义为多层 depth。 | 输入图像、多层预测或相对排序预测；输出 pair/triplet/quadruplet tuple accuracy、layer_first / layer_all 指标。 | LayeredDepth real benchmark、LayeredDepth-Syn、HF 数据、eval scripts。 | 证明透明 depth 不是单一标量，提出真实/合成多层协议。 | P0 多层任务定义；给 `D_front/D_through` 监督和 claim 边界。 |
| SeeGroup | 把 per-pixel multi-layer depth 建模为 depth-axis point process / self-determined grouping。 | 输入单图和 LayeredDepth 数据；输出 unordered multi-layer depth candidates / groups；eval 在 LayeredDepth。 | PyTorch + LayeredDepth；公开 checkpoint 和训练/验证脚本。 | 不预设固定层数/顺序，用 permutation-invariant likelihood 处理多层深度。 | P0 multi-layer teacher / SOTA；可仿造 matching、grouping、teacher cache。 |
| MDA | 每像素 mixture-density / multi-hypothesis depth，透明区域可激活多个 depth components。 | 输入 RGB；输出 mixture components、weights、single-depth selection；官方有训练、评测、HF checkpoint。 | Depth Anything 3 / mixture-density head。 | 用多峰表示处理边界 flying points，并扩展到透明/遮挡几何。 | P1 强威胁；不要把“多假设”写成主创新，可借 head/loss。 |
| Diffusion4RobustDepth | 用 diffusion 生成困难条件数据，训练/微调 MDE 以增强非朗伯/极端场景鲁棒性。 | 输入 RGB；输出 monocular depth；代码、生成数据、模型权重公开。 | Diffusion-generated data + MDE backbone。 | 不是透明专门方法，而是 robust MDE data route。 | P1 通用困难场景 baseline，证明透明问题不是普通 robust augmentation 即可解决。 |
| MODEST | 单 RGB 同时做透明 segmentation 与 depth，语义与几何迭代融合。 | 输入 RGB；输出 transparent mask / segmentation 和 depth；数据入口 Syn-TODD / ClearPose，权重公开。 | PyTorch，ICRA 透明物体单图模型。 | 将透明 mask 与 depth 联合建模，面向单图透明物体。 | P1 辅助 baseline；若我们用 mask 必须计入 mask 成本并做 noisy/no-mask 消融。 |
| TransCG / DFNet | RGB-D depth completion：RGB + raw depth 经过 DFNet 补全透明区域 metric depth。 | 输入 RGB、raw depth；输出 completed metric depth；本地 minimal runner 已跑通。 | 官方 TransCG repo、DFNet、TransCG dataset、RealSense D435/L515 数据。 | 大规模真实透明 RGB-D 数据集 + depth filler + grasping baseline。 | P1 A2 / robot failure slice 数据源；经典 RGB-D completion 基线。 |
| ReMake | RGB + raw depth + monocular relative depth + instance mask 三路融合，输出透明 completed metric depth。 | 输入 RGB、raw depth、relative depth、mask；输出 completed depth；本地 minimal runner 已跑通主网络。 | Swin / ResNet18 / Depth Anything 或 LeReS / TransCG / ClearGrasp。 | 把 foundation MDE relative depth 和 mask 接进透明 RGB-D completion。 | P1 强后处理 baseline；A2 必须证明不是普通 MDE+mask completion。 |
| ClearGrasp / LIDF | RGB-D 透明 depth completion 经典路线：mask / normal / boundary / local implicit / optimization。 | 输入 RGB-D、mask、normal/boundary 或局部 patch；输出 completed depth / point cloud。 | ClearGrasp synthetic-real 数据、global optimization；LIDF local implicit function。 | 透明 RGB-D completion 的经典强门槛。 | related work 和 L1 baseline；不宜作为第一批重跑，但必须承认。 |
| ClearPose / DREDS | ClearPose 给透明物体 depth/normal/pose adversarial benchmark；DREDS 给 domain-randomized sim2real RGB-D restoration。 | 输入 RGB-D / scene 数据；输出 depth completion / pose / restoration 指标。 | RealSense L515 / synthetic randomized pipeline / SwinDRNet。 | 数据和 sim2real 资源，覆盖遮挡、液体、非平面、透明盖等泛化。 | P1/P2 泛化数据与数据路线威胁；避免只在 TransCG 过拟合。 |
| MOMA | 单 RGB 相对深度通过 one-shot sparse metric calibration 做 scale-rotation-shift 对齐，用于机器人抓取。 | 输入 RGB、少量 sparse GT depth / calibration；输出 metric depth 和 grasp result。 | MDE backbone + sparse calibration + UR5 grasping。 | 把 sparse metric alignment 与 RGB-based robot grasping 绑定。 | A2 最危险近邻；必须做 MOMA-style post-hoc / SRS 对照。 |
| SeeClear | 透明 mask -> 生成式 opacification -> off-the-shelf MDE，降低透明外观对深度的干扰。 | 输入 RGB、transparent mask；输出 opaque-composited image 和 depth；demo checkpoint 公开，完整数据待发布。 | Conditional diffusion opacification + DA3 / MoGe。 | 先把透明物体变成几何一致的不透明外观，再估深度。 | P2 强威胁 / inference ablation；不要做单纯 opacification idea。 |
| AISPO | affine-invariant shape prior 增强非朗伯物体深度可靠性，面向机器人 manipulation。 | 论文级 I/O：输入 RGB-D / depth prediction；输出 reliability / corrected depth / manipulation success。 | 机器人非朗伯 manipulation pipeline。 | 用 shape prior 和 reliability 处理非朗伯深度不可信。 | A2 related work 强威胁；代码未公开前先 monitor。 |
| ASGrasp / Dex-NeRF / ClearDepth | active stereo / multi-view / NeRF / GS 等强传感器系统。 | 输入多视角、active stereo 或 robot sensing；输出 reconstruction / grasp pose / grasp success。 | GraspNet / NeRF / active stereo / robotic setup。 | 系统上界，不是同输入方法。 | 用来限定我们的 low-cost single-image / sparse-anchor claim。 |

## 2. Depth4ToM

### 方法骨架

Depth4ToM 的问题是 transparent and mirror surfaces 的单目/双目 depth。核心不是机器人 RGB-D completion，而是把透明/镜面区域的目标 depth 定义成 camera 前方最近物理表面，然后用 inpainting 生成 proxy / virtual depth 微调 MDE。

```text
RGB image + ToM mask
  -> inpaint ToM region / generate proxy appearance
  -> run MDE / stereo teacher
  -> produce virtual front-surface depth
  -> fine-tune MiDaS / DPT
  -> predict ToM single-depth
```

它和我们 `Layer-Aware ToM Depth` 的关系:

```text
Depth4ToM gives D_single / D_front supervision
LayeredDepth / SeeGroup gives D_through / multi-layer supervision
our selector maps multi-layer hypotheses back to D_single
```

### 代码 I/O

官方仓库: https://github.com/CVLAB-Unibo/Depth4ToM-code

本地尚未克隆，但已有调研确认其提供 data、monocular weights、proxy labels 和 table 脚本。对我们来说，应该把它包装成如下 I/O:

```python
Depth4ToMInput(
    image,
    tom_mask_or_proxy_mask,
    dataset_name="Booster|Trans10K|MSD",
    split="train|val|test",
)
```

```python
Depth4ToMOutput(
    depth_single,
    depth_front_proxy,
    tom_metrics,
    other_metrics,
    prediction_path,
)
```

优先要跑的不是训练，而是:

```bash
# 伪命令，按官方 repo 实际 README 调整
bash scripts/table2.sh
bash scripts/table3.sh
```

我们需要保留官方输出目录，转成统一格式:

```text
runs/depth4tom/booster/<split>/
  predictions/
  metrics.json
  config.yaml
```

### 基于什么框架

MiDaS / DPT，Trans10K / MSD virtual depth，Booster benchmark。它是训练式 ToM MDE 适配路线，不是 frozen / training-free 方法。

### 创新

Depth4ToM 的关键创新是 ToM 区域 target definition: 透明/镜面不是学背景层，也不是学反射纹理对应深度，而是学 closest/front physical surface。

### 对我们用途

P0 主基线。第一阶段应直接用官方 weights 和 eval，作为:

- `D_front` / `D_single` 的 teacher。
- Booster ToM single-depth 主表对照。
- 证明我们不是在重新发明 ToM depth adaptation。

## 3. Booster / NTIRE ToM Benchmark

### 方法骨架

Booster 本身不是方法，而是 transparent / mirror / non-Lambertian depth benchmark。它提供高分辨率 stereo / mono 数据、material mask 和 ToM class split。它的价值是把普通全图 depth 指标拆成 ToM / Other 区域。

```text
image / stereo pair
  -> method predicts depth
  -> evaluate full image + ToM mask + non-ToM region
  -> report metric or scale-aligned protocol
```

### 代码 I/O

项目页: https://cvlab-unibo.github.io/booster-web/

建议统一包装:

```python
BoosterSample(
    image,
    depth_gt_metric,
    tom_mask,
    mirror_mask,
    transparent_mask,
    intrinsics,
    sample_id,
)
```

```python
BoosterEvalResult(
    rmse_tom,
    mae_tom,
    absrel_tom,
    delta_tom,
    rmse_other,
    metric_protocol,
    affine_aligned_protocol,
)
```

### 基于什么框架

数据集 / challenge / dev kit。NTIRE 2026 mono metric track 对我们尤其重要，因为它要求 metric depth，而不是只做 scale / shift 对齐。

### 创新

Booster 把 specular / transparent surfaces 单独定义为评测对象，使 ToM failure 不被普通区域平均掉。

### 对我们用途

P0 评测协议。所有透明/镜面方法都应该在 Booster 或其协议上报:

- metric 主表。
- affine-invariant 对照。
- ToM mask 内指标。
- boundary / high-error slice。

## 4. LayeredDepth

### 方法骨架

LayeredDepth 重新定义透明深度: 一条 camera ray 上可能有多个 medium transition，因此 transparent depth 不应被压成一个标量。

```text
RGB image
  -> predict multiple ordered depth layers along ray
  -> compare layer relations using relative tuples
```

它提供两个关键资产:

- real benchmark: in-the-wild 图片 + relative depth tuples。
- synthetic data: LayeredDepth-Syn，可提供多层 metric supervision。

### 代码 I/O

官方仓库: https://github.com/princeton-vl/LayeredDepth

HF 数据: https://huggingface.co/datasets/princeton-vl/LayeredDepth

我们应仿造的最小 I/O:

```python
LayeredDepthSample(
    image,
    tuple_labels,
    layer_depths_syn=None,
    sample_id=None,
)
```

```python
LayeredDepthPrediction(
    layers=[D1, D2, D3, ...],
    confidences=[C1, C2, C3, ...],
    first_layer=D_front,
)
```

```python
LayeredDepthEval(
    pair_accuracy,
    triplet_accuracy,
    quadruplet_accuracy,
    layer_first_score,
    layer_all_score,
)
```

### 基于什么框架

公开 benchmark / eval scripts / synthetic generator。real benchmark 主要是 relative tuple，不应被当作 metric depth GT。

### 创新

它的创新是任务定义和评测协议: 用多层 depth 和 relative tuple 暴露 single-depth 方法的概念错误。

### 对我们用途

P0 多层协议。我们不需要从零标注多层透明 depth，应该直接用:

- LayeredDepth-Syn 训练 `D_front/D_through`。
- LayeredDepth real validation/test 做外部多层评测。
- tuple violation 生成 `C_layer` / failure supervision。

## 5. SeeGroup

### 方法骨架

SeeGroup 是 LayeredDepth 上的 multi-layer transparent surface depth 方法。它不固定每个像素有几层，也不强行指定固定顺序 head，而是使用 self-determined grouping / point-process 风格建模。

```text
RGB image
  -> dense features
  -> predict depth-axis layer candidates
  -> self-determine grouping / active layers
  -> permutation-invariant likelihood
  -> multi-layer depth output
```

### 代码 I/O

官方仓库: https://github.com/princeton-vl/SeeGroup

建议把官方 checkpoint 输出缓存成:

```text
teacher/seegroup/<dataset>/<sample_id>.npz
  layers: float32[K,H,W]
  scores: float32[K,H,W] or float32[K]
  valid_mask: bool[K,H,W]
```

统一接口:

```python
SeeGroupTeacherOutput(
    layer_candidates,
    layer_scores,
    first_layer,
    ambiguity_map,
)
```

### 基于什么框架

PyTorch + LayeredDepth。公开 checkpoint、validation/test/training scripts，可直接作为 teacher 或 SOTA baseline。

### 创新

不把多层 depth 简化为 ordered multi-head，而是让模型自己决定 layer grouping，并用 permutation-invariant objective 规避层顺序不稳定。

### 对我们用途

P0 teacher / strong baseline。我们第一阶段不应重写 SeeGroup，而应:

1. 跑官方 checkpoint。
2. 缓存 teacher output。
3. 在我们的 `D_front/D_through/D_single/C_layer` 上做 distillation。
4. 如果 V1 ordered head 被质疑，再仿造 SeeGroup 的 grouping / matching 做 V3。

## 6. MDA

### 方法骨架

MDA 用 mixture-density 表示每个像素的多深度假设。它本来针对边界 flying points，也扩展到透明区域: 一个透明像素可同时有可见透明表面和背后几何的多个 depth component。

```text
RGB image
  -> backbone features
  -> K mixture components per pixel
  -> component weights / uncertainty
  -> selected depth or multi-hypothesis output
```

### 代码 I/O

官方仓库: https://github.com/biansy000/MDA

建议把它作为 baseline 和 head 参考:

```python
MDAPrediction(
    components,   # K x H x W depth
    weights,      # K x H x W probability
    selected_depth,
    uncertainty,
)
```

### 基于什么框架

Depth Anything 3 / PyTorch / mixture-density head / HF checkpoints。

### 创新

MDA 把 depth 从单峰回归改成多峰分布，允许一个像素存在多个合理深度。

### 对我们用途

P1 强威胁。我们不能把“多假设 depth”当主创新。可复用的是:

- mixture head 设计。
- component assignment / loss。
- boundary flying-point 指标。

我们的差异必须写成: transparent / mirror target semantics + single-depth to multi-layer bridge + reproducible ToM protocol。

## 7. Diffusion4RobustDepth

### 方法骨架

Diffusion4RobustDepth 不是透明专门方法，而是用 diffusion 生成困难条件数据，再微调 MDE，提高模型在非朗伯、极端光照、风格扰动等条件下的鲁棒性。

```text
base image / scene
  -> diffusion generates challenging-condition images
  -> train / fine-tune MDE
  -> evaluate robust depth
```

### 代码 I/O

官方仓库: https://github.com/fabiotosi92/Diffusion4RobustDepth

统一包装:

```python
RobustDepthInput(image, condition_type, dataset, split)
RobustDepthOutput(depth, metrics_by_condition)
```

### 基于什么框架

Diffusion-generated data + monocular depth backbone。项目公开 code、generated dataset 和 model weights。

### 创新

它证明一种数据路线: 不必改透明专门结构，也可以通过困难条件增强改善 depth robustness。

### 对我们用途

P1 通用 robust baseline。它适合回答 reviewer 问题:

> 你们的透明/非朗伯提升是不是普通 robust training 就能得到?

如果 Diffusion4RobustDepth 在 ToM mask 内仍失败，就能支撑 layer-aware / ToM-specific target 的必要性。

## 8. MODEST

### 方法骨架

MODEST 是单 RGB 透明物体 segmentation + depth 方法。它把语义和几何做 iterative fusion，直接面向透明物体，而不是 RGB-D completion。

```text
RGB image
  -> semantic transparent segmentation branch
  -> geometry depth branch
  -> iterative semantic-geometric fusion
  -> transparent mask + depth
```

### 代码 I/O

官方仓库: https://github.com/D-Robotics-AI-Lab/MODEST

建议包装:

```python
MODESTInput(image, dataset="Syn-TODD|ClearPose")
MODESTOutput(mask_pred, depth_pred, metrics)
```

### 基于什么框架

PyTorch，Syn-TODD / ClearPose，官方 weights 和 train/test/inference scripts。

### 创新

它把 transparent segmentation 和 depth 联合优化。对任何使用 mask 的透明 depth 工作都是强近邻。

### 对我们用途

P1 辅助 baseline。若我们的 layer-aware 方法显式输入 `tom_mask`，必须做:

- GT mask。
- proxy mask。
- noisy mask。
- no-mask。

否则会被 MODEST / ReMake 质疑为依赖强语义先验。

## 9. TransCG / DFNet

### 方法骨架

TransCG 的任务是 RGB-D 透明物体 depth completion。它不是单目 MDE。输入 RGB + raw depth，输出 completed metric depth。

```text
RGB + raw depth
  -> DFNet encoder-decoder
  -> completed metric depth
  -> transparent mask metrics / grasping demo
```

透明区域的 raw depth 可能是 0、背景深度或噪声。DFNet 假设 raw depth 中仍有足够可信邻域，可通过 RGB 和空间上下文补全。

### 代码 I/O

本地核心路径:

- `external/transcg/official/models/DFNet.py`
- `external/transcg/official/datasets/transcg.py`
- `external/transcg/official/inference.py`
- `external/transcg/official/configs/default.yaml`
- `复现/tools/transcg/run_dfnet_minimal.py`

最小 smoke test:

```bash
conda run -n transcg python 透明物体/复现/tools/transcg/run_dfnet_minimal.py \
  --out-dir 透明物体/runs/transcg/minimal_synthetic
```

真实样本接口:

```bash
conda run -n transcg python 透明物体/复现/tools/transcg/run_dfnet_minimal.py \
  --rgb 透明物体/data/transcg/scene21/1/rgb1.png \
  --depth 透明物体/data/transcg/scene21/1/depth1.png \
  --gt 透明物体/data/transcg/scene21/1/depth1-gt.png \
  --out-dir 透明物体/runs/transcg/scene21_1_dfnet
```

样本文件结构:

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

### 基于什么框架

官方 TransCG repo，DFNet，TransCG dataset，RealSense D435 / L515 数据。README 给过 RTX 3090 / CUDA11.1 / PyTorch1.9 风格环境；本地 smoke 用 CPU 环境验证了前向。

### 创新

TransCG 的核心资产是数据集和任务闭环: 57,715 张真实 RGB-D、51 个透明物体、130 个场景，并给出 DFNet 和抓取 baseline。

### 对我们用途

P1 A2 / robot failure slice 第一数据源。用途:

- transparent mask 内 metric correction。
- no-anchor transparent 区域。
- raw depth vs completed depth。
- ReMake / MOMA-style / A2 对照。

不应把 TransCG 与严格单 RGB 方法做不公平横比，除非明确输入条件。

## 10. ReMake

### 方法骨架

ReMake 仍是 RGB-D depth completion，但加入两个强先验: monocular relative depth 和 instance mask。

```text
RGB + mask          -> Swin image encoder
relative depth      -> Swin relative-depth encoder
raw depth           -> ResNet18 depth encoder
multi-scale fusion  -> decoder
completed metric depth
```

它和我们的关系很直接: 如果我们要做 transparent-grasp metric anchoring，ReMake 是最强的同类后处理 / completion baseline。

### 代码 I/O

本地核心路径:

- `external/remake/official/models/remake.py`
- `external/remake/official/datasets/transcg.py`
- `external/remake/official/run_utils/inferencer.py`
- `external/remake/official/configs/test/transcg_remake.yaml`
- `external/remake/official/configs/inference/remake.yaml`
- `复现/tools/remake/run_remake_minimal.py`

最小 smoke test:

```bash
conda run -n remake python 透明物体/复现/tools/remake/run_remake_minimal.py \
  --out-dir 透明物体/runs/remake/minimal_synthetic
```

真实样本最小接口:

```bash
conda run -n remake python 透明物体/复现/tools/remake/run_remake_minimal.py \
  --rgb 透明物体/data/transcg/scene21/1/rgb1.png \
  --depth 透明物体/data/transcg/scene21/1/depth1.png \
  --mask 透明物体/data/transcg/scene21/1/depth1-gt-mask.png \
  --gt 透明物体/data/transcg/scene21/1/depth1-gt.png \
  --out-dir 透明物体/runs/remake/scene21_1_smoke
```

完整官方链路还需要 `DepthAnythingV2` 权重，官方代码期望 `checkpoints/depth_anything_v2_vits.pth`。

### 基于什么框架

SwinTransformer、ResNet18、Depth Anything / LeReS、TransCG、ClearGrasp。官方提供 train/test/inference/realworld inference scripts 和 checkpoint。

### 创新

ReMake 的创新是把 MDE relative depth、instance mask 和 raw depth 融合进透明 RGB-D completion，直接面向抓取。

### 对我们用途

P1 强 baseline。A2 / transparent anchoring 必须回答:

> 为什么不用 ReMake 这种 MDE + mask + raw depth 后处理?

所以需要:

- ReMake 可运行 baseline。
- MOMA-style sparse alignment。
- global affine / patch affine。
- 我们的 sampling-time / layer-aware 方法。

并且把 mask、relative depth 生成、completion 网络都计入系统成本或 `nfe_real`。

## 11. ClearGrasp / LIDF

### 方法骨架

ClearGrasp 是经典 transparent RGB-D manipulation baseline:

```text
RGB-D + transparent mask
  -> predict surface normals / occlusion boundaries / mask
  -> clean raw depth
  -> global optimization
  -> completed transparent depth
```

LIDF 则把局部隐式函数用于 transparent depth completion:

```text
RGB-D local patch
  -> local implicit depth function
  -> refinement / hard-negative mining
  -> completed depth
```

### 代码 I/O

ClearGrasp: https://github.com/Shreeyak/cleargrasp

LIDF: https://github.com/NVlabs/implicit_depth

典型输入:

```python
RGBDCompletionInput(
    rgb,
    raw_depth,
    transparent_mask,
    normals=None,
    boundaries=None,
    intrinsics=None,
)
```

输出:

```python
CompletedDepthOutput(
    depth_completed,
    mask_metrics,
    point_cloud=None,
    grasp_proxy=None,
)
```

### 基于什么框架

ClearGrasp 环境较老，依赖 PyTorch1.3 / CUDA9 风格环境和 global optimization 组件；LIDF 依赖 ClearGrasp / Omniverse 数据，训练环境也较旧。

### 创新

这两者共同定义了 transparent RGB-D depth completion 的经典 post-hoc 门槛。

### 对我们用途

不建议第一批重跑全量，但必须作为 related work 和 baseline threshold。若 reviewer 要求完整 RGB-D completion 对照，优先先跑 TransCG / ReMake，再视时间补 ClearGrasp / LIDF。

## 12. ClearPose / DREDS

### 方法骨架

ClearPose 是透明物体 dataset / benchmark，不是单一方法。它提供 RGB、raw depth、rendered true depth、normal、instance label、6D pose 和多种 adversarial splits。

DREDS / SwinDRNet 是 sim2real restoration route:

```text
domain-randomized synthetic RGB-D
  -> depth sensor simulation
  -> train restoration network
  -> transfer to real transparent/specular objects
```

### 代码 I/O

ClearPose: https://github.com/opipari/ClearPose

DREDS: https://github.com/PKU-EPIC/DREDS

建议统一数据接口:

```python
TransparentRGBDSample(
    rgb,
    raw_depth,
    gt_depth,
    mask,
    normal=None,
    pose=None,
    split_tags=["occlusion", "liquid", "non_planar"],
)
```

### 基于什么框架

ClearPose 基于 RealSense L515 采集数据和 benchmark branches；DREDS 基于 Blender / domain randomization / SwinDRNet。

### 创新

ClearPose 的价值是泛化 split；DREDS 的价值是提醒我们数据驱动 sim2real restoration 是强路线。

### 对我们用途

P1/P2 泛化验证。不要只在 TransCG 调参。ClearPose 可作为:

- 遮挡、液体、非平面、透明盖 split。
- depth completion / pose 辅助指标。

DREDS 作为数据路线 threat，说明我们如果主张 low-cost / frozen prior，必须明确和大规模 sim2real restoration 的差异。

## 13. MOMA

### 方法骨架

MOMA 做 monocular one-shot metric-depth alignment for RGB-based robot grasping。它不是透明专门网络，但和 A2 的 sparse metric anchoring 很近。

```text
RGB image
  -> monocular relative depth
  -> sparse depth calibration points
  -> scale / rotation / shift alignment
  -> metric depth for grasping
```

### 代码 I/O

仓库入口: https://github.com/GreatenAnoymous/MOMA

建议仿造出一个同源后处理 baseline:

```python
SparseMetricAlignmentInput(
    relative_depth,
    sparse_depth_points,
    intrinsics=None,
    mask_valid=None,
)
```

```python
SparseMetricAlignmentOutput(
    depth_metric,
    alignment_params,
    residual_on_anchors,
    transparent_mask_metrics,
)
```

### 基于什么框架

MDE backbone + one-shot sparse metric calibration + robot grasping。完整复现需要机器人或 sparse depth calibration setup；但后处理数学本身可先离线仿造。

### 创新

MOMA 把 sparse metric alignment 和 RGB grasping 绑定，是 A2 “采样期注入优于输出端校准”最危险近邻。

### 对我们用途

必须做 L1 post-hoc 对照:

- global scale / shift。
- scale / rotation / shift。
- patch-wise affine。
- MOMA-style sparse metric alignment。

如果 A2 透明 slice 赢不了这类后处理，不应把透明物体作为主贡献。

## 14. SeeClear

### 方法骨架

SeeClear 的核心是 generative opacification: 先把透明物体区域生成成几何一致的不透明外观，再用 off-the-shelf MDE。

```text
RGB + transparent mask
  -> mask preparation / refinement
  -> conditional diffusion opacification
  -> composite opaque image
  -> DA3 / MoGe depth
```

### 代码 I/O

官方仓库: https://github.com/YumengHe/SeeClear

建议先作为 inference-only baseline:

```python
SeeClearInput(image, transparent_mask)
SeeClearOutput(opaque_image, refined_mask, depth_pred)
```

### 基于什么框架

Conditional diffusion opacification + off-the-shelf MDE。官方 demo checkpoint 已公开，但完整 SeeClear-396k 数据截至本轮调研仍不是第一阶段完整复现资产。

### 创新

它不直接改 depth 网络，而是改输入外观，把透明区域转成更接近普通不透明物体的视觉证据。

### 对我们用途

P2 强威胁。它会压住任何“先做透明预处理再跑 MDE”的 idea。我们可以把它作为:

- inference-only ablation。
- opacification route related work。
- 数据公开后的强 baseline。

不要在 SeeClear-396k 未可用前把它作为主训练基线。

## 15. AISPO / ASGrasp / 多视角系统上界

### 方法骨架

AISPO 强调 affine-invariant shape prior 和 depth reliability，面向非朗伯机器人 manipulation。ASGrasp / Dex-NeRF / ClearDepth 等使用 active stereo、多视角、NeRF 或更强 sensing。

```text
stronger sensing or shape prior
  -> more reliable geometry
  -> grasp / manipulation pipeline
```

### 代码 I/O

AISPO 当前先按论文级 I/O 记录:

```python
NonLambertianReliabilityInput(rgb, raw_depth_or_pred_depth, mask=None)
NonLambertianReliabilityOutput(depth_reliable, reliability_map, manipulation_metric)
```

ASGrasp 这类系统:

```python
ActiveStereoInput(rgbd_sequence_or_multiview, camera_calib, robot_setup)
ReconstructionGraspOutput(point_cloud, grasp_poses, success_rate)
```

### 基于什么框架

机器人系统、active stereo / multi-view / NeRF / grasp detection。输入条件明显强于单图 MDE。

### 创新

这些工作证明透明物体几何可以通过更强 sensing 或系统闭环解决。

### 对我们用途

不作为同输入 baseline。它们的用途是限定 claim:

- 我们不是替代 active stereo / multi-view / NeRF。
- 我们只主张 single-image / sparse-anchor / low-cost failure slice。
- 如果要写机器人应用，必须承认这些是系统上界。

## 16. 建议统一接口

### 16.1 数据样本接口

为了同时接 Depth4ToM / Booster / LayeredDepth / TransCG / ReMake，建议统一成:

```python
ImageDepthSample(
    sample_id: str,
    image: Tensor,                  # RGB, H x W x 3
    raw_depth: Optional[Tensor],     # metric raw sensor depth
    gt_depth: Optional[Tensor],      # metric GT or refined GT
    tom_mask: Optional[Tensor],      # transparent / mirror / ToM mask
    instance_mask: Optional[Tensor],
    layer_depths: Optional[List[Tensor]],
    tuple_labels: Optional[dict],
    intrinsics: Optional[Tensor],
    dataset: str,
    split: str,
    tags: list[str],
)
```

### 16.2 模型输出接口

```python
DepthPrediction(
    depth_single: Tensor,
    depth_front: Optional[Tensor],
    depth_through: Optional[Tensor],
    depth_completed: Optional[Tensor],
    confidence: Optional[Tensor],
    layer_components: Optional[Tensor],  # K x H x W
    component_weights: Optional[Tensor],
    metadata: dict,
)
```

### 16.3 评测输出接口

```python
EvalResult(
    metric_full: dict,
    metric_tom: dict,
    metric_other: dict,
    affine_full: dict,
    affine_tom: dict,
    boundary: dict,
    no_anchor_tom: dict,
    tuple_scores: dict,
    risk_coverage: Optional[dict],
    runtime: dict,
)
```

### 16.4 目录约定

```text
透明物体/
  external/<method>/official/      # 官方代码
  weights/<method>/                # checkpoint，忽略入库
  data/<dataset>/                  # 数据，忽略入库
  runs/<method>/<dataset>/<split>/ # predictions + metrics
  teacher/<method>/<dataset>/      # SeeGroup / MDA teacher cache
  复现/<method>.md                 # 复现记录
```

## 17. 第一阶段必跑

### P0: CCF-A 视觉主线

1. `Depth4ToM` 官方权重和 Booster eval。
2. `LayeredDepth` validation eval 跑通。
3. `SeeGroup` checkpoint 在 LayeredDepth 上跑通。
4. `Depth4ToM on LayeredDepth` gap diagnostic。
5. `SeeGroup first/front layer on Booster` 可行性测试。

### P1: 透明 / 机器人 failure slice

1. `TransCG` scene21 小块真实样本下载和 DFNet inference。
2. `ReMake` 接真实 TransCG 样本和 Depth Anything V2 relative depth。
3. `MOMA-style sparse alignment` 离线后处理 baseline。
4. `Booster` metric vs affine 双协议。
5. `MODEST` 单 RGB transparent mask/depth baseline。

### P2: 威胁与补充

1. `MDA` checkpoint sanity，确认是否作为 multi-hypothesis baseline。
2. `Diffusion4RobustDepth` 作为 non-Lambertian robust MDE baseline。
3. `SeeClear` demo inference，等 SeeClear-396k 后升级。
4. `AISPO / DepthFocus` 继续 monitor 代码发布。

## 18. 对我们方法设计的直接约束

从这些工作反推，我们不能写:

- “首次做透明物体深度估计”。
- “首次用 MDE 修透明物体”。
- “多假设 depth 是主要创新”。
- “单图方法超过 active stereo / multiview / NeRF 系统”。

更合理的主张是:

```text
透明/镜面单目深度的关键问题是 depth target semantics:
single-depth benchmark 要 front/contact surface,
multi-layer benchmark 要 ray-level layer structure,
robot failure slice 要 metric/contact depth and reliability.

我们复用已有 robust backbone 和公开 benchmark,
在最小新增模块中学习 layer-aware hypotheses,
再通过 selector / confidence 回到传统 MDE 或 A2 metric anchoring 输出。
```

第一版最小实现:

```text
Depth4ToM / Depth Anything backbone
  + LayeredDepth-Syn supervision
  + SeeGroup teacher cache
  + D_front / D_through / D_single / C_layer heads
  + Booster + LayeredDepth dual evaluation
```

A2 透明 slice 最小实现:

```text
TransCG / ClearPose / Booster
  + raw depth / global affine / patch affine
  + MOMA-style sparse alignment
  + ReMake if runnable
  + A2 sampling-time metric anchoring
  -> metric ToM, boundary, no-anchor transparent metrics
```

## 19. 下一步

1. 克隆 `Depth4ToM`、`LayeredDepth`、`SeeGroup` 到 `透明物体/external/`。
2. 补 `复现/Depth4ToM.md`、`复现/LayeredDepth.md`、`复现/SeeGroup.md` 三个运行记录。
3. 建一个统一 `runs/` 输出约定，所有 baseline 都保存 `predictions/metrics.json/config.yaml`。
4. 先跑 gap diagnostics，不先训练新模型。
5. 若 gap 成立，再实现 V1 ordered multi-head；若无 gap，转 reliability / protocol paper。
