# Idea Cards: 面向透明物体抓取的 MDE / A2 研究方向

Date: 2026-06-29

Mode: standard idea optimization after literature search.

Venue lens: 默认按 CCF-A CVPR/ICCV/AI/CV 口径打磨问题、机制和证据；机器人抓取实验作为应用证据。若主投稿机器人方向，可转 ICRA/CoRL/RSS/RAL，但不把这些直接称为 CCF-A。

Raw seed: “瞄准具体机器人应用场景来思考 MDE，比如透明物体抓取，一般需要矫正 depth。”

Known closest-work risks: ClearGrasp, LIDF, TransCG, DREDS, MOMA, ReMake, SeeClear, AISPO, LayeredDepth, SeeGroup.

## Raw Idea Diagnosis

这个 seed 的价值不在“透明物体需要 depth correction”本身。这个结论已经被 ClearGrasp、TransCG、ReMake、AISPO 等工作覆盖。真正可能有价值的是把透明抓取变成 A2 的高压应用场景：在 RGB-D 传感器失效或只允许 RGB/少量锚的条件下，测试 sampling-time metric anchoring 是否比后处理更能把少量可靠几何传播到透明 mask 内、边界附近和无锚区域。

最危险的 novelty overlap 是 MOMA 和 ReMake。MOMA 已经把 affine-invariant MDE 通过 one-shot sparse depth calibration 对齐到 metric 并用于真实抓取；ReMake 已经用 instance mask + MDE 引导透明物体 RGB-D depth completion。A2 必须避开“又一个 MDE+mask correction”的表述，主张应收窄为：冻结深度先验、近单步、采样期注入、同源后处理对照、透明 failure slice。

## Candidate 1: Transparent-Grasp Metric Anchoring for Frozen Diffusion Depth

Development label: `needs-evidence`, best A2-compatible route.

Task: 给透明/反光物体抓取场景中的单图或 RGB-D 失效区域恢复 grasp-relevant metric depth。

Gap: 现有透明 depth completion 多为 RGB-D post-hoc restoration；MOMA 做 one-shot metric alignment，但不测试扩散/MDE 采样期注入是否比等价后处理更能传播 metric 修正。

Root challenge: 透明区域的观测 depth 常指向背景或缺失，relative MDE 又没有可靠绝对尺度；少量可信锚如果只在输出后拟合，容易在透明区域内部和边界处无法传播。

Core insight: 把机器人场景中的可靠几何锚，如桌面、非透明邻域、少量真实 depth、接触/夹爪校准点，作为 sampling-time metric constraint 注入冻结扩散深度轨迹，让模型先验在去噪过程中传播到无锚透明区域。

Proposed mechanism:

- 输入: RGB，透明/反光 mask 可选，稀疏锚来自 oracle GT、有效 RGB-D 非透明区、桌面平面或 one-shot calibration。
- 骨干: Marigold/E2E-FT/Lotus/DepthFM 等冻结深度先验。
- 核心操作: 沿用 A2 proxy-anchored CCF + 几何锚采样期烘焙。
- 对照: 全局 affine、patch-wise affine、AnchorD-like 后处理、MOMA-style sparse alignment、ReMake/AISPO-like depth completion。
- 输出: 单层 grasp-relevant metric depth，限定为接触/前表面，不声称完整多层透明重建。

Contribution type: 方法 + 应用 failure-slice 评测。

Evidence package:

- L0: CCF 不是单点 x0 或多噪声平均装饰，按 A2 原 gate。
- diag: bias-var 证明不是只降方差，按 A2 原 gate。
- L1: 在 TransCG/ClearPose/Booster 透明 mask 内，sampling-time 注入优于同源 patch-wise 后处理。
- L2: 报 `nfe_real`，验证 near-single-step 是否仍可用。
- 机器人相关: 离线 grasp proxy 或真实 tabletop grasp success，当前全部 `待跑`。

Reviewer risks:

- `requires-new-result`: 必须真正跑透明 slice，否则只是应用包装。
- `design-fixable`: 透明 mask 来源若太强，会被 ReMake/MODEST 压住；需有 mask-free 或 mask-noisy 消融。
- `evidence-fixable`: 必须同时报 metric 和 affine，防止“假米制”。
- `likely-pivot`: 如果 L1 不赢 patch-wise affine，透明应用会削弱 A2 主张。

## Candidate 2: Transparent MDE Foundation-Model Failure Slice Benchmark

Development label: `salvageable`, conservative benchmark/protocol route.

Task: 建立 MDE foundation models 在透明/反光/机器人深度矫正场景中的统一 failure-slice 协议。

Gap: Depth Anything V2、Metric3D、UniDepth、Depth Pro、Marigold/E2E-FT、DepthFM、MOMA/ReMake/AISPO 常在不同协议、数据和任务上报告，缺少统一 metric/affine 双协议与透明 mask 内切片。

Root challenge: 对齐协议会掩盖 metric failure；透明区域又有背景层/前表面/多层冲突，普通全图 AbsRel 不足以解释抓取风险。

Core insight: 与其先做新模型，不如先把“透明抓取到底如何评价 MDE”定义清楚，形成 reviewer 难以回避的 protocol contribution。

