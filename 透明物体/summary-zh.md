# 机器人透明物体 MDE 与 Depth Correction 调研总结

日期：2026-06-30

本总结基于同目录 `literature-spec.md`、`papers.md`、`papers.csv` 和 `search-notes.md`。目标不是写透明物体综述，而是判断透明/反光物体抓取是否适合成为 A2 的应用 failure slice，以及哪些近作会压住 A2 的 novelty。

## 一句话结论

透明物体抓取中的 depth correction 不是空白方向。ClearGrasp、LIDF、TransCG、DREDS 已经把 RGB-D 透明深度恢复和抓取 baseline 做成熟；Depth4ToM、MODEST、MOMA、ReMake、SeeClear、AISPO 又把 MDE、mask、one-shot metric alignment、生成式 opacification 和 affine-invariant shape prior 接进透明/非朗伯场景。A2 如果要用这个场景，最安全的定位不是“做透明物体深度估计”，而是把透明/反光物体作为验证 sampling-time metric anchoring 的高压 failure slice。

## 当前最值得优先读的论文

| 优先级 | 论文/资源 | 为什么先读 | 跟进建议 |
|---|---|---|---|
| 1 | [MOMA](https://arxiv.org/abs/2506.17110) | 单 RGB + one-shot sparse metric alignment + UR5 grasping，和 A2 稀疏锚/metric grounding 最像 | 必读；必须做 MOMA-style post-hoc/SRS 对照 |
| 2 | [ReMake](https://arxiv.org/abs/2508.02507) | 透明抓取 + MDE + instance mask + RGB-D completion，代码、checkpoint、训练成本明确 | 强跟进；作为透明抓取直接 baseline |
| 3 | [SeeClear](https://arxiv.org/abs/2603.19547) | 生成式 opacification + off-the-shelf MDE，直接压住“透明预处理再跑 MDE”路线 | 强观察；等权重/数据，先读方法边界 |
| 4 | [LayeredDepth](https://arxiv.org/abs/2503.11633) + [SeeGroup](https://arxiv.org/abs/2605.28735) | 多层透明深度会挑战“唯一真 depth”的假设 | 必读；A2 需限定 contact/front/grasp-relevant surface |
| 5 | [MODEST](https://arxiv.org/abs/2502.14616) | 单 RGB 联合透明分割和深度，代码与 RTX 4090 环境公开 | 若 A2 用 mask/semantic 先验，必须对照或解释 |
| 6 | [TransCG](https://arxiv.org/abs/2202.08471) | 57,715 张真实透明 RGB-D，含抓取 baseline，是透明 failure slice 首选数据 | 作为第一批离线数据源 |
| 7 | [Booster / NTIRE 2026](https://cvlab-unibo.github.io/booster-web/ntire26.html) | 高分辨率非朗伯 benchmark；2026 mono track 明确 metric depth/cm RMSE | 用来区分 metric 协议和 affine 对齐协议 |
| 8 | [ClearGrasp](https://arxiv.org/abs/1910.02550) + [LIDF](https://arxiv.org/abs/2104.00622) | 经典 RGB-D post-hoc completion baseline | related work 和 L1 post-hoc 门槛不能绕过 |
| 9 | [AISPO](https://arxiv.org/abs/2606.25503) | affine-invariant shape prior + 非朗伯机器人 manipulation，与 A2 概念相邻 | 代码未找到，先强观察 |

## 分层判断

### 第一层：A2 直接威胁

- MOMA：已经把稀疏真实 depth calibration、metric MDE 和机器人抓取绑定。A2 必须证明采样期注入优于输出端 sparse calibration。
- ReMake：已经把 instance mask、MDE relative depth、RGB-D completion 和透明抓取连起来。A2 不能只说“用 MDE 修透明物体”。
- AISPO：强调 affine-invariant shape prior 和机器人非朗伯 depth reliability，会挑战 A2 的 affine prior/物理可用深度表述。
- SeeClear：生成式 opacification 让透明区域变成稳定 opaque view，再接 MDE。任何生成式透明预处理路线都会被它覆盖。
- MODEST：单 RGB 透明 segmentation + depth 的直接近邻；A2 若依赖 mask，要把 mask 成本和误差计入。

### 第二层：数据与协议支柱

- TransCG：真实透明 RGB-D 和抓取 baseline，是透明 failure slice 的首选。
- ClearPose：透明物体 depth/normal/pose，多 adversarial split，适合外部泛化。
- Booster/NTIRE：高分辨率 ToM mask 和 mono/stereo challenge；2025 先 scale/shift 对齐，2026 明确 metric mono depth，这个差异对 A2 很重要。
- LayeredDepth/SeeGroup：多层深度要求 A2 限定单层输出的任务含义。

### 第三层：经典背景和系统上界

- ClearGrasp、LIDF、DREDS：经典 RGB-D completion/restoration 路线，定义后处理和 sim2real baseline。
- ASGrasp、Dex-NeRF、ClearDepth：active stereo/multi-view/NeRF 系统上界，A2 不能宣称替代这些部署点。
- Depth4ToM、Robust Non-Lambertian MDE：训练式 ToM MDE 适配，提醒 A2 必须突出 frozen/training-free 或低成本约束。

## 对 A2 的判断

A2 可以把透明/反光物体作为 application failure slice，但不适合把整篇论文改成“透明物体新模型”。更防守的研究问题是：

> 在透明/反光物体导致传感器深度失效、且只有少量可信几何锚的情况下，采样期 metric anchoring 是否比等价 post-hoc scale/shift/patch/mask alignment 更能把米制约束传播到透明 mask、边界和无锚区域？

这个问题比“透明物体需要 depth correction”更贴 A2，因为它正好对应 L1 gate、`nfe_real`、metric/affine 双协议和 failure-slice 诊断。

## 推荐实验路线

第一批不要上真实机器人，先做离线透明 failure slice：

| Stage | 数据 | 目标 | 对照 | 状态 |
|---|---|---|---|---|
| S1 | TransCG | 透明 mask 内 metric correction | raw depth、global affine、patch affine、MOMA-style SRS、ReMake if runnable | 待跑 |
| S2 | ClearPose | 遮挡/液体/非平面等泛化 slice | ClearGrasp/LIDF/TransCG baseline、MODEST if runnable | 待跑 |
| S3 | Booster/NTIRE | 非朗伯高分辨率 metric vs affine 协议 | Depth Anything V2、Metric3D、UniDepth、Depth Pro、Marigold/E2E-FT、Depth4ToM | 待跑 |
| S4 | LayeredDepth/SeeGroup | 单层 contact-surface claim 边界 | first-layer depth、多层 depth baseline | 待跑 |
| S5 | Robot/grasp proxy | depth 修正是否减少 invalid grasp | MOMA/ReMake/AISPO/ASGrasp 作为文献或可跑对照 | 待跑 |

## 必须保留的指标纪律

- metric 主表和 affine-invariant 对照分开报。
- transparent-mask、boundary、no-anchor transparent 区域单独报。
- `nfe` 和 `nfe_real` 分开写；mask predictor、opacification、rerank、depth completion 都计入 `nfe_real`。
- 所有机器人抓取成功率、invalid grasp、collision、latency 目前都是 `待跑`。
- 若 A2 透明 slice 不赢同源后处理对照，透明应用只能作为诊断失败模式，不应作为主贡献。

## 今天可以发给 guanhua 的短版

我重新细查了透明/反光物体抓取中的 MDE 和 depth correction。结论是这个方向非常拥挤：ClearGrasp/LIDF/TransCG/DREDS 是经典 RGB-D depth completion 主线；MOMA/ReMake/MODEST/SeeClear/AISPO 是 2025-2026 的直接威胁；LayeredDepth/SeeGroup 会从多层深度角度质疑单层 depth 定义。A2 最适合的切口不是做透明物体新模型，而是把透明/反光物体作为 metric anchoring 的 failure slice，检验采样期注入是否比等价 post-hoc scale/shift/patch/mask alignment 更能把少量锚传播到透明 mask、边界和无锚区域。第一批建议读 MOMA、ReMake、SeeClear、LayeredDepth+SeeGroup、MODEST、TransCG、Booster，再决定是否把透明 slice 加进 A2 的 L1/diag 实验。

## 下一步

1. 先读 MOMA/ReMake/SeeClear，确认 A2 的 novelty 边界。
2. 在 A2 failure slices 中规划 TransCG/Booster/ClearPose 的透明 mask 指标，全部标 `待跑`。
3. 设计同源后处理对照：global affine、patch affine、MOMA-style SRS、mask-guided completion。
4. 继续监控 AISPO 和 SeeClear 的代码/权重/数据发布状态。
