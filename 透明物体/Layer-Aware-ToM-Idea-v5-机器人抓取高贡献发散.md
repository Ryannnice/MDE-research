# Layer-Aware ToM Idea v5：机器人抓取高贡献方向发散

日期: 2026-07-11

本文接在 `Layer-Aware-ToM-Idea-v4-机器人抓取贡献重构.md` 之后，专门回答：

> `ContactDepthPack` 作为机器人抓取 idea，贡献是不是仍然不够大？如果要把透明物体抓取方向做得更有论文贡献，应往哪些相关 idea 发散？

结论先说清楚：如果 v4 只是“在 ReMake / DFNet 上加 contact / through / risk 多头，然后做离线 grasp proxy”，贡献半径确实偏中等，容易被认为是 ReMake + LayeredDepth + uncertainty 的组合。要把贡献做大，应该把中心从“一个更好的 depth head”推进到以下几类更强问题：

1. 新任务/协议：透明物体抓取到底该如何评测接触几何，而不是只评测 depth RMSE。
2. 新闭环：模型不仅输出 depth，还决定何时抓、何时拒绝、何时主动获取信息。
3. 新表示：绕开 single completed depth，直接学习 contact / occupancy / collision / affordance。
4. 新数据机制：构造能系统覆盖透明失败模式的仿真、配对、探测或交互数据。
5. 新系统能力：在低成本传感器下，用最少额外动作解决透明物体抓取的不确定性。

Novelty status: unsearched。本文没有重新联网做最新文献检索，所有 novelty 判断都基于本目录已有调研；后续强 novelty claim 需要再做 `ccf-literature-searcher` 或人工文献核验。

## 0. 为什么 v4 可能贡献不够大

v4 的核心是：

```text
ContactDepthPack = D_contact + D_through + D_envelope + N_contact + C_grasp
```

这个想法比 v3 更贴近机器人抓取，但仍有三个贡献风险。

### 风险 1：像 ReMake 的语义多头版

ReMake 已经把：

```text
RGB + raw depth + monocular relative depth + mask -> completed metric depth
```

接到透明物体抓取。v4 如果只是在同样输入上增加几个输出头，reviewer 很可能问：

```text
为什么这不是 ReMake + uncertainty / normal / mask loss?
```

要突破，必须证明新增表示改变了任务闭环，例如减少 background-as-contact、降低 collision violation，或让系统知道何时不该抓。

### 风险 2：离线 grasp proxy 说服力有限

如果没有真实 robot log，grasp proxy 是必要但不充分的。机器人 venue 容易追问：

```text
Depth metric 好了，真实抓取是否真的更好？
proxy 是否和物理失败相关？
```

因此更大的 idea 应该把 proxy 本身做成可验证协议，或把方法推向 closed-loop / active sensing。

### 风险 3：层语义不是机器人独有贡献

LayeredDepth / SeeGroup 已经强调多层透明 depth。v4 的 contact / through 区分如果没有机器人动作条件，会被看成把视觉层语义迁移到机器人而已。

更强的切口应该是：

```text
robot action changes which depth is useful
```

也就是 suction、parallel-jaw、collision checking、active probing 对同一透明区域需要不同几何读出。

## 1. 贡献半径阶梯

| 等级 | 形态 | 贡献半径 | 风险 |
|---|---|---|---|
| L1 | 给 ReMake / DFNet 加 contact head | 小到中 | 容易被认为工程增量 |
| L2 | `ContactDepthPack` + grasp proxy + 强 baseline | 中 | 无真实机器人时仍偏弱 |
| L3 | 新的 transparent grasp geometry benchmark / protocol | 中到大 | 工程量和协议可信度要求高 |
| L4 | 风险校准 + selective / abstention grasping | 大 | 需要证明拒绝策略有实际价值 |
| L5 | 主动感知 / 触碰 / sparse anchor acquisition policy | 大 | 系统复杂，实验成本高 |
| L6 | 直接学习 contact / occupancy / affordance，弱化 depth | 大 | 数据标注和可解释性更难 |
| L7 | 仿真-真实透明传感失败生成器 + benchmark | 大 | 需要做出可信仿真或配对数据 |

