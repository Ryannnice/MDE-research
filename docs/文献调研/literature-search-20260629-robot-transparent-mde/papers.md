# Literature Search: 机器人透明物体抓取中的 MDE 与 Depth Correction

Date: 2026-06-29

Search purpose: 调研“面向具体机器人应用场景思考 MDE”，重点是透明/反光物体抓取中由于传感器深度缺失、错深度、折射/反射导致的 depth correction 问题，并把机会点转化为 A2 可用 idea。

Target venue/family: 默认按 CCF-A 的 CVPR/ICCV/AI/CV 视角组织；机器人抓取实验可服务 ICRA/CoRL/RSS/RAL，但这些不在当前 CCFA venue map 的 CCF-A 列表内。

Source-quality policy: 已应用。优先 arXiv、CVF/ECVA、PMLR、IEEE RA-L/ICRA 信息页、项目页；MDPI 来源未纳入。

Local folder:

- `pdfs/`: 已下载 23 个 PDF。
- `papers.csv`: 逐篇表格和质量标签。
- `download_manifest.tsv`: 下载来源清单。

## Summary

- 核心结论 1: “透明物体抓取需要 depth correction”不是空白方向。ClearGrasp、LIDF、TransCG、DREDS、ReMake、AISPO 已经把 RGB-D depth completion/restoration 和真实抓取做成成熟主线。
- 核心结论 2: 2025-2026 的新趋势把 MDE foundation model 直接放进透明/非朗伯场景，例如 MOMA、MODEST、ReMake、SeeClear、SeeGroup、AISPO。因此 A2 若切入这个场景，不能只说“用单目深度补透明物体”，必须强调 metric grounding、采样期注入、物理可用深度、以及同源后处理对照。
- 核心结论 3: 多层深度正在成为新门槛。LayeredDepth 与 SeeGroup 说明透明物体不是天然单层 depth 问题；抓取到底需要前表面、后表面、背景层还是接触面，必须在任务定义中明确。
- 最适合 A2 的切口: 把透明/反光物体作为 metric-depth failure slice，而不是把整篇论文变成“透明物体新模型”。A2 的强点是 training-free / near-single-step / sampling-time metric anchoring，应该和 ReMake/MOMA/AISPO/SeeClear 形成机制差异。

## Paper Table

