# Literature Search：Shell-Aware Multi-Layer Transparent Grasping

日期：2026-07-19
检索目的：核验“多层透明薄壳抓取”的新颖性边界、最近威胁、baseline 与数据资源
目标 venue/family：机器人 / 计算机视觉顶会，具体 venue 待定
来源质量策略：仅保留官方 proceedings、CVF、PMLR、IEEE/DOI、arXiv、官方项目页和代码仓库；已应用来源排除策略

## Summary

- **结论**：透明物体抓取、透明餐具操作、两层透明重建、多层深度和体素占据都不是空白。
- **最接近工作**：T²SQNet、ASGrasp、ReMake、Trans2Occ、ShellGrasp-Net。
- **最强感知威胁**：LayeredDepth、SeeGroup、MDA、DepthFocus。
- **机会类型**：`crowded but open + benchmark gap + mechanism gap`。
- **仍可能开放的缺口**：低成本单视角条件下，显式恢复并评估物理外/内界面、rim、局部壁厚和腔体自由空间，再证明这些量在固定抓取管线中影响接触安全。
- **最高优先级动作**：在做新模型前，以 T²SQNet、ReMake 和 Trans2Occ 为核心完成 shell-failure diagnostic，并核验 GT mesh 是否真的含内壁与厚度。

## Paper Table

评分含义：Insight、Completeness、Numeric evidence 均为 1–5；`Risk` 表示必须精读、可能直接压缩 novelty，不表示论文质量差。

