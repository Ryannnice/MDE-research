# Layer-Aware ToM Idea v4：面向机器人抓取的贡献重构

日期: 2026-07-11

本文基于 `Layer-Aware-ToM-Idea-v3-框架与Scope优化.md`、`透明物体单目深度估计用于机器人.md`、`方法骨架与代码IO调研.md`、`透明物体_TransCG与ReMake代码数据解读.md` 以及当前 TransCG / ReMake smoke test 记录，专门重构一个问题：

> 如果这次论文要贡献于机器人抓取领域，而不是主要贡献于透明/镜面 MDE benchmark bridge，那么 Layer-Aware ToM idea 应该如何重新收紧、命名、设计方法和组织实验？

当前判断：v3 的核心洞察仍然有价值，但主线必须从“跨 single-depth / multi-layer benchmark 的 depth target 语义桥接”改成“机器人动作到底应该消费哪一种透明深度，以及如何把它可靠读出”。机器人抓取不是 v3 的 appendix，而是 v4 的主任务。

## 0. 一句话版本

透明物体抓取需要的不是一张视觉上合理的深度图，而是可执行的接触面深度、碰撞包络和风险估计；我们把透明像素保留为多种语义深度假设，再根据抓取动作读出 `D_contact` 和 `D_envelope`，避免机器人把透射背景或平均深度当成可接触表面。

更短版本：

```text
Transparent grasping should consume contact geometry, not a visually plausible
single depth map. Preserve layer hypotheses first, read out action-conditioned
contact depth only when planning a grasp.
```

推荐中文讲法：

```text
透明物体抓取的关键不是让深度图看起来更完整，
而是把前表面、透射背景和无效传感器深度分开，
再为吸取、夹取和碰撞检测读出正确的接触几何。
```

## 1. 从 v3 到 v4 的核心转向

v3 的中心问题是：

```text
透明/镜面像素在不同 benchmark 中应该输出哪一种 depth target?
```

v4 的中心问题是：

```text
透明物体抓取中，机器人应把哪一层几何当作接触面、占据边界和风险源?
```

这个转向会改变论文的四个边界：

| 维度 | v3 视觉桥接口径 | v4 机器人抓取口径 |
|---|---|---|
| 主任务 | single-depth 与 multi-layer depth 协议桥接 | 透明物体 grasp-relevant depth correction / readout |
| 主输出 | `D_front`, `D_through`, `D_single`, `C_layer` | `D_contact`, `D_through`, `D_envelope`, `N_contact`, `C_grasp` |
| 主证据 | Booster / Depth4ToM / LayeredDepth / SeeGroup | TransCG / ClearPose / ReMake / MOMA-style alignment / grasp proxy |
| 主贡献 | target semantics bridge | action-conditioned contact geometry readout |

因此 v4 不应继续说：

```text
机器人抓取只是 A2 extension / appendix slice.
```

应改成：

```text
Layer-aware target semantics is the perception mechanism, transparent object
grasping is the task where the mechanism becomes necessary and measurable.
```

## 2. 推荐标题和定位

首选标题：

**ContactDepthPack: Grasp-Conditioned Depth Readout for Transparent Object Manipulation**

中文：

**ContactDepthPack：面向透明物体操作的抓取条件化深度读出**

备选标题：

- **Grasp-Aware Layered Depth Readout for Transparent Object Grasping**
- **Which Transparent Depth Should a Robot Grasp? Contact-Aware Readout from Layered Depth Hypotheses**
- **From Transparent Depth Hypotheses to Robot Contact Geometry**

不推荐标题：

- `Transparent Object Depth Completion for Robotics`
- `Layer-Aware Monocular Depth Estimation for Transparent Objects`
- `Transparent Object Grasping with Monocular Depth`

原因：

1. 第一个会被 ClearGrasp / LIDF / TransCG / ReMake / DREDS 拉进传统 RGB-D completion 横比。
2. 第二个仍是 v3 视觉任务，不能体现抓取贡献。
3. 第三个会被 MOMA / MODEST / SeeClear 压住，而且单 RGB 的 metric/contact depth 难度和证据成本更高。

最稳定位：

```text
本文不是提出又一个透明物体 depth completion network，
而是提出一个抓取条件化的透明深度读出框架：
模型先保留 front / through / invalid 等层语义假设，
再根据 suction、parallel-jaw grasp 和 collision checking 读出 contact depth、
occupied envelope 和 grasp risk。
```

