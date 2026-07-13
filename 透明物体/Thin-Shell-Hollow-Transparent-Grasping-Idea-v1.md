# Thin-Shell / Hollow Transparent Object Grasping Idea v1

日期: 2026-07-12

本文基于 `pdfs/ReMake_2026_remake_mde_mask_transparent_grasping.pdf` 的技术路线分析，整理一个更聚焦透明物体抓取本体的 idea：

> **Shell-Aware Transparent Object Grasping**  
> 面向薄壳 / 空心透明物体的抓取几何估计。

核心判断：

```text
ReMake 已经把 RGB-D + mask + monocular relative depth -> completed depth -> 6-DoF grasp
这条路线做得很强。

我们的机会不应是再做一张更好的 completed depth map，
而是抓 ReMake 自己承认的限制：
single completed depth / generative completion 容易把 beaker、cup、tube 这类空心透明物体补成实心闭合表面，
丢失抓取所需的 outer wall、inner wall、rim、wall thickness 和 hollow cavity geometry。
```

Novelty status: needs-search。本文已基于 ReMake 本地 PDF 和本目录已有透明物体材料做定位，但投稿前仍需对 thin-shell transparent grasping、hollow object grasping、rim-aware grasping、container grasping 做标准文献检索。

## 0. 一句话版本

透明杯、瓶、碗、试管、酒杯不是实心透明块；机器人抓取它们时需要薄壳几何：外壁、内壁、杯口 / rim、壁厚、开口边界和稳定接触 patch。现有 transparent depth completion 方法通常输出一张 completed depth 或单点云，容易把空心结构补成实心闭合表面。我们研究 shell-aware transparent grasping：不只补深度，而是显式恢复和利用薄壳抓取几何。

更短：

```text
Transparent grasping should preserve hollow shell geometry, not collapse it into
a single completed surface.
```

中文口号：

```text
抓透明杯不是抓一个实心点云，而是抓一个薄壳结构。
```

## 1. ReMake 技术路线和它已经覆盖的空间

### 1.1 ReMake 的问题设定

ReMake 的任务是：

```text
single-view RGB-D transparent object depth completion
-> completed metric depth
-> target point cloud extraction
-> 6-DoF grasp generation
```

它不是纯单目，也不是多层透明重建，而是面向机器人抓取的 RGB-D depth completion。

### 1.2 ReMake 的输入输出

输入：

```text
RGB image
raw depth
transparent / instance mask
relative depth from Depth Anything
```

输出：

```text
completed depth map Do
```

然后用 instance mask 提取 target object point cloud，再送入 PCF-Grasp 生成 6-DoF grasp。

### 1.3 ReMake 的网络结构

ReMake 的框架可以概括为：

```text
RGB + mask        -> Swin Transformer encoder -> Fmask
relative depth    -> Swin Transformer encoder -> Frel
raw depth         -> MLP encoder              -> Fdepth
Fmask + Frel + Fdepth -> residual MLP decoder -> completed depth
```

它的两个核心模块：

1. **Mask-attention encoding**  
   把 transparent / instance mask 直接拼到 RGB 输入，让网络显式知道透明区域在哪里，而不是靠 RGB-D 自己隐式判断哪些 depth 可靠。

2. **Relative depth cue**  
   用 Depth Anything 生成 non-metric relative depth，提供透明物体与背景 / 周围物体之间的粗空间关系，改善不同视角和背景下的泛化。

### 1.4 ReMake 的 dataset insight

ReMake 对 TransCG 透明区域做了很有价值的拆解：

```text
Reflection: 深度缺失或 0 值。
Refraction: 有非零深度，但因为折射而失真，不可靠。
Normal: 有非零深度，且相对可靠。
```

它反对把 transparent mask 内的 raw depth 全部抹掉，因为那会丢掉 normal 区域的有效深度。

### 1.5 ReMake 的训练选择

ReMake 默认采用全图 global L1 loss：