| # | Title | Year | Venue/source | Link | Type | Insight | Completeness | Numeric evidence | Overall | 与本课题的关系 |
|---|---|---:|---|---|---|---:|---:|---:|---|---|
| 1 | T²SQNet: A Recognition Model for Manipulating Partially Observed Transparent Tableware Objects | 2024/2025 | CoRL 2024 / PMLR 2025 | [PMLR](https://proceedings.mlr.press/v270/kim25d.html) | method + benchmark/tool | 5 | 5 | 4 | Risk | 已覆盖透明杯、碗、瓶、酒杯等低维完整形状与操作；最强任务级近邻 |
| 2 | Rethinking Transparent Object Grasping: Depth Completion with Monocular Depth Estimation and Instance Mask | 2026 | IEEE RA-L / arXiv | [arXiv](https://arxiv.org/abs/2508.02507) | pure method | 4 | 4 | 4 | Risk | 同输入路线最直接 baseline；论文明确暴露空心结构被补成实心的失败 |
| 3 | ASGrasp: Generalizable Transparent Object Reconstruction and 6-DoF Grasp Detection from RGB-D Active Stereo Camera | 2024 | ICRA | [arXiv/DOI](https://arxiv.org/abs/2405.05648) | pure method | 4 | 4 | 4 | Risk | 已有两层重建 + 6-DoF 抓取；主动双目系统上界 |
| 4 | Trans2Occ: Voxel Occupancy Estimation and Grasp for Transparent Objects from Simulation to Reality | 2026 | arXiv preprint | [arXiv](https://arxiv.org/abs/2606.01777) | pure method | 4 | 3 | 3 | Risk | 单 RGB 体素占据与抓取；直接挑战“绕开单深度就是新贡献” |
| 5 | Simultaneous Object Reconstruction and Grasp Prediction using a Camera-centric Object Shell Representation | 2022 | IROS | [arXiv](https://arxiv.org/abs/2109.06837) | pure method | 4 | 4 | 4 | Risk | ShellGrasp-Net 已使用 entry/exit object shell；术语与表示近邻 |
| 6 | Seeing and Seeing Through the Glass: Real and Synthetic Data for Multi-Layer Depth Estimation | 2025 | ICCV | [arXiv](https://arxiv.org/abs/2503.11633) | pure benchmark | 5 | 5 | N/A benchmark | A | LayeredDepth 提供 1,500 张真实 benchmark 与 15,300 张 synthetic 数据；多层任务基础 |
| 7 | SeeGroup: Multi-Layer Depth Estimation of Transparent Surfaces via Self-Determined Grouping | 2026 | CVPR 2026 Oral | [arXiv](https://arxiv.org/abs/2605.28735) | pure method | 5 | 4 | 4 | Risk | 把每条射线多层深度建模为无序事件；压缩普通 \(K\)-head novelty |
| 8 | Modeling Depth Ambiguity: A Mixture-Density Representation for Flying-Point-Free Depth Estimation | 2026 | arXiv preprint | [arXiv](https://arxiv.org/abs/2606.02552) | pure method | 4 | 3 | 3 | Risk | mixture density 多假设深度，并扩展到透明层；多峰 head 不是新点 |
| 9 | DepthFocus: Controllable Depth Estimation for See-Through Scenes | 2026 | CVPR | [project](https://junhong-3dv.github.io/depthfocus-project/) | method + benchmark | 5 | 4 | 4 | Risk | 用参考深度可控选择透射层；动作条件选层已有强近邻 |
| 10 | ClearGrasp: 3D Shape Estimation of Transparent Objects for Manipulation | 2020 | ICRA | [arXiv](https://arxiv.org/abs/1910.02550) | method + benchmark | 5 | 5 | 5 | A | 透明 RGB-D depth/normal/boundary 与机器人操作经典基线 |
| 11 | RGB-D Local Implicit Function for Depth Completion of Transparent Objects | 2021 | CVPR | [CVF](https://openaccess.thecvf.com/content/CVPR2021/html/Zhu_RGB-D_Local_Implicit_Function_for_Depth_Completion_of_Transparent_Objects_CVPR_2021_paper.html) | pure method | 4 | 5 | 5 | A | 强局部 implicit depth completion baseline |
| 12 | TransCG: A Large-Scale Real-World Dataset for Transparent Object Depth Completion and a Grasping Baseline | 2022 | IEEE RA-L / ICRA | [arXiv](https://arxiv.org/abs/2202.08471) | method + benchmark | 5 | 5 | 4 | A | 57,715 张真实 RGB-D、51 个物体、130 个场景；首选真实诊断资源 |
| 13 | Seeing Glass: Joint Point-Cloud and Depth Completion for Transparent Objects | 2021/2022 | CoRL 2021 / PMLR 2022 | [PMLR](https://proceedings.mlr.press/v164/xu22b.html) | pure method | 4 | 4 | 4 | B | 说明点云 + depth completion 已是成熟路线 |
| 14 | GraspNeRF: Multiview-based 6-DoF Grasp Detection for Transparent and Specular Objects Using Generalizable NeRF | 2022/2023 | CoRL 2022 / PMLR 2023 | [arXiv](https://arxiv.org/abs/2210.06575) | pure method | 4 | 4 | 4 | B | 多视角神经重建抓取系统上界 |
| 15 | Where Shall I Touch? Vision-Guided Tactile Poking for Transparent Object Grasping | 2023 | IEEE/ASME T-Mech | [arXiv](https://arxiv.org/abs/2208.09743) | pure method | 4 | 4 | 4 | B | 主动触觉探测路线；为单视图不可辨识提供替代方案 |

### LayeredDepth benchmark-quality note

- **Benchmark scope**：真实与合成的透明多层深度。
- **Task realism**：真实数据覆盖自然透明场景，合成数据支持任意多层标签。
- **Metric validity**：适合验证层次关系和多界面感知；不是物理内/外壁、壁厚或抓取接触的现成 benchmark。
- **Baseline coverage**：包括单层模型适配与多层基线，SeeGroup 进一步扩展。
- **Adoption / reproducibility**：数据、评测与生成器公开。
- **Known limitation for this project**：光学多层标签不自动等于薄壳接触语义。

## Clusters

### Cluster 1：Single-depth completion and transparent manipulation

- 代表：ClearGrasp、LIDF、TransCG、Seeing Glass、ReMake。
- 已解决：RGB-D 透明区域缺失深度恢复、点云补全、与基础抓取管线连接。
- 剩余缺口：这些输出在空心薄壳上的内外壁、rim、壁厚和腔体是否正确，缺少统一量化。
- 差异路线：把“实心化 / 闭口”变成可复现 failure slice，并固定 planner 验证动作后果。
- 风险：如果强 completion 在目标对象上已经足够，则新表示没有必要。

### Cluster 2：Shape / occupancy representations for grasping

- 代表：T²SQNet、Trans2Occ、ShellGrasp-Net。
- 已解决：低维完整形状、体素占据、camera-centric entry/exit shell 均可服务抓取。
- 剩余缺口：对透明薄壁的物理多界面配对、rim、局部厚度和 cavity free-space 没有统一任务定义与主表。
- 差异路线：直接比较 shell-specific metrics 和相同 planner 下的失败，而不是泛泛声称“更完整 3D”。
- 风险：这是最可能覆盖中心 claim 的簇；G0 必须先审计。

### Cluster 3：Multi-layer / multi-hypothesis perception

- 代表：LayeredDepth、SeeGroup、MDA、DepthFocus。
- 已解决：透明场景多层数据、无序事件、多峰深度、条件式选层。
- 剩余缺口：将光学层映射为物理材料界面与抓取接触语义。
- 差异路线：界面 transition grammar、shell topology、thickness / rim / cavity 和下游机器人证据。
- 风险：仅做 \(K\)-depth head 或 action-conditioned layer selection 会被覆盖。

### Cluster 4：Stronger sensing and active information

- 代表：ASGrasp、GraspNeRF、Where Shall I Touch?；补充近邻 Dex-NeRF。
- 已解决：主动 stereo、多视角 NeRF、触觉探测可绕开单视角不确定性。
- 剩余缺口：单视角低成本设置下的可校准薄壳估计与拒抓。
- 差异路线：主表限制输入；强传感器只做上界。若单图不可辨识成为主瓶颈，可把“一次最小主动观测”作为后续扩展。

## Opportunity Map

| Cluster | Status | Open gap | Possible direction | Evidence needed | Risk |
|---|---|---|---|---|---|
| Single-depth completion | crowded but open / mechanism gap | 空心结构实心化是否系统影响抓取 | shell failure benchmark + fixed-planner analysis | 真实 shell GT、强 baseline、失败相关性 | 中高 |
| Shape / occupancy grasping | covered central claim / benchmark gap | 细粒度物理薄壳语义是否有增益 | 与 T²SQNet、Trans2Occ 直接对打 | 同对象同规划器、rim/cavity/thickness 指标 | 极高 |
| Multi-layer perception | crowded but open | 光学层缺乏物理接触语义 | semantic interface events + topology | 嵌套消融与机器人映射 | 高 |
| Active / multi-view | deployment/system gap | 更强感知成本高 | 单视角主线 + optional minimal action | 成本、成功率、risk–coverage | 中 |
| Thin-shell evaluation | benchmark gap / negative-result opportunity | 缺少统一 shell-to-grasp 证据 | 小而严谨的诊断 benchmark | GT 可信度与跨方法适配 | 中 |

## Benchmark And Dataset Candidates

| Name | Link | Task | 可支持指标 | Fit | 主要风险 |
|---|---|---|---|---|---|
| LayeredDepth | [project/arXiv](https://arxiv.org/abs/2503.11633) | 透明多层深度 | interface depth、layer count、ordering | 感知基础 | 不含抓取薄壳语义 |
| TransCG | [project/arXiv](https://arxiv.org/abs/2202.08471) | 真实 RGB-D completion + grasp | front depth、mesh-derived shell 待审计 | 真实诊断首选 | mesh 可能不保留真实壁厚 |
| TablewareNet | [via T²SQNet](https://proceedings.mlr.press/v270/kim25d.html) | 参数化餐具生成 | shape、opening、可控尺寸 | 强 shape prior 与 synthetic source | 需确认内外表面导出 |
| ClearGrasp | [arXiv](https://arxiv.org/abs/1910.02550) | 透明 RGB-D manipulation | depth、normal、boundary | completion baseline | 薄壳 GT 不完整 |
| 自建 ShellBench | 待定 | 物理薄壳 + 抓取 | 全部 shell 与 robot metrics | 最匹配 | 标注、扫描和规模成本 |

## Citation And Positioning Cautions

- 不使用“透明餐具抓取首次提出”“两层透明重建首次用于抓取”“多层透明 depth 是空白”。
- T²SQNet 是任务级第一近邻；ReMake 是 matched-input 第一近邻；ASGrasp 是两层系统第一近邻；Trans2Occ 是 occupancy 第一近邻。
- `ShellGraspPack` 不再作为表示名，避免与 ShellGrasp-Net 混淆。
- 2026 arXiv preprint 与正式 proceedings 工作分开标注；不把预印本写成已同行评审。
- 所有“未显式建模内外壁 / rim / thickness / cavity”的判断，在论文写作前还需逐篇全文与代码核验；当前报告用于确定实验 gate，不替代最终 related-work citation audit。

