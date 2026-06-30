# 机器人透明物体 MDE 与 Depth Correction 细致调研 Spec

日期：2026-06-30

## 任务背景

本文件用于规范“透明/反光物体机器人抓取中的 MDE、depth completion、metric alignment、multi-layer depth”调研。原始动机是把透明物体抓取作为 A2 的具体应用场景来审视：透明物体常使 RGB-D 传感器产生缺失深度、背景错深度、反射/折射错深度，而机器人抓取需要可物理消费的米制深度。

本阶段不是写泛泛综述，而是形成一套可直接服务 A2 的威胁清单、候选论文表、数据/代码/算力判断和实验协议建议。所有 A2 相关实验结论必须保持 `待跑`，直到本仓库存在真实 CSV 或机器人日志。

## 调研目标

找出透明/反光物体、机器人操作、单目/双目/RGB-D 深度修正、多层透明深度、非朗伯 MDE 中最能威胁或支撑 A2 的论文与资源，重点判断：

1. 哪些论文已经把“透明物体需要 depth correction”做成成熟方法或 benchmark。
2. 哪些近作已经把 monocular/foundation MDE 放进透明物体抓取或非朗伯场景。
3. 哪些论文最接近 A2 的 sparse metric anchor、one-shot calibration、affine-invariant prior、sampling-time correction。
4. 哪些数据集可用于 A2 的透明/反光 failure slice。
5. 哪些方法有公开代码、checkpoint、数据脚本和可判断的 GPU/硬件成本。
6. A2 如果进入透明物体场景，应如何区分 metric protocol 与 affine-invariant protocol，如何区分 `nfe` 与 `nfe_real`。

## 决策问题

需要回答：

1. 透明/反光物体深度修正的主线已经有哪些代表工作？
2. 2025-2026 年有哪些新近工作构成 reviewer threat？
3. 每篇论文是否有官方代码、checkpoint、数据入口和可运行脚本？
4. 每篇论文的数据是否公开、是否需要机器人、RealSense、active stereo、多视角、Blender/Infinigen 或私有合成管线？
5. GPU/硬件信息是否公开；复现成本应标为低/中/高/不明。
6. 工作流程是 RGB-D post-hoc completion、MDE fine-tuning、one-shot metric alignment、generative opacification、multi-layer depth、shape prior，还是 active/stereo/NeRF 系统？
7. 实际创新是否只是换数据/加 mask/加后处理，还是提出了新问题定义、新训练目标、新多层协议或新 robot-ready 深度机制？
8. 对 A2 来说，哪些工作必须作为 L1 后处理门槛、L2 `nfe_real` 门槛、diag failure-slice 门槛或写作边界？

## 检索范围

### 主题关键词

中文主题：

- 透明物体、反光物体、镜面、非朗伯表面、玻璃、折射、反射
- 机器人抓取、机器人操作、6-DoF grasp、suction、tabletop manipulation
- 单目深度估计、米制深度、相对深度、RGB-D depth completion、depth restoration
- 稀疏深度校准、one-shot calibration、metric alignment、affine-invariant prior
- 透明物体多层深度、front surface、back surface、contact surface、grasp-relevant depth

英文关键词：

- transparent object, specular object, mirror surface, non-Lambertian surface, glass
- robotic manipulation, grasping, suction, 6-DoF grasp, tabletop robot
- monocular depth estimation, metric depth, RGB-D depth completion, depth restoration
- sparse depth calibration, one-shot metric alignment, affine-invariant prior
- multi-layer depth, layered depth, contact surface, transparent surfaces

### 论文来源

优先来源：

- arXiv、CVF Open Access、ECVA、PMLR、IEEE Xplore、项目主页、GitHub 官方仓库、Hugging Face 数据页。
- 机器人论文可来自 ICRA、CoRL、RSS、IROS、RA-L，但不能直接标为 CCF-A。
- CVPR/ICCV 论文按 CCF-A 视角标注；ECCV、ICRA、CoRL、RA-L、arXiv 单独标注，不混成 CCF-A。
- 不使用只有搜索片段、博客复述或不稳定二手页面支撑关键判断。

## 主候选标准

主候选优先满足：

1. 与透明/反光物体深度、机器人操作或非朗伯 MDE 强相关。
2. 有公开论文页，最好有官方代码、数据或 checkpoint。
3. 能直接影响 A2 的 novelty、baseline、数据集或协议。
4. 近作优先；经典工作如果构成绕不过去的 baseline，也纳入主候选。