```text
L(Do, Dgt)
```

而不是只在 transparent mask 内做 masked loss。它的理由是：透明区域深度重建需要周围区域的空间关系，mask-only supervision 在数据集上可能更好，但真实泛化更差。

### 1.6 ReMake 的真实抓取实验

ReMake 用 Franka + PCF-Grasp 做真实抓取，物体包括：

```text
bottle
large tube
small tube
tube with water
beaker
wine glass
cup
```

它测试 top-down、bird-eye、horizontal 三种相机视角，发现 DFNet / TDCNet 在非 top-down 视角下泛化明显下降，而 ReMake 更稳。

### 1.7 ReMake 的关键限制

最重要的是 ReMake 自己在 Discussion 中指出：

```text
relative depth estimation model and depth completion model are generative models
and tend to produce closed surfaces.
They struggle to represent internal hollow structures of transparent objects;
e.g., beakers are often reconstructed as solid objects.
```

这正是 Thin-Shell / Hollow 方向的入口。

## 2. 我们不能和 ReMake 抢什么

不要把新 idea 写成：

```text
RGB-D + mask + MDE relative depth -> better completed depth -> higher grasp success.
```

这会和 ReMake 正面冲突，而且 ReMake 已经做了：

- mask 作为网络输入。
- Depth Anything relative depth 作为辅助。
- global loss vs mask loss。
- TransCG benchmark。
- real-world grasp with PCF-Grasp。
- 多视角 / 背景变化泛化。

也不要只写：

```text
我们加一个 shell-aware loss，让 completed depth 更好。
```

这仍然会被看作 ReMake 的小修小补。

## 3. 我们应该切开的核心空位

ReMake 的主输出是一张 completed metric depth。对实心或外表面抓取，这很合理；但对薄壳 / 空心透明物体，机器人需要的不只是最近可见表面。

典型对象：

```text
transparent cup
beaker
wine glass
test tube
transparent bowl
thin transparent box
open-top transparent container
```

这些对象有抓取相关几何：

| 几何 | 为什么对抓取重要 |
---|---|
| outer wall | 夹爪 / 吸盘首先接触的外表面 |
| inner wall | 空心结构和壁厚估计，需要避免把容器当实心 |
| rim / opening boundary | 杯口 / 碗口常是稳定抓取或避碰关键 |
| wall thickness | 夹爪接触稳定性、碰撞和 slip 风险 |
| hollow cavity | 决定对象是不是容器、是否可从内外抓、是否有内部空间 |
| local shell normal | 吸盘和夹爪接触 patch 的法向稳定性 |
| shell grasp affordance | 哪些壳体区域可夹、可吸、可避碰 |

因此中心问题应改成：

```text
How can a robot perceive and grasp hollow transparent objects when single-depth
completion collapses thin-shell geometry into solid or closed surfaces?
```

中文：

```text
当单层深度补全会把空心透明物体补成实心闭合表面时，机器人如何恢复并利用薄壳抓取几何？
```

## 4. Optimized Idea Card

### Task

给定单视角 RGB-D 观测和目标实例 mask，预测空心 / 薄壳透明物体的抓取几何表示，并生成稳定的 6-DoF 抓取候选。

### Gap

现有透明物体抓取路线大多以 completed depth / completed point cloud 为中间目标。ReMake 通过 mask + MDE relative depth 强化了这一路线，但它仍然输出单一 completed depth，并承认容易把 hollow transparent objects 补成 solid / closed surfaces。

### Root Challenge

薄壳透明物体的真实几何不是一个单层 surface：

```text
camera ray may hit:
  outer wall
  inner wall / back wall
  rim / opening boundary
  transmitted background
```

单层 completed depth 会把这些结构压成一个表面，导致：

- 杯口 / rim 消失。
- beaker / cup 被补成实心块。
- 夹爪 collision envelope 错。
- 吸盘接触 patch 法向不稳定。
- parallel-jaw 抓取选到错误侧面或错误厚度。

