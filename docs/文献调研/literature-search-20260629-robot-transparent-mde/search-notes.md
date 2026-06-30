# Search Notes

日期：2026-06-30

模式：重新细致调研，仿照低功耗/持续学习/Agent 自进化调研的规格化输出。目标是补齐透明物体方向的代码、数据、GPU、流程、创新、评测位置和 A2 威胁判断。

## 查询关键词

核心查询：

- `transparent object perception robotic manipulation survey depth completion grasping`
- `transparent object depth completion grasping dataset ClearGrasp TransCG`
- `transparent object monocular depth estimation robot grasping`
- `non-Lambertian monocular depth estimation transparent mirror surfaces`
- `transparent object depth completion MDE instance mask`
- `monocular one-shot metric-depth alignment robot grasping MOMA`
- `Rethinking Transparent Object Grasping ReMake code`
- `SeeClear Reliable Transparent Object Depth Estimation Generative Opacification GitHub`
- `SeeGroup Multi-Layer Depth Estimation Transparent Surfaces GitHub`
- `AISPO Affine-Invariant Shape Prior non-Lambertian robotics`
- `NTIRE 2026 HR Depth from Images of Specular and Transparent Surfaces`
- `DepthShield transparent mirror surfaces depth estimation code`

代码/仓库核验查询：

- GitHub API / README: `Shreeyak/cleargrasp`
- GitHub API / README: `NVlabs/implicit_depth`
- GitHub API / README: `Galaxies99/TransCG`
- GitHub API / README: `opipari/ClearPose`
- GitHub API / README: `PKU-EPIC/DREDS`
- GitHub API / README: `CVLAB-Unibo/Depth4ToM-code`
- GitHub API / README: `jun7-shi/ASGrasp`
- GitHub API / README: `D-Robotics-AI-Lab/MODEST`
- GitHub API / README: `princeton-vl/LayeredDepth`
- GitHub API / README: `GreatenAnoymous/MOMA`
- GitHub API / README: `ChengYaofeng/ReMake`
- GitHub API / README: `YumengHe/SeeClear`
- GitHub API / README: `princeton-vl/SeeGroup`
- GitHub API / README: `SeracoZ/DepthShield`

## 主要来源

- arXiv abstract/html/pdf pages for listed papers.
- CVF Open Access / ECVA pages for CVPR, ICCV, ECCV papers.
- PMLR pages for CoRL papers.
- IEEE RA-L / project pages where public.
- Official GitHub repositories and README files.
- Booster official project and NTIRE 2025/2026 challenge pages.
- Existing local `pdfs/` and `download_manifest.tsv`.

## 本轮新核验到的事实

### 代码与数据

- ClearGrasp repo 提供 API、training/testing、RealSense demo、dataset 和 checkpoint；环境较旧，依赖 PyTorch 1.3、CUDA 9.0、C++ `depth2depth`。
- LIDF 官方 repo 提供 code/checkpoint，README 明确测试环境为 4x Tesla V100 32GB、CUDA 10.2。
- TransCG 官方 repo 是 `Galaxies99/TransCG`，README 明确 57,715 张真实 RGB-D、51 个透明物体、130 个场景，并给 RTX 3090/CUDA11.1/PyTorch1.9 环境。
- ClearPose 官方 repo 是 `opipari/ClearPose`，公开 RGB、raw depth、true depth、normal、6D pose 和多 adversarial split。
- DREDS 官方 repo 是 `PKU-EPIC/DREDS`，提供 DREDS simulated、STD real、DepthSensorSimulator、SwinDRNet 和 CatePoseEstimation。
- Depth4ToM 官方 repo 是 `CVLAB-Unibo/Depth4ToM-code`，公开 virtual depth 数据、monocular weights 和部分代码；README 明确 stereo training code 不完全释放。
- ASGrasp 官方 repo 是 `jun7-shi/ASGrasp`，公开 checkpoint 和 inference 脚本，依赖 active stereo/MVS/GSNet。
- MODEST repo 提供 Syn-TODD/ClearPose 数据入口、weights、training/eval/inference；README 明确 RTX 4090 测试环境。
- LayeredDepth repo 提供 Hugging Face benchmark、evaluate/upload scripts 和 synthetic generator；synthetic 生成需要定制 Blender/Infinigen。
- MOMA repo 存在，README 说明 one-shot metric depth alignment、UR5 grasping/suction、透明物体；README 较短，可运行性仍需后续实际拉代码核验。
- ReMake 官方 project page 链到 `ChengYaofeng/ReMake`；README 提供 env、checkpoint、ClearGrasp/TransCG/OOD 数据入口、train/test/inference/realworld_inference 脚本。
- SeeClear 官方 repo 是 `YumengHe/SeeClear`；当前是 code-only release，README 标注 model weights 和 dataset links coming soon。
- SeeGroup 官方 repo 是 `princeton-vl/SeeGroup`；README 提供 released checkpoint、validation/test/training 脚本。
- DepthShield repo 是 `SeracoZ/DepthShield`；当前只作为 demo-level 观察项，venue/论文状态未核验。

