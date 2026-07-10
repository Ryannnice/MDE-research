# Layer-Aware ToM Depth Idea v3：框架与 Scope 优化

日期: 2026-07-10

本文件基于 `方法骨架与代码IO调研.md`、`layer_aware_tom_depth_plan.md` 和已复现的 TransCG / ReMake 代码流，专门回答一个问题：

> 看完 Depth4ToM、Booster、LayeredDepth、SeeGroup、MDA、MODEST、TransCG、ReMake、MOMA、SeeClear 这些代表性工作之后，透明物体 topic 应该怎么收紧、怎么搭框架、怎么讲故事，才不像 AI 直接拼出来的“透明深度大一统系统”。

## 0. 汇报版：一句话、标题、贡献和模型边界

### 0.1 一句话讲解

透明/镜面像素不该被强行回归成一个 depth 标量；我们复用现有 MDE backbone 和公开 benchmark，先保留前表面、透射层、单层读出和可信度等 `DepthHypothesisPack`，再按任务选择该输出哪一种 depth。

更短版本：

```text
透明/镜面 depth 的核心不是再造一个 backbone，
而是先保留多种物理语义的 depth hypotheses，
再根据 benchmark 或下游任务做正确 readout。
```

### 0.2 标题

首选标题：

**Bridging Single-Depth and Multi-Layer Depth for Transparent and Mirror Surfaces**

中文可讲成：

**面向透明/镜面表面的单层深度与多层深度桥接**

备选标题：

- **Layer-Aware Monocular Depth Estimation for Transparent and Mirror Surfaces**
- **Which Depth Should Transparent Objects Have? Task-Conditioned Depth Readout for ToM Surfaces**
- **DepthHypothesisPack: Preserving and Selecting Transparent Surface Depths**

不推荐标题：

- `Transparent Object Depth Estimation for Robotics`
- `Robust Transparent Object Depth Completion`
- `Multi-Hypothesis Depth for Transparent Objects`

这些标题要么把 scope 拉进机器人 RGB-D completion 战场，要么会被 ReMake / MDA / SeeGroup 压住。

### 0.3 核心贡献

贡献 1：**问题定义**

指出透明/镜面 MDE 的关键不是缺新网络，而是 depth target 语义混乱：前表面、透射背景、多层结构、传统单层输出不是同一个目标。

贡献 2：**方法**

提出 `DepthHypothesisPack` / layer-aware readout model，在现有 MDE backbone 上增加多语义深度头，同时输出：

```text
D_front   : 透明/镜面物体前表面或 contact/front surface depth
D_through : 透射背景或后层 depth
D_single  : 传统 MDE / Booster / Depth4ToM 需要的单层 depth
C_layer   : 多层歧义、失败风险或可信度
selector  : 根据任务选择 front / through / normal / invalid
```

贡献 3：**评测桥接**

把 Depth4ToM / Booster 的 single-depth metric 协议和 LayeredDepth / SeeGroup 的 multi-layer 协议接起来，证明方法不是只在一个 benchmark 上刷分。

一句话贡献：

```text
我们不是再做一个透明深度网络，而是提出一种 layer-aware depth target bridge，
让透明/镜面像素先保留多种物理语义的深度假设，
再根据 benchmark 或下游任务选择正确输出。
```

### 0.4 我们是否提出了一个模型

是，但要精确表述：我们提出的不是一个从零训练的新 depth backbone，而是一个接在现有 MDE backbone 上的 **layer-aware readout model / hypothesis head**。

不建议说：

```text
We propose a new monocular depth backbone.
```

建议说：

```text
We propose a layer-aware depth readout model that augments existing monocular
depth backbones with semantically assigned transparent-surface depth hypotheses.
```

中文表述：

> 我们提出一个透明/镜面深度的 layer-aware 读出模型，在现有 MDE 骨干上增加多语义深度头，输出前表面、透射层、传统单层深度和可信度。

模型结构可以写成：