最现实的策略不是在 L1 上加模块，而是选一个 L3-L5 的主贡献，再让 v4 的 `ContactDepthPack` 成为其中的感知子模块。

## 2. 发散 Idea A：Transparent Grasp Geometry Benchmark

### 一句话

建立一个透明物体抓取几何协议：评测 contact surface、background-as-contact、collision envelope 和 risk calibration，而不是只评测 transparent-mask depth RMSE。

### 核心问题

现有透明深度论文常报告 depth completion 指标，但机器人真正失败的是：

- 把透射背景当接触面。
- 边界飞点导致夹爪碰撞。
- 吸盘 patch 法向错误。
- 高不确定区域仍被 planner 选中。

这些失败不一定被 RMSE 充分解释。因此需要一个抓取几何协议，把 depth error 转成 action-relevant failure metrics。

### 方法机制

基于 TransCG / ClearPose / B-TOGE / 可采集小规模 robot data，构建统一 evaluator：

```text
Depth prediction
  -> contact candidate extraction
  -> suction patch evaluation
  -> parallel-jaw collision proxy
  -> background-as-contact classifier
  -> risk-coverage / selective grasp curve
```

输出不只是 leaderboard，而是 failure taxonomy：

```text
raw invalid hole
background-as-contact
front-surface shift
boundary flying point
normal instability
collision-envelope underestimation
overconservative rejection
```

### 贡献类型

新 benchmark / protocol + empirical diagnostic。

### 为什么比 v4 大

v4 是一个方法；Idea A 改变“透明物体抓取深度应该怎么被评价”。如果协议被接受，即使新模型增益不大，也能作为社区贡献。

### 最小证据包

| Claim | Evidence |
|---|---|
| RMSE 不能充分预测 grasp geometry quality | 比较 raw depth、DFNet、ReMake、MOMA-style alignment 的 RMSE 与 contact proxy 排序不一致案例 |
| 新指标能定位机器人相关失败 | failure taxonomy + qualitative + per-category table |
| 协议可复现 | 统一数据 adapter、固定 planner、公开 evaluator |

### 主要风险

- `evidence-fixable`: 没有真实机器人验证时，proxy 可信度会被质疑。
- `design-fixable`: 指标如果太多，会像工程 checklist。
- `needs-search`: 需要确认是否已有类似 transparent grasp benchmark。

### 最小落地版本

先不做新模型，直接跑：

```text
raw depth
DFNet
ReMake
global affine
patch affine
MOMA-style SRS
```

如果这些 baseline 在新指标上表现出互补失败，Idea A 就成立。

## 3. 发散 Idea B：Risk-Calibrated Selective Grasping

### 一句话

透明物体抓取的关键不只是补全深度，而是知道哪些抓取候选不可信；模型输出 calibrated grasp risk，并在高风险透明区域选择拒绝、换动作或请求主动感知。

### 核心问题

透明物体的错深度往往是灾难性局部错误。一个平均 RMSE 更低的 depth map，如果在接触点附近给出高置信错误，可能比保守拒绝更危险。

因此任务应从：

```text
minimize depth error
```

改成：

```text
maximize successful grasps under calibrated risk and bounded abstention cost
```

### 方法机制

```text
RGB-D + optional MDE/mask
  -> contact geometry prediction
  -> grasp candidate generation
  -> per-candidate risk estimator
  -> selective policy:
       accept grasp
       reject grasp
       switch suction / parallel-jaw
       request active sensing
```

核心不是普通 uncertainty map，而是 candidate-level risk：

```text
C_pixel -> C_patch -> C_grasp
```

训练信号可以来自：