## 3. Target Venue 和审稿口径假设

目标领域：机器人抓取 / 机器人感知 / 透明物体 manipulation。

优先 venue 口径：

- ICRA / IROS / CoRL / RA-L：强调机器人任务闭环、可复现系统、grasp-relevant metrics、真实或强 proxy 证据。
- 若转回 CVPR / ICCV / ECCV：必须把主贡献改回视觉机制和 benchmark protocol，真实抓取只能作为应用验证。

当前本文按机器人 venue 组织，不按纯 CCF-A 视觉口径组织。由于仓库尚未有真实机器人 CSV 或 robot log，所有真实抓取成功率只能写成 `待跑`；第一版可主打离线 grasp proxy + 透明 mask metric + 复现 baseline，不能提前声称“提高真实抓取成功率”。

## 4. Optimized Idea Card

### Task

给定机器人单视角观测，预测透明物体的可抓取接触几何，而不是只预测一张普通 depth map。

推荐主输入设定：

```text
RGB image
raw depth from commodity RGB-D sensor
optional: transparent / instance mask
optional: monocular relative depth
optional: sparse metric anchors
```

推荐主输出：

```text
ContactDepthPack {
  D_contact: 机器人可接触的前表面 / 最近物理表面深度,
  D_through: 透射背景或后层深度,
  D_envelope: 保守占据 / 碰撞包络深度,
  N_contact: 接触面法向或局部几何,
  C_grasp: 抓取风险 / 深度可信度,
  selector: contact | through | invalid | unknown,
  action_readout: suction | parallel_jaw | collision_check
}
```

### Gap

现有透明物体机器人深度工作大多输出一张 completed depth：

- ClearGrasp / LIDF / TransCG / TODE / FDCT / DREDS：修复 RGB-D 深度，但主目标仍是一张 metric depth map。
- ReMake：把 MDE relative depth 和 instance mask 加进 RGB-D completion，强相关，但仍主要输出 completed metric depth。
- MOMA：用 one-shot sparse metric alignment 把单目相对深度对齐到机器人场景，强威胁，但它对齐的是单一深度输出。
- MODEST / SeeClear：从单 RGB 或 opacification 路线改善透明深度，但不直接区分机器人接触面、透射背景和碰撞包络。
- LayeredDepth / SeeGroup：说明透明像素多层，但不回答机器人应抓哪一层、何时拒绝抓取。

缺口不是“还没有透明物体抓取深度方法”，而是：

```text
现有方法常把透明像素压成一张 completed depth，
但机器人抓取需要的是 action-conditioned contact geometry:
哪一层可接触，哪一层是背景，哪一区域应被视为碰撞风险或不可信。
```

### Root Challenge

透明物体抓取中的 depth ambiguity 比普通 MDE 更危险，因为错误深度会直接改变接触点和碰撞判断。

| 深度语义 | 传感器/视觉表现 | 抓取后果 |
|---|---|---|
| `D_contact` | 透明杯前壁、玻璃容器外表面、吸盘接触面 | 正确生成点云、法向、吸取点或夹取接触点 |
| `D_through` | 透过物体看到的背景或后层结构 | 若误当接触面，夹爪/吸盘会穿过目标或碰撞 |
| `D_invalid` | RealSense / ToF 空洞、0 值、飞点 | 点云破洞，候选抓取缺失或法向不稳 |
| `D_average` | single-head 网络在多目标监督下学到的平均解 | 表面位置偏移，碰撞包络错误 |
| `D_envelope` | 对物体占据范围的保守估计 | 用于避免碰撞和拒绝高风险抓取 |

机器人任务不能只问 “depth RMSE 是否下降”，还要问：

```text
这个 depth 是否让接触点落在真实前表面附近？
这个 depth 是否避免把背景当作透明物体表面？
这个 depth 是否能在不确定区域拒绝高风险 grasp？
```

### Core Insight

> Transparent grasping should read contact geometry from semantically assigned depth hypotheses, not from a single completed depth map.

三层概念必须分开：

```text
Visual / sensor evidence:
  RGB, raw depth, invalid-depth mask, MDE relative depth, object mask

Layer hypotheses:
  front/contact surface, transmitted/background layer, invalid/noisy raw depth

Robot readout:
  suction contact patch, parallel-jaw contact pair, collision envelope, reject/abstain
```

