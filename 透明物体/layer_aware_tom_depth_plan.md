# Layer-Aware ToM Depth 深入调研与课题规划

> **状态：支撑感知线。** 当前总项目主线为 [Shell-Aware Multi-Layer Transparent Grasping](Shell-Aware-Multi-Layer-Transparent-Grasping-Idea-v2.md)。本文继续负责 Depth4ToM / LayeredDepth / SeeGroup 的感知协议与复现资产，不再单独定义总项目 idea。

日期: 2026-07-07

目标: 把 `Layer-Aware ToM Depth` 从 idea 细化成一个可复现、可证伪、面向 CCF-A 视觉会议口径的研究计划。本文只写规划，不写已完成实验；所有未跑结论保持 `待跑`。

## 一句话判断

这个方向值得主攻，但不能写成“把 Depth4ToM 和 SeeGroup 接起来”。更稳的论文主张是:

> 透明/镜面单目深度的核心问题不是缺一个更大的网络，而是单一 depth 标量把前表面、透射/背景层、镜面/反射外观和任务单层输出混成了一个监督目标。我们从可复现的 Depth4ToM、LayeredDepth 和 SeeGroup 出发，学习一组有语义的 layer-aware depth hypotheses，并证明它能在传统 ToM single-depth benchmark 和 multi-layer transparent benchmark 之间建立可复现桥接。

## 关键结论

| 结论 | 含义 |
|---|---|
| 主入口仍是 `Depth4ToM + LayeredDepth + SeeGroup` | 三者分别给 single-depth ToM baseline、multi-layer 数据/协议、多层 SOTA teacher |
| 新发现的近期威胁是 `DepthFocus` 和 `MDA` | DepthFocus 是 CVPR 2026 controllable see-through depth，但仓库当前基本占位；MDA 有代码/权重，用 mixture-density 做多假设深度并扩展到透明层 |
| 方法不能只靠 mixture/multi-head | SeeGroup 和 MDA 已经覆盖“多峰/多层表示”的一部分，必须强调 `depth target semantics` 和 `single-depth <-> multi-layer` 可复现桥接 |
| 第一轮不应碰真实机器人 | 先用 Depth4ToM/Booster 与 LayeredDepth/SeeGroup 跑出离线证据；机器人只作为远期应用边界 |
| 最危险失败条件 | 在 Booster/Depth4ToM single-depth 上不赢 Depth4ToM，或只在 LayeredDepth 上有效但不能泛化到 ToM metric benchmark |

## 核验来源