### Core Insight

> Transparent grasping for hollow objects should preserve shell geometry rather than optimize only single-depth completion.

### Proposed Mechanism

提出 `ShellGraspPack`：

```text
ShellGraspPack {
  D_outer: outer/front wall depth,
  D_inner: inner/back wall or rear shell depth,
  R_rim: rim / opening boundary curve,
  T_wall: local wall thickness,
  O_cavity: hollow cavity / empty interior mask,
  N_shell: local shell normal,
  A_shell: graspable shell affordance,
  C_shell: shell geometry confidence / risk
}
```

它不是 ReMake 的 completed depth 替代品，而是面向薄壳透明对象的抓取几何表示。

### Contribution Type

主贡献应收成两项：

1. **New setting / representation**  
   定义 shell-aware transparent grasping，指出 single completed depth 对 hollow transparent objects 的结构性缺陷，并提出 `ShellGraspPack`。

2. **Method / evidence**  
   学习 outer / inner / rim / thickness / cavity / shell affordance，并证明它比 single-depth completion 更能支持薄壳透明物体抓取。

可以有第三项辅助贡献：

3. **Benchmark slice / diagnostic**  
   构建 hollow transparent object grasping slice，专门评估 cup / beaker / tube / bowl 等薄壳对象的 rim、thickness、cavity 和 grasp success。

## 5. 方法蓝图

### 5.1 输入

第一版不要太激进，沿用 ReMake 的可行输入：

```text
RGB image
raw depth
transparent / instance mask
optional: monocular relative depth
optional: ReMake completed depth as baseline candidate
```

这样能保持和 ReMake 公平对比。

### 5.2 表示层

模型不直接只输出 `Do`，而输出：

```text
D_outer
D_inner
R_rim
T_wall
O_cavity
N_shell
A_shell
C_shell
```

必要时仍可输出一个辅助 completed depth，但它不能是主贡献。

### 5.3 几何约束

薄壳结构应满足：

```text
D_outer < D_inner          within transparent object mask
T_wall = D_inner - D_outer projected by local ray / normal
rim boundary separates shell surface and cavity opening
cavity should be empty / non-solid in occupancy representation
grasp contact patches lie on stable shell surfaces, not hallucinated filled interior
```

### 5.4 网络结构选项

保守实现：

```text
ReMake-style encoders:
  RGB + mask -> encoder
  raw depth -> encoder
  relative depth -> encoder

Shell decoder:
  outer depth head
  inner depth head
  rim head
  thickness head
  cavity occupancy head
  shell affordance head
  confidence head
```

更强实现：

```text
multi-hypothesis ray head:
  per pixel predicts K shell intersections
  semantic assignment: outer / inner / background
  grasp readout samples shell contact patches
```

### 5.5 Grasp Readout

从 `ShellGraspPack` 生成抓取：

```text
suction:
  choose stable outer shell patch with low curvature and high C_shell

parallel-jaw:
  choose opposing shell contact regions with valid wall thickness and collision clearance

rim grasp:
  choose rim segments with enough opening boundary confidence and gripper clearance
```

注意：这不是长程规划，只是透明薄壳物体自身的 grasp candidate generation。

## 6. 与 ReMake 的关系

### 6.1 ReMake 是强 baseline

主实验必须包括：

```text
raw depth + PCF-Grasp
DFNet + PCF-Grasp
TDCNet + PCF-Grasp
ReMake + PCF-Grasp
ReMake + shell-aware postprocess, if useful
Ours ShellGraspPack
```

### 6.2 我们的 claim 不能写错

不写：

```text
ReMake cannot grasp transparent objects.
```

ReMake 已经真实抓取成功率很强。

应该写：

```text
ReMake substantially improves single-depth completion and grasping under view
and background shifts. However, its single completed depth representation tends
to close hollow structures, which is a structural limitation for thin-shell
transparent objects. We address this complementary failure mode.
```