### Proposed Mechanism

主机制是 `ContactDepthPack`，它继承 v3 的 `DepthHypothesisPack`，但把 readout 从 benchmark-conditioned 改为 grasp-conditioned。

```text
RGB + raw depth + optional mask / relative depth
  -> Evidence Encoder
  -> Layer Hypothesis Head
  -> Contact-Semantic Assignment
  -> ContactDepthPack
  -> Grasp-Conditioned Readout Adapter
  -> fixed grasp planner / grasp proxy
```

非显然点是：多层语义不是为了“多输出几张 depth”，而是为了避免机器人把错误层当作可接触表面。

## 5. 方法蓝图

### Stage 1: Robot Evidence Encoding

输入不应只设成单 RGB。机器人抓取最需要 metric/contact geometry，因此主设定建议是 low-cost RGB-D + optional MDE prior：

```text
RGB
raw_depth
raw_valid_mask
optional transparent/instance mask
optional relative_depth from Depth Anything / LeReS / Depth4ToM / MODEST
```

设计原则：

- `raw_depth` 提供米制尺度，但透明区域常空洞或读到背景。
- `relative_depth` 提供形状连续性，但尺度可能不可靠。
- `mask` 可提高透明区域定位，但必须计入成本并做 GT / predicted / noisy / no-mask 消融。
- `LayeredDepth / SeeGroup` 可作为层语义 teacher，不作为机器人主 benchmark。

### Stage 2: Layer Hypothesis Construction

预测或缓存多个候选：

```text
D_raw_valid: 传感器可信深度区域
D_contact_candidate: 前表面候选
D_through_candidate: 背景 / 后层候选
D_completion_candidate: 普通 completed depth
C_raw_failure: raw depth 是否空洞 / 背景错深 / 飞点
```

监督来源：

| 来源 | 用途 | 注意 |
|---|---|---|
| TransCG / ClearPose GT depth | metric contact/front depth 主监督 | 要确认 GT depth 与机器人接触面的定义 |
| raw depth + mask | 生成 invalid / background-read failure 标签 | 不把 raw depth 当真值 |
| Depth4ToM / Booster | front-surface ToM 语义参考 | 非机器人数据，只作辅助 |
| LayeredDepth / SeeGroup | through / multi-layer ambiguity teacher | 不把 tuple 分数当抓取成功证据 |
| ReMake / DFNet output | baseline 或 pseudo candidate | 不应把它们的输出当无条件 GT |

### Stage 3: Contact-Semantic Assignment

把 depth components 赋予机器人语义：

```text
candidate components
  -> contact/front
  -> through/background
  -> raw-invalid/noisy
  -> unknown/abstain
```

这一步是 v4 的关键。区别于 MDA / SeeGroup 的匿名多假设，也区别于 ReMake 的单图补全：

```text
每个候选 depth 必须能解释为机器人会不会碰到的几何层。
```

建议损失：

- `L_contact`: contact/front depth 的 metric loss，在透明 mask 和接触候选区域加权。
- `L_through`: through/background 与 contact 的排序或 separation loss。
- `L_envelope`: 保守占据边界不应落在背景深度之后。
- `L_conf`: 高误差 / raw failure / multi-layer ambiguity 区域的 risk calibration。
- `L_readout`: 固定 grasp planner 下的 contact patch / collision proxy consistency。

### Stage 4: Grasp-Conditioned Readout

不同抓取动作需要不同 readout：

```text
if action == suction:
    use D_contact + N_contact + local planarity + C_grasp

if action == parallel_jaw:
    use D_contact + object boundary + collision envelope + contact-pair consistency

if action == collision_check:
    use D_envelope, not D_through

if C_grasp is low:
    abstain or route to active sensing / stronger method
```

输出不应只是 `depth.png`，而应是可被 grasp planner 消费的结构：

```text
ContactDepthPack -> point cloud from D_contact
                 -> conservative occupancy from D_envelope
                 -> risk map from C_grasp
                 -> fixed planner proposes grasps
```

### Stage 5: Sparse Metric Anchoring as Baseline and Optional Module

MOMA-style sparse metric alignment 是最危险近邻，不能放在相关工作里轻描淡写。v4 必须把它纳入实验：