```text
RGB image
  -> borrowed MDE backbone
  -> layer-aware hypothesis head
       -> D_front
       -> D_through
       -> D_single
       -> C_layer
       -> selector / task-conditioned readout
```

输入：

```text
RGB image
optional: ToM mask / proxy mask / teacher output
```

骨干：

```text
Depth4ToM / DPT / Depth Anything / Metric3D 等现有 MDE backbone
```

我们新增的模型部分：

```text
Layer-aware hypothesis head + DepthHypothesisPack + task-conditioned readout
```

### 0.5 最稳的论文定位

最稳定位：

```text
借用现有 robust backbone 和公开 benchmark，
研究透明/镜面像素到底应该输出哪一种 depth target，
并提出一个 layer-aware readout model 连接 single-depth 和 multi-layer 协议。
```

不要把主线写成：

```text
透明物体机器人抓取深度补全系统
```

机器人 / A2 / TransCG / ReMake / MOMA-style sparse alignment 适合作为 appendix 或 second-stage application slice，不应抢主贡献。

## 1. 结论：idea 不需要推翻，但必须从“透明物体深度估计”收成“深度目标语义桥接”

如果按早期口径直接写成：

```text
我们做透明/镜面物体单目深度估计，
结合 Depth4ToM、LayeredDepth、SeeGroup、MDE backbone、confidence、robot grasp。
```

会显得像把已有工作拼在一起。问题不在这些模块没用，而在 scope 太散：

- Depth4ToM 已经做了透明/镜面 ToM single-depth 训练和 Booster 评测。
- LayeredDepth 已经把透明 depth 重新定义成多层 medium transition。
- SeeGroup 已经做了 strong multi-layer transparent depth。
- MDA 已经覆盖 multi-hypothesis / mixture-depth 表示的一部分。
- MODEST 已经做了单 RGB 透明 segmentation + depth。
- ReMake 已经把 MDE relative depth、mask 和 raw depth 接进透明抓取 depth completion。
- SeeClear 已经覆盖“先生成不透明外观再跑 MDE”的路线。
- MOMA 已经把 sparse metric alignment 和 RGB robot grasping 绑定。

这些工作的共同提醒是：

```text
透明物体深度的核心矛盾不是缺一个更大网络，
而是同一个像素下，“图像可见的纹理深度”、“透明前表面深度”、
“多层光学结构”和“下游任务需要的单层深度”不是同一个目标。
```

因此 v3 推荐把主 idea 收成：

> **Layer-Aware ToM Depth studies how monocular depth models should preserve multiple transparent-surface depth hypotheses and collapse them into the right task-specific depth target only at readout time.**

中文版本：

> Layer-Aware ToM Depth 研究的是透明/镜面单目深度中的“目标语义桥接”：模型先保留前表面、透射/背景层、传统单层输出和可信度等多种 depth hypotheses，再根据 benchmark 或下游任务选择应该读出哪一种 depth，而不是一开始就把透明 depth 压成一个标量。

一句话收紧：

```text
visible depth cue != physical front surface != multi-layer geometry != task depth target
```

## 2. 推荐 Scope：借他们的代码和 benchmark，但只打一个中心问题

### 2.1 不推荐的 Scope

不建议主论文声称：

```text
我们统一解决透明物体单目深度、RGB-D completion、多层透明重建、
机器人抓取、可靠性、生成式 opacification 和 sparse metric alignment。
```

这个 scope 会触发三类 reviewer 风险：

1. **像拼装**：每个部件都能在现有工作里找到强近邻。
2. **证据发散**：Depth4ToM、LayeredDepth、SeeGroup、MODEST、ReMake、MDA、Booster、TransCG 全都要完整跑，任何一个薄弱都会被抓。
3. **贡献边界不清**：到底是新 MDE、协议桥接、多层深度、机器人 depth correction，还是 uncertainty / reliability。

也不建议把标题写成：

```text
Transparent Object Depth Estimation for Robotics
```

