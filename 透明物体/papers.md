# 机器人透明物体 MDE 与 Depth Correction 细致调研

日期：2026-06-30

本报告重新调研“机器人透明/反光物体抓取中的单目深度估计、RGB-D depth completion、metric alignment、多层透明深度和非朗伯评测”。目标是给 A2 判断应用切口、baseline、数据集和 reviewer threat，而不是证明 A2 已经在该场景有效。所有 A2 相关数字仍为 `待跑`。

参考输出形态：同目录 `literature-spec.md` 定义的字段；短版结论见 `summary-zh.md`；结构化表格见 `papers.csv`；检索记录见 `search-notes.md`。

## 一句话结论

透明物体抓取中的 depth correction 已经是拥挤方向。ClearGrasp、LIDF、TransCG、DREDS 把 RGB-D 透明深度恢复和抓取基线做成了成熟主线；Depth4ToM、MODEST、MOMA、ReMake、SeeClear、AISPO 又把 MDE、mask、one-shot metric alignment、生成式 opacification 和 affine-invariant shape prior 接入透明/非朗伯深度。A2 若切入这个场景，不能说“用 MDE 修透明物体”是新贡献，必须收窄到“冻结深度先验 + 采样期 metric anchoring + 同源 post-hoc 对照 + 透明/反光 failure slice + `nfe_real` 成本纪律”。

## 主候选表

CCF-A 状态说明：本表只把 CVPR/ICCV 标为“CCF-A 视角确认”。ECCV、ICRA、CoRL、RA-L、arXiv、challenge 页面单独标注；这些工作可能很强，但不直接算本项目 CCFA map 中的 A 会/刊。