| # | Title | Year | Venue/source | Link | Type | Overall | Notes |
|---|---:|---|---|---|---|---|
| 1 | Robotic Perception of Transparent Objects: A Review | 2024 | IEEE TAI / arXiv | [arXiv](https://arxiv.org/abs/2304.00157) | survey | A | 透明物体机器人感知总综述，覆盖分割、重建、位姿、多模态。 |
| 2 | Survey on Monocular Metric Depth Estimation | 2025 | arXiv | [arXiv](https://arxiv.org/abs/2501.11841) | survey | B | 补充 metric MDE 背景，强调相对深度到米制深度的部署问题。 |
| 3 | ClearGrasp | 2020 | ICRA / arXiv | [arXiv](https://arxiv.org/abs/1910.02550) | method + benchmark | A | RGB-D、法线/mask/边界预测、透明表面深度修正、真实抓取。 |
| 4 | RGB-D Local Implicit Function for Depth Completion of Transparent Objects | 2021 | CVPR / arXiv | [arXiv](https://arxiv.org/abs/2104.00622) | pure method | A | Local implicit depth completion，速度和泛化是关键卖点。 |
| 5 | Seeing Glass | 2021 | CoRL / PMLR | [PMLR](https://proceedings.mlr.press/v164/xu22b.html) | pure method | A | 联合点云与 depth completion，代表透明物体几何补全路线。 |
| 6 | Dex-NeRF | 2022 | CoRL / PMLR | [PMLR](https://proceedings.mlr.press/v164/ichnowski22a.html) | system/tool | B | 用 NeRF 支撑透明物体抓取，是多视图/主动感知高成本强基线。 |
| 7 | TransCG | 2022 | IEEE RA-L | [arXiv](https://arxiv.org/abs/2202.08471) | method + benchmark | A | 大规模真实透明物体 RGB-D depth completion 数据集和抓取 baseline。 |
| 8 | ClearPose | 2022 | ECCV | [ECVA PDF](https://www.ecva.net/papers/eccv_2022/papers_ECCV/papers/136680372.pdf) | pure benchmark | A | 透明物体数据集和 benchmark，适合泛化评测。 |
| 9 | DREDS / SwinDRNet | 2022 | ECCV | [ECVA PDF](https://www.ecva.net/papers/eccv_2022/papers_ECCV/papers/136990369.pdf) | method + benchmark | A | sim2real depth restoration，直接面向反光/透明物体抓取。 |
| 10 | Booster | 2023 | arXiv / benchmark | [arXiv](https://arxiv.org/abs/2301.08245) | pure benchmark | A | 高分辨率透明/镜面 depth benchmark，含 material masks。 |
| 11 | Challenges of Depth Estimation for Transparent Objects | 2023 | SSRR / TU Wien PDF | [PDF](https://repositum.tuwien.at/bitstream/20.500.12708/190761/1/Weibel-2023-Challenges%20ofDepth%20Estimation%20forTransparent%20Objects-am.pdf) | other | B | 问题陈述和挑战梳理，适合作为背景。 |
| 12 | Depth4ToM | 2023 | ICCV / arXiv | [arXiv](https://arxiv.org/abs/2307.15052) | pure method | A | 用 inpainting + MDE pseudo labels 适配透明/镜面区域。 |
| 13 | Transparent Object Depth Completion | 2024 | arXiv | [arXiv](https://arxiv.org/abs/2405.15299) | pure method | B | 融合 single-view RGB-D completion 与 multi-view depth。 |
| 14 | ASGrasp | 2024 | ICRA / arXiv | [arXiv](https://arxiv.org/abs/2405.05648) | system/tool | A | 主动立体 + 透明物体重建 + 6-DoF grasp。 |
| 15 | Towards Robust MDE in Non-Lambertian Surfaces | 2024 | arXiv | [arXiv](https://arxiv.org/abs/2408.06083) | pure method | A | 直接训练 MDE 处理透明/镜面 ToM 区域，是 MDE 适配近邻。 |
| 16 | ClearDepth | 2024 | arXiv / project | [arXiv](https://arxiv.org/abs/2409.08926) | method + benchmark | A | stereo ViT + Sim2Real，面向透明物体机器人操作。 |
| 17 | LayeredDepth | 2025 | arXiv / dataset | [arXiv](https://arxiv.org/abs/2503.11633) | pure benchmark | Risk | 多层透明深度数据，挑战单层 depth 假设。 |
| 18 | MODEST | 2025 | arXiv | [arXiv](https://arxiv.org/abs/2502.14616) | pure method | A | 单 RGB 同时做透明物体分割与深度估计。 |
| 19 | MOMA | 2025 | arXiv | [arXiv](https://arxiv.org/abs/2506.17110) | system/tool | Risk | one-shot sparse depth calibration 将 affine-invariant MDE 对齐到 metric，用于真实抓取。 |
| 20 | ReMake | 2026 | IEEE RA-L / arXiv | [arXiv](https://arxiv.org/abs/2508.02507) | pure method | Risk | instance mask + MDE 引导 RGB-D depth completion，专门服务透明物体抓取。 |
| 21 | SeeClear | 2026 | arXiv / project | [arXiv](https://arxiv.org/abs/2603.19547) | pure method | Risk | 生成式 opacification 后接 off-the-shelf MDE，直接解决透明外观不稳定。 |
| 22 | SeeGroup | 2026 | arXiv / CVPR 2026 | [arXiv](https://arxiv.org/abs/2605.28735) | pure method | Risk | 多层 depth 的 unordered event/point-process 建模。 |
| 23 | AISPO | 2026 | IEEE RA-L 11(7) forthcoming / arXiv | [arXiv](https://arxiv.org/abs/2606.25503) | pure method | Risk | affine-invariant shape prior 强化非朗伯物体深度物理可用性。 |

## Clusters

### Cluster 1: RGB-D Depth Completion / Restoration for Transparent Grasping

- Representative papers: ClearGrasp, LIDF, Seeing Glass, TransCG, DREDS, Transparent Object Depth Completion, ReMake, AISPO.
- Already solves: 传感器原始 depth 在透明区域缺失/错深度，RGB-D 网络可通过 mask、normal、implicit representation、MDE prior、shape prior 或 sim2real 数据恢复更可用的深度。
- Remaining gap: 很多工作以 post-hoc restoration 为主，较少直接比较“采样期注入 vs 同源后处理”；物理可用性通常用抓取成功率补充，但 metric/affine 协议和透明 mask 内指标不总是统一。
- Possible rescue/differentiation route: A2 可以把透明物体作为 `metric zero-align + affine 对照 + transparent slice + grasp proxy` 的强 failure slice，证明 sampling-time metric anchoring 不是 patch/instance-mask 后处理。
- How it affects A2: ReMake 与 AISPO 是最近威胁；A2 必须保留 L1 的 patch-wise 后处理门槛，并加入透明/反光 slice。

### Cluster 2: Datasets, Benchmarks, and Protocols

- Representative papers: TransCG, ClearPose, Booster, Challenges of Depth Estimation, LayeredDepth.
- Already solves: 透明物体真实 RGB-D、synthetic-to-real、material masks、高分辨率非朗伯评测、多层 depth 标注开始出现。
- Remaining gap: 单目/MDE foundation models 在透明抓取场景下缺少统一的 metric/affine 双协议；LayeredDepth 暴露“透明物体到底是哪一层 depth”的任务定义问题。
- Possible rescue/differentiation route: 做一个轻量 protocol paper 或 A2 附加评测：同一模型在全图、透明 mask、边界、无锚区、多层冲突区分别报告 metric 和 affine。
- How it affects A2: 如果 A2 只在 NYU/KITTI 讲 metric grounding，透明物体场景能成为更有应用说服力的压力测试。

### Cluster 3: Monocular / Foundation MDE Adaptation to Non-Lambertian Surfaces

- Representative papers: Depth4ToM, Robust MDE in Non-Lambertian Surfaces, MODEST, MOMA, ReMake, SeeClear.
- Already solves: 通过 pseudo labels、专门训练、mask/MDE 引导、one-shot calibration、生成式 opacification，把普通 MDE 拉向透明/镜面区域。
- Remaining gap: 多数方法需要训练、额外 mask、专门数据、生成模块或校准流程；对 `nfe_real`、采样成本、training-free 限制的讨论不足。
- Possible rescue/differentiation route: A2 的差异可以写成 training-free sampling-time metric correction on frozen depth priors，而不是 another transparent-depth network。
- How it affects A2: MOMA 是最危险近邻，因为它已经把 sparse depth calibration 和 RGB-only grasp 绑定；A2 需要强调 CCF/采样轨迹机制与同源后处理对照。

### Cluster 4: Multi-View, Stereo, NeRF, and Active Perception

- Representative papers: Dex-NeRF, ASGrasp, ClearDepth, Transparent Object Depth Completion.
- Already solves: 在更强传感器或多视角条件下，透明物体几何恢复和抓取可以明显更稳。
- Remaining gap: 多视图/stereo/NeRF 的设备、时间、标定和主动扫描成本高；不一定适合低成本 RGB 或 near-single-step 场景。
- Possible rescue/differentiation route: A2 可以主打低成本单图/少锚场景，但需要在实验里承认 stereo/active sensing 是上界或不同部署点。
- How it affects A2: 不要宣称替代主动感知，只宣称在“单图或极少锚”的部署约束下更好地修正 metric depth。

### Cluster 5: Multi-Layer Transparent Depth

- Representative papers: LayeredDepth, SeeGroup.
- Already solves: 透明物体 depth 可是多层结构，固定前后顺序并不总合理。
- Remaining gap: 机器人抓取究竟消费哪一层 depth 仍需任务化定义，可能是接触面、可见表面、遮挡后物体或安全碰撞包络。
- Possible rescue/differentiation route: 将 A2 从“恢复唯一真 depth”收窄为“恢复 grasp-relevant contact surface metric depth”，并把多层场景作为失败/局限。
- How it affects A2: 这是写作边界的关键。单层 metric depth claim 必须加限定，否则会被 SeeGroup/LayeredDepth 质疑。

## Opportunity Map

| Cluster | Status | Open gap | Possible direction | Evidence needed | Risk |
|---|---|---|---|---|---|
| RGB-D depth correction | crowded but open | 采样期 metric anchoring 与 post-hoc restoration 的单变量对照不足 | A2-transparent slice：同源锚、同源基底，比较 sampling-time vs patch/mask postprocess | TransCG/ClearPose/Booster + metric/affine + transparent mask + no-anchor region | ReMake/AISPO 近邻很强 |
| Benchmark/protocol | benchmark gap | foundation MDE 在透明抓取下缺少统一 metric/affine/physical-plausibility 协议 | 透明/反光 failure-slice benchmark for MDE foundation models | Depth Anything V2、Marigold/E2E-FT、Metric3D、UniDepth、Depth Pro、A2 | 可能更像 benchmark paper，方法贡献弱 |
| MDE adaptation | crowded but open | 训练/生成/校准方法多，但 training-free frozen diffusion sampling 仍少 | frozen MDE diffusion with sparse robot anchors | L0/L1/L2/diag gates + ReMake/MOMA/SeeClear 对照 | MOMA 已覆盖 one-shot metric alignment |
| Active/stereo/NeRF | deployment-system gap | 设备成本高，低成本 RGB/少锚方案仍有价值 | 单 RGB + table/contact/sparse-depth anchors 的低成本抓取 depth correction | 真实桌面抓取或离线 grasp proxy | 机器人实验成本高 |
| Multi-layer depth | mechanism gap | 单层 depth 与透明物体物理结构冲突 | contact-surface depth rather than visible-depth | LayeredDepth/SeeGroup + grasp label or contact proxy | 任务定义难，数据不足 |

## Benchmark And Dataset Candidates

| Name | Link | Task | Metrics | Baselines | Fit | Risks |
|---|---|---|---|---|---|---|
| TransCG | [arXiv](https://arxiv.org/abs/2202.08471) | 透明物体 depth completion + grasp baseline | depth error、mask/surface metrics、grasp proxy | ClearGrasp、LIDF、TransCG baseline、ReMake | 最贴近透明抓取 | 主要是 RGB-D correction，不是纯 MDE |
| ClearPose | [ECVA PDF](https://www.ecva.net/papers/eccv_2022/papers_ECCV/papers/136680372.pdf) | 透明物体数据/benchmark | depth/pose/reconstruction 相关 | ClearGrasp、LIDF 等 | 泛化与遮挡测试 | 数据协议需细读 |
| Booster | [arXiv](https://arxiv.org/abs/2301.08245) | 透明/镜面 MDE/stereo depth benchmark | material mask 内深度误差、全图误差 | Depth Anything、Metric3D、Depth4ToM、Robust MDE | 非朗伯 failure slice 很强 | 不是抓取数据 |
| LayeredDepth | [arXiv](https://arxiv.org/abs/2503.11633) | 多层透明 depth | multilayer/relative depth 指标 | LayeredDepth baselines、SeeGroup | 检验单层 claim 边界 | A2 单层输出天然吃亏 |
| SeeGroup / Layered transparent setting | [arXiv](https://arxiv.org/abs/2605.28735) | unordered multi-layer depth | permutation-invariant 多层指标 | SeeGroup | 定义 contact-surface vs multilayer 的理论边界 | 数据和任务转化成本高 |
| Real robot tabletop grasp | MOMA/ReMake/ASGrasp/AISPO papers | 抓取成功、碰撞、pose/grasp validity | grasp success、invalid grasp ratio、depth physical plausibility | MOMA、ReMake、AISPO、ASGrasp | 应用说服力最大 | 本地未跑，所有结果必须写待跑 |

## Citation And Positioning Cautions

- 透明抓取 depth correction 主线已被 ClearGrasp、TransCG、DREDS、ReMake、AISPO 覆盖，不能把“透明物体需要 depth correction”当 novelty。
- 单目/MDE 透明物体近作已很密集：Depth4ToM、MODEST、Robust Non-Lambertian MDE、MOMA、SeeClear。A2 必须把 novelty 放在 training-free sampling-time metric anchoring，而不是普通 MDE adaptation。
- MOMA 与 A2 最像：都是用少量真实 depth/sparse calibration 将 affine-invariant MDE 拉到 metric depth。A2 必须用 L1 gate 证明 sampling-time 注入优于 post-hoc scale/shift/patch affine。
- ReMake 与 AISPO 是 transparent grasping 的直接威胁：都强调物理可用的深度和真实抓取。A2 如果只报 AbsRel，会显得离应用还差一步。
- LayeredDepth/SeeGroup 会挑战“唯一 ground-truth depth”的假设。A2 论文中应限定输出为单层 metric depth，若进入透明抓取，应进一步限定为 contact-surface 或 grasp-relevant surface。
- Depth Anything V2、Metric3D、UniDepth、Depth Pro、Marigold/E2E-FT、DepthFM、AnchorD、Defocus-Marigold 仍需作为 MDE reviewer threats。透明物体场景不能替代 A2 原有 L0/L1/L2/diag gates。

## Downloaded PDFs

已下载并用 `pypdf` 抽检页数/标题片段的 PDF 数量: 23。

失败或未纳入:

- `2021_cvpr_lidf_transparent_depth_completion.pdf`: CVF 直链文件名失败，已用 arXiv 备份 `2104.00622` 下载。
- `2023_depth4tom_transparent_mirror_surfaces.pdf`: 机构镜像失败，已用 arXiv `2307.15052` 下载。
- `2026_seegroup_multilayer_depth_cvf.pdf`: CVF 2026 直链失败，已用 arXiv `2605.28735` 下载。
- `2026_beyond_rgbd_glass_mirrors_see_through_review.pdf`: 仓储直链失败，未纳入主表。