这个标题会自动把我们拉进 ClearGrasp、TransCG、DREDS、ReMake、MOMA、AISPO、ASGrasp 的机器人系统战场，第一阶段证据不够。

### 2.2 推荐的主 Scope

推荐主 scope：

```text
Layer-Aware ToM Depth bridges single-depth transparent/mirror MDE benchmarks
and multi-layer transparent depth benchmarks through task-conditioned depth
hypothesis readout.
```

中文版本：

> 本文不主张重新定义全部透明物体感知，而是解决一个更窄的问题：如何在单图 MDE 中同时保留透明/镜面区域的多种 depth hypotheses，并在 Booster / Depth4ToM 这类 single-depth metric 协议和 LayeredDepth / SeeGroup 这类 multi-layer 协议之间做可复现桥接。

这个 scope 借鉴几类工作，但不被任何一篇完全覆盖：

| 借鉴对象 | 借什么 | 不借什么 |
|---|---|---|
| Depth4ToM | ToM front-surface single-depth target、Booster 评测、官方权重/脚本 | 不把工作写成另一个 inpainting + fine-tuning |
| LayeredDepth | 多层透明 depth 定义、tuple eval、synthetic supervision | 不把 real tuple 当 metric GT，不主张完整光学重建 |
| SeeGroup | multi-layer teacher、permutation-invariant grouping、强 baseline | 不把“多层/多假设”本身当主创新 |
| MDA | mixture / multi-hypothesis head 参考 | 不把 mixture-density 作为唯一贡献 |
| MODEST / ReMake | mask 与 depth 的直接威胁、机器人补全 baseline | 不把主线变成 mask-guided RGB-D completion |
| Booster / NTIRE | metric ToM protocol 和 material mask | 不只刷全图指标 |

P0 主论文只覆盖三件事：

1. **Target semantics**：透明/镜面区域的 depth target 拆成 `front / through / single / invalid-or-uncertain`。
2. **Cross-protocol bridge**：同一模型能同时服务 Booster / Depth4ToM single-depth 和 LayeredDepth multi-layer eval。
3. **Task-conditioned readout**：模型不是永远输出某个固定层，而是通过 selector / confidence 决定当前任务需要哪种 depth。

### 2.3 放到 Appendix / Future Work 的 Scope

以下内容不要放进主 claim：

- RGB-D depth completion 全量超越 ClearGrasp / LIDF / TransCG / ReMake。
- 真实机器人 grasp success。
- 生成式 opacification 训练。
- active stereo / multiview / NeRF 系统比较。
- MOMA 式 sparse metric alignment 的完整机器人复现。
- 新数据集或新 benchmark。
- 完整多层透明光学重建。

可以作为扩展讨论：

```text
The proposed DepthHypothesisPack can also support RGB-D completion,
robotic contact-depth readout, and sparse metric anchoring, but this paper
evaluates the core bridge between single-depth ToM and multi-layer depth protocols.
```

## 3. 优化后的 Idea Card

### 标题

推荐：

**Bridging Single-Depth and Multi-Layer Depth for Transparent and Mirror Surfaces**

备选：

- **Layer-Aware Monocular Depth Estimation for Transparent and Mirror Surfaces**
- **Which Depth Should Transparent Objects Have? Task-Conditioned Depth Readout for ToM Surfaces**
- **DepthHypothesisPack: Preserving and Selecting Transparent Surface Depths**

不推荐：

- `Transparent Object Depth Estimation for Robotics`
- `Robust Transparent Object Depth Completion`
- `Multi-Hypothesis Depth for Transparent Objects`

这些标题要么太机器人，要么被 ReMake / MDA / SeeGroup 压住。

### Task

给定单张 RGB 图像，模型需要在透明/镜面区域输出一组语义可解释的 depth hypotheses，并根据任务读出传统 single-depth 或 multi-layer prediction：

```text
image I
  -> DepthHypothesisPack {
       D_front,
       D_through,
       D_single,
       C_layer,
       P_task / selector
     }
```

### Gap

现有工作分别解决了问题的一部分：