- depth residual near candidate contact patch。
- collision proxy violation。
- background-as-contact label。
- synthetic perturbation / mask noise / raw-depth corruption。
- small real robot trial if available。

### 贡献类型

新 decision setting + method + evaluation。

### 为什么比 v4 大

v4 仍在做“更好几何”。Idea B 引入 decision under uncertainty：透明物体抓取允许模型说“不确定，不抓这个点”。这更贴近机器人安全和部署。

### 最小证据包

| Claim | Evidence |
|---|---|
| Pixel uncertainty 不等于 grasp risk | pixel ECE vs candidate-level failure AUROC 对比 |
| Selective policy 提升可靠抓取 | risk-coverage curve，固定 coverage 下 proxy failure rate 下降 |
| 机制不是靠阈值调参 | compare confidence from ReMake residual, MC dropout, ensemble, proposed candidate-risk head |

### 主要风险

- `requires-new-result`: 如果没有真实抓取，risk 的物理意义仍可能不足。
- `design-fixable`: 必须避免变成普通 uncertainty head。
- `evidence-fixable`: 需要校准指标，不能只报 AUROC。

### 最小落地版本

用离线数据先定义 pseudo grasp failure：

```text
failure = contact depth error > threshold
       or normal error > threshold
       or collision envelope violated
       or selected contact lies on through/background layer
```

再做 risk-coverage：

```text
coverage from 100% to 50%
measure remaining candidate failure rate
```

## 4. 发散 Idea C：Active Sparse Anchoring for Transparent Grasping

### 一句话

不要只做 MOMA-style 输出端 sparse metric alignment；让机器人主动选择最有价值的 sparse anchor / probe / view，用最少额外测量消除透明物体抓取的不确定性。

### 核心问题

MOMA 类路线通常假设 sparse metric anchor 已给定，或者做一次性标定。但透明物体最关键的问题是：

```text
应该在哪里获取少量可靠 metric 信息，才能最大幅度降低抓取风险？
```

这可以是：

- depth anchor。
- robot touch/probe point。
- active stereo view。
- suction pre-contact measurement。
- wrist camera small motion。

### 方法机制

```text
Initial RGB-D observation
  -> uncertainty / layer ambiguity map
  -> candidate anchor acquisition policy
  -> get sparse metric/contact observation
  -> update ContactDepthPack / occupancy
  -> plan grasp
```

核心 representation：

```text
Value of Information for Transparent Contact Geometry
```

不是把 anchor 均匀采样，而是根据：

- high layer ambiguity。
- candidate grasp sensitivity。
- collision envelope uncertainty。
- expected reduction of background-as-contact。

选择下一处测量。

### 贡献类型

新 active perception policy + system design。

### 为什么比 v4 大

v4 是被动感知。Idea C 把透明物体抓取改成主动信息获取问题，直接回应“透明对象本来就不可从单视角完全确定”的根本瓶颈。

### 最小证据包

| Claim | Evidence |
|---|---|
| 随机 sparse anchors 效率低 | random / grid / high-gradient / MOMA-style anchors 对比 |
| action-aware anchor 更能降低 grasp risk | same number of anchors 下 risk-coverage / collision proxy 更好 |
| 少量主动信息足够 | 1, 3, 5 anchors or probes 的 sample-efficiency curve |

### 主要风险

- `needs-feasibility-check`: 真实 touch/probe 或 active camera 实验成本更高。
- `venue-mismatch`: 如果只做离线 anchor simulation，机器人 venue 可能认为系统性不足。
- `needs-search`: 需要查 active perception / next-best-view / tactile probing 透明物体近作。

### 最小落地版本

先不接真实机器人，用 TransCG / ClearPose GT 模拟 sparse anchors：

```text
allowed query: reveal GT depth at selected pixels / local patch
budget: 1, 3, 5, 10 anchors
goal: reduce grasp candidate failure
```

如果 simulated active anchoring 明显优于 random / uncertainty-only，再升级到真实 probe。