Proposed mechanism:

- 数据: TransCG、ClearPose、Booster、LayeredDepth。
- 模型: Depth Anything V2、Metric3D、UniDepth、Depth Pro、Marigold/E2E-FT、DepthFM、MOMA/ReMake/AISPO 若代码可用。
- 协议: metric zero-align 主表，affine-invariant 对照，透明 mask、边界、无锚区、遮挡/多层冲突区单独报告。
- 物理指标: invalid grasp proxy、contact-surface error、depth discontinuity sanity、平面/碰撞可行性。

Contribution type: benchmark/protocol + empirical finding.

Evidence package:

- `待跑` foundation model 统一评测。
- `待跑` 协议敏感性：metric vs affine、全图 vs mask 内、单层 vs 多层。
- `待跑` A2 作为一个 method row，检验是否因采样期锚定改善 transparent slice。

Reviewer risks:

- `venue-mismatch`: 纯 benchmark 若没有新数据或惊人发现，CVPR/ICCV 主会风险高。
- `design-fixable`: 可以把它变成 A2 的强附录/诊断章节，而不是独立 paper。
- `requires-new-result`: 需要大量模型可跑性与协议复现。

Best use: 作为 A2 的实验扩展和审稿防线，优先级高于独立立项。

## Candidate 3: Contact-Surface Depth Instead of Single Visible Depth

Development label: `needs-mechanism`, ambitious reframing.

Task: 针对透明物体抓取，预测机器人真正消费的 contact-surface metric depth，而不是普通单层可见深度。

Gap: LayeredDepth 和 SeeGroup 指出透明物体有多层深度；但机器人抓取并不一定需要全部层，可能需要可接触外表面、碰撞包络或稳定吸附/夹持 surface。

Root challenge: 视觉 ground truth 和操作 ground truth 不一致。背景层 depth 对图像解释有意义，但对抓取会误导；前表面/后表面/厚度又可能难以从单图唯一确定。

Core insight: 把透明深度从“恢复物理所有层”改成“恢复下游动作需要的那一层”，用 grasp/contact 约束选择 depth hypothesis。

Proposed mechanism:

- 基础 MDE 输出 relative/metric candidates。
- 多层先验来自 LayeredDepth/SeeGroup 或多 seed diffusion uncertainty。
- 接触选择器使用 mask、边界、桌面、抓取候选、碰撞检测、少量 tactile/contact 锚。
- A2 的 metric anchor 用于把被选 surface 校到米制尺度。

Contribution type: new problem setting + method.

Evidence package:

- LayeredDepth/SeeGroup 上的多层候选质量，`待跑`。
- TransCG/ClearPose 上的 contact-surface proxy，`待跑`。
- 真实抓取或模拟 grasp validity，`待跑`。

Reviewer risks:

- `needs-domain-constraint`: contact-surface label 怎么来是最大问题。
- `requires-new-result`: 可能需要新标注或机器人实验。
- `design-fixable`: 首版可以只作为 A2 讨论/失败模式，不一定主攻。

Best use: 中长期方向。若有机器人资源或可构造 contact proxy，可以变成更独特的 paper。

## Candidate 4: Generative Opacity as an Uncertainty Probe for Metric Anchoring

Development label: `near-pivot`, risky but interesting.

Task: 使用透明区域的多种“变不透明”生成候选来估计透明深度不确定性，并把不确定性引导到 metric anchoring。

Gap: SeeClear 已经提出 generative opacification + off-the-shelf MDE。直接复刻没有新意。但 SeeClear 更像生成一个稳定 opaque view 后跑 MDE，未必把生成多样性转成可校准的不确定性和锚传播策略。

Root challenge: 透明区域的 RGB 外观不是物体表面纹理，单次 opacification 可能把错误外观固定成错误深度。

Core insight: 不把 opacification 当确定预处理，而是把多个生成候选当作 depth hypothesis ensemble；与 sparse metric anchors 一起选择/校准更物理合理的候选。

Proposed mechanism:

- 透明 mask 或 detector 定位。
- 生成多个 opaque candidates。
- 每个 candidate 跑 frozen MDE/Marigold。
- 用锚一致性、边界连续性、桌面/重力/碰撞约束对候选加权。
- 输出 metric depth + uncertainty。

Contribution type: empirical diagnostic + method.

Evidence package:

- 与 SeeClear 单次 opacification、Depth4ToM、MODEST、ReMake 比较，`待跑`。
- 不确定性 calibration: risk-coverage、transparent mask 内高错误召回，`待跑`。
- A2 采样期锚是否比输出端加权更有效，`待跑`。

Reviewer risks:

- `covered central claim`: SeeClear 已覆盖 opacification 主线。
- `design-fixable`: 只有当多候选不确定性和 A2 锚定有清晰增益时才值得推进。
- `requires-new-result`: 需要生成模型工程，成本可能偏高。

Best use: 如果 A2 原路线在透明 slice 上失效，可作为 rescue/pivot；不建议当前主攻。

## Candidate 5: One-Shot Robot Calibration as A2 Anchor Source