- Depth4ToM 强化了 ToM single-depth，但仍把透明区域压成一个目标。
- LayeredDepth / SeeGroup 强调多层透明结构，但没有直接解决传统 MDE benchmark 的 single-depth readout。
- MDA 给了多假设表示，但它的核心不围绕 ToM target semantics 和 cross-protocol bridge。
- MODEST / ReMake 用 mask / RGB-D completion 面向透明物体，但不解释 single-depth 与 multi-layer 任务之间的语义差异。

缺口不是“还没人做透明深度”，而是：

```text
single-depth ToM protocol and multi-layer transparent protocol
currently speak different target languages.
```

### Root Challenge

透明/镜面像素下可能同时存在四种互相冲突的 depth 语义：

| 语义 | 例子 | 对应任务 |
|---|---|---|
| `D_front` | 杯子前表面、玻璃门前表面 | Booster / Depth4ToM single-depth、机器人 contact depth |
| `D_through` | 透过玻璃看到的背景 | LayeredDepth multi-layer、视觉解释 |
| `D_reflect` | 镜面中反射物体的 apparent cue | failure / reliability，不应直接当真实 ray depth |
| `D_single` | 传统 MDE 需要的一张 depth map | 常规 benchmark / downstream API |

如果训练时只给一个 depth map，模型会在这些目标之间学到不稳定平均解，尤其在边界、强折射、薄透明物体、背景纹理穿透处失败。

### Core Insight

> Transparent depth should be represented as hypotheses first and collapsed into a task-specific scalar only at readout time.

三个层级必须分开：

```text
Visual evidence: RGB appearance, mask, MDE prior, layer teacher
Depth hypotheses: front, through, single, ambiguous/invalid
Task readout: Booster single-depth, LayeredDepth multi-layer, robot contact depth
```

### Proposed Mechanism

主机制不是“更大 backbone”，而是一个 layer-aware readout layer：

```text
Host MDE backbone
  -> Layer Hypothesis Head
  -> Target-Semantic Assignment
  -> Confidence / Ambiguity Estimator
  -> DepthHypothesisPack
  -> Task-Specific Readout Adapter
```

DepthHypothesisPack 是中心对象：

```text
DepthHypothesisPack {
  D_front: closest physical surface,
  D_through: transmitted/background or later transparent layer,
  D_single: selected task depth,
  C_layer: ambiguity / reliability map,
  selector: front | through | normal | invalid,
  support: teacher/source metadata
}
```

### Contribution Type

主贡献收成三项：

1. **Problem / framing**：形式化透明/镜面 MDE 的 depth target semantics 问题，区分 visual cue、physical front surface、multi-layer geometry 和 task readout。
2. **Method**：提出 DepthHypothesisPack 和 layer-aware readout，让单图模型同时输出 `D_front/D_through/D_single/C_layer`。
3. **Protocol bridge**：在 Booster / Depth4ToM single-depth metric 与 LayeredDepth multi-layer tuple 上同时评估，证明不是只在单一协议刷分。

不要把“新数据集”“新机器人系统”“新多峰表示”写成主贡献。

## 4. 学他们怎么“编”：本 topic 应该这样搭框架

### 4.1 按 Depth4ToM 的方式编：先抓目标定义，而不是网络结构

Depth4ToM 的成熟之处是它没有泛泛说透明物体难，而是明确：

```text
ToM surface depth should be the closest/front surface depth.
```

我们要继承这个编法，但往前推进一步：

```text
Depth4ToM defines the single-depth target.
We define how that target coexists with multi-layer targets and how it is selected.
```

所以论文第一节不要从“透明物体很难抓”开始，而要从 target ambiguity 开始：

```text
The same transparent pixel may require different depth targets under different protocols.
```

### 4.2 按 LayeredDepth / SeeGroup 的方式编：让 benchmark 定义问题边界

LayeredDepth 的核心贡献是协议，不是工程技巧。SeeGroup 的贡献也围绕 LayeredDepth 的 multi-layer evaluation 展开。