### 6.3 最强差异

| 维度 | ReMake | Shell-Aware idea |
---|---|---|
| 中间目标 | completed depth map | shell grasp geometry |
| 几何假设 | 单一 metric surface / point cloud | outer-inner-rim-thickness-cavity |
| 强项 | 泛化的 transparent depth completion | 空心薄壳对象抓取结构 |
| 已验证 | TransCG + real grasp under viewpoint shifts | 需要 hollow-specific slice |
| 可能失败 | hollow object reconstructed as solid | thin shell label / geometry acquisition difficult |

## 7. 实验设计

### 7.1 数据对象

必须把对象切成 shell categories：

```text
beaker
cup
wine glass
test tube
transparent bowl
transparent box
solid transparent block / solid object as control
```

ReMake 也测试了 tube、beaker、wine glass、cup，但它没有专门评估 hollow geometry。因此我们可以复用这些类别，但换评测目标。

### 7.2 数据来源

可选路径：

1. **真实对象 + CAD / mesh / manual measurement**  
   对杯、碗、管、盒做简单 mesh 或手工测壁厚 / rim。

2. **合成薄壳透明数据**  
   用 Blender / existing CAD 生成 outer / inner / rim / thickness GT。

3. **LayeredDepth / SeeGroup teacher 辅助**  
   用多层透明 depth teacher 提供 outer / inner 候选，但不能把它当机器人最终证据。

4. **ReMake / TransCG real grasp setup**  
   保持真实机器人抓取对比。

### 7.3 主指标

不要只报 RMSE。建议指标：

| 指标 | 说明 |
---|---|
| outer depth error | 外壁接触面误差 |
| inner depth error | 内壁 / 后壁估计误差 |
| front-back separation error | outer-inner 分离是否正确 |
| wall thickness error | 壁厚估计 |
| rim localization F1 / Chamfer | 杯口 / 开口边界 |
| cavity occupancy IoU | 是否把空心内部保留下来 |
| shell normal error | 接触 patch 法向 |
| grasp success | 真实抓取成功率 |
| wrong-side contact rate | 抓到错误侧 / 错误层 |
| collision / slip rate | 壳体几何错误导致的失败 |

### 7.4 主表

Table 1: Hollow geometry quality

```text
Methods:
  ReMake completed depth
  ReMake + heuristic rim extraction
  LayeredDepth / SeeGroup readout
  Ours ShellGraspPack

Metrics:
  rim F1, thickness error, cavity IoU, outer/inner error
```

Table 2: Shell grasping performance

```text
Objects:
  cup, beaker, wine glass, tube, bowl

Metrics:
  success rate, collision, slip, wrong-side-contact
```

Table 3: Generalization

```text
Viewpoints:
  top-down, bird-eye, horizontal

Background:
  simple, textured, distant background

Metrics:
  shell geometry + grasp success
```

Table 4: Ablation

```text
Ours w/o D_inner
Ours w/o rim
Ours w/o thickness
Ours w/o cavity
Ours w/o shell confidence
Ours single-depth only
```

## 8. 关键 qualitative

必须展示几类失败：

1. ReMake 把 beaker / cup 补成实心或闭合块。
2. ReMake point cloud 看起来完整，但 rim / inner cavity 消失，导致 grasp planner 选错接触。
3. ShellGraspPack 保留 outer / inner / rim，生成更合理的侧壁或 rim grasp。
4. 对 solid transparent object，ShellGraspPack 不应强行 hallucinate hollow structure。
5. 水或厚曲面导致多层混淆时，`C_shell` 能降低高风险抓取。

## 9. Reviewer 风险