### 训练/硬件成本

- LIDF: 4x Tesla V100 32GB。
- TransCG: RTX 3090 测试环境。
- MODEST: RTX 4090 测试环境。
- ReMake: 1x RTX 3090 约 80 小时，或 8x RTX 3090 DDP 约 10 小时。
- SeeClear: 论文页报告 4x H100 NVL 约 30 小时；README 当前不含权重/数据。
- AISPO: 论文页报告 8x A100 训练、RTX 3090 评测；代码未找到。
- MOMA: 论文页报告 RTX 3090 实时推理；训练成本未公开。
- ClearGrasp、ClearPose、DREDS、Depth4ToM、ASGrasp、LayeredDepth、SeeGroup 的 GPU 型号或训练时间若 README 未明确，本报告写“未公开”或“型号/时间未公开”。

### 协议差异

- Booster/NTIRE 2025 mono track 对单目深度先做 scale/shift matching，再评估 ABS Rel、delta、MAE、RMSE，ToM class 的 delta1.05 用于排名。
- Booster/NTIRE 2026 mono track 改成 metric mono，明确要求提交 cm 单位 metric depth，并用 ToM class RMSE 排名。
- 这个差异非常适合支撑 A2 的研究纪律：metric 主表和 affine-invariant 对照必须分开，不能把 scale/shift 后结果当米制深度 claim。

## 未纳入主候选或降级原因

- MDPI 等非优先来源未纳入。
- 只有搜索片段、没有稳定论文页或官方仓库的工作未纳入主表。
- `DepthShield` 只作为 demo repo 观察，未作为 peer-reviewed 强威胁。
- `ClearDepth` 和 2024 `Transparent Object Depth Completion` 因代码/数据路径未在本轮核清，放观察名单。
- `Beyond RGB-D: A Review on Improving Depth Estimation Around Glass, Mirrors, and See-through Objects` 仍未找到稳定可核验论文/仓储状态，未纳入主表。

## 当前不确定项

- MOMA 仓库 README 较短，是否包含完整训练/评测脚本需要后续实际 clone 后核验。
- AISPO 是否会公开代码、数据和 checkpoint，需持续监控。
- SeeClear 权重和 SeeClear-396k 数据尚未在 README 中发布，当前不能作为可复现实验对象。
- SeeGroup 已公开 checkpoint 和脚本，但训练 GPU 型号/时间未公开。
- ClearDepth、Robust Non-Lambertian MDE、Transparent Object Depth Completion 的代码状态仍待补查。
- 本仓库当前没有透明物体实验 CSV 或机器人日志，因此所有 A2 transparent slice、grasp proxy、real robot 结论均为 `待跑`。

## A2 Handoff Notes

### 写作

- 不写“透明物体深度估计未解决”；改写为“现有透明 depth correction 已成熟，但缺少在同源条件下比较 sampling-time metric anchoring 与 post-hoc alignment/completion 的证据”。
- 透明物体输出要限定为 single-layer grasp-relevant/contact/front-surface metric depth，不声称完整多层透明重建。
- related work 必须覆盖 ClearGrasp、LIDF、TransCG、DREDS、Depth4ToM、MODEST、MOMA、ReMake、SeeClear、LayeredDepth/SeeGroup、AISPO。

### 实验

- 第一批数据：TransCG、ClearPose、Booster。
- 第二批边界：LayeredDepth/SeeGroup。
- 必跑对照：global affine、patch-wise affine、MOMA-style SRS、mask-guided completion、ReMake if runnable、Depth4ToM/MODEST if runnable。
- 必报指标：metric AbsRel/RMSE、affine-invariant 对照、transparent-mask error、boundary error、no-anchor transparent error、`nfe_real`、latency。
- 真实抓取或 grasp proxy 当前全部 `待跑`。

### 监控

- SeeClear weights/dataset release。
- AISPO code/checkpoint release。
- NTIRE 2026 final challenge report/leaderboard/code release。
- MOMA 仓库是否补充完整复现实验脚本。
- ClearDepth / Robust Non-Lambertian MDE / Transparent Object Depth Completion 是否公开代码。