| # | 论文/资源 | 年份/来源 | CCF-A 状态 | 代码/数据 | 数据可收集性 | GPU/硬件信息 | 流程标签 | A2 建议 |
|---|---|---|---|---|---|---|---|---|
| 1 | [ClearGrasp](https://arxiv.org/abs/1910.02550) | 2020 ICRA | 机器人 venue，非本表 CCF-A | [code/data/checkpoint](https://github.com/Shreeyak/cleargrasp) | 高；72GB synthetic train、1.7GB val/test、RealSense demo | README 给 Ubuntu16/PyTorch1.3/CUDA9，GPU 型号未公开 | RGB-D + mask/normal/boundary + global optimization | 必读背景；L1 post-hoc depth completion 门槛 |
| 2 | [LIDF](https://arxiv.org/abs/2104.00622) | 2021 CVPR | CCF-A 确认 | [code/checkpoint](https://github.com/NVlabs/implicit_depth) | 中；ClearGrasp + Omniverse | README: 4x Tesla V100 32GB, CUDA10.2 | RGB-D local implicit depth completion | 强基线；透明区域局部补全门槛 |
| 3 | [TransCG](https://arxiv.org/abs/2202.08471) | 2022 RA-L / ICRA | 机器人 journal/conference | [code/data](https://github.com/Galaxies99/TransCG), [dataset](https://graspnet.net/transcg) | 高；57,715 张真实 RGB-D、51 透明物体、130 场景 | README: RTX 3090, CUDA11.1 | RGB-D depth completion + grasping baseline | 第一优先数据源；透明 mask 与抓取 proxy 起点 |
| 4 | [ClearPose](https://arxiv.org/abs/2203.03890) | 2022 ECCV | 非本表 CCF-A | [dataset/code branches](https://github.com/opipari/ClearPose) | 高；RGB、raw depth、true depth、normal、6D pose | 未公开统一 GPU | dataset + depth completion/pose benchmark | 泛化/遮挡/液体/非平面 split；A2 外部测试 |
| 5 | [DREDS / SwinDRNet](https://arxiv.org/abs/2208.03792) | 2022 ECCV | 非本表 CCF-A | [code/data](https://github.com/PKU-EPIC/DREDS) | 中高；130k 合成 RGBD + 38k STD 真实数据，非商用 | GPU 未公开 | domain-randomized simulation + RGB-D restoration | sim2real 强威胁；不应被 A2 包装成数据优势 |
| 6 | [Booster](https://arxiv.org/abs/2301.08245) + [NTIRE 2026](https://cvlab-unibo.github.io/booster-web/ntire26.html) | 2023 benchmark / CVPR workshops | 资源/挑战 | [dataset/challenge](https://cvlab-unibo.github.io/booster-web/) | 高；高分辨率 stereo/mono、material mask、ToM class | 未公开；挑战要求可复现实验材料 | high-res non-Lambertian MDE/stereo benchmark | metric vs affine 协议关键证据；A2 透明 failure slice |
| 7 | [Depth4ToM](https://arxiv.org/abs/2307.15052) | 2023 ICCV | CCF-A 确认 | [code/data/weights](https://github.com/CVLAB-Unibo/Depth4ToM-code) | 高；Trans10K/MSD proxy labels + Booster | GPU 未公开 | inpainting + MDE pseudo label + fine-tuning | 单目 ToM 适配强 baseline；区分 A2 training-free |
| 8 | [ASGrasp](https://arxiv.org/abs/2405.05648) | 2024 ICRA | 机器人 venue | [code/checkpoint](https://github.com/jun7-shi/ASGrasp) | 中；active stereo、MVS、GSNet/GraspNet 依赖 | README: PyTorch1.9.1/CUDA11.1，GPU 型号未公开 | active stereo reconstruction + 6-DoF grasp | 传感器/系统上界；不和单 RGB 少锚直接混比 |
| 9 | [MODEST](https://arxiv.org/abs/2502.14616) | 2025 ICRA / arXiv | 机器人 venue / arXiv | [code/weights](https://github.com/D-Robotics-AI-Lab/MODEST) | 高；Syn-TODD + ClearPose | README: RTX 4090 测试环境 | single RGB segmentation + depth + iterative fusion | 单目透明深度近邻；若 A2 用 mask 必须对照 |
| 10 | [LayeredDepth](https://arxiv.org/abs/2503.11633) | 2025 ICCV / arXiv | ICCV 视角强相关 | [code/data](https://github.com/princeton-vl/LayeredDepth), [HF data](https://huggingface.co/datasets/princeton-vl/LayeredDepth) | 中；real relative benchmark + synthetic generator，生成需定制 Blender/Infinigen | GPU 未公开 | multi-layer transparent depth dataset/protocol | 概念边界；A2 单层 depth 必须限定 contact/grasp-relevant surface |
| 11 | [MOMA](https://arxiv.org/abs/2506.17110) | 2025 arXiv | 未录用/待核验 | [code](https://github.com/GreatenAnoymous/MOMA) | 中；UR5、稀疏 GT depth 校准、透明物体抓取 | 论文页报告 RTX 3090 实时推理，训练成本未公开 | one-shot sparse metric alignment for RGB grasping | 最危险近邻；必须做 MOMA-style post-hoc/SRS 对照 |
| 12 | [ReMake](https://arxiv.org/abs/2508.02507) | 2026 RA-L | 机器人 journal | [code/checkpoint](https://github.com/ChengYaofeng/ReMake) | 高；ClearGrasp、TransCG、OOD 数据入口 | README: 1x3090 80h 或 8x3090 10h | instance mask + MDE + RGB-D depth completion | 透明抓取直接威胁；强跟进 baseline |
| 13 | [SeeClear](https://arxiv.org/abs/2603.19547) | 2026 arXiv | 未录用/待核验 | [code-only release](https://github.com/YumengHe/SeeClear) | 中；SeeClear-396k 论文数据，README 标注 weights/data coming soon | 论文报告 4x H100 NVL 约 30h；README 仅代码 | generative opacification + off-the-shelf MDE | 生成式预处理强威胁；复现需等权重/数据 |
| 14 | [SeeGroup](https://arxiv.org/abs/2605.28735) | 2026 CVPR Oral | CCF-A 确认 | [code/checkpoint](https://github.com/princeton-vl/SeeGroup) | 中；LayeredDepth validation/test | README 支持 single/multi GPU，型号/时间未公开 | unordered point-process multi-layer depth | 多层透明深度强威胁；限定 A2 claim 边界 |
| 15 | [AISPO](https://arxiv.org/abs/2606.25503) | 2026 RA-L forthcoming / arXiv | 机器人 journal | 代码未找到 | 中；非朗伯机器人 manipulation 评测 | 论文页报告 8x A100 训练、RTX 3090 评测 | affine-invariant shape prior for depth reliability | 与 A2 affine prior/metric correction 相邻；强观察，代码公开后跟进 |

## 单篇压缩摘要

### 1. ClearGrasp

《ClearGrasp: 3D Shape Estimation of Transparent Objects for Manipulation》（2020，ICRA，代码：有）主要解决 RGB-D 相机在透明物体区域给出缺失或背景深度的问题。它使用合成训练数据、真实测试数据和 RealSense D400 demo，我们收集难度为高，原因是训练/测试包和 checkpoints 仍公开，但环境较老且包含 C++ global optimization 组件。GPU 型号未公开；README 给出 Ubuntu 16.04、PyTorch 1.3、CUDA 9.0、RealSense 依赖。工作流程是用 RGB 预测 surface normal、occlusion boundary、transparent mask，清理输入 depth 后用 global optimization 重建透明物体深度。实际创新是把透明物体 depth completion 与机器人操作闭环打通，而不是通用 MDE。评测放在透明物体深度误差和 suction/parallel-jaw manipulation。对 A2 的影响是：它定义了经典 post-hoc RGB-D depth completion 门槛，A2 不能把“透明物体需要修深度”写成 novelty。综合判断：必读背景。

### 2. LIDF

《RGB-D Local Implicit Function for Depth Completion of Transparent Objects》（2021，CVPR，代码：有）主要解决透明物体 RGB-D depth completion 的局部几何泛化问题。它使用 ClearGrasp 与 Omniverse Object Dataset，我们收集难度为中，原因是数据和 checkpoint 有入口，但旧 CUDA/PyTorch 环境和多阶段训练较重。GPU/硬件信息为 4x Tesla V100 32GB、CUDA 10.2、PyTorch 1.6.0。工作流程是先做 local implicit depth completion，再 refinement/hard-negative mining。实际创新是将局部隐式函数用于透明区域深度补全。评测在 ClearGrasp/Omniverse 等透明 depth completion setting。对 A2 的影响是：它是透明 RGB-D 局部补全强 baseline，L1 后处理对照若不包括同源 patch/local affine 或 LIDF 类方法，说服力不足。综合判断：强基线。

### 3. TransCG

《TransCG: A Large-Scale Real-World Dataset for Transparent Object Depth Completion and a Grasping Baseline》（2022，RA-L/ICRA，代码：有）主要解决真实透明物体 RGB-D depth completion 数据不足和抓取验证缺口。它构建 57,715 张 RGB-D 图像、51 个透明物体、130 个场景和透明物体 3D mesh，我们收集难度为高，原因是项目页、GitHub 和数据入口公开。GPU/硬件信息为 README 测试环境 RTX 3090、CUDA 11.1、PyTorch 1.9.0。工作流程是 DFNet 对 RGB-D 输入做深度填充，并给出抓取 demo/baseline。实际创新是大规模真实数据 + 透明 depth completion + grasp baseline。评测位置包括 TransCG/ClearGrasp/Omniverse 以及机器人抓取 demo。对 A2 的影响是：它应作为透明 failure slice 的第一优先离线数据源，透明 mask、原始 depth、completed depth 和抓取 proxy 都能服务 L1/diag。综合判断：强跟进。

### 4. ClearPose

《ClearPose: Large-scale Transparent Object Dataset and Benchmark》（2022，ECCV，代码/数据：有）主要解决透明物体数据和 benchmark 问题，覆盖 RGB、raw depth、rendered true depth、normal、instance label、6D pose。它包含 RealSense L515 采集的 63 个透明物体、多 set、多 adversarial 条件，我们收集难度为高，原因是 DropBox 数据和 GitHub benchmark branches 公开。GPU/硬件信息未公开为统一成本。工作流程不是提出单一新 MDE，而是提供 depth completion 与 pose estimation benchmark，复用 ImplicitDepth、TransCG、FFB6D 等。实际创新是数据覆盖：重遮挡、新背景、opaque distractor、液体、非平面、translucent cover。评测位置在 depth completion 和 pose 任务。对 A2 的影响是：它适合检验透明场景泛化，不应只在 TransCG 上调参。综合判断：强数据资源。

### 5. DREDS / SwinDRNet

《Domain Randomization-Enhanced Depth Simulation and Restoration for Perceiving and Grasping Specular and Transparent Objects》（2022，ECCV，代码：有）主要解决反光/透明物体深度仿真和真实 depth restoration 的 sim2real 问题。它提供 DREDS 合成数据、STD 真实数据、深度传感器仿真和 SwinDRNet，我们收集难度为中高，原因是数据公开但体量大、依赖 Blender/仿真/网络训练。GPU 信息未在 README 中明确。工作流程是大规模 domain-randomized RGBD 合成，训练 RGBD fusion restoration 网络，再转到真实 STD 和下游 category-level pose/grasp。实际创新是把传感器噪声仿真与 depth restoration 结合。评测位置包括真实 RGBD、pose estimation、grasping。对 A2 的影响是：如果 A2 在透明 slice 上只靠少量锚，必须承认 sim2real restoration 是强数据路线；A2 的差异应是 frozen prior 与采样期 metric anchor，而不是数据量。综合判断：强威胁。

### 6. Booster / NTIRE

《Booster: A Benchmark for Depth from Images of Specular and Transparent Surfaces》（2023，benchmark，代码/数据：数据与挑战入口）主要解决高分辨率透明/镜面 depth benchmark。它提供 606 个 12Mpx 样本、85 个场景、material segmentation mask 和 15K unlabeled samples；NTIRE 2025/2026 继续用 Booster 做高分辨率透明/反光 depth 挑战，我们收集难度为高，原因是 dataset stereo/mono、dev kit、challenge server 公开。GPU 信息未公开。工作流程是 dataset/protocol，而非单一模型。关键协议差异是：NTIRE 2025 mono track 先做 scale/shift 对齐，而 NTIRE 2026 mono metric track 明确要求提交 cm 单位 metric depth，并用 ToM class RMSE 排名。对 A2 的影响是：这直接支撑本项目区分 metric protocol 与 affine-invariant protocol，透明/反光 mask 内指标应单独报。综合判断：强评测资源。

### 7. Depth4ToM

《Learning Depth Estimation for Transparent and Mirror Surfaces》（2023，ICCV，代码：有）主要解决透明/镜面 ToM 表面的单目/双目深度训练问题。它使用 Trans10K、MSD、Booster，并公开 proxy label、weights 和代码，我们收集难度为高。GPU 信息未公开。工作流程是对 ToM 区域做 inpainting，再用 MDE/stereo 模型生成 pseudo labels，微调 MiDAS/DPT 或 stereo 网络。实际创新是无需真实 ToM GT 的 pseudo-label generation 和 fine-tuning pipeline。评测位置主要在 Booster，比较 monocular/stereo ToM 表面误差。对 A2 的影响是：Depth4ToM 是“训练/伪标签修透明区域”的强近邻；A2 必须强调 training-free frozen prior 与采样期 metric anchoring，而不是另一个 ToM fine-tune。综合判断：强跟进。

### 8. ASGrasp

《ASGrasp: Generalizable Transparent Object Reconstruction and 6-DoF Grasp Detection from RGB-D Active Stereo Camera》（2024，ICRA，代码：有）主要解决主动立体 RGB-D 相机下透明物体重建和 6-DoF 抓取。它依赖 active stereo/MVS、GSNet/GraspNet 和 checkpoint，我们收集难度为中，原因是代码公开但硬件/系统链路和 grasp dependencies 更重。GPU 型号未公开，README 给出 Python 3.8、PyTorch 1.9.1、CUDA 11.1。工作流程是从 active stereo 恢复多层/透明几何，再做 6-DoF grasp detection。实际创新更接近系统路线和传感器路线。评测位置在透明物体重建与抓取。对 A2 的影响是：ASGrasp 应作为更强传感器上界，而不是同等输入 baseline；A2 若主打单 RGB/少锚，应把部署约束写清楚。综合判断：可观察强系统。

### 9. MODEST

《Monocular Depth Estimation and Segmentation for Transparent Object with Iterative Semantic and Geometric Fusion》（2025，ICRA/arXiv，代码：有）主要解决单 RGB 同时做透明物体 segmentation 与 depth estimation。它使用 Syn-TODD 与 ClearPose，我们收集难度为高，原因是 repo 提供 weights、训练、测试、推理脚本。GPU/硬件信息为 README 测试环境 RTX 4090、Python 3.8、CUDA 11.1。工作流程是语义和几何多尺度融合，再迭代 refinement。实际创新是透明目标的单图联合分割与深度，而不是 metric sparse alignment。评测位置在合成和真实透明数据集。对 A2 的影响是：如果 A2 需要 transparent mask 或语义先验，MODEST 是直接威胁；A2 要么做 mask-free/noisy-mask 消融，要么把 mask 视为外部条件并公平计入 `nfe_real`/模块成本。综合判断：强跟进。

### 10. LayeredDepth

《Seeing and Seeing Through the Glass: Real and Synthetic Data for Multi-Layer Depth Estimation》（2025，ICCV/arXiv，代码/数据：有）主要解决透明物体的多层深度定义问题。它提供真实 in-the-wild 相对多层 benchmark 和 synthetic data generator，我们收集难度为中，原因是 Hugging Face 数据和 evaluate/upload scripts 公开，但 synthetic 生成需要定制 Blender 4.2 和 Infinigen。GPU 信息未公开。工作流程是建立 layer_all 和 layer_first 两类评测，支持 1/3/5/7 层提交。实际创新是把透明深度从单层扩展为多层，暴露“透明物体真 depth 是哪一层”的任务定义问题。评测位置在 LayeredDepth validation/test server。对 A2 的影响是：A2 单层 metric depth 必须限定为 grasp-relevant contact/front surface，不能声称完整透明 optical reconstruction。综合判断：概念边界，强跟进。

### 11. MOMA

《Monocular One-Shot Metric-Depth Alignment for RGB-Based Robot Grasping》（2025，arXiv，代码：有）主要解决单 RGB 抓取中 affine-invariant MDE 不能直接输出米制深度的问题。它使用少量 sparse GT depth points 做 scale-rotation-shift calibration，并在 UR5 上做抓取/吸取，我们收集难度为中，原因是代码入口存在但 README 较短、机器人复现需要硬件。GPU/硬件信息为论文页报告 RTX 3090 实时推理，训练成本未公开。工作流程是先用 MDE 预测相对深度，再通过 one-shot sparse depth calibration 对齐到 metric，用于 RGB-based robot grasping。实际创新更接近部署校准和 metric alignment，而不是透明专用网络。评测位置包括 UR5 抓取和透明物体。对 A2 的影响是：MOMA 是最危险近邻，因为它已经把稀疏 depth anchor 与 metric MDE 机器人抓取绑定；A2 必须用同源后处理/SRS 对照证明 sampling-time 注入不是输出端校准。综合判断：最高优先级威胁。

### 12. ReMake

《Rethinking Transparent Object Grasping: Depth Completion with Monocular Depth Estimation and Instance Mask》（2026，RA-L，代码：有）主要解决透明物体抓取中的 RGB-D depth completion。它使用 ClearGrasp、TransCG 和 OOD 数据入口，我们收集难度为高，原因是 GitHub 提供 env、checkpoint、train/test/inference/realworld_inference 脚本。GPU/硬件信息为 README 报告 1x3090 训练 80 小时，8x3090 DDP 训练 10 小时；真实抓取代码依赖 PCFGrasp/RealSense D435。工作流程是 instance mask + MDE relative depth + original depth 编码融合，预测 completed depth。实际创新是将 MDE 和 instance mask 放进透明抓取 depth completion，而不是泛化单目深度。评测位置在 ClearGrasp、TransCG、OOD 和 real-world inference/grasp。对 A2 的影响是：ReMake 是“透明抓取 + MDE + mask + RGB-D completion”的直接威胁；A2 若透明 slice 不赢同源 post-hoc/mask-guided completion，不能把该应用当核心贡献。综合判断：强跟进。

### 13. SeeClear

《SeeClear: Reliable Transparent Object Depth Estimation via Generative Opacification》（2026，arXiv，代码：有但 code-only）主要解决透明外观不稳定导致 MDE 错误的问题。它引入 SeeClear-396k synthetic paired transparent/opaque dataset，但 README 标明 pretrained checkpoints 和 dataset links coming soon，我们收集难度为中偏低，原因是当前可跑性受权重/数据发布限制。GPU/硬件信息为论文页报告 4x H100 NVL 约 30 小时训练。工作流程是 transparent mask preparation、conditional diffusion opacification、mask refinement、opaque compositing，再接 Depth Anything 3 或 MoGe。实际创新是把透明区域先生成成几何一致的不透明外观，再用 off-the-shelf MDE。评测位置包括透明 depth estimation 数据与 off-the-shelf MDE 对照。对 A2 的影响是：SeeClear 会压住“预处理透明外观再跑 MDE”的路线；A2 若使用生成或多候选 opacification，必须明确自己是在做 uncertainty/metric anchoring，而不是复刻 SeeClear。综合判断：强观察，等权重/数据。

### 14. SeeGroup

《SeeGroup: Multi-Layer Depth Estimation of Transparent Surfaces via Self-Determined Grouping》（2026，CVPR Oral，代码：有）主要解决透明多层深度中层顺序/层分配不固定的问题。它使用 LayeredDepth，公开 checkpoint、validation/test 脚本和训练脚本，我们收集难度为中。GPU 型号和训练时间未公开，README 支持 single-GPU 和 multi-GPU training。工作流程是将每个像素射线上的多层深度视为 unordered point-process events，用 permutation-invariant likelihood 训练 self-determined grouping。实际创新是多层深度建模和无序层分组，而不是单层 metric depth。评测位置在 LayeredDepth，README 报告 quadruplet relative depth accuracy 从 61.34% 到 70.09%。对 A2 的影响是：SeeGroup 是单层透明 depth claim 的强概念威胁；A2 必须把输出定义成单层 grasp-relevant/contact surface，并把 multi-layer 场景写成局限或诊断。综合判断：强跟进。

### 15. AISPO

《AISPO: Enhancing Depth Reliability for Robotic Manipulation of Non-Lambertian Objects via Affine-Invariant Shape Prior》（2026，RA-L forthcoming/arXiv，代码：未找到）主要解决非朗伯物体机器人操作中的深度可靠性。它把 affine-invariant shape prior 用于增强物理可用深度，我们收集难度为中，原因是论文可读但未找到公开代码。GPU/硬件信息为论文页报告 8x A100 训练、RTX 3090 评测。工作流程是利用 affine-invariant prior 强化透明/反光等非朗伯区域深度，再服务机器人 manipulation。实际创新与 A2 的 affine-invariant prior、metric correction、物理可用深度非常相邻。评测位置包括非朗伯物体和机器人相关任务。对 A2 的影响是：AISPO 是近期 reviewer threat，尤其会挑战“affine prior + 物理可用 depth”的 novelty；代码公开前先强观察，公开后进入复现列表。综合判断：强观察/威胁。

## 观察名单

| 论文/资源 | 观察原因 | 对 A2 的用法 |
|---|---|---|
| [Robotic Perception of Transparent Objects: A Review](https://arxiv.org/abs/2304.00157) | 机器人透明物体综述；不是方法 baseline | 写 related work 边界和任务分类 |
| [Survey on Monocular Metric Depth Estimation](https://arxiv.org/abs/2501.11841) | metric MDE 综述；不是透明物体专门工作 | 支撑 metric/affine protocol 背景 |
| [Seeing Glass / TranspareNet](https://proceedings.mlr.press/v164/xu22b.html) | CoRL 2021，点云+depth completion；代码路径未重点核验 | 说明 RGB-D/point cloud 联合补全是成熟主线 |
| [Dex-NeRF](https://proceedings.mlr.press/v164/ichnowski22a.html) | CoRL 2022，NeRF 透明物体抓取；系统成本高 | 作为多视角/active perception 上界 |
| [Transparent Object Depth Completion](https://arxiv.org/abs/2405.15299) | 2024 arXiv，single-view + multi-view depth completion；代码未核验 | 多视角 refinement 观察 |
| [Towards Robust MDE in Non-Lambertian Surfaces](https://arxiv.org/abs/2408.06083) | 2024 arXiv，直接训练 MDE 适配透明/镜面；代码未核验 | 训练式 non-Lambertian MDE 威胁 |
| [ClearDepth](https://arxiv.org/abs/2409.08926) | 2024 arXiv/project，stereo + sim2real 透明操作；代码未找到 | stereo/sim2real 上界 |
| [DepthShield](https://github.com/SeracoZ/DepthShield) | 2026 demo repo，mask-aware + blur refinement；venue/论文状态待核验 | 观察 plug-and-play ToM inference-time refinement |
| NTIRE 2025/2026 Booster challenges | challenge 生态持续更新；不是单一论文 | 监控 leaderboard 和 metric-vs-affine 规则变化 |

## 方法簇与 A2 差异

### Cluster 1: RGB-D Depth Completion / Restoration

代表：ClearGrasp、LIDF、TransCG、DREDS、ReMake、AISPO。

已解决：透明区域 RGB-D 原始 depth 缺失/错深度，常可通过 mask、normal、boundary、local implicit representation、domain-randomized sim2real、MDE prior 或 shape prior 修复。

A2 差异：A2 不能把自己写成 another RGB-D completion network。若进入透明场景，主张应是 frozen prior 的 sampling-time metric anchoring 是否优于等价 post-hoc alignment/completion，且必须有同源 patch/mask/global affine 对照。

### Cluster 2: Single RGB / Foundation MDE Adaptation

代表：Depth4ToM、MODEST、MOMA、SeeClear、Robust Non-Lambertian MDE。

已解决：通过 ToM inpainting pseudo labels、联合 segmentation-depth、one-shot calibration、opacification、区域引导训练，把单目 MDE 拉向透明/镜面区域。

A2 差异：A2 必须强调 training-free 或低训练成本、冻结深度先验、采样期注入、`nfe_real` 明确；否则会被 MODEST/Depth4ToM/SeeClear 压住。

### Cluster 3: Sparse Metric Alignment for Robot Grasping

代表：MOMA、AISPO，以及 ReMake 中的 MDE relative depth/useful geometry。

已解决：少量真实 depth 或 affine-invariant prior 可把相对深度变成更物理可用的机器人深度。

A2 差异：MOMA 已经覆盖 one-shot sparse depth calibration。A2 必须证明采样期 metric constraint 的传播效果不同于输出端 scale/shift/SRS/patch affine；这应成为 L1 gate，而不是附加消融。

### Cluster 4: Multi-Layer Transparent Depth

代表：LayeredDepth、SeeGroup。

已解决：透明物体 depth 不一定是单层，可有前表面、后表面、背景层或多层 unordered events。

A2 差异：A2 输出单层 depth 时必须明确定义为 grasp-relevant/contact/front surface；多层场景要作为失败模式或边界实验，而不是声称完整光学重建。

### Cluster 5: Active Stereo / NeRF / Multi-View Systems

代表：ASGrasp、Dex-NeRF、ClearDepth、Transparent Object Depth Completion。

已解决：更强传感器、多视角、主动扫描或 NeRF 可提高透明物体几何恢复。

A2 差异：A2 应把这些方法作为部署上界/系统上界，强调自己的约束是单图、低成本、少锚或近单步。不能宣称在所有机器人系统下替代 active/stereo/NeRF。

## 数据集与协议优先级

| 优先级 | 数据/协议 | 用途 | A2 可跑指标 | 风险 |
|---|---|---|---|---|
| 1 | TransCG | 真实透明 RGB-D depth completion + grasp baseline | transparent-mask AbsRel/RMSE、raw-vs-completed、no-anchor transparent error、grasp proxy `待跑` | RGB-D completion 任务，需改造成 MDE/frozen prior 协议 |
| 2 | ClearPose | 透明物体 depth/normal/pose，多 adversarial split | mask 内 metric/affine、遮挡/液体/非平面 slice `待跑` | rendered true depth 与物理接触面关系需说明 |
| 3 | Booster / NTIRE | 非朗伯高分辨率 MDE/stereo；ToM mask；2026 metric mono | ToM RMSE、full vs ToM、metric vs affine、分辨率/成本 `待跑` | 高分辨率成本高，不是机器人抓取数据 |
| 4 | DREDS / STD | sim2real RGB-D restoration，specular/transparent/diffuse | restoration 对照、domain gap、真实 STD slice `待跑` | 数据/仿真链路较重 |
| 5 | LayeredDepth / SeeGroup | 多层透明 depth 边界 | first-layer vs multi-layer、contact-surface proxy `待跑` | 单层 A2 天然不覆盖完整多层 |
| 6 | ReMake/ClearGrasp benchmark setup | 透明抓取 depth completion 直接对照 | ReMake vs A2 同源后处理 `待跑` | 依赖 mask/RealSense/PCFGrasp，`nfe_real` 需计完整 |
| 7 | Real robot tabletop grasp | 应用证明 | success、invalid grasp、collision、latency `待跑` | 本仓库当前无 robot log，不能写结果 |

## A2 最小可行实验协议

### 必须保留的 gate

- L0：确认 CCF/采样期约束不是单点 x0 修补、不是多噪声平均装饰。
- L1：同源后处理对照必须包括 global affine、patch-wise affine、MOMA-style scale/rotation/shift、mask-guided postprocess；透明场景应尽量加入 ReMake/Depth4ToM/MODEST 可跑版本。
- L2：报告 `nfe_real`。如果用了 mask predictor、opacification、MDE backbone、depth completion、候选集 rerank，都计入真实链路成本。
- diag：报告 bias-var、transparent-mask error、boundary error、no-anchor transparent error，确认不是只降方差或只在锚附近变好。

### 透明 slice 指标

| 指标 | 目的 | 状态 |
|---|---|---|
| full-image metric AbsRel/RMSE | 与 A2 主协议保持可比 | 待跑 |
| affine-invariant AbsRel/RMSE | 区分 metric 成果与对齐成果 | 待跑 |
| transparent-mask AbsRel/RMSE | 是否真修透明/反光区域 | 待跑 |
| transparent-boundary RMSE | 是否稳定处理折射/边界不连续 | 待跑 |
| no-anchor transparent AbsRel | 少量锚是否能传播到无锚透明区域 | 待跑 |
| contact-surface proxy | 机器人消费的 depth 是否更可用 | 待跑 |
| invalid-grasp / collision proxy | 应用价值，不等同真实抓取 | 待跑 |
| `nfe_real` / latency | 与 near-single-step 主张一致 | 待跑 |

## 写作边界

- 可以写：透明/反光物体是 A2 的高压 failure slice；现有方法多为训练式、RGB-D post-hoc、mask-guided、生成式预处理或强传感器系统；A2 关心采样期 metric anchoring 是否比同源输出端校准更能传播 sparse geometry。
- 不应写：A2 解决透明物体深度估计；A2 超过 active stereo/NeRF/多层透明深度；A2 已经提高抓取成功率。
- 必须写：MOMA、ReMake、AISPO、SeeClear、MODEST、LayeredDepth/SeeGroup 是近期 reviewer threat；所有机器人抓取和透明 slice 结果当前 `待跑`。

## 今天可以转给 guanhua 的优先阅读列表

1. MOMA：最接近 A2 sparse metric anchor + robot grasping 的近邻，必须先读。
2. ReMake：最直接的“透明抓取 + MDE + instance mask + RGB-D completion”威胁，代码和训练成本明确。
3. SeeClear：生成式 opacification 路线，防止 A2 误入“预处理透明外观再跑 MDE”的拥挤表述。
4. LayeredDepth + SeeGroup：多层透明深度会挑战单层 depth 定义，必须决定 contact-surface claim。
5. MODEST：单 RGB 透明分割+深度近邻，尤其威胁任何 mask/semantic 版本 A2。
6. TransCG + Booster：前者给机器人透明 RGB-D failure slice，后者给高分辨率非朗伯/metric-vs-affine 协议。
7. ClearGrasp + LIDF：经典 RGB-D post-hoc completion 基线，写 related work 和 L1 门槛不能绕过。
8. AISPO：代码未公开但 novelty 很近，作为高优先级观察威胁。

## 下载与核验状态

本目录 `pdfs/` 已有 23 个 PDF；`download_manifest.tsv` 记录了 arXiv/CVF/PMLR/项目页下载入口。当前环境缺少 `pdftotext` 和 `pypdf`，本轮细化主要用官方论文页、项目主页、GitHub README/API、挑战页面与已有 PDF 清单交叉核验。未能从官方 README 或论文页确认的信息统一写为“未公开/待核验”。