```text
single depth + global affine
single depth + patch affine
single depth + MOMA-style SRS / sparse metric anchors
ContactDepthPack + semantic contact readout + same anchors
```

如果加入 sparse anchors，主张应写成：

```text
Anchors are more useful when applied to the contact-surface hypothesis than
to a mixed transparent depth map.
```

不要提前写成：

```text
我们优于 MOMA.
```

除非已经在同一输入、同一 anchor、同一 grasp proxy 或真实抓取协议下跑完。

## 6. 贡献重写

推荐三项贡献：

1. **Problem / setting**  
   形式化透明物体抓取中的 depth target ambiguity：机器人需要的是 contact depth、collision envelope 和 risk，而不是单一视觉 depth。

2. **Method / representation**  
   提出 `ContactDepthPack`，把透明区域的 front/contact、through/background、invalid/noisy 和 confidence 分开，并根据 suction / parallel-jaw / collision checking 做 grasp-conditioned readout。

3. **Evaluation / evidence protocol**  
   建立可复现的透明物体 grasp-relevant depth 评测：在 TransCG / ClearPose / ReMake-compatible pipeline 上同时报告 metric depth、transparent-mask depth、contact/front proxy、collision / invalid grasp proxy、risk-coverage，并与 DFNet、ReMake、MOMA-style alignment 等同输入 baseline 比较。

不要把以下内容写成主贡献：

- 新透明物体数据集。
- 完整多层透明光学重建。
- 超越 active stereo / NeRF / 3DGS / multiview 系统。
- 真实机器人 grasp success 提升，除非已有真实机器人日志。
- 单纯多假设 depth head。

## 7. 与强近邻的切分

| 近邻 | 它已经做了什么 | v4 必须切开的点 |
|---|---|---|
| TransCG / DFNet | RGB-D 透明 depth completion + grasp baseline | 我们不是只补全 depth，而是显式区分 contact / through / invalid 并验证 grasp-relevant readout |
| ReMake | RGB + raw depth + MDE relative depth + mask 融合，直接面向透明抓取 | 我们要证明 ReMake-style single completed depth 会混淆层语义；或在同输入下提升 contact / risk / grasp proxy |
| MOMA | 单 RGB + sparse metric alignment 用于机器人抓取 | 我们要用同样 anchors 对比：锚定 mixed depth vs 锚定 contact hypothesis |
| MODEST | 单 RGB 透明 segmentation + depth | 若用 mask，必须计入 mask 成本；若不用 raw depth，要面对 MODEST 的单 RGB 直接威胁 |
| SeeClear | opacification + MDE | 我们不主张把透明变不透明，而是保留 contact / through 分歧并输出风险 |
| LayeredDepth / SeeGroup | 多层透明 depth 定义和 SOTA | 它们回答“有几层”，我们回答“机器人应抓哪一层、何时拒绝” |
| ASGrasp / GraspNeRF / TranSplat / TRAN-D | active / multiview / NeRF / GS 系统上界 | 输入条件更强；作为上界和边界，不做同输入横比 |
| AISPO | 非朗伯 robot manipulation 的 shape prior / reliability 威胁 | 需持续 monitor；若代码不可用，先做概念对照和 reliability 指标对齐 |

## 8. 实验计划：主表怎么收

v4 的主表不能再以 Booster / LayeredDepth 为核心。推荐主表如下。

### Table 1: Transparent Metric Depth on Robot Datasets

目标：证明 `D_contact` 在透明区域和边界区域是可用的 metric depth。

| 数据 | Baselines | 指标 |
|---|---|---|
| TransCG test / fixed subset | raw depth, DFNet, ReMake, global affine, patch affine, MOMA-style SRS | full RMSE / MAE / AbsRel, transparent-mask RMSE, boundary RMSE, invalid-depth recovery |
| ClearPose subset | raw depth, ClearGrasp/LIDF if runnable, ReMake-compatible baseline, MODEST if runnable | transparent-mask RMSE, normal error, category / occlusion split |

### Table 2: Contact and Collision Proxy

目标：证明 depth 改善真正作用到抓取几何，而不是只改善全图误差。

推荐 proxy：