## 5. 发散 Idea D：Depth-Free Contact Affordance for Transparent Objects

### 一句话

放弃“先恢复一张正确深度图再抓取”的传统路径，直接预测透明物体的 contact affordance、collision occupancy 和 grasp success field。

### 核心问题

透明物体 depth 本身有多义性。机器人最终不一定需要完整深度图，它需要：

```text
哪里能吸？
哪里能夹？
哪里会撞？
哪里不确定？
```

如果 full depth 是中间代理目标，可能会把模型引向不必要的视觉重建问题。

### 方法机制

```text
RGB-D / RGB + optional mask
  -> object-centric representation
  -> contact affordance field
  -> conservative occupancy envelope
  -> grasp pose distribution
  -> uncertainty / abstention
```

监督可以来自：

- depth-derived contact labels。
- mesh / pose if TransCG object models可用。
- synthetic grasp simulation。
- fixed analytic grasp planner labels。
- small real grasp outcome labels。

关键区别：

```text
predict what the robot needs, not all depth layers.
```

### 贡献类型

新 representation / task setting。

### 为什么比 v4 大

它从根本上挑战 transparent depth completion 的中间目标，把论文从“depth 方法”改成“transparent grasp representation”。

### 最小证据包

| Claim | Evidence |
|---|---|
| Full depth improvement 不一定等于 grasp improvement | 找到 RMSE 更好但 contact affordance 更差的 baseline case |
| Direct contact representation 更稳 | fixed planner 下 candidate success proxy 更好 |
| Occupancy envelope 降低 collision | collision violation 与 conservative envelope 对比 |

### 主要风险

- `needs-evidence-design`: 没有真实 grasp label 时，affordance label 可能被质疑是 depth proxy 换皮。
- `requires-new-result`: 需要更强 simulation 或真实抓取支撑。
- `design-fixable`: 必须保留可解释几何，否则像 black-box grasp detector。

### 最小落地版本

先做 hybrid：

```text
ContactDepthPack branch
GraspAffordance branch
shared encoder
```

实验比较：

```text
depth-only planner
affordance-only planner
hybrid planner
```

如果 affordance-only 太黑箱，保留 hybrid 作为稳妥路线。

## 6. 发散 Idea E：Transparent Sensor Failure Simulator / Corruption Engine

### 一句话

构建一个透明物体 RGB-D 传感失败生成器，系统模拟 invalid holes、background reads、refraction noise 和 boundary flying points，用于训练和评测透明抓取深度方法。

### 核心问题

TransCG / ClearPose 等数据宝贵，但真实透明传感失败模式有限且采集成本高。现有方法常在固定数据集上训练/评测，难以回答：

```text
模型到底学会了透明几何，还是记住了某个传感器的失败分布？
```

如果能可控生成 sensor failure，就能测试鲁棒性和泛化。

### 方法机制

```text
clean / GT geometry + RGB
  -> material / thickness / incidence / background parameters
  -> RGB-D corruption engine
       invalid holes
       background depth leakage
       boundary flying points
       local scale bias
       speckle / multi-path noise
  -> train/evaluate depth completion and grasp policy
```

不一定追求物理光学完全准确，重点是可控失败模式和真实统计校准。

### 贡献类型

数据生成 / benchmark / empirical finding。

### 为什么比 v4 大

它不只是提出一个模型，而是提供一个可复用的数据和压力测试工具，能服务多个透明物体方法。

### 最小证据包

| Claim | Evidence |
|---|---|
| corruption engine 覆盖真实失败类型 | 与 TransCG / real samples 的 invalid ratio、boundary error、background-read 统计对齐 |
| 用它训练更泛化 | train synthetic-corruption, test TransCG / ClearPose / OOD |
| 它能区分方法弱点 | method performance by corruption type |

### 主要风险

- `needs-mechanism`: 过于 ad hoc 的 corruption 会被质疑为数据增强。
- `evidence-fixable`: 需要真实传感失败统计校准。
- `venue-mismatch`: 如果没有机器人抓取指标，可能更像数据/视觉论文。

