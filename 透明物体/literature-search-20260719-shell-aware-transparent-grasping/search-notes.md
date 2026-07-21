# Search Notes

日期：2026-07-19

## Safe Queries Used

- `"transparent tableware" manipulation grasp reconstruction`
- `"transparent object" multi-layer reconstruction 6-DoF grasp`
- `"transparent object grasping" hollow shell rim wall thickness`
- `"object shell representation" grasp prediction entry exit depth`
- `"multi-layer depth" transparent surfaces`
- `"single-view occupancy" transparent object grasp`
- `"transparent object depth completion" hollow solid beaker`
- `"transparent object grasping" NeRF tactile active stereo`

查询仅使用公开的研究主题词，不包含未公开实验结果、个人身份或内部项目原文。

## Sources Checked

- CVF Open Access；
- PMLR / CoRL proceedings；
- arXiv stable paper records；
- IEEE DOI / journal metadata；
- 论文官方项目页；
- 作者官方 GitHub 仓库；
- 本仓库已归档论文 PDF，特别是 ReMake、LayeredDepth、SeeGroup、TransCG。

## Screening Decisions

### Included as closest threats

- T²SQNet：透明餐具任务与操作级最近工作；
- ReMake：相同低成本输入路线与空心结构失败动机；
- ASGrasp：两层透明重建接 6-DoF grasp；
- Trans2Occ：单图占据表示与透明抓取；
- ShellGrasp-Net：已有 object-shell 表示与命名冲突；
- LayeredDepth / SeeGroup / MDA / DepthFocus：多层、多假设和条件选层边界。

### Included as foundations or system bounds

- ClearGrasp、LIDF、TransCG、Seeing Glass；
- GraspNeRF；
- Where Shall I Touch?。

### Screened but not placed in the final 15

- Dex-NeRF：与 GraspNeRF 同属多视角神经重建上界，保留为补充引用；
- LucidGrasp：更偏透明实验室器具的 pose / liquid manipulation；
- Evo-NeRF：更偏主动下一视角与 NeRF；
- Seeing Through Glass / transparent enclosure reconstruction：更偏容器内部场景重建；
- ClearPose、DREDS：可用于数据和 sim-to-real，但不是当前 shell task 的最接近 15 篇；
- MODEST、Depth4ToM、SeeClear、AISPO：是透明深度的重要工作，已在仓库既有综述中覆盖；本轮优先保留对“多层薄壳抓取”最直接的候选。

## Excluded Sources

- 来源质量策略排除的出版平台、低信号 venue 和无法追溯原始论文的页面未进入候选表，也未用于新颖性结论。
- 只有搜索摘要而无稳定论文记录的候选未纳入。
- 博客和二手综述仅用于发现关键词，不作为最终证据。

## Unknowns

- T²SQNet 在 thin-shell / cavity 指标上的真实表现尚未测量，不能从表示形式直接推断失败；
- Trans2Occ 是 2026-06 新预印本，代码、数据、体素分辨率与内腔表现需全文 / 仓库审计；
- TransCG、TablewareNet 和 LayeredDepth-Syn 的 mesh / renderer 是否保留可用的物理内外壁与局部厚度，仍是 G0 问题；
- ASGrasp 的“两层”与本项目四类物理界面如何对应，需读代码和数据标注；
- 真实透明物体的壁厚 GT 获取方式尚未确定；
- 最终 target venue 和机器人硬件尚未确定。

## Handoff Notes

### For writing

- 不写“任务空白”；
- 用“explicit grasp-relevant physical shell interfaces are under-specified and under-evaluated”；
- T²SQNet、ASGrasp、Trans2Occ 和 ShellGrasp-Net 必须出现在 Introduction / Related Work 的 novelty boundary 中。

### For idea optimization

- 表示名使用 `LayeredShellGeometry`；
- 贡献中心是 interface semantics + shell topology + grasp evidence；
- 普通 \(K\)-depth head、action-conditioned layer 和 occupancy 不能单独构成主贡献。

### For experiment design

- G0 先于模型开发；
- 按输入预算分组 baseline；
- T²SQNet / Trans2Occ 是 representation threat，ReMake 是 matched-input baseline，ASGrasp / GraspNeRF 是 system upper bound；
- 必须加入 rim、cavity、thickness、topology 和 fixed-planner 指标。

### For review

- 最危险问题是“为什么 T²SQNet 或 Trans2Occ 不够”；
- 第二危险问题是“单图是否能辨识后壁和壁厚”；
- 第三危险问题是“离线 shell metric 与真实抓取是否相关”。