Development label: `salvageable`, practical engineering route.

Task: 用一次性机器人/相机标定或少量可信深度点作为 A2 的真实 anchor source，让 frozen MDE 在具体机器人工作站中输出 metric depth。

Gap: A2 当前先用公开数据集 GT 稀疏采样做 oracle 机制验证；真实锚源还待替换。MOMA 已经证明 one-shot sparse depth calibration 对 RGB-based grasping有应用价值，但没有 A2 的扩散采样期机制。

Root challenge: 真实部署不能依赖 dense GT。必须把锚源从 oracle 迁移到真实可获得信号，如桌面平面、相机内参、非透明区域有效 RGB-D、已知标定板、夹爪接触点。

Core insight: A2 的“几何锚”可以落地为机器人工作站的少量稳定几何事实，而透明物体抓取正是最需要这种锚的场景。

Proposed mechanism:

- 锚源 1: table plane + camera calibration。
- 锚源 2: 非透明区域 RGB-D valid points。
- 锚源 3: one-shot 标定物/夹爪触碰点。
- 锚源 4: object-size prior 或 grasp candidate contact height，作为弱锚。
- 与 A2 `sample_sparse_oracle` 分离，新增 real-anchor simulation layer。

Contribution type: system design + method validation.

Evidence package:

- Oracle anchors vs realistic anchors 的 gap，`待跑`。
- anchor count/noise/dropout sweep，`待跑`。
- MOMA-style post-hoc alignment vs A2 sampling-time injection，`待跑`。
- `nfe_real` 和 latency，`待跑`。

Reviewer risks:

- `covered central claim`: MOMA 已经很近。
- `design-fixable`: 需要把区别钉在采样期机制和同源后处理，而不是“我也用少量锚”。
- `evidence-fixable`: 若没有机器人或真实数据，至少需要 TransCG/ClearPose 上的锚模拟严谨。

Best use: 与 Candidate 1 合并，作为 A2 透明抓取版的 anchor-source chapter。

## Best Development Route

最建议当前推进的是 Candidate 1 + Candidate 5 的组合：

题目草案: `Transparent-Grasp Metric Anchoring: Training-Free Sampling-Time Depth Correction for Frozen Diffusion MDE`

一句话: 在透明/反光物体抓取场景中，用少量机器人可得几何锚在冻结扩散深度采样期注入 metric constraint，证明它比同源 post-hoc patch/mask alignment 更能修正透明区域和无锚区域的 grasp-relevant metric depth。

为什么它最贴 A2:

- 直接复用 A2 的 L0/L1/L2/diag gate。
- 透明物体是 A2 已有 failure slice，不是凭空换题。
- ReMake/MOMA/AISPO 虽强，但它们反而提供了清晰对照：后处理/校准/shape prior vs 采样期注入。
- 机器人应用场景能解释为什么 metric 协议比 affine-invariant 协议更重要。

最小可行实验:

| Stage | Dataset / setting | Claim | Baselines | Status |
|---|---|---|---|---|
| S0 | A2 原 NYU/KITTI 或 mock | 原 gate 不破 | A2 原臂 | 待跑 |
| S1 | TransCG / ClearPose | 透明 mask 内 metric depth correction | ClearGrasp、LIDF、TransCG baseline、patch affine、ReMake/AISPO 若可跑 | 待跑 |
| S2 | Booster | 非朗伯 MDE failure slice | Depth Anything V2、Metric3D、UniDepth、Depth Pro、Marigold/E2E-FT、Depth4ToM、Robust MDE | 待跑 |
| S3 | LayeredDepth / SeeGroup subset | 单层 contact-surface claim 边界 | single-layer MDE、SeeGroup | 待跑 |
| S4 | Robot/grasp proxy | 修正深度是否减少 invalid grasp | MOMA、ReMake、AISPO、ASGrasp/ClearDepth 作为不同传感器上界 | 待跑 |

## Claim Boundaries

- 可以声称: 面向透明/反光 failure slice 的 training-free sampling-time metric correction 机制。
- 暂不声称: 解决所有透明物体完整光学重建。
- 暂不声称: 超过 stereo、active sensing、NeRF 在所有机器人设置下的性能。
- 必须报告: metric 主表、affine 对照、transparent mask slice、no-anchor region、`nfe_real`、后处理同源对照。
- 必须保留: 失败模式。透明多层、强折射、遮挡严重、mask 错误、锚稀疏或偏置时都应单独写。

## Next Work Queue

1. 在 A2 failure slices 中把透明/反光从合成 mask 扩展到 TransCG/ClearPose/Booster 的真实 mask。
2. 增加 `transparent_mask_absrel`、`transparent_boundary_rmse`、`no_anchor_transparent_absrel`、`contact_surface_proxy` 占位指标。
3. 增加 realistic anchor simulator: table plane、valid RGB-D non-transparent points、one-shot sparse calibration、anchor noise/dropout。
4. 跑 `patch affine`、`MOMA-style global/scale-rotation-shift`、`ReMake/AISPO if available` 的后处理对照。
5. 所有数字保持 `待跑`，直到真实 CSV 存在。