| Proxy | 解释 |
|---|---|
| contact-point depth error | 抓取候选接触点附近的前表面误差 |
| suction patch normal error | 吸盘局部法向是否稳定 |
| local planarity / curvature error | 吸取区域是否被背景错深度拉坏 |
| parallel-jaw collision violation | 夹爪路径是否穿过保守占据包络 |
| background-as-contact rate | 透射背景被误选为接触面的比例 |
| invalid-grasp risk filtering | 按 `C_grasp` 拒绝高风险候选后，剩余 grasp proxy 是否改善 |

必须保持 grasp planner 固定，只替换 depth input，否则无法证明是 depth readout 的贡献。

### Table 3: Grasp-Conditioned Readout Ablation

目标：证明 v4 的机制不是模块堆叠。

| Variant | 含义 | 要证明什么 |
|---|---|---|
| `SingleDepth` | 普通单头 completed depth | 单标量不足 |
| `MultiHyp-NoSemantic` | 多头 depth，但不分 contact / through | 匿名多假设不够 |
| `Contact-NoEnvelope` | 只输出 `D_contact`，没有 `D_envelope` | 碰撞包络对抓取安全有用 |
| `Contact-NoRisk` | 不输出 `C_grasp` | 风险过滤不是装饰 |
| `Contact-NoAction` | 不区分 suction / parallel-jaw | action-conditioned readout 必要 |
| `Contact-NoMDE` | 不用 relative depth prior | MDE prior 的贡献 |
| `Contact-NoMask` | 不用 mask | 方法是否完全依赖 mask |
| `Contact-Full` | 完整 `ContactDepthPack` | 主模型 |

### Table 4: Layer Semantics Boundary

目标：保留 v3 的层语义优势，但变成辅助证据。

| 数据 / teacher | 目的 |
|---|---|
| Depth4ToM / Booster | 验证 contact/front target 与 ToM front-surface 定义一致 |
| LayeredDepth / SeeGroup | 验证 `D_contact` 不等于 `D_through`，并定位 multi-layer ambiguity |
| high-risk transparent examples | 展示错误层 readout 如何导致 bad grasp proxy |

这张表不要抢主贡献，只服务一个问题：

```text
为什么机器人抓取不能只用一张普通 completed depth?
```

### Table 5: Real Robot, If Available

只有在已有或能快速采集真实机器人日志时才放主文。否则放计划或 appendix。

| 指标 | 说明 |
|---|---|
| grasp success rate | suction / parallel-jaw 分开 |
| collision / miss / slip / no-contact failure taxonomy | 失败原因要和 depth error 对齐 |
| attempts per object category | 透明杯、瓶、碗、盒、厚玻璃等分开 |
| runtime / sensor setup | 是否满足机器人在线使用 |

如果没有真实 robot log，写法必须保守：

```text
We evaluate grasp-relevant geometric proxies and leave physical robot trials
as the next validation step.
```

## 9. 指标纪律

机器人抓取口径下，不能只报视觉 depth 指标。

必须报：

| 指标 | 原因 |
|---|---|
| metric RMSE / MAE / AbsRel | 机器人需要米制几何 |
| transparent-mask metric | 不能被非透明区域平均掩盖 |
| boundary metric | 夹爪和吸盘常在边界附近失败 |
| raw invalid recovery | 透明传感器空洞是真实痛点 |
| background-as-contact rate | 直接衡量是否误把透射背景当表面 |
| contact patch normal / planarity | 对 suction 重要 |
| collision envelope violation | 对 parallel-jaw / motion planning 重要 |
| risk-coverage / selective grasp proxy | `C_grasp` 是否能拒绝高风险区域 |
| runtime / nfe / nfe_real | mask、MDE、opacification、completion 都要计成本 |

`metric` 和 `affine-aligned` 必须分开。affine 指标只能说明形状，不足以支撑机器人抓取。

## 10. 最小落地路线

### P0: 不训练新模型，先搭评测闭环

| 步骤 | 动作 | 产物 |
|---|---|---|
| 1 | 下载一块 TransCG 真实数据，例如 `scene21-30` | RGB、raw depth、GT、mask、DFNet baseline 样本包 |
| 2 | 在同一批样本跑 DFNet minimal runner | raw vs DFNet 的 transparent-mask 指标 |
| 3 | 补齐 ReMake 真实 inference 的 Depth Anything V2 relative depth | ReMake 同输入 baseline |
| 4 | 实现 global affine / patch affine / MOMA-style sparse alignment | 最危险后处理对照 |
| 5 | 写固定 grasp proxy evaluator | suction patch、parallel-jaw collision、background-as-contact |