| 资源 | 状态 | 对本课题的作用 |
|---|---|---|
| [Depth4ToM](https://github.com/CVLAB-Unibo/Depth4ToM-code) | ICCV 2023；公开 dataset、monocular weights、proxy labels、`scripts/table2.sh`/`scripts/table3.sh` | strong single-depth ToM baseline；定义 closest/front surface 风格的 ToM 输出 |
| [Booster](https://cvlab-unibo.github.io/booster-web/) / [NTIRE 2026](https://cvlab-unibo.github.io/booster-web/ntire26.html) | 高分辨率透明/镜面 benchmark；NTIRE 2026 metric mono track 要求 cm depth | ToM metric 主表和 transparent/mirror class split |
| [LayeredDepth](https://github.com/princeton-vl/LayeredDepth) / [HF](https://huggingface.co/datasets/princeton-vl/LayeredDepth) | ICCV 2025；real benchmark、validation/test eval、LayeredDepth-Syn | multi-layer task definition 与 first-layer/multi-layer eval |
| [SeeGroup](https://github.com/princeton-vl/SeeGroup) | CVPR 2026 Oral；checkpoint、validation/test/training 脚本公开 | multi-layer teacher、permutation-invariant loss 和强 baseline |
| [Diffusion4RobustDepth](https://github.com/fabiotosi92/Diffusion4RobustDepth) | ECCV 2024；代码、生成数据、模型权重公开 | 非朗伯/ToM robust MDE baseline |
| [MODEST](https://github.com/D-Robotics-AI-Lab/MODEST) | ICRA 2025；单 RGB 透明 segmentation + depth，代码/权重公开 | 单图透明物体 depth 近邻；机器人动机较强，放辅助 baseline |
| [MDA](https://github.com/biansy000/MDA) | 2026 arXiv；代码、训练、评测、HF checkpoint 公开 | mixture-density/multi-hypothesis 强威胁；可作为新增 baseline |
| [DepthFocus](https://github.com/junhong-3dv/DepthFocus) | CVPR 2026；当前仓库只有 README，demo/code 仍在准备 | controllable see-through depth 强概念威胁；暂不能作为完整复现入口 |
| [SeeClear](https://github.com/YumengHe/SeeClear) | ECCV 2026；demo checkpoint 公开，SeeClear-396k 数据仍未发布 | 生成式 opacification 威胁；当前不满足完整训练复现 |

## 资产复用判断: 不从 0 到 1

本课题的执行原则是先复用公开代码、权重、数据和评测协议，再在最小必要位置加 layer-aware / semantic-selector 组件。不要先造新 backbone、新数据集或新 benchmark。第一轮目标是把已有 robust backbone 和透明/多层 benchmark 接起来，证明 gap 和最小增量是否真实存在。

### 直接可用资产矩阵

| 资源 | 能否直接为我们所用 | 直接拿什么 | 可仿造什么 | 不建议做什么 | 本课题落点 |
|---|---|---|---|---|---|
| `Depth4ToM` | **能，P0 主骨干/主基线** | 官方 monocular weights、Trans10K/MSD virtual depth、Booster eval 入口、`table2/table3` 脚本 | ToM front-surface target、mask + inpainting 生成 virtual depth 的训练流程、ToM/Other split | 不要重复声称“首次做透明/镜面 single-depth” | V0/V1 的 single-depth teacher、warm start、Booster 主表基线 |
| `Booster / NTIRE` | **能，P0 主评测** | ToM/Other material mask、高分辨率 depth benchmark、metric mono 协议 | metric vs affine 双协议、透明/镜面类别分片、cm-level reporting | 不要只报全图 AbsRel，掩盖 ToM 区域失败 | 传统 single-depth ToM 主表，检验 `D_single/D_front` 是否有用 |
| `LayeredDepth` | **能，P0 多层协议/数据** | HF benchmark、validation/test eval、LayeredDepth-Syn、多层 prediction 格式 | ray-level layer definition、pair/triplet/quadruplet tuple eval、first-layer/all-layer 指标 | 不要把 real relative tuple 当 metric GT 使用 | 多层监督和协议边界，验证 `D_front/D_through` 是否真有层语义 |
| `SeeGroup` | **能，P0 teacher/强基线** | checkpoint、validation/test/training 脚本、多层预测输出 | permutation-invariant matching、depth-axis point-process / grouping loss、teacher pseudo-label | 不要把 SeeGroup 简单串到 Depth4ToM 后面当创新 | multi-layer teacher、SOTA 对照、V2/V3 loss 设计参考 |
| `MDA` | **能，P1 强威胁/头部参考** | 训练和评测代码、HF checkpoint、mixture-density head | 每像素多假设 depth component、mixture assignment、boundary flying-point 处理 | 不要把“多假设/mixture depth”当主 novelty | reviewer threat；可作为 V3 stronger head 或 ablation |
| `Diffusion4RobustDepth` | **能，P1 通用鲁棒 baseline** | 代码、生成数据、模型权重 | 非朗伯/困难条件 stress protocol、robust augmentation | 不要把它当透明专用方法 | 通用 robust MDE 对照，说明透明失败不是普通鲁棒性即可解决 |
| `MODEST` | **能，P1 单 RGB 透明辅助基线** | segmentation + depth 权重、Syn-TODD/ClearPose 入口、train/test/inference 脚本 | mask/depth 联合输出、透明实例级评测组织方式 | 不要让主方法强依赖 GT mask 却不计 mask 成本 | 辅助 baseline；GT/proxy/noisy/no-mask 消融参考 |
| `TransCG / ClearPose` | **能，P1 应用切片数据** | 真实透明 RGB-D、mask、completed/true depth、部分抓取或 pose 相关标注 | transparent-mask、boundary、occlusion/liquid/non-planar split | 不要与单 RGB 方法做不公平 RGB-D 同输入横比 | A2 / robot failure slice；检验透明区域 metric correction |
| `ReMake` | **能，P1 RGB-D completion 强基线** | checkpoint、train/test/inference/realworld inference 脚本、MDE+mask+RGB-D completion pipeline | mask-guided completion、MDE relative depth 与 raw depth 融合方式 | 不要把本方法写成普通 MDE+mask depth completion | A2 后处理对照；证明 sampling-time / layer-aware 不是同质修补 |
| `SeeClear` | **部分能，P2 demo/威胁** | demo checkpoint、transparent mask preparation、opacification inference pipeline | 生成式 opacification 作为透明预处理 baseline | 在 SeeClear-396k 未公开前，不把它列为完整训练复现基线 | inference-only ablation；数据公开后升为强 baseline |
| `DepthFocus` | **暂不能，P2 monitor** | 当前只能读 concept / README | controllable layer selection、intent-driven depth preference | 代码未发布前不要安排核心实验依赖 | related work 强威胁；代码放出后补 controllable selection 对照 |

### 推荐复用路线

**主线不是新造骨干，而是“Depth4ToM / Depth Anything / Metric3D 这类单层 robust backbone + LayeredDepth / SeeGroup 多层 teacher + Booster metric benchmark”。**

第一版直接采用 `Depth4ToM-DPT` 或 `Depth4ToM-MiDaS` 作为 warm start，优点是 ToM front-surface 目标已经对齐，能快速跑通 Booster 主表。主论文版再换成 `Depth Anything V2` 或 `Metric3D V2` encoder/head 体系，避免 reviewer 认为只是在旧 DPT 上做小改。

多层部分不从零标注。`LayeredDepth-Syn` 给训练监督，`LayeredDepth real validation/test` 只做外评，`SeeGroup` checkpoint 先作为 teacher 生成多层 pseudo-label 和失败区域，再决定是否实现更复杂的 point-process / mixture head。

评测不自造 leaderboard。直接用 `Depth4ToM/Booster` 报 metric single-depth，用 `LayeredDepth` 报 tuple / layer 指标，用 `MDA/SeeGroup` 报多假设威胁，用 `MODEST/ReMake/TransCG` 补透明物体或机器人切片。

### 可以仿造的接口

| 模块 | 建议仿造对象 | 我们的最小接口 | 目的 |
|---|---|---|---|
| 样本对象 | Depth4ToM + LayeredDepth | `ImageInstance(image, mask_tom?, depth_metric?, layer_depths?, tuple_labels?, dataset, split)` | 统一 single-depth 和 multi-layer 数据入口 |
| 模型输出 | SeeGroup + MDA + Depth4ToM | `DepthPrediction(D_front, D_through?, D_single, C_layer?, components?)` | 避免把所有方法硬压成一个 depth map |
| 评测输出 | Booster + LayeredDepth | `EvalResult(metric_tom, metric_other, affine_tom, tuple_scores, boundary_scores, risk_coverage?)` | 同时服务 ToM metric 表和 multi-layer 表 |
| teacher cache | SeeGroup / MDA checkpoint output | `teacher/{dataset}/{image_id}.npz` 保存 multi-layer candidates、weights、confidence | 避免每次训练重复跑重模型 |
| baseline log | Depth4ToM scripts + LayeredDepth eval | `runs/{method}/{dataset}/{split}/predictions + metrics.json` | 让新增方法和官方 baseline 同协议比较 |

### 最小实现策略

1. **先跑资产，不先写模型**: Depth4ToM table 复现、LayeredDepth eval 跑通、SeeGroup checkpoint 跑通、MDA checkpoint sanity。
2. **先做 adapter，不改 backbone**: 写统一 dataloader / evaluator，把 Depth4ToM、Booster、LayeredDepth 的输入输出对齐。
3. **先做小头，不训练大模型**: 在冻结或半冻结 backbone 上加 `D_front/D_through/D_single/C_layer` head，验证是否比 single-head 有信号。
4. **先做 teacher distillation，不人工造标签**: 用 SeeGroup/MDA/LayeredDepth-Syn 产生多层监督，Depth4ToM/Booster 约束 front/single depth。
5. **只在证据足够时升级复杂 head**: 如果 ordered multi-head 已有增益，再参考 SeeGroup/MDA 做 point-process 或 mixture-density variant。

### 是否适合 A2 透明 failure slice

如果目标转向 A2 / metric anchoring，而不是 CCF-A 视觉主线，资产复用也不应从零开始:

| 需求 | 直接资产 | 用法 |
|---|---|---|
| 透明区域 metric correction 数据 | TransCG、ClearPose、Booster | 按 transparent mask、boundary、no-anchor 区域报告 metric error |
| 同源后处理对照 | MOMA-style sparse alignment、AnchorD-like patch affine、ReMake | 证明 sampling-time anchoring 不是普通后处理可替代 |
| 单 RGB / ToM baseline | Depth4ToM、MODEST、SeeClear demo | 检验透明 mask 内是否比现成 ToM 方法更稳 |
| 多层 claim 边界 | LayeredDepth、SeeGroup | 限定 A2 输出是 `contact/front surface`，不声称完整多层透明重建 |

结论: `Layer-Aware ToM Depth` 的主线可以直接站在 `Depth4ToM + LayeredDepth + SeeGroup` 上；A2 透明切片可以直接站在 `TransCG/ClearPose/Booster + ReMake/MOMA-style/Depth4ToM` 上。真正需要自己写的是统一 adapter、layer-aware head、selector/confidence 和 ablation，不是数据、benchmark 或 backbone。

## 最近邻工作减法

### Depth4ToM

Depth4ToM 的关键设定是: 透明/镜面区域的目标 depth 是相机前方最近表面的 depth，而不是透过去或反射出来的内容。它用 mask + random color inpainting 生成 virtual depth，再微调 MiDaS/DPT。论文表 2 中 DPT 在 Booster ToM 区域从 Base RMSE 136.28 mm 降到 83.06 mm，`delta < 1.05` 从 37.70% 升到 54.67%；表 3 说明 proxy segmentation 也能复现接近效果。

剩余空位:

- 仍是单一 depth target，无法解释透明区域到底学的是 front surface、背景层还是网络平均解。
- virtual depth 依赖 inpainting 和聚合，伪标签本身没有层语义和可靠性。
- 评测强在 Booster ToM single-depth，但无法回答 LayeredDepth 的 multi-layer 问题。

### LayeredDepth

LayeredDepth 把透明物体 depth 定义为一条 camera ray 上所有 medium transition 的有序层。它的 real benchmark 有 1,500 张 in-the-wild 图片和 14.2M relative depth tuples；LayeredDepth-Syn 有 15,300 张合成图，其中 14,800 train、500 val。单层方法在 LayeredDepth 上仍明显困难，Depth4ToM 的 quadruplet accuracy 为 70.61，Depth Anything V2 为 70.43，Depth Pro 为 69.46；Metric3D V2 用合成数据 fine-tune 后能到 75.20。

剩余空位:

- 它证明了多层必要性，但没有给传统 ToM single-depth benchmark 一个清晰桥接方式。
- real benchmark 是 relative tuple，不是 metric depth；不能直接替代 Booster/Depth4ToM 的 metric single-depth 表。
- multi-layer baseline 与传统 MDE backbone 的接口仍有提升空间。

### SeeGroup

SeeGroup 把 per-pixel multi-layer depth 建模为 depth-axis point process，用 permutation-invariant likelihood 解决层顺序/分组不固定的问题。它在 LayeredDepth benchmark 上把 all quadruplet relative accuracy 从 Multi-head DA v2 的 61.34 提到 70.09。

剩余空位:

- 它解决的是 multi-layer grouping，不是 ToM single-depth 的任务语义桥接。
- 它没有直接证明在 Booster/Depth4ToM-style ToM metric/front-surface 输出上更好。
- 它的输出是多层候选，需要进一步定义如何选出传统 MDE 所需的 `D_single`。

### MDA

MDA 是新增强威胁。它用 mixture-density 表示每个像素的多深度假设，本来瞄准边界 flying points，也扩展到透明区域: 透明像素可同时激活多个 depth components，输出可见透明表面和背后 occluded geometry。仓库已经公开训练代码、评测脚本和 HF checkpoints；默认 DA3 + mixture + sky 模型可复现。

剩余空位:

- 当前是 arXiv preprint，不是已确认顶会入口。
- 透明部分更像 mixture representation 的扩展，不是围绕 ToM benchmark/Depth4ToM/LayeredDepth 做的专门任务定义。
- 它提供了很强的 baseline 和损失设计参考；我们的 novelty 不能是“多假设”，必须是“透明/镜面 target semantics + single-depth/multi-layer bridge + reproducible ToM protocol”。

### DepthFocus

DepthFocus 是 CVPR 2026，提出 controllable / intent-driven see-through depth，使用 scalar depth preference 选择不同 see-through 层。它很接近“用户或任务选择哪一层 depth”的概念。但当前 GitHub 只有 README，写着 camera-ready 和 demo code 准备中；截至 2026-07-07 不能作为完整可复现起点。

剩余空位:

- 它是 stereo/see-through controllable depth 主线，不是严格单图 ToM MDE。
- 当前代码未发布，短期只能作为 reviewer threat。
- 如果后续代码放出，本课题需要把 DepthFocus 作为“controllable layer selection”对照或 related work 强威胁。

## 研究问题

核心问题:

> 能否训练一个单图 depth model，在透明/镜面区域输出一组语义可解释的 depth hypotheses，并且同时满足传统 ToM single-depth metric 评测和 multi-layer transparent depth 评测？

三个可证伪假设:

| 假设 | 预期证据 | 失败判据 |
|---|---|---|
| H1: 单一 depth label 是透明 ToM 的弱监督瓶颈 | Layer-aware supervision 在 transparent mask / boundary / multi-layer tuple 上优于 single-depth baseline | 只要换 backbone 或更多数据就能达到同样效果 |
| H2: 多层 teacher 能改善 single-depth ToM 输出 | 用 LayeredDepth/SeeGroup teacher 后，在 Booster/Depth4ToM ToM 区域仍提升或不掉点 | 只在 LayeredDepth 有效，Booster single-depth 变差 |
| H3: 可信度/层选择能解释失败 | `C_layer` 与高误差区域、背景透射错、边界错有稳定相关 | confidence 只是普通 uncertainty，不能定位透明特有失败 |

## 输出定义

模型输出不直接叫“透明 depth”，而是拆成如下目标:

| 符号 | 含义 | 监督来源 | 备注 |
|---|---|---|---|
| `D_front` | 最靠近相机的透明/镜面物理表面 depth | Depth4ToM virtual depth、Booster GT、LayeredDepth layer 1 | 传统 ToM single-depth 最重要 |
| `D_through` | 透明物体后方可见背景或后层 depth | LayeredDepth odd layers、SeeGroup teacher、LayeredDepth-Syn GT | 只对透明有效；镜面不强行定义 |
| `D_reflect` | 镜面/反射外观对应的非物理 depth cue | 暂不作为主监督 | 可作为 failure type，不作为主输出 |
| `D_single` | 传统 MDE 输出的单层 depth | 由 selector 选择 front / opaque normal depth | 用于 Booster/Depth4ToM/普通 MDE 主表 |
| `C_layer` | 每个像素是否存在多层歧义、输出是否可信 | teacher disagreement、residual、tuple violation | 服务 reliability 和 selective eval |
| `P_task` | 任务选择概率，如 front / through / invalid | synthetic GT、teacher、mask | 用于从多层候选落回单层输出 |

镜面 caveat: 透明物体可以自然定义 `D_through`；镜面中的反射内容不是真实沿相机 ray 的背后层。镜面样本主张应收窄为 `D_front + failure/reliability`，不要把 mirror reflection 强写成透射层。

## 方法设计

### 版本 V0: 只做诊断，不训练新模型

目的: 证明空位真实存在。

步骤:

1. 复现 Depth4ToM DPT/MiDaS 在 Booster ToM 区域的表 2/3。
2. 用 Depth4ToM/DA V2/Depth Pro/Metric3D 在 LayeredDepth validation 上跑 `layer_first` 或 single-layer tuple eval。
3. 跑 SeeGroup checkpoint，在 LayeredDepth 上复现 validation 指标。
4. 尝试把 SeeGroup first layer 输出对齐到 Booster/Depth4ToM metric protocol，记录是否可行；若不可行，只写为协议边界。

产物: 一张 gap table，显示 single-depth ToM 方法和 multi-layer 方法各自在哪个协议失败。

### 版本 V1: Ordered multi-head baseline

目的: 做最小可跑方法，不碰复杂 point-process。

Backbone:

- 快速版: DPT / Depth4ToM DPT 权重。
- 主论文版: Depth Anything V2 或 Metric3D V2 backbone，方便对齐 LayeredDepth/SeeGroup 和强 MDE baseline。

输出:

- `D_1, D_2, D_3` ordered heads。
- `D_single = selector(D_1, D_2, D_3, C_layer)`。
- `C_layer` 预测是否多层/可信。

损失:

- `L_front`: 对 Depth4ToM virtual depth / Booster front-surface target 做 masked regression。
- `L_layer_syn`: 在 LayeredDepth-Syn 上监督多层 metric depth。
- `L_tuple`: 在 LayeredDepth 协议上使用相对顺序损失；真实 validation 不用于训练主模型，只用于调参外评。
- `L_single`: 保持非透明区域常规 MDE 性能。
- `L_conf`: 用 baseline residual 或 teacher disagreement 构造 reliability target。

优点: 实现快，容易 ablation。

缺点: ordered heads 会被 SeeGroup 批评，层分组不稳定。

### 版本 V2: Semantically selectable hypotheses

目的: 形成真正论文主线。

输出不是简单 `layer 1/2/3`，而是:

- `H_front`: front/closest physical surface。
- `H_through`: transmitted/background layer。
- `H_single`: task single-depth output。
- `H_residual`: optional extra hypothesis for ambiguous boundary/reflection。

关键机制:

1. Semantic target conditioning: 给每个 head 一个 target token，如 `front`、`through`、`single`，避免固定 depth order 造成歧义。
2. Teacher-aligned assignment: 在 LayeredDepth/SeeGroup teacher 上使用 permutation matching，但匹配结果再映射到语义 heads。
3. Single-depth selector: 让 `D_single` 学会在 opaque 区走普通 depth，在透明/镜面区走 `front`，在不可靠区输出低 confidence。
4. Reliability calibration: `C_layer` 预测多层歧义强度和当前 single-depth 是否可信。

建议命名:

- `LA-ToM`: Layer-Aware Transparent-or-Mirror Depth。
- `SLA-MDE`: Semantically Layer-Aware Monocular Depth Estimation。

### 版本 V3: Mixture-density / point-process variant

目的: 对抗 MDA 和 SeeGroup reviewer threat。

做法:

- 参考 SeeGroup 的 intensity function 或 MDA 的 mixture-density head，输出 `K=4` components。
- 在透明像素允许多个 components active；在 opaque 像素约束 weight sum 接近 1。
- 加一个 semantic selector，把 components 映射成 `front`、`through`、`single`。

注意:

- 不能把这个作为唯一创新，因为 SeeGroup/MDA 已经覆盖了多峰表示。
- 它适合作为 V2 的 stronger head 或 ablation。

## 训练数据与评测数据

| 数据/资源 | 角色 | 监督/指标 | 注意事项 |
|---|---|---|---|
| Trans10K + MSD virtual depths | Depth4ToM-style training | ToM mask + virtual depth | 无真实 depth；用于复现和 weak supervision |
| Booster train / benchmark | ToM single-depth metric eval | ToM/Other split、MAE/RMSE/AbsRel/delta | 高分辨率，先 quarter/full-res 两套 |
| NTIRE 2026 Booster metric mono | metric protocol 目标 | ToM RMSE cm | 需要关注最终 leaderboard/code release |
| LayeredDepth-Syn | multi-layer training | per-layer metric depth、synthetic val AbsRel/RMS/delta | 合成域；适合训练多层头 |
| LayeredDepth real validation/test | multi-layer evaluation | pair/triplet/quadruplet tuple accuracy，layer_first/layer_all | real val 不应被当训练集 |
| SeeGroup checkpoint | teacher/baseline | multi-layer predictions | 训练成本 4x L40 250k steps，可先只用 checkpoint |
| Diffusion4RobustDepth | robust MDE baseline | ToM qualitative/Booster/ClearGrasp | 不是透明专门方法 |
| MODEST | single RGB transparent baseline | segmentation + depth | ICRA/机器人动机强；作为辅助 |
| MDA | mixture-density baseline | LayeredDepth transparent extension、boundary metrics | 新增强威胁；可跑但不是顶会确认 |

## 实验矩阵

### E0: 复现门槛

| 实验 | 成功标准 | 失败处理 |
|---|---|---|
| Depth4ToM Table 2/3 复现 | DPT ToM RMSE / delta 与论文同量级 | 修环境与数据；不能跳过 |
| LayeredDepth eval.py 跑通 | `layer_first` 和 `layer_all` 能产生指标 | 先跑官方 sample/prediction 格式 |
| SeeGroup checkpoint eval | validation 指标接近 README/论文 | 若不稳定，只作为 teacher 观察 |
| MDA demo/eval 可跑性 | checkpoint inference 跑通 | 若依赖 DA3 太重，先列为 monitor |

### E1: Gap diagnostics

| 问题 | 对比 | 指标 |
|---|---|---|
| single-depth ToM 方法是否混层 | Depth4ToM / DA V2 / Depth Pro on LayeredDepth | P/T/Q tuple accuracy，layer_first vs mixed |
| multi-layer 方法是否能回到 metric single-depth | SeeGroup/MDA first layer on Booster | ToM RMSE/AbsRel，scale-aligned vs metric |
| inpainting virtual depth 是否可靠 | Depth4ToM virtual depth vs Booster GT | ToM residual、boundary residual、mask subtype |
| 多层歧义是否对应高误差 | LayeredDepth tuple violation vs Depth4ToM residual | correlation、AUROC |

### E2: 方法主表

| 数据 | 主指标 | 必须报 |
|---|---|---|
| Booster / Depth4ToM protocol | ToM RMSE、MAE、AbsRel、delta；Other 区域不掉点 | metric 主表 + affine 对照 |
| LayeredDepth real | pair/triplet/quadruplet accuracy，layer_first/layer_all | 与 Depth4ToM、DA V2、SeeGroup、MDA 比较 |
| LayeredDepth-Syn val | per-layer AbsRel/RMS/delta | 证明多层头没有坍缩 |
| Normal depth sanity set | NYU/KITTI 或 Booster Other | 不为透明提升牺牲普通区域 |

### E3: Ablation

| Ablation | 要回答的问题 |
|---|---|
| single-head vs ordered multi-head vs semantic heads | 增益来自多输出还是语义 target |
| without SeeGroup teacher | teacher 是否必要 |
| without LayeredDepth-Syn | 多层监督是否必要 |
| without Depth4ToM virtual depth | single-depth ToM anchor 是否必要 |
| without selector / direct first-head as single | `D_single` 是否真的学会任务选择 |
| without confidence | reliability 是否帮助 selective prediction |
| K=2/3/4 hypotheses | 是否需要多于 front/background 两层 |
| GT mask vs proxy mask vs no mask | 是否过度依赖透明 mask |
| transparent-only vs transparent+mirror | mirror 是否应单独建模 |

### E4: Reliability diagnostics

| 指标 | 定义 | 目标 |
|---|---|---|
| risk-coverage | 按低可信度拒绝像素后，剩余 ToM depth error | 证明 `C_layer` 有用 |
| failure AUROC | 预测 high-residual / tuple-violation 像素 | 证明能定位透明失败 |
| ECE on ToM | 透明区域置信度校准 | 防止只做漂亮 heatmap |
| boundary RMSE | 透明边界窄带误差 | 对抗 MDA/flying-point 风险 |

## Baseline 清单

第一批必跑:

1. `Depth4ToM-DPT`: 官方权重和脚本。
2. `Depth4ToM-MiDaS`: 论文原表补充。
3. `Depth Anything V2`: LayeredDepth/SeeGroup 的强 backbone 近邻。
4. `Depth Pro / Metric3D V2`: LayeredDepth 单层强 baseline。
5. `SeeGroup`: multi-layer teacher/SOTA。
6. `MDA`: mixture-density 强威胁。

第二批再跑:

1. `Diffusion4RobustDepth`: non-Lambertian robust baseline。
2. `MODEST`: 单 RGB transparent segmentation + depth。
3. `SeeClear demo`: 只做 inference 观察，等 SeeClear-396k 发布后再列完整复现。
4. `DepthFocus`: 等 code/demo release 后纳入。

## 论文贡献设计

推荐贡献写法:

1. Problem: 重新审视透明/镜面 MDE 的 single-depth 监督歧义，并把它形式化为 semantic layer-aware target selection。
2. Method: 一个能输出 `D_front`、`D_through`、`D_single` 和 `C_layer` 的单图 depth model，结合 Depth4ToM single-depth supervision 与 LayeredDepth/SeeGroup multi-layer supervision。
3. Protocol: 同时在 Booster/Depth4ToM metric ToM 和 LayeredDepth multi-layer tuple 上评估，避免只在单一协议刷分。
4. Evidence: 展示 layer-aware supervision 改善 ToM single-depth、multi-layer ordering、boundary/reliability，同时普通区域不退化。

不要写:

- “我们首次解决透明物体深度估计”。
- “我们的创新是多峰深度表示”。这会被 SeeGroup/MDA 压住。
- “我们恢复完整透明光学几何”。当前只能说 visible layers / task depth hypotheses。
- “超过 stereo/active/multiview 系统”。本课题是单图 MDE。

## 风险与对策

| 风险 | 严重性 | 对策 |
|---|---:|---|
| MDA 抢走 mixture-density novelty | 高 | 不把 mixture 写主贡献；主张改为 ToM target semantics + cross-protocol bridge |
| DepthFocus code 发布后概念接近 | 高 | 明确其是 controllable/stereo see-through；本课题是 single-image ToM/MDE + reproducible Depth4ToM/LayeredDepth bridge |
| 只在 LayeredDepth 提升，Booster 不提升 | 高 | 主张收窄为 multi-layer transparent depth；停止 CCF-A single-depth claim |
| Booster 提升但 LayeredDepth 不提升 | 中高 | 退回为 Depth4ToM successor，novelty 变弱；需 reliability 或 label-quality 贡献救场 |
| 过度依赖 mask | 中高 | 必跑 GT/proxy/noisy/no-mask 消融；mask 成本写清 |
| mirror 与 transparent 混用造成语义不清 | 中 | transparent 主张 `front/through`；mirror 主张 `front/reliability` |
| LayeredDepth real 只有 relative labels | 中 | metric 结论只在 Booster/Depth4ToM；LayeredDepth 只报 tuple ordering |
| 训练成本过高 | 中 | 先做 V1 ordered-head，小模型证明；V2/V3 作为主模型 |

## 8 周执行计划

| 时间 | 任务 | 交付物 |
|---|---|---|
| Week 1 | 环境和数据: Depth4ToM、LayeredDepth、SeeGroup；确认 MDA 可跑性 | `repro_notes.md`、baseline raw outputs |
| Week 2 | 复现门槛: Depth4ToM table2/table3、LayeredDepth eval、SeeGroup val | baseline table v0 |
| Week 3 | Gap diagnostics: Depth4ToM on LayeredDepth、SeeGroup/MDA on single-depth协议可行性 | gap figure + failure taxonomy |
| Week 4 | V1 ordered multi-head prototype | first training curves + synthetic/validation metrics |
| Week 5 | V2 semantic heads + selector | main method v1 |
| Week 6 | Ablation: teacher、synthetic、多层、selector、confidence、mask noise | ablation table |
| Week 7 | Robustness: Booster high-res/NTIRE metric、boundary、risk-coverage | final table draft |
| Week 8 | 写作与补实验 | paper outline + related work + figures |

## Go / no-go gates

| Gate | Go | No-go |
|---|---|---|
| G0: 复现 | Depth4ToM/LayeredDepth/SeeGroup 都能跑通 | 环境或数据无法稳定复现，先转 benchmark 工程 |
| G1: Gap | single-depth 与 multi-layer 协议存在可视化和定量错位 | 如果现有方法已经同时解决，换题 |
| G2: Main gain | transparent mask 内优于 Depth4ToM，LayeredDepth tuple 不低于强 baseline | 若只提升一个协议，收窄主张 |
| G3: Reviewer defense | 能解释 MDA/SeeGroup/DepthFocus 差异 | 如果差异只剩工程组合，不投 CCF-A |
| G4: Robustness | mask noise、boundary、普通区域 sanity 都过 | 否则改成 diagnostic/reliability paper |

## 最小第一批实验清单

1. `Depth4ToM-DPT` on Booster: 复现 ToM RMSE/MAE/AbsRel/delta。
2. `Depth4ToM-DPT` on LayeredDepth `layer_first`: 看 single-depth front-surface 在 relative tuple 上的表现。
3. `SeeGroup` checkpoint on LayeredDepth validation: 复现 multi-layer P/T/Q。
4. `Depth4ToM vs SeeGroup` 可视化: 同一透明图上对比 single-depth/front/background。
5. `MDA` demo/checkpoint sanity: 确认是否能作为 baseline。
6. 小样本 prototype: 用 LayeredDepth-Syn 训练 `D_front/D_through` heads，再用 Depth4ToM virtual depth 约束 `D_single`。

## 推荐论文题目草案

- `Layer-Aware Monocular Depth Estimation for Transparent and Mirror Surfaces`
- `Which Depth Should Transparent Objects Have? Layer-Aware Targets for ToM Monocular Depth`
- `Bridging Single-Depth and Multi-Layer Depth for Transparent Surface Perception`

最推荐标题方向是第三个，因为它最准确地区分本课题与 Depth4ToM、SeeGroup、MDA 和 DepthFocus。

## 立即下一步

1. 先建立 `repro/depth4tom`、`repro/layereddepth`、`repro/seegroup` 三个复现记录。
2. 不先写新模型，先跑出 gap diagnostics: `Depth4ToM on LayeredDepth` 与 `SeeGroup first-layer on Booster`。
3. 把 MDA 加入观察/可跑 baseline；DepthFocus 加入 monitor，等其 demo/code release。
4. 第一版模型只做 V1 ordered multi-head，确保 2 周内能看到是否有信号。
5. 若 V1 有信号，再升级 V2 semantic heads；若 V1 无信号，先转 reliability/failure taxonomy。