### 最小落地版本

从简单 corruption 开始：

```text
mask-conditioned invalid holes
background-depth replacement
boundary dilation + flying-point noise
local affine bias
```

先证明这些 corruption 能复现 baseline 的已知失败排序，再扩展物理参数。

## 7. 发散 Idea F：Counterfactual Opaque Twin for Grasping

### 一句话

为透明物体构造“如果它是不透明的”反事实几何/外观，用来分离可见纹理、真实前表面和抓取接触面的监督。

### 核心问题

SeeClear 类路线把透明区域变成不透明外观再跑 MDE，但抓取需要的不只是视觉 opacification，而是：

```text
透明物体如果是不透明实体，机器人应该看到什么接触几何？
```

这个反事实可以成为训练信号和诊断工具。

### 方法机制

```text
transparent RGB-D observation
  -> estimate / synthesize opaque-twin appearance and depth
  -> compare:
       raw transparent sensor depth
       opaque-twin contact depth
       through/background depth
  -> train contact readout / failure classifier
```

与 SeeClear 的区别应写成：

```text
opacification is not the final method; opaque-twin geometry is used as a
counterfactual supervision and diagnostic target for robot contact.
```

### 贡献类型

新 supervision / counterfactual data / diagnostic。

### 为什么比 v4 大

它提供一个更强的监督解释：透明抓取的目标是 counterfactual opaque contact geometry，而不是任意 completed depth。

### 最小证据包

| Claim | Evidence |
|---|---|
| opaque-twin target 更接近 grasp contact | 与 TransCG GT / mesh / normal / contact proxy 对齐 |
| 它能过滤 through/background 错误 | background-as-contact rate 下降 |
| 比直接 opacification 更稳 | SeeClear-style preprocessing vs counterfactual-contact supervision |

### 主要风险

- `needs-search`: SeeClear / opaque-paired synthetic data 已非常接近，必须查清差异。
- `needs-feasibility-check`: paired opaque twin 数据难获得。
- `design-fixable`: 不能只变成生成式外观增强。

### 最小落地版本

不用先生成真实图片，先做 geometry-level opaque twin：

```text
transparent mask + GT depth / mesh
  -> derive front contact surface
  -> train model to predict counterfactual contact depth
```

如果后续有 paired rendering，再加入 appearance counterfactual。

## 8. 发散 Idea G：Action-Conditioned Layer Readout Policy

### 一句话

同一个透明像素对不同动作有不同有用层：吸取要接触面，夹取要碰撞包络，观察/重建要多层；学习一个 action-conditioned layer readout policy，而不是固定输出 `D_contact`。

### 核心问题

v4 已经有 action readout，但还不够中心化。更强的表述是：

```text
transparent depth is not a perception output; it is an action-conditioned query.
```

同一张 ContactDepthPack 支持不同 query：

```text
query = suction_contact
query = parallel_jaw_clearance
query = object_removal_scene_update
query = safe_motion_collision
query = active_sensing_target
```

### 方法机制

```text
Depth hypotheses + action token / grasp candidate
  -> cross-attention readout
  -> query-specific depth / occupancy / risk output
```

形式上可做成：

```text
H = {D1, D2, ..., confidence, mask, raw-depth validity}
q = action descriptor
readout = f(H, q)
```

这比手写 suction / parallel-jaw 规则更一般。

### 贡献类型

新 action-conditioned perception formulation + method。

### 为什么比 v4 大

它把透明深度估计从静态预测改成 action-conditioned perception，理论上可以扩展到抓取、避障、scene update 等多个机器人任务。

### 最小证据包

| Claim | Evidence |
|---|---|
| 不同动作需要不同 readout | suction vs parallel-jaw vs collision 的最优层不同案例 |
| action-conditioned readout 优于固定 front-depth | per-action proxy table |
| readout 学到而不是硬编码 | action token ablation, shuffled action ablation |