观察名单包括：

- 代码缺失或 demo-only。
- 不是透明 MDE 主线，但对任务定义、传感器上界、多层深度或评测生态有启发。
- 复现成本明显高，短期不适合作为 A2 第一批实验。

## 每篇论文必须抽取的信息

每篇主候选至少抽取：

1. 基本信息：标题、作者/团队、年份、venue/source、论文链接、代码链接、项目/数据链接。
2. CCF-A 状态：CVPR/ICCV 已确认；ECCV/ICRA/CoRL/RA-L/arXiv/挑战页面分别标注，不冒充 CCF-A。
3. 代码状态：有/无/待核验；是否有 README、训练脚本、测试脚本、checkpoint、数据脚本。
4. 数据可收集性：公开数据、合成数据、真实 RGB-D、机器人采集、RealSense/active stereo、多视角、Blender/Infinigen 等依赖。
5. GPU/硬件信息：GPU 型号、数量、训练时间、运行环境、RealSense/UR5/active stereo 等；未公开则写“未公开”。
6. 工作流程：mask、MDE、RGB-D completion、diffusion/generation、metric alignment、shape prior、multi-layer、grasp pipeline。
7. 实际创新：对 A2 来说是 baseline、威胁、协议资源、数据资源还是概念边界。
8. 评测位置：TransCG、ClearPose、Booster、LayeredDepth、real robot、UR5、RealSense、challenge server 等。
9. A2 影响：应进入 L1/L2/diag 哪个 gate，或者作为 writing threat / observation。

## 输出格式

### 主表

主报告应先给候选表：

| 序号 | 论文 | 年份/来源 | CCF-A 状态 | 代码 | 数据可收集性 | GPU/硬件 | 流程标签 | 创新强度 | A2 建议 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

建议字段取值：

- 强跟进：对 A2 直接构成威胁或强 baseline，代码/数据路径较清楚。
- 必读背景：经典 baseline 或数据协议，必须读但不一定复现。
- 可观察：有启发但复现或相关性不够直接。
- 排除/暂缓：证据不足、来源不稳或与 A2 主线太远。

### 单篇压缩段落

每篇主候选后给一段中文摘要，格式：

```text
《论文标题》（年份，venue/source，代码：有/无/待核验）主要解决……。它使用/构建了……数据集或 benchmark，我们收集难度为……，原因是……。GPU/硬件信息为……；若未公开则写未公开。工作流程是……。实际创新更接近于……。评测放在……。对 A2 的影响是……。综合判断：强跟进/必读背景/可观察/暂缓。
```

### 观察名单

观察名单必须说明未进入主候选的原因，例如不是单目/透明 MDE 主线、代码缺失、复现成本太高、只适合作为传感器上界或评测生态。

## A2 写作与实验纪律

- 不要把“透明物体深度困难”当 novelty；ClearGrasp、TransCG、DREDS、ReMake、AISPO 已经覆盖。
- 不要把 affine-invariant 对齐结果写成 metric-depth 成果；metric 主表和 affine 对照必须分开。
- 不要把 `nfe` 写成 `nfe_real`；透明场景若用 opacification、mask、MDE、多候选或 postprocess，都要计入真实链路成本。
- 不要把机器人抓取成功率写成 A2 结论；本仓库没有真实 CSV 或 robot log 前，一律 `待跑`。
- A2 的可辩护切口应是：冻结深度先验、近单步或低 `nfe_real`、采样期 metric anchoring、同源 post-hoc 对照、透明/反光 failure slice。
- ReMake、MOMA、AISPO、SeeClear、SeeGroup、MODEST 是透明场景的近期高优先级威胁。

## 成功标准

一次完整调研完成后，应交付：

1. 12-18 篇主候选或强观察论文。
2. 至少 5 篇直接威胁：MOMA、ReMake、SeeClear、SeeGroup/LayeredDepth、AISPO/MODEST。
3. 每篇主候选有代码、数据、GPU/硬件、流程、创新、评测位置和 A2 影响判断。
4. 形成可当天转交给 guanhua 的优先阅读列表。
5. 给出 A2 透明 failure-slice 的最小可行实验协议，所有未跑实验标记 `待跑`。
