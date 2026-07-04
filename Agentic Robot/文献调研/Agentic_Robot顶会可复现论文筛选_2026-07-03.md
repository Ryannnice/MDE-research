# Agentic Robot 顶会可复现论文筛选

日期: 2026-07-03  
范围: 2023-2026 年顶会/强会中的 agentic robot、VLA/机器人基础模型、长程操作、机器人数据 scale、仿真数据生成与可复现 benchmark。  
筛选原则: 优先 CCF-A 机器学习/视觉会议（ICLR/ICML/NeurIPS/CVPR）和机器人顶会/强会（RSS/CoRL/ICRA/IROS）；主表只放有官方代码、公开数据/公开 benchmark、能在短时间启动复现的工作。  
术语说明: 这里把用户说的 "Asian tick robot" 按 `Agentic Robot / 具身机器人智能体` 理解，重点是高层语言/视觉推理、低层可执行机器人策略、数据规模化与闭环复现。

## 0. 一页结论

如果目标是第一时间复现，不建议从真实机器人或闭源大模型系统开始。最稳路线是先跑通三个公开仿真/数据基线，再进入 VLA:

| 顺序 | 推荐入口 | 会议 | 为什么先做 | 复现形态 |
|---:|---|---|---|---|
| 1 | [Diffusion Policy](https://diffusion-policy.cs.columbia.edu/) | RSS 2023 | 代码、数据、Colab、日志和 checkpoint 都完整，是最低摩擦的 visuomotor policy 基线 | 先跑 PushT / image policy，再迁移到 LIBERO/RoboCasa |
| 2 | [LIBERO](https://libero-project.github.io/main.html) | NeurIPS 2023 D&B | 语言条件机器人操作 benchmark，后续 OpenVLA/Agentic Robot 都绕不开 | 跑 BC/DP/OpenVLA fine-tune 的小套件 |
| 3 | [VIMA](https://vimalabs.github.io/) | ICML 2023 | multimodal prompt robot agent，数据、仿真、代码、checkpoint 公开，适合验证语言/图像提示 | 跑 VIMA-Bench 零样本/少样本 generalization |
| 4 | [Octo](https://octo-models.github.io/) | RSS 2024 | 开源通用机器人策略，模型小于 OpenVLA，基于 Open X-Embodiment | 先做 checkpoint inference，再做小数据微调 |
| 5 | [OpenVLA](https://openvla.github.io/) | CoRL 2024 | 7B 开源 VLA，是近两年 agentic robot executor 的核心基线 | 先跑 LIBERO/BridgeData eval，再做 LoRA/FT |
| 6 | [MimicGen](https://mimicgen.github.io/) / [RoboCasa](https://robocasa.ai/) | CoRL 2023 / RSS 2024 | 数据生成和日常厨房任务 scale，适合做自己的数据扩增实验 | 先跑 demo playback/BC，再逐步加数据规模 |

优先复现组合建议:

| 组合 | 目标 | 最小可行实验 |
|---|---|---|
| `LIBERO + Diffusion Policy + OpenVLA` | 复现当前 agentic robot 低层 executor 基线 | 选 LIBERO-Spatial/Goal 各 1-2 个任务，跑 DP 与 OpenVLA-FT |
| `VIMA + GenSim` | 复现多模态 prompt 与 LLM 生成任务路线 | 跑 VIMA-Bench；用 GenSim 生成/加载 CLIPort 任务 |
| `MimicGen + RoboCasa/RoboCasa365` | 复现数据 scale 与仿真扩增路线 | 从少量 human demos 生成 synthetic demos，训练 BC/DP |
| `Octo/OpenVLA + Open X-Embodiment` | 复现通用机器人策略路线 | 先下载 checkpoint 做 inference，再抽 OXE 子集微调 |
| `UMI/Mobile ALOHA` | 复现真实机器人数据采集路线 | 无硬件先跑公开数据和训练脚本；有硬件再做部署 |

## 1. P0: 第一时间可以启动复现

这些工作满足: 顶会/强会、官方代码、公开数据或公开 benchmark、复现实验入口清楚。

| 工作 | 年份/会议 | 方向 | 代码/数据 | 复现难度 | 推荐动作 |
|---|---|---|---|---:|---|
| [Diffusion Policy: Visuomotor Policy Learning via Action Diffusion](https://diffusion-policy.cs.columbia.edu/) | RSS 2023 | 扩散式低层 visuomotor policy | [GitHub](https://github.com/real-stanford/diffusion_policy), 官方 data/Colab/checkpoints | 低 | 先复现 PushT 和 image policy，作为所有后续操作策略基线 |
| [LIBERO: Benchmarking Knowledge Transfer for Lifelong Robot Learning](https://libero-project.github.io/main.html) | NeurIPS 2023 Datasets & Benchmarks | lifelong / language-conditioned manipulation benchmark | [GitHub](https://github.com/Lifelong-Robot-Learning/LIBERO), demos/tasks | 低-中 | 先跑 LIBERO-Spatial 或 LIBERO-Goal 小套件 |
| [VIMA: General Robot Manipulation with Multimodal Prompts](https://vimalabs.github.io/) | ICML 2023 | 多模态 prompt robot agent | [GitHub](https://github.com/vimalabs/VIMA), VIMA-Bench, expert trajectories, checkpoints | 中 | 跑官方 eval，重点看 prompt 形式和泛化协议 |
| [MimicGen](https://mimicgen.github.io/) | CoRL 2023 | 从少量 human demos 自动生成大规模机器人数据 | [GitHub](https://github.com/NVlabs/mimicgen), [HF datasets](https://huggingface.co/datasets/amandlek/mimicgen_datasets) | 中 | 先跑官方 demo generation，再训练 robomimic BC |
| [GenSim: Generating Robotic Simulation Tasks via LLMs](https://liruiw.github.io/gensim) | ICLR 2024 Spotlight | LLM 生成仿真任务和 expert goals | [GitHub](https://github.com/liruiw/GenSim), demo/dataset/model links | 中 | 先复现已有 generated tasks，暂时不要一开始接真实机器人 |
| [Open X-Embodiment: Robotic Learning Datasets and RT-X Models](https://robotics-transformer-x.github.io/) | ICRA 2024 | 多机器人、多任务真实操作数据与 RT-X 模型 | [GitHub](https://github.com/google-deepmind/open_x_embodiment), RLDS/OXE 数据 | 中-高 | 先只下载一个 OXE 子数据集，验证 RLDS pipeline |
| [Octo: An Open-Source Generalist Robot Policy](https://octo-models.github.io/) | RSS 2024 | 开源通用机器人策略 | [GitHub](https://github.com/octo-models/octo), HF checkpoints, OXE 数据 | 中 | 先跑 checkpoint inference；再选 OXE/Bridge 子集 fine-tune |
| [OpenVLA: An Open-Source Vision-Language-Action Model](https://openvla.github.io/) | CoRL 2024 | 7B VLA, language-conditioned robot action | [GitHub](https://github.com/openvla/openvla), [HF weights](https://huggingface.co/openvla/openvla-7b), OXE | 中-高 | 先复现 LIBERO/Bridge eval，再考虑 LoRA |
| [DROID](https://droid-dataset.github.io/) | RSS 2024 | 大规模真实世界机器人操作数据集 | [platform code](https://github.com/droid-dataset/droid), [policy learning](https://github.com/droid-dataset/droid_policy_learning), dataset visualizer/Colab | 中-高 | 先做数据读取和小规模 policy learning，不要先全量训练 |
| [RoboCasa](https://robocasa.ai/) | RSS 2024 | 厨房日常任务仿真与数据 scale | [GitHub](https://github.com/robocasa/robocasa), demos/assets/tasks | 中 | 先跑 demo playback 和 1-2 个 task 的 BC/DP |
| [UMI: Universal Manipulation Interface](https://umi-gripper.github.io/) | RSS 2024 | in-the-wild human demo 到机器人策略 | [GitHub](https://github.com/real-stanford/universal_manipulation_interface), [UMI data community](https://umi-data.github.io/) | 中-高 | 无硬件先跑公开 cup dataset 和 SLAM pipeline |
| [ManiSkill-HAB](https://arth-shukla.github.io/mshab/) | ICLR 2025 | GPU 加速家庭重排/低层操作 benchmark | [GitHub](https://github.com/arth-shukla/mshab), HF models/datasets | 中 | 先跑 single subtask，不先下载全量 490GB |
| [MimicLabs / What Matters in Learning from Large-Scale Datasets](https://robo-mimiclabs.github.io/) | ICLR 2025 | 数据组成、检索与 scale 规律 | [GitHub](https://github.com/Gatech-RL2/mimiclabs), [HF data](https://huggingface.co/datasets/vaibhavsaxena11/mimiclabs_datasets) | 中 | 复现 camera pose / spatial arrangement 的小规模数据组合实验 |
| [RoboCasa365](https://robocasa.ai/) | ICLR 2026 | 365 任务、2500 厨房环境、通用机器人 benchmark | [GitHub release](https://github.com/robocasa/robocasa), demos/assets/leaderboard | 中-高 | 只抽 5-10 个任务做 sanity check；全量用于后续 |

## 2. P1: 高价值但复现门槛更高

这些工作也有代码或数据，但存在算力、硬件、API、环境复杂度等门槛。适合在 P0 跑通后跟进。

| 工作 | 年份/会议 | 方向 | 开源状态 | 主要门槛 | 建议 |
|---|---|---|---|---|---|
| [RVT: Robotic View Transformer](https://robotic-view-transformer.github.io/) | CoRL 2023 | 多视角 3D manipulation transformer | [GitHub](https://github.com/NVlabs/RVT), RLBench | 全量 18 RLBench tasks 训练较重 | 先复现 1-3 个 RLBench task |
| [ACT / ALOHA](https://tonyzhaozh.github.io/aloha/) | RSS 2023 | action chunking + 低成本双臂操作 | [GitHub](https://github.com/tonyzhaozh/aloha), hardware/tutorial/data links | 真实硬件和相机标定较重 | 无硬件先复现 ACT training；作为 DP 之外的传统强基线 |
| [3D Diffuser Actor](https://3d-diffuser-actor.github.io/) | CoRL 2024 | 3D scene token + diffusion policy | [GitHub](https://github.com/nickgkan/3d_diffuser_actor), [HF checkpoints](https://huggingface.co/katefgroup/3d_diffuser_actor), RLBench/CALVIN | RLBench/CALVIN 环境和训练时间 | 适合作为 3D/深度几何方向强基线 |
| [Mobile ALOHA](https://mobile-aloha.github.io/) | CoRL 2024 | 低成本双臂移动操作 | [GitHub](https://github.com/MarkFzp/mobile-aloha), TFDS `aloha_mobile` | 真实硬件复现重；数据约数十 GB | 无硬件先复现 ACT training；有硬件再部署 |
| [MOKA](https://moka-manipulation.github.io/) | RSS 2024 | VLM + mark-based visual prompting 开放词汇操作 | [GitHub](https://github.com/moka-manipulation/moka) | GPT-4V/API 与真实/仿真执行栈 | 可作为 agentic perception/affordance baseline |
| [Eureka](https://eureka-research.github.io/) | ICLR 2024 | LLM 生成奖励函数，强化学习机器人技能 | [GitHub](https://github.com/eureka-research/Eureka), Isaac Gym tasks | 依赖 LLM API 与 GPU RL | 更适合 reward/skill 自动发现方向 |
| [BEHAVIOR-1K](https://behavior.stanford.edu/index.html) | CoRL 2022, 2024+ 持续更新 | 长程家庭任务 benchmark | [GitHub](https://github.com/StanfordVL/BEHAVIOR-1K), OmniGibson/assets | Omniverse/资产/长程任务复杂 | 用作长程 agentic stress test，不建议第一天开始 |
| [VoxPoser](https://voxposer.github.io/) | CoRL 2023 | LLM/VLM 生成 3D value maps | [GitHub](https://github.com/huangwl18/VoxPoser) | 依赖 VLM/LLM 和 3D perception stack | 适合和 MDE/深度几何信号结合 |
| [Code as Policies](https://code-as-policies.github.io/) | ICRA 2023 | LLM 生成可执行机器人 policy code | 项目页/代码公开 | API 与机器人 primitive API 适配 | 适合做 agentic 高层程序控制 baseline |

## 3. P2: 新但不建议立刻作为主复现

这些工作很重要，但存在代码缺失、权重/数据不完整、或完整复现成本过高的问题。可以写 related work，不建议压成第一轮实验主线。

| 工作 | 年份/会议 | 原因 | 当前处理 |
|---|---|---|---|
| [CoT-VLA](https://cot-vla.github.io/) | CVPR 2025 | 项目页和论文公开，但未看到明确官方代码入口 | 作为 reasoning VLA 相关工作引用，暂不做主复现 |
| [SPEAR-1](https://spear.insait.ai/) | CVPR 2026 | 模型权重/3D 数据公开信号强，但完整训练/评测代码链路仍需核查 | 作为 3D-aware VLA 新威胁关注 |
| [pi0 / openpi](https://github.com/Physical-Intelligence/openpi) | 2024-2025 技术报告/开源仓库 | 代码和权重已开放，但原始大规模训练数据不完全公开，非顶会主论文 | 可做强工程 baseline，不放顶会主筛选表 |
| RT-2 / PaLM-E / RoboCat | CoRL/ICML 等 | 影响力高，但权重、训练数据、机器人栈闭源或不完整 | 只在 related work 讨论，不投入第一轮复现 |
| Dobb-E | arXiv 2023 | 数据/代码/硬件设计开放，但未确认顶会正式论文 | 家庭机器人方向可关注，不作为“顶会筛选”主项 |

## 4. 按研究路线分组

### 4.1 VLA / 通用机器人策略

| 工作 | 关键问题 | 数据规模 | 适合复现什么 |
|---|---|---:|---|
| Open X-Embodiment / RT-X | 多机器人、多任务数据统一格式能否带来跨 embodiment 迁移 | 1M+ real robot trajectories, 22 robot embodiments（项目页口径） | 数据下载、RLDS 格式、跨数据集训练 |
| Octo | 小得多的 open-source generalist policy 能否快速 fine-tune | 800k OXE episodes | inference、few-hour fine-tune、goal image/language conditioning |
| OpenVLA | 7B VLA 是否能成为通用 executor | 970k OXE episodes | LIBERO/BridgeData eval、LoRA/FT |
| CrossFormer / cross-embodiment learning | navigation + manipulation 等异构数据是否能共训 | 900k trajectories, 20 embodiments（PMLR 口径） | 先作为文献威胁，代码数据链路需再核查 |

优先级: `Octo -> OpenVLA -> OXE 子集训练`。OpenVLA 更接近 agentic robot executor，但 Octo 更容易在一般 GPU 上快速迭代。

### 4.2 语言/多模态 prompt 与 agentic 规划

| 工作 | 关键问题 | 复现入口 | 注意点 |
|---|---|---|---|
| VIMA | 文本、图像、视频提示能否统一成 robot prompt | VIMA-Bench + 官方代码 | 完全在仿真里跑，适合第一轮验证 prompt 泛化 |
| GenSim | LLM 能否生成仿真任务、expert goals 和课程 | CLIPort-style env + 官方 generated tasks | 新任务生成依赖 LLM，先用公开任务复现 |
| MOKA | VLM 能否用标注点/网格做开放词汇 affordance | 官方 demo code | 依赖 VLM API，不适合作为无 API 的硬复现 |
| VoxPoser | LLM/VLM 能否生成 3D value maps 做轨迹规划 | 官方 demo code | 是 MDE/深度几何结合点 |

优先级: `VIMA + GenSim` 先跑纯仿真，MOKA/VoxPoser 作为后续几何/感知增强路线。

### 4.3 数据 scale / 数据生成 / benchmark

| 工作 | 关键问题 | 数据/环境 | 推荐理由 |
|---|---|---|---|
| MimicGen | 少量 human demos 能否自动扩成高质量数据 | 48k+ released demos, robosuite/robomimic | 直接服务“数据不够”的问题 |
| DROID | 大规模 in-the-wild 真实操作数据是否提升泛化 | 76k demos / 350h / 数百 scenes | 真实数据 scale 主基准 |
| UMI | 不用真实机器人采集 in-the-wild 演示，能否迁移到机器人 | GoPro + hand-held gripper 数据 | 数据采集系统本身很值得复现 |
| RoboCasa / RoboCasa365 | 真实感厨房仿真 + LLM/generative assets 能否 scale | 100 -> 365 tasks, human + synthetic demos | 与长程家庭操作和 agentic benchmark 很贴近 |
| ManiSkill-HAB | GPU 加速低层家庭重排是否能高效 benchmark | TidyHouse/PrepareGroceries/SetTable 数据 | 适合做可控、快速、长程 stress test |
| MimicLabs | 哪些数据维度真正影响泛化 | controlled data generation | 对后续写“为什么收这种数据”有直接价值 |

优先级: 如果已有机器人学习代码基础，先跑 `MimicGen`; 如果想做 household agent，先跑 `RoboCasa`; 如果关注真实数据泛化，先跑 `DROID/UMI`。

### 4.4 3D/深度几何操作策略

| 工作 | 关键问题 | 公开资源 | 与 MDE 的交叉 |
|---|---|---|---|
| RVT | 多视角 re-render + transformer 是否比 voxel 更高效 | code + RLBench | 可用深度/多视角几何做输入增强 |
| 3D Diffuser Actor | diffusion action policy 是否能从 3D scene tokens 获益 | code + checkpoints + RLBench/CALVIN | 直接连接深度、点云、3D token 表示 |
| SPEAR-1 | 3D-aware VLM 是否能减少机器人数据需求 | weights / 3D-annotated data | 是 2026 年 3D-aware VLA 方向强威胁 |
| VoxPoser | 3D value map 是否能作为显式空间约束 | demo code | 可把 MDE 作为 value-map/constraint 输入 |

优先级: `RVT/3D Diffuser Actor` 比 `SPEAR-1` 更适合立刻动手，因为代码、benchmark 和复现协议更明确。

## 5. 推荐复现路线

### 5.1 3 天快速起跑

| 天数 | 目标 | 产物 |
|---:|---|---|
| Day 1 | 跑通 Diffusion Policy 官方 demo 和一个视觉任务 | 环境可用、日志、checkpoint eval 截图/数值 |
| Day 2 | 安装 LIBERO，跑一个 task suite 的数据加载和 baseline | 成功加载 demos，跑出最小 rollout |
| Day 3 | 跑 VIMA 或 GenSim 中一个官方任务 | 多模态 prompt 或 generated task pipeline 可用 |

### 5.2 2 周 P0 路线

| 阶段 | 目标 | 验收标准 |
|---|---|---|
| Week 1 | `LIBERO + DP/OpenVLA` 小规模复现 | 2-4 个任务的 success rate 能稳定复跑 |
| Week 1 | `VIMA` 官方 benchmark 子集 | 复现官方 checkpoint eval 流程 |
| Week 2 | `Octo` inference/fine-tune | 成功加载 HF checkpoint，并在小数据上 fine-tune |
| Week 2 | `MimicGen` 数据生成 | 从 source demos 生成新 demos，并训练一个 BC policy |
| Week 2 | `RoboCasa` 单任务训练/评测 | demo playback + 一个任务 baseline |

### 5.3 后续研究切口

| 切口 | 可以复用的 P0/P1 工作 | 研究问题 |
|---|---|---|
| Agentic verifier | LIBERO + OpenVLA + VIMA | verifier 是否能减少长程任务级联错误 |
| 几何/深度增强 executor | RVT + 3D Diffuser Actor + VoxPoser | 深度/3D token 是否提升遮挡、空间冲突、目标放置 |
| 数据选择与 scale | MimicGen + MimicLabs + DROID | 什么数据维度最值得收，如何检索最相关 demos |
| 家庭长程任务 | RoboCasa365 + ManiSkill-HAB + BEHAVIOR-1K | 长程任务中计划、记忆、恢复怎样评测 |
| 真实数据采集 | UMI + Mobile ALOHA + DROID | 低成本采集能否支撑 VLA fine-tune |

## 6. 不建议第一轮投入的坑

| 坑 | 原因 | 替代方案 |
|---|---|---|
| 一开始复现 RT-2/PaLM-E/RoboCat | 训练数据/权重/机器人栈闭源，不满足可复现筛选 | 用 OpenVLA/Octo |
| 一开始下载全量 OXE/DROID/RoboCasa365 | 数据巨大，容易先卡在存储和格式转换 | 先抽子集或跑官方 mini demo |
| 一开始上真实机器人 | 硬件、标定、安全、相机同步会吞掉主要时间 | 先仿真/公开数据跑通算法 |
| 只跑单步 pick-place | agentic robot 的核心是长程、失败检测、恢复 | 至少包含 LIBERO-Long/RoboCasa/ManiSkill-HAB 子集 |
| 只比较 VLA，不比较 DP/ACT | reviewer 会质疑强传统策略 baseline 缺失 | Diffusion Policy 和 ACT 至少保留一个 |

## 7. 参考链接

- Open X-Embodiment / RT-X: [project](https://robotics-transformer-x.github.io/), [code/data](https://github.com/google-deepmind/open_x_embodiment)
- Octo: [project](https://octo-models.github.io/), [code](https://github.com/octo-models/octo)
- OpenVLA: [project](https://openvla.github.io/), [code](https://github.com/openvla/openvla), [weights](https://huggingface.co/openvla/openvla-7b)
- Diffusion Policy: [project](https://diffusion-policy.cs.columbia.edu/), [code](https://github.com/real-stanford/diffusion_policy)
- LIBERO: [project](https://libero-project.github.io/main.html), [code](https://github.com/Lifelong-Robot-Learning/LIBERO)
- VIMA: [project](https://vimalabs.github.io/), [code](https://github.com/vimalabs/VIMA)
- MimicGen: [project/docs](https://mimicgen.github.io/), [code](https://github.com/NVlabs/mimicgen), [dataset](https://huggingface.co/datasets/amandlek/mimicgen_datasets)
- GenSim: [project](https://liruiw.github.io/gensim), [code](https://github.com/liruiw/GenSim)
- DROID: [project](https://droid-dataset.github.io/), [robot platform](https://github.com/droid-dataset/droid), [policy learning](https://github.com/droid-dataset/droid_policy_learning)
- RoboCasa/RoboCasa365: [project](https://robocasa.ai/), [code](https://github.com/robocasa/robocasa)
- UMI: [project](https://umi-gripper.github.io/), [code](https://github.com/real-stanford/universal_manipulation_interface), [community data](https://umi-data.github.io/)
- Mobile ALOHA: [project](https://mobile-aloha.github.io/), [code](https://github.com/MarkFzp/mobile-aloha), [TFDS data](https://www.tensorflow.org/datasets/catalog/aloha_mobile)
- RVT: [project](https://robotic-view-transformer.github.io/), [code](https://github.com/NVlabs/RVT)
- 3D Diffuser Actor: [project](https://3d-diffuser-actor.github.io/), [code](https://github.com/nickgkan/3d_diffuser_actor), [checkpoints](https://huggingface.co/katefgroup/3d_diffuser_actor)
- ManiSkill-HAB: [project](https://arth-shukla.github.io/mshab/), [code](https://github.com/arth-shukla/mshab)
- MimicLabs: [paper/project](https://robo-mimiclabs.github.io/), [code](https://github.com/Gatech-RL2/mimiclabs), [data](https://huggingface.co/datasets/vaibhavsaxena11/mimiclabs_datasets)
- ACT / ALOHA: [project](https://tonyzhaozh.github.io/aloha/), [code](https://github.com/tonyzhaozh/aloha)
- MOKA: [project](https://moka-manipulation.github.io/), [code](https://github.com/moka-manipulation/moka)
- Eureka: [project](https://eureka-research.github.io/), [code](https://github.com/eureka-research/Eureka)
- VoxPoser: [project](https://voxposer.github.io/), [code](https://github.com/huangwl18/VoxPoser)
- Code as Policies: [project](https://code-as-policies.github.io/)
- BEHAVIOR-1K: [project](https://behavior.stanford.edu/index.html), [code](https://github.com/StanfordVL/BEHAVIOR-1K)
- CoT-VLA: [project](https://cot-vla.github.io/)
- SPEAR-1: [project](https://spear.insait.ai/), [CVPR 2026 paper](https://openaccess.thecvf.com/content/CVPR2026/html/Nikolov_SPEAR-1_Scaling_Beyond_Robot_Demonstrations_via_3D_Understanding_CVPR_2026_paper.html)