### 主要风险

- `needs-evidence-design`: 如果只有两种动作，action-conditioned 可能显得过度设计。
- `design-fixable`: action descriptor 必须具体，不能泛泛用文本 token。
- `needs-search`: 需要查 task-conditioned perception / action-conditioned depth 近作。

### 最小落地版本

先支持三个 query：

```text
suction_contact
parallel_jaw_collision
background_reconstruction
```

如果这三者在同一像素选择不同层，就能支撑 formulation。

## 9. 发散 Idea H：Transparent Object Grasping as POMDP

### 一句话

把透明物体抓取建模为部分可观测决策问题：不可直接观测的真实接触几何是 latent state，RGB-D / MDE / probe 都只是 observation，机器人需要在信息获取和抓取之间权衡。

### 核心问题

透明物体不是单次感知必然可解的问题。由于透射、反射、传感器空洞和多层结构，真实 contact geometry 在单视角下可能不可辨识。

因此更合理的主张是：

```text
transparent grasping is a belief-state problem, not a depth-completion problem.
```

### 方法机制

```text
belief over contact geometry / occupancy
  observation update from RGB-D / MDE / mask / sparse anchor / touch
  action:
    grasp
    observe next view
    touch/probe
    abstain
  reward:
    grasp success - collision cost - sensing cost
```

不一定要做完整 POMDP solver，可以做 amortized policy：

```text
belief representation = ContactDepth distribution
policy = choose grasp or information action
```

### 贡献类型

新 problem formulation + closed-loop system。

### 为什么比 v4 大

它给出一个更根本的理论/系统框架，解释为什么透明物体抓取不能只靠 single-shot depth completion。

### 最小证据包

| Claim | Evidence |
|---|---|
| 单次 depth completion 存在不可消除歧义 | ambiguity cases from LayeredDepth / TransCG / synthetic |
| belief update 降低失败 | simulated anchors / views / probes under sensing budget |
| sensing cost 与 success tradeoff 可控 | success-risk-cost curve |

### 主要风险

- `needs-feasibility-check`: 完整 POMDP 可能过重。
- `venue-mismatch`: 若没有真实系统，容易像概念框架。
- `design-fixable`: 需要一个非常简洁的 belief 表示，否则论文会散。

### 最小落地版本

不要一开始做全 POMDP。先做：

```text
belief = K contact depth hypotheses + probabilities
action = grasp or query one sparse anchor
policy = expected risk reduction
```

这与 Idea C 可以合并。

## 10. 组合路线建议

不要同时做 8 个 idea。更实际的是组合成 3 条可投稿路线。

### 路线 1：Benchmark-first

```text
Idea A + v4 ContactDepthPack as baseline method
```

主贡献：

```text
Transparent Grasp Geometry Benchmark / Evaluator
```

适合条件：

- 短期没有真实机器人。
- 能较快跑 TransCG / ReMake / DFNet / MOMA-style baseline。
- 想先产出可靠、可复现、可支撑后续论文的资产。

风险：

```text
工程味重，必须有清晰 failure taxonomy 和 baseline 反直觉发现。
```

### 路线 2：Selective / Safe Grasping

```text
Idea B + Idea G + v4 ContactDepthPack
```

主贡献：

```text
Risk-calibrated action-conditioned transparent grasping
```

适合条件：

- 可以做较强离线 grasp proxy。
- 可能补少量真实机器人验证。
- 想让论文从 depth 走向 decision。

风险：

```text
没有真实 grasp 时，risk policy 的说服力依赖 proxy 设计。
```

### 路线 3：Active Information Acquisition

```text
Idea C + Idea H + v4 ContactDepthPack
```

主贡献：

```text
Active sparse anchoring / probing for transparent object grasping
```

适合条件：

- 愿意做系统实验或至少做高质量 simulated anchor acquisition。
- 想避开 ReMake / MOMA 的直接 depth completion 战场。
- 可以承受更高实现复杂度。