我们要借这个边界：

```text
LayeredDepth tells us transparent surfaces are multi-layer.
Booster tells us downstream MDE benchmarks still require one metric depth map.
Our question is how to bridge them without losing target semantics.
```

这样能避免 reviewer 说“你只是把 Depth4ToM 和 SeeGroup 串起来”。我们不是串联两个模型，而是把两个 benchmark 的 target language 统一到一个 readout 框架里。

### 4.3 按 MDA 的方式编：承认多假设不是 novelty

MDA 已经把 multi-hypothesis / mixture-depth 做成强威胁。我们的写法必须避开：

```text
We propose multi-hypothesis depth.
```

改成：

```text
We propose semantically assigned depth hypotheses for transparent/mirror target readout.
```

也就是说，`D_front` 和 `D_through` 不是匿名 mixture components，而是可评测、可读出、可对应到 benchmark 的语义目标。

### 4.4 按 ReMake / MODEST 的方式编：把 mask 成本讲清

MODEST 和 ReMake 会攻击任何依赖 mask 的方法：

- 如果用 GT mask，系统不公平。
- 如果用 predicted mask，mask error 和模型成本必须计入。
- 如果用 mask + RGB-D raw depth，那就不是严格单目。

因此主论文应默认：

```text
mask is optional / proxy input, not a hidden oracle.
```

实验必须有：

| 消融 | 目的 |
|---|---|
| GT mask | 上界 |
| proxy / predicted mask | 实际设定 |
| noisy mask | 鲁棒性 |
| no mask | 证明不是完全靠 mask |

### 4.5 按 Booster 的方式编：metric 和 affine 必须分开

透明/镜面区域很容易用 scale-shift 对齐掩盖问题。主表必须分开：

```text
metric depth: real deployment / NTIRE 2026 mono metric
affine-aligned depth: shape quality / relative structure
```

如果只报 affine，不能支撑机器人或 metric-depth claim。

### 4.6 按 MOMA / A2 的方式编：后处理 baseline 必须强

如果把本文接到 A2 / sparse metric anchoring，必须承认 MOMA 和 AnchorD-style patch affine 的压力。

A2 相关 claim 只能放成附录或 second-stage：

```text
DepthHypothesisPack may improve sparse metric anchoring because anchors can be applied
to D_front rather than a mixed transparent depth map.
```

但主论文第一阶段不要声称采样期 anchoring 优于所有后处理，除非真的跑了 MOMA-style / patch-affine 对照。

## 5. v3 方法框架：从“模型堆叠”改成“depth target 编译器”

推荐用“编译器”隐喻组织方法：

```text
Raw visual evidence is not directly a depth target.
Layer-Aware ToM compiles visual evidence into a task-conditioned DepthHypothesisPack.
```

### 5.1 输入输出

输入：

```text
image I:
  RGB image

optional observations:
  ToM mask / proxy mask
  base MDE prediction
  multi-layer teacher prediction
  sparse metric anchors, only in A2 extension
```

输出：

```text
DepthHypothesisPack H:
  D_front
  D_through
  D_single
  C_layer
  selector / P_task
  support metadata
```

评测读出：

```text
Booster / Depth4ToM:
  read D_single or D_front as metric single-depth

LayeredDepth:
  read D_front + D_through + optional extra layers

Reliability:
  read C_layer and selector uncertainty

A2 / robot extension:
  read D_front / contact-depth only
```

### 5.2 四个阶段

#### Stage 1: Backbone Evidence Extraction

先复用已有 backbone，不从零训练：

```text
RGB image
  -> Depth4ToM / DPT / Depth Anything / Metric3D features
  -> base single-depth prior
```

借鉴：

- Depth4ToM 的 ToM single-depth prior。
- Depth Anything / Metric3D 的 robust general depth prior。
- Diffusion4RobustDepth 的 non-Lambertian robust baseline。

#### Stage 2: Layer Hypothesis Construction

生成多个候选 depth：