P0 的 go / no-go：

```text
如果 grasp proxy 对不同 depth baseline 不敏感，说明评测设计不够好，先修评测。
如果 ReMake 在 contact proxy 上已经非常强，主方法必须专注于 risk / reject 或 action-conditioned envelope。
```

### P1: ContactDepthPack V1

先做最小可验证版本：

```text
RGB + raw depth + optional mask + relative depth
  -> shared encoder
  -> D_contact head
  -> D_through / background head
  -> D_envelope head
  -> C_grasp head
```

不要第一版就上复杂 point-process 或生成式 opacification。先证明语义分头和抓取读出有用。

P1 的 go / no-go：

```text
如果 D_contact 不超过 ReMake / DFNet，改成 reliability / grasp-risk filtering 贡献。
如果 depth 指标提升但 grasp proxy 不变，说明机器人贡献不成立，回到 v3 视觉桥接口径。
如果只在 GT mask 下有效，必须把 mask 作为系统输入成本写清，或者加入 predicted/noisy mask 鲁棒性。
```

### P2: Layer Semantics and Generalization

加入 Depth4ToM / LayeredDepth / SeeGroup：

- 用 Depth4ToM / Booster 支撑 front/contact target 的语义。
- 用 LayeredDepth / SeeGroup 标注或诊断 through/background ambiguity。
- 用 ClearPose 或 B-TOGE 做泛化，不只在 TransCG 调参。

### P3: Physical Robot Trial

若有设备，再做真实抓取。建议小规模但干净：

```text
same robot, same camera, same planner, same object set,
only depth source changes.
```

记录失败类型：

- no-contact。
- background-contact。
- collision。
- slip。
- mask / segmentation fail。
- high-risk rejected。

## 11. 论文图建议

### Figure 1: 透明抓取为什么不是单 depth

画透明杯和相机 ray：

```text
camera ray
  -> front/contact glass surface: should grasp / collide here
  -> back wall or transmitted background: visible but not first contact
  -> raw depth invalid / background read
```

旁边画错误后果：

```text
single completed depth reads background -> suction misses / gripper collides
```

### Figure 2: ContactDepthPack

```text
RGB + raw depth + optional MDE/mask
  -> Evidence Encoder
  -> Layer Hypothesis Head
  -> Contact-Semantic Assignment
  -> ContactDepthPack
       D_contact
       D_through
       D_envelope
       N_contact
       C_grasp
  -> Grasp-Conditioned Readout
       suction patch
       parallel-jaw contact pair
       collision envelope
       abstain
```

### Figure 3: Evaluation Protocol

三列：

```text
Depth quality:
  TransCG / ClearPose metric transparent-mask errors

Grasp geometry:
  contact patch, normal, collision envelope, background-as-contact

Risk:
  risk-coverage, selective grasp proxy, failure examples
```

### Figure 4: Qualitative Failure Cases

展示四种 case：

- raw depth 背景错深度。
- ReMake / single-depth 输出平均层。
- `ContactDepthPack` 选中前表面。
- `C_grasp` 拒绝多层高风险区域。

## 12. Abstract 草稿

```text
Transparent objects break robot grasping pipelines because the depth consumed
by a grasp planner is often neither the raw sensor return nor the visually
dominant background seen through the object. Existing transparent depth
completion methods typically predict a single completed depth map, while recent
layered-depth studies show that transparent rays can contain multiple valid
geometric hypotheses. We argue that robot grasping requires an action-conditioned
readout of contact geometry rather than a task-agnostic single depth.

We introduce ContactDepthPack, a grasp-aware representation that separates
contact/front-surface depth, transmitted/background depth, conservative collision
envelope, local contact geometry and grasp risk. Given RGB-D observations with
optional monocular depth or mask priors, our method preserves transparent
surface hypotheses and reads out the geometry required by suction, parallel-jaw
grasping and collision checking. We evaluate the approach on transparent-object
robot perception benchmarks with metric depth, contact-geometry proxies,
collision-risk proxies and selective prediction, comparing against raw depth,
RGB-D completion, MDE-assisted completion and sparse metric alignment baselines.
```