| 风险 | 类型 | 严重性 | 处理 |
---|---|---|---|
| “这只是 ReMake 加多头” | design-fixable | 高 | 主表必须是 rim/thickness/cavity/grasp failure，而不是 depth RMSE |
| “hollow GT 很难获得” | needs-feasibility-check | 高 | 先用 CAD / synthetic + 少量真实测量；明确 GT 来源 |
| “抓杯子只看外壁就够了” | evidence-fixable | 高 | 设计 rim grasp、thin tube、open cup、wine glass 等需要 inner/rim 的 case |
| “多层深度已有 LayeredDepth / SeeGroup” | writing-fixable | 中高 | 强调 robot shell grasp geometry，不是通用 multi-layer depth |
| “ASGrasp / multiview 系统能重建完整几何” | venue-boundary | 中高 | 限定 single-view / low-cost RGB-D，ASGrasp 作为系统上界 |
| “真实抓取提升不明显” | requires-new-result | 高 | 如果 depth/geometry 好但 grasp 不提升，转成 diagnostic benchmark |
| “对象类别太窄” | venue-mismatch | 中 | 强调 thin-shell transparent objects 在日常和实验室中常见；补 solid control |
| “MDE relative depth 不提供细节” | known limitation | 中 | 不依赖 MDE 做 rim/thickness 主监督，只作 context cue |

## 10. 最小可行计划

### Week 1: ReMake baseline and shell failure examples

```text
复现 ReMake 在 cup / beaker / tube / wine glass 上的输出。
收集 qualitative：closed surface / solidified beaker / missing rim。
实现简单 rim / cavity diagnostic。
```

Go / no-go:

```text
如果 ReMake 在所有 hollow objects 上都保留了足够 rim/cavity，
则该方向风险变高，需要转向 risk/confidence 或 active sensing。
```

### Week 2: Build shell slice

```text
选择 5-8 个透明薄壳对象。
获取 CAD / mesh / 手工几何标注。
定义 rim、outer、inner、thickness、cavity 指标。
```

### Week 3: ShellGraspPack V0

```text
基于 ReMake-style encoder 加 shell heads。
先在 synthetic / CAD rendered data 训练。
真实图像做 fine-tune 或 teacher adaptation。
```

### Week 4: Grasp readout and robot test

```text
实现 side-wall grasp、rim grasp、suction patch。
与 ReMake + PCF-Grasp 对比。
记录 collision / slip / wrong-side-contact。
```

## 11. Go / No-Go Gate

Go 条件：

```text
ReMake / single-depth baseline 在 hollow objects 上出现可重复的 solidification / missing-rim failure；
shell-specific metrics 能解释 grasp failure；
ShellGraspPack 至少在 rim / cavity / thickness 指标上明显优于 single-depth baseline；
真实或 proxy grasp 显示 shell-aware readout 有收益。
```

No-go 条件：

```text
ReMake 的 completed depth 已足够支持 hollow grasp；
hollow geometry GT 无法可靠获得；
shell metrics 和 grasp success 没有相关性；
新增 head 只提升视觉指标，不改变抓取失败类型。
```

Pivot：

```text
如果 shell geometry 太难，转成 Hollow Transparent Grasp Diagnostic Benchmark；
如果 geometry 指标有效但方法弱，先发表 benchmark / failure taxonomy；
如果真实抓取难，先做 ReMake failure analysis + shell proxy。
```

## 12. 最终成熟版本

成熟标题：

```text
Shell-Aware Transparent Object Grasping
```

成熟问题：

```text
Transparent household and laboratory objects are often hollow thin-shell
structures. Existing single-depth completion methods improve external surface
reconstruction but can collapse hollow objects into closed or solid shapes,
removing shell geometry needed for stable grasping.
```

成熟贡献：

```text
We formulate shell-aware transparent grasping, introduce ShellGraspPack to
represent outer/inner shell surfaces, rim boundaries, wall thickness, hollow
cavity and shell grasp affordance, and evaluate it on hollow transparent objects
where single completed depth fails to preserve grasp-critical geometry.
```

一句话边界：

```text
ReMake solves mask- and MDE-guided single-depth completion for transparent
grasping; we solve hollow thin-shell grasp geometry that single completed depth
structurally collapses.
```