```text
features
  -> D_front head
  -> D_through head
  -> optional K components
  -> C_layer ambiguity map
```

借鉴：

- LayeredDepth-Syn 的多层监督。
- SeeGroup 的 teacher candidates。
- MDA 的 component / mixture 思路。

#### Stage 3: Target-Semantic Assignment

把候选 depth 映射成语义目标，而不是保持匿名 component：

```text
candidate depth components
  -> front / through / normal / invalid assignment
  -> semantic consistency losses
```

这是本文的关键非平凡点。它和 MDA / SeeGroup 的区别在于：我们的 readout 目标直接对应 Booster / LayeredDepth / robot contact 的任务语义。

#### Stage 4: Task-Specific Readout

根据任务读出：

```text
if benchmark == Booster:
    D_single = selector(front for ToM, normal for opaque)

if benchmark == LayeredDepth:
    output [D_front, D_through, ...]

if task == reliability:
    output C_layer and abstention

if task == robot_contact:
    output D_front only
```

借鉴：

- Booster 的 ToM / Other split。
- LayeredDepth 的 layer_first / layer_all。
- Transparent Depth Reliability 的 risk-coverage。

### 5.3 为什么不是简单拼装

非显然交互是：

```text
multi-layer supervision tells the model what alternatives exist,
single-depth ToM supervision tells which alternative conventional MDE needs,
and task-conditioned readout prevents the model from averaging incompatible targets.
```

如果只做其中一个：

- 只有 Depth4ToM：仍是单一 depth，解释不了多层歧义。
- 只有 LayeredDepth / SeeGroup：不能直接回到 Booster / MDE single-depth metric。
- 只有 MDA：多假设是匿名的，不保证 front / through 可解释。
- 只有 confidence：只是诊断，不能解决 target readout。
- 只有 ReMake / MODEST：更像透明物体专用系统，不是 single-depth / multi-layer bridge。

## 6. 最小主论文实验应该怎么收

### 6.1 主表只保留三条

主论文不要平均铺开所有透明工作。建议主表：

| 主表 | 借来的框架 | 证明什么 |
|---|---|---|
| Table 1: ToM single-depth | Depth4ToM / Booster | `D_single/D_front` 在传统 metric ToM 协议有效 |
| Table 2: Multi-layer depth | LayeredDepth / SeeGroup | `D_front/D_through` 保留多层语义，不只是刷 single-depth |
| Table 3: Readout / reliability | Booster + LayeredDepth cross-eval | selector / `C_layer` 解释 target ambiguity，支持 selective prediction |

TransCG / ReMake / MOMA-style 可以作为 Appendix 或 A2 extension：

```text
application slice evidence, not main bridge evidence
```

### 6.2 当前结果对 scope 的反馈

按本仓库当前状态：

| 方向 | 当前成熟度 | 对 v3 scope 的影响 |
|---|---|---|
| TransCG / DFNet | 官方代码、checkpoint、合成 smoke 已跑通；真实 test 待跑 | 可作为 P1 robot failure slice，不支撑主论文 single-depth bridge |
| ReMake | 官方代码、checkpoint、主网络 smoke 已跑通；完整 Depth Anything 链路待补 | 可作为强 baseline，但不要让主线变成 RGB-D completion |
| Depth4ToM | 已调研为 P0，但本地尚未克隆 / 复现 | 必须第一优先补，否则 Booster 主表没有根 |
| LayeredDepth | 已调研为 P0，但本地尚未跑 eval | 必须第一优先补，否则 multi-layer claim 没根 |
| SeeGroup | 已调研为 P0 teacher，但本地尚未跑 checkpoint | 必须补 teacher cache，否则 layer-aware 训练靠空想 |
| MDA / MODEST | 强 baseline，尚未本地接入 | P1，不应阻塞第一版 gap diagnostic |

因此当前主 claim 应写成计划/设计口径：

```text
We propose a layer-aware target bridge and identify a borrowed-backbone evaluation plan.
```