注意：最后一句只有在真的跑完对应 baseline 后才能从 proposal 口吻改成 result 口吻。

## 13. Introduction 五段结构

1. 机器人抓透明物体时，RGB-D depth 常空洞、读到背景或出现飞点；错误 depth 会直接导致 miss、collision、slip。
2. 现有 RGB-D completion / MDE-assisted 方法输出一张 completed depth，但透明像素天然有 contact layer 和 through layer，单 depth 容易混淆任务目标。
3. 多层透明深度工作说明 layer ambiguity 真实存在，但机器人抓取还需要回答哪一层可接触、哪一层只用于解释视觉、何时拒绝动作。
4. 核心 insight：先保留 semantically assigned depth hypotheses，再根据 suction / parallel-jaw / collision checking 读出 contact geometry。
5. 本文提出 `ContactDepthPack`，并用透明机器人数据、强 baseline、grasp proxy 和 risk-coverage 验证，而不是只做视觉 benchmark 指标。

## 14. Reviewer 风险登记

| 风险 | 类型 | 严重性 | 处理 |
|---|---|---|---|
| “这只是 ReMake 加几个 head” | design-fixable | 高 | 主表必须显示 contact / through / envelope / risk 的机制消融，而非只报 RMSE |
| “没有真实机器人实验，不算抓取贡献” | evidence-fixable / venue-mismatch | 高 | 若无 robot log，目标 venue 要谨慎；至少做强 grasp proxy 并明确真实实验为下一步 |
| “MOMA-style alignment 已能解决 metric depth” | evidence-fixable | 高 | 必须实现 global / patch / SRS sparse alignment 对照 |
| “mask 是 oracle” | design-fixable | 高 | GT / predicted / noisy / no-mask 全部报告，计入 `nfe_real` |
| “多层 depth 与机器人接触面 GT 不一致” | needs-evidence | 中高 | 明确 LayeredDepth 只作语义边界，不作机器人主 GT |
| “指标仍是 depth，不是 grasp” | evidence-fixable | 高 | 加 contact patch、collision envelope、background-as-contact、risk-coverage |
| “输入条件不公平” | writing-fixable / design-fixable | 高 | 严格分组：RGB-D、RGB-D+MDE+mask、single RGB、active/multiview 上界 |
| “透明对象种类泛化不足” | needs-new-result | 中 | TransCG 后补 ClearPose / B-TOGE / OOD object split |
| “真实时间太慢” | evidence-fixable | 中 | 报 runtime、MDE/mask/opacification cost 和 planner cost |

## 15. 当前应执行的下一步

最优先不是写新模型，而是把机器人主证据闭环打通：

1. 在 TransCG 真实子集上跑 raw depth、DFNet、ReMake、global affine、patch affine、MOMA-style sparse alignment。
2. 实现统一 `ContactDepthEval`：transparent-mask depth、boundary depth、contact patch、background-as-contact、collision proxy、risk-coverage。
3. 用这些结果决定 `ContactDepthPack` 的第一版最小模型。如果 ReMake 已强，优先做 `C_grasp` 和 action-conditioned `D_envelope`；如果 ReMake 在背景错深度处失败明显，优先做 contact / through semantic split。
4. 再接 Depth4ToM / LayeredDepth / SeeGroup 作为层语义解释，而不是先重回视觉 benchmark 主线。

## 16. 最终成熟版本应该长什么样

成熟版本的口号：

```text
Transparent grasping needs contact-aware depth readout, not a single completed
depth map.
```

成熟版本的贡献边界：

```text
We do not solve complete transparent reconstruction.
We do not claim to beat active sensing or multiview systems.
We study low-cost single-view robot perception for transparent grasping.
We show that semantically separating contact, through, envelope and risk improves
grasp-relevant geometry under fixed planners and fair baselines.
```

成熟版本的实验闭环：

```text
depth metric improves where robot cares
  -> contact / collision proxy improves under a fixed planner
  -> risk map rejects high-failure transparent regions
  -> optional real robot trials confirm the proxy
```

最该收紧的一句话：

```text
ContactDepthPack turns transparent depth ambiguity into robot-action geometry:
it preserves front/contact, through/background and invalid depth hypotheses,
then reads out contact depth, collision envelope and grasp risk for the action
being planned.
```