风险：

```text
系统工作量最大，但贡献上限也更高。
```

### 路线 4：Representation-first

```text
Idea D + Idea G
```

主贡献：

```text
Depth-free / depth-light contact affordance representation for transparent grasping
```

适合条件：

- 有 grasp planner 或 grasp simulation。
- 想彻底摆脱“又一个 depth completion”定位。

风险：

```text
需要强 label 或真实/simulated grasp evidence，否则容易变成 affordance proxy。
```

### 路线 5：Data-engine-first

```text
Idea E + Idea F
```

主贡献：

```text
Transparent sensor failure generation and counterfactual contact supervision
```

适合条件：

- 有能力做仿真、渲染或数据生成。
- 想形成可复用资产和长期方向。

风险：

```text
物理真实性和真实分布校准是主要挑战。
```

## 11. 当前更值得保留的核心 insight

不管选哪条路线，下面这个 insight 应该保留：

```text
透明物体的问题不是“缺一张更好看的 depth map”，
而是机器人动作需要在多种不兼容几何解释之间做有风险的选择。
```

对应地，`ContactDepthPack` 最好不要当论文主贡献，而应当降级为通用中间表示：

```text
ContactDepthPack is the representation.
The paper contribution should be benchmark, selective decision, active anchoring,
or action-conditioned perception.
```

## 12. 眼下最推荐继续推进的两个方向

这不是严格排名，而是基于当前仓库资产的开发路线判断。

### 方向 X：Transparent Grasp Geometry Benchmark + Failure Taxonomy

原因：

- 直接利用当前已复现的 TransCG / ReMake smoke test。
- 不依赖立刻训练新模型。
- 可以先把“贡献不够大”的问题转成“社区现在评测错了什么”。
- 后续所有方法 idea 都能吃这个 evaluator。

最小 2 周目标：

```text
下载 TransCG 子集
跑 raw / DFNet / ReMake / affine / MOMA-style
实现 background-as-contact、contact patch normal、collision proxy、risk-coverage
产出一张 failure taxonomy 表和 10 个强 qualitative case
```

### 方向 Y：Active Sparse Anchoring / Selective Grasping

原因：

- 能避开 ReMake 的“同输入补全网络”优势。
- 能把 MOMA 从强威胁变成对照：MOMA 给定 anchors，我们研究 anchors 应该怎么选、何时该获取。
- 机器人贡献更明显，因为它引入 sensing/action cost。

最小 2 周目标：

```text
用 TransCG GT 模拟 sparse depth query
比较 random / grid / uncertainty / contact-risk-aware anchor selection
看 1/3/5 anchors 下 grasp proxy 是否明显改善
```

## 13. 下一步决策 gate

建议先用实验而不是口号决定路线：

```text
Gate 1:
  如果 baseline 的 RMSE 排序与 grasp proxy 排序明显不一致，
  优先走 Benchmark-first。

Gate 2:
  如果 C_grasp 能有效筛掉高失败候选，
  优先走 Selective / Safe Grasping。

Gate 3:
  如果少量 simulated anchors 能显著减少 transparent grasp proxy failure，
  优先走 Active Sparse Anchoring。

Gate 4:
  如果 direct affordance label 比 depth proxy 更能解释 grasp failure，
  再考虑 Depth-Free Contact Affordance。
```

## 14. 文档结论

对“contribution 是不是不够大”的直接回答：

```text
是的，若 v4 只作为一个多头 depth model，贡献不够大。
但 v4 的核心洞察可以升级：
不要把 ContactDepthPack 当终点，把它当成支撑 benchmark、selective decision、
active anchoring 或 action-conditioned perception 的中间表示。
```

最值得优先发展的更大问题：

```text
How should a robot measure, decide, and act under transparent-depth ambiguity?
```

这比：

```text
How can we predict a better transparent depth map?
```

更像机器人抓取领域的核心贡献。