只有跑完 Depth4ToM / LayeredDepth / SeeGroup 的 P0 复现后，才能升级成：

```text
We demonstrate that semantic layer-aware readout improves both ToM single-depth
and multi-layer transparent depth evaluation.
```

### 6.3 关键 ablation 名称要跟框架一致

不要用太多工程模块名。用贴合中心对象的 ablation：

| Variant | 含义 |
|---|---|
| `SingleDepth` | 普通 single-head depth baseline |
| `LA-NoSemantic` | 多 head，但不分 front / through / single 语义 |
| `LA-NoTeacher` | 不用 SeeGroup / LayeredDepth teacher |
| `LA-NoSelector` | 直接取 first head 或平均，不做 task readout |
| `LA-NoConfidence` | 不预测 `C_layer`，无法 selective / abstention |
| `LA-NoFrontSupervision` | 不用 Depth4ToM / Booster front target |
| `LA-Full` | DepthHypothesisPack + semantic heads + selector + confidence |

这些名字比 `w/o module X` 更容易让读者看到机制闭环。

## 7. 论文图应该怎么画

### Figure 1: 原框架的问题

画一个透明杯子像素射线：

```text
camera ray
  -> front glass surface: D_front
  -> back surface / transmitted background: D_through
  -> reflected / refracted visual cue: D_reflect
```

旁边放两个 benchmark：

```text
Booster / Depth4ToM asks for one front-surface metric depth.
LayeredDepth asks for multi-layer ordering.
```

红色标注：

```text
single scalar supervision mixes incompatible depth targets.
```

### Figure 2: DepthHypothesisPack 框架

```text
RGB image
  -> borrowed MDE backbone
  -> Layer Hypothesis Head
  -> Target-Semantic Assignment
  -> DepthHypothesisPack
        D_front
        D_through
        D_single
        C_layer
        selector
  -> Task Readout Adapters
        Booster single-depth
        LayeredDepth multi-layer
        reliability / selective prediction
```

这张图讲“我们的中心对象是什么”。

### Figure 3: 借来的 host frameworks

三列：

```text
Depth4ToM / Booster:
  image + ToM mask -> D_single metric eval

LayeredDepth / SeeGroup:
  image -> multi-layer teacher / tuple eval

MDA / MODEST / ReMake:
  threats and auxiliary baselines
```

这张图讲“我们不是自造 runner，而是统一插在不同 I/O 边”。

## 8. 文章叙事建议

### Abstract 的编法

不要写：

```text
We propose a new transparent object depth estimation network with multi-layer
prediction, reliability, masks, and robot grasping.
```

建议写：

```text
Transparent and mirror surfaces expose a target ambiguity in monocular depth:
the visible image evidence, the closest physical surface, the transmitted
background, and the depth required by downstream benchmarks are often different.
Existing ToM depth methods optimize a single front-surface target, while recent
multi-layer benchmarks reveal that transparent rays contain multiple valid depth
hypotheses. We introduce Layer-Aware ToM Depth, a borrowed-backbone framework
that preserves semantically assigned depth hypotheses and collapses them into
task-specific readouts only at evaluation time. The central representation,
DepthHypothesisPack, contains front-surface, transmitted/background, single-depth
and ambiguity estimates. We evaluate it by bridging existing ToM single-depth
and multi-layer transparent depth protocols rather than introducing a new dataset...
```

### Introduction 的 5 段

1. Transparent / mirror surfaces break the single-depth assumption in MDE。
2. Existing ToM work defines a useful single-depth target, but multi-layer work shows that this target is incomplete。
3. The gap is not another network, but target semantics and readout。
4. Key insight：preserve hypotheses first, collapse by task later。
5. Our framework：DepthHypothesisPack + borrowed benchmark evaluation。

### Contributions 的编法

建议三项：

1. We formulate depth target semantics for transparent and mirror monocular depth, distinguishing front-surface, transmitted/background, single-depth and ambiguous targets.
2. We introduce DepthHypothesisPack, a layer-aware representation and readout mechanism that preserves multiple transparent depth hypotheses and selects task-specific outputs.
3. We evaluate the bridge on borrowed protocols: Booster / Depth4ToM for metric single-depth, LayeredDepth / SeeGroup for multi-layer depth, and reliability diagnostics for ambiguous regions.

不要写五六个贡献，不要把 mask、confidence、teacher、adapter 各写成一个贡献。

## 9. 对现有文档 / 计划的改法

当前仓库里已经有这些雏形：

- `layer_aware_tom_depth_plan.md`
- `方法骨架与代码IO调研.md`
- `summary-zh.md`
- `idea_cards.md`
- `透明物体_TransCG与ReMake代码数据解读.md`
- `复现/TransCG_DFNet.md`
- `复现/ReMake.md`

建议概念映射如下：

| 现有概念 | v3 论文概念 |
|---|---|
| `Layer-Aware ToM Depth` | 主 idea 名称 |
| `D_front / D_transmitted / D_single / C_layer` | `DepthHypothesisPack` 字段 |
| `Depth4ToM + LayeredDepth + SeeGroup` | borrowed P0 host frameworks |
| `Transparent Depth Reliability` | `C_layer` / selective readout 辅助贡献 |
| `Dual-Target Transparent MDE` | target semantics 的理论解释 |
| `TransCG / ReMake` | A2 / robot extension，不是主线核心 |
| `MOMA-style SRS / patch affine` | A2 后处理对照 |

如果继续开发，优先补三个缺口：

1. 新建统一 `ImageDepthSample` / `DepthPrediction` / `EvalResult` adapter，按 `方法骨架与代码IO调研.md` 的接口执行。
2. 克隆并跑通 `Depth4ToM`、`LayeredDepth`、`SeeGroup`，因为它们是 v3 主 scope 的三根柱子。
3. 第一版模型只做 V1 ordered / semantic heads，先验证 gap，不要直接上复杂 point-process 或 robot pipeline。

## 10. 最终成熟版本应该长什么样

成熟的论文不是“透明物体模块很多”，而是读者能用一句话复述：

> Layer-Aware ToM Depth keeps transparent depth as semantically assigned hypotheses and only reads out the depth target required by the task.

成熟的 scope 是：

```text
We study which depth target a transparent pixel should output.
We do not propose a new transparent-object dataset.
We do not claim to solve all RGB-D completion or robotic grasping.
We bridge single-depth ToM and multi-layer transparent depth using borrowed
backbones and benchmarks.
```

成熟的实验是：

```text
每个主实验都回答一个 target-semantics 问题：

Booster / Depth4ToM:
  读出的 D_single / D_front 是否满足传统 metric ToM?

LayeredDepth / SeeGroup:
  保留的 D_front / D_through 是否满足多层关系?

Reliability / selector:
  模型是否知道什么时候 single-depth 读出不可靠?
```

成熟的图是：

```text
透明像素为什么不是一个 depth -> DepthHypothesisPack 如何保留多目标 ->
不同 benchmark 如何读出不同目标 -> 指标如何验证 readout 正确。
```

## 11. 当前最该收紧的一句话

旧版：

```text
我们做面向透明物体的鲁棒单目深度估计。
```

新版：

```text
Layer-Aware ToM Depth is a borrowed-backbone framework that preserves transparent
surface depth hypotheses and performs task-conditioned depth readout across
single-depth and multi-layer protocols.
```

中文：

> Layer-Aware ToM Depth 不是再做一个透明深度网络，而是在已有 MDE backbone 和公开 benchmark 上加一层“深度目标语义桥接”：透明/镜面像素可以同时保留前表面、透射层、传统单层和可信度，只有到具体评测或任务读出时，才选择应该输出哪一种 depth。

这个版本更像 Depth4ToM、LayeredDepth、SeeGroup 那类论文的“编法”：先借成熟框架，再抓一个中间抽象，最后让实验指标围绕这个抽象闭环。
