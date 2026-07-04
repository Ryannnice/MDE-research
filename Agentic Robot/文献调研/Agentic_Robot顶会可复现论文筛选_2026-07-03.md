# Agentic Robot 顶会可复现论文筛选

日期: 2026-07-04
修正对象: 2026-07-03 版过度偏向 VLA / 数据 scale / benchmark, 未贴合 `Agentic Robot` 与 `Goal2Skill` 的真正主线。
修正目标: 调研与两篇 PDF 相近的 agent + robot 工作, 重点是长程机器人操作中的 planner、executor、verifier/critic、memory、reflection、recovery、programmatic constraints, 而不是训练或雕塑一个新 VLA 模型。
CCFA 使用说明: 按本地 `ccf-literature-searcher` standard mode 与 `ccf-common` source policy 执行; 使用公开关键词检索, 优先官方论文页、项目页、GitHub、arXiv/OpenReview/CVF/PMLR/IEEE/ACM; MDPI/低质来源不纳入主表; 未复现实验一律写“原文报告”或“待跑”。

## 0. 一页修正结论

`Agentic Robot` 和 `Goal2Skill` 的可模仿点不是“再造一个更大的 VLA”, 而是把已有 VLA / diffusion policy / primitive library 放进一个可审计的 agentic harness:

```text
instruction
  -> planner: task decomposition, pre/post-condition, constraints
  -> executor: OpenVLA / DP / ACT / skill primitive
  -> verifier / monitor / critic: progress, failure, stuck, unsafe future state
  -> memory: raw keyframes, working summary, error register
  -> recovery: retry, adjust-param, rollback, replan
```

因此, 2026-07-03 版中 `OpenVLA / Octo / SpatialVLA / pi0` 等应从“主研究路线”降级为 executor 或 reviewer-threat baseline。真正应该优先调研和复现的是:

| 优先级 | 研究路线 | 代表工作 | 为什么贴近两篇 PDF |
|---|---|---|---|
| P0 | Planner-Executor-Verifier-Recovery 闭环 | Agentic Robot, Code-as-Monitor, HELM, SV-VLA, CLOVER | 都把错误检测/验证/重规划放进执行环, 直接对应 Agentic Robot 的 SAP |
| P0 | Memory-aware agentic manipulation | Goal2Skill, RMBench, HELM, RoboCerebra | 都强调长程任务中 history、working memory、error register 不是普通长上下文 |
| P0 | Programmatic / geometric constraints | ReKep, VoxPoser, Code as Policies, ProgPrompt, MOKA | 可模仿为“LLM/VLM 生成可执行约束/代码/3D value map”, 比端到端模型更可控 |
| P1 | Reflection / imagined future / self-improvement | Reflective Planning, SOAR, RoboClaw | 对应 Goal2Skill 的 reflection 与 Agentic Robot 的 recovery, 但复现成本更高 |
| P1 | Agentic task/data generation | GenSim, RoboGen, AutoRT | 不是运行时控制核心, 但能生成长程任务、失败样本和训练数据 |
| P2 | Pure VLA / model scaling | OpenVLA, Octo, SpatialVLA, Long-VLA, pi0/pi0.5 | 必须作为 executor/baseline/threat, 不建议作为本方向第一贡献 |

推荐第一阶段的立项句子:

> 构建一个 model-agnostic agentic robot harness: 在不改动底层 VLA/DP executor 的前提下, 用结构化子目标、显式记忆、可执行几何/语义约束 verifier 和分级 recovery, 提升 LIBERO-Long / RMBench / VLABench 上的长程操作鲁棒性。

最小可行复现路线:

| 阶段 | 目标 | 最小实验 | 成败门槛 |
|---|---|---|---|
| Week 1 | 复现 executor 与环境 | LIBERO-Long 小任务 + OpenVLA/DP baseline | 能稳定跑 rollout, 不追全套 SOTA |
| Week 2 | Agentic Robot-style SAP | planner 分解 + verifier gate + retry/replan | 相比裸 executor, 长程错误级联减少 |
| Week 3 | Goal2Skill-style memory | RMBench 2-3 个 memory task + raw keyframe memory + error register | memory ablation 有方向性收益 |
| Week 4 | 可模仿创新点 | 加入 Code-as-Monitor/ReKep 式约束 verifier 或 geometry-aware monitor | 证明不是单纯多调 VLM, 而是约束/记忆/恢复机制有效 |

## 1. 与两篇 PDF 的目标对齐

### 1.1 两篇 PDF 的共同贡献边界

| 维度 | Agentic Robot | Goal2Skill | 对本调研的筛选含义 |
|---|---|---|---|
| 核心问题 | 长程操作错误积累, 无验证推进 | 记忆依赖、部分可观测、失败恢复 | 筛选长程/闭环/失败恢复论文, 不筛普通 pick-place |
| 高层系统 | SAP: Planner -> Executor -> Verifier -> Recovery | Dual-system: planner + memory + verifier/reflection + executor | 重点找 planner/harness/monitor/recovery |
| 低层执行 | OpenVLA executor | VLA / diffusion skill library | VLA 是执行器, 不是主贡献 |
| 判断信号 | temporal verifier 判定 subgoal 是否完成/卡住 | post-condition verifier + reflection | verifier/critic/failure monitor 是主线 |
| 记忆 | 相对弱 | episodic history + working memory + error register | 记忆是 Goal2Skill 的核心差异 |
| 风险 | verifier 标注与泛化不足 | 代码/细节不足, 需自搭 | 找可开源补位论文和 benchmark |

### 1.2 需要从 2026-07-03 版删除的隐含假设

- 错误假设 1: “Agentic Robot = VLA 论文筛选”。
  修正: Agentic Robot 是 VLA 外部的 agentic coordination protocol。

- 错误假设 2: “复现优先级按模型/数据规模排序”。
  修正: 复现优先级应按 harness 是否可拆、verifier 是否可训、memory/recovery 是否可消融排序。

- 错误假设 3: “顶会可复现 = 只收 NeurIPS/ICML/ICLR/CVPR”。
  修正: CCF-A 视角下 CVPR/ICCV/NeurIPS/ICML/ICLR 是 A 类; RSS/CoRL/ICRA/IROS 是机器人顶会/强会, 不能冒充 CCF-A, 但在 robot manipulation 方向必须纳入。

## 2. 主表: Agentic Robot / Goal2Skill 近邻论文

评分说明: `Insight / Complete / Evidence` 为 1-5 的文献质量与可审计性粗评, 不是接收概率。`Evidence=N/A benchmark` 表示基准论文不按方法数值评分。

| # | 工作 | 年份/来源 | 类型 | 代码/数据 | Agentic 机制 | Insight | Complete | Evidence | 本方向用途 |
|---:|---|---|---|---|---|---:|---:|---:|---|
| 1 | [Agentic Robot](https://arxiv.org/abs/2505.23450) / [project](https://agentic-robot.github.io/) / [code](https://github.com/Agentic-Robot/agentic-robot) | 2025 arXiv | pure method/system | GitHub 可见 | SAP: planner-executor-verifier-recovery | 4 | 3 | 4 | P0 主复现; LIBERO-Long 闭环模板 |
| 2 | [Goal2Skill](https://arxiv.org/abs/2604.13942) | 2026 arXiv | pure method | 未找到明确官方代码 | memory + adaptive planning + reflection | 4 | 2 | 3 | P0/P1 仿框架; RMBench memory/recovery 模板 |
| 3 | [Code-as-Monitor](https://zhoues.github.io/Code-as-Monitor/) / [CVF PDF](https://openaccess.thecvf.com/content/CVPR2025/papers/Zhou_Code-as-Monitor_Constraint-aware_Visual_Programming_for_Reactive_and_Proactive_Robotic_Failure_CVPR_2025_paper.pdf) | CVPR 2025 | pure method | 项目页/论文; 代码入口需核查 | VLM 生成监控代码, reactive + proactive failure detection | 5 | 4 | 4 | P0 verifier/monitor 强近邻; 可替代简单 yes/no VLM verifier |
| 4 | [HELM](https://arxiv.org/abs/2604.18791) | 2026 arXiv | method + protocol | 未找到官方代码 | episodic memory + learned state verifier + rollback/replan | 4 | 3 | 4 | P0 机制威胁; 与 Goal2Skill/Agentic Robot 直接撞线 |
| 5 | [Reflective Planning](https://reflect-vlm.github.io/) / [code](https://github.com/yunhaif/reflect-vlm) | 2025 arXiv | method + benchmark | code, models, dataset 可见 | diffusion future imagination + VLM reflection | 4 | 4 | 4 | P0/P1 reflection baseline; 可复现实验入口清楚 |
| 6 | [CLOVER](https://proceedings.neurips.cc/paper_files/paper/2024/hash/fad8962279154544ed69bb63eb14d677-Abstract-Conference.html) / [code](https://github.com/OpenDriveLab/CLOVER) | NeurIPS 2024 | pure method | code/checkpoints 可见 | visual plan + feedback error + replan | 4 | 4 | 4 | P0 闭环视觉控制强基线; CCF-A |
| 7 | [SV-VLA](https://arxiv.org/abs/2604.02965) / [code](https://github.com/edsad122/SV-VLA) | 2026 arXiv | pure method | code 可见 | heavy VLA macro-planner + lightweight online verifier | 4 | 3 | 3 | P0 效率/鲁棒 verifier 路线; 与 SAP verifier 对齐 |
| 8 | [ReKep](https://rekep-robot.github.io/) / [PMLR](https://proceedings.mlr.press/v270/huang25g.html) / [code](https://github.com/huangwl18/ReKep) | CoRL 2024 | pure method | demo code 可见 | VLM/large vision model 生成 3D relational keypoint constraints | 5 | 4 | 4 | P0 几何/约束 planner 模板; 适合与 MDE/深度结合 |
| 9 | [VoxPoser](https://voxposer.github.io/) / [OpenReview](https://openreview.net/forum?id=9_8LF30mOC) / [code](https://github.com/huangwl18/VoxPoser) | CoRL 2023 | pure method | demo code 可见 | LLM/VLM 生成 3D value maps 供 motion planner 使用 | 5 | 4 | 4 | P0 几何 grounding 先驱; ReKep 前身 |
| 10 | [MOKA](https://moka-manipulation.github.io/) / [RSS page](https://roboticsconference.org/2024/program/papers/62/) / [code](https://github.com/moka-manipulation/moka) | RSS 2024 | pure method | code 可见 | mark-based keypoint affordance, VLM-to-action bridge | 4 | 4 | 4 | P1 open-world affordance front-end; 可服务 verifier/skill parameter |
| 11 | [SayCan](https://say-can.github.io/) / [arXiv](https://arxiv.org/abs/2204.01691) | CoRL 2022 | pure method | 项目页; 完整机器人栈不全 | LLM planning score + skill affordance/value score | 5 | 3 | 4 | P1 planner-executor 解耦祖先; 不是现代 verifier loop |
| 12 | [Inner Monologue](https://proceedings.mlr.press/v205/huang23c.html) / [project](https://innermonologue.github.io/) | CoRL 2022 | pure method | 项目页 | environment feedback 写回语言上下文 | 4 | 3 | 4 | P1 feedback/replanning 祖先; 适合 related work |
| 13 | [ProgPrompt](https://progprompt.github.io/) / [arXiv](https://arxiv.org/abs/2209.11302) | ICRA 2023 | pure method | 项目/代码线索可见 | program-like prompt, precondition/assertion, situated planning | 4 | 3 | 3 | P1 typed subgoal / precondition 表达参考 |
| 14 | [Code as Policies](https://code-as-policies.github.io/) / [IEEE](https://ieeexplore.ieee.org/document/10160591/) | ICRA 2023 | pure method | project/colab | LLM 生成可执行 robot policy code | 4 | 3 | 3 | P1 programmatic executor/planner 参考 |
| 15 | [Instruct2Act](https://arxiv.org/abs/2305.11176) / [code](https://github.com/OpenGVLab/Instruct2Act) | 2023 arXiv/OpenReview | pure method | code 可见 | LLM 生成 perception-planning-action Python loop | 3 | 3 | 3 | P1 可复现 agent loop; 非顶会主证据 |
| 16 | [DoReMi](https://arxiv.org/abs/2307.00329) / [project](https://sites.google.com/view/doremi-paper) | IROS 2024 | pure method | 项目页; 代码未确认 | LLM 生成约束, VLM 连续检测 plan-execution misalignment | 4 | 3 | 3 | P1 recovery 近邻; 与 Code-as-Monitor/Agentic Robot 对比 |
| 17 | [CoPAL](https://arxiv.org/abs/2310.07263) | ICRA 2024 | pure method | 代码需核查 | reasoning/planning/motion 多层反馈与 corrective replanning | 3 | 3 | 3 | P1 corrective planning 相关工作 |
| 18 | [VIMA](https://vimalabs.github.io/) / [PMLR PDF](https://proceedings.mlr.press/v202/jiang23b/jiang23b.pdf) / [code](https://github.com/vimalabs/VIMA) | ICML 2023 | method + benchmark | code/benchmark/data 可见 | multimodal prompts unify task specs | 4 | 5 | 4 | P1 prompt/benchmark 参考; CCF-A |
| 19 | [GenSim](https://openreview.net/forum?id=OI3RoHoWAN) / [code](https://github.com/liruiw/GenSim) | ICLR 2024 Spotlight | system/tool | code 可见 | LLM 生成 simulation tasks, goals, curricula, demonstrations | 4 | 4 | 4 | P1 生成长程任务/失败数据; CCF-A |
| 20 | [RoboGen](https://proceedings.mlr.press/v235/wang24cc.html) / [project](https://robogen-ai.github.io/) / [code](https://github.com/Genesis-Embodied-AI/RoboGen) | ICML 2024 | system/tool | code 可见 | propose-generate-learn 自引导技能学习循环 | 4 | 4 | 4 | P1 自动任务/技能生成; CCF-A |
| 21 | [SOAR](https://proceedings.mlr.press/v270/zhou25b.html) / [project](https://auto-improvement.github.io/) / [code](https://github.com/rail-berkeley/soar) | CoRL 2024 | system + dataset | code/data 可见 | VLM task proposal + success detection + autonomous data loop | 4 | 4 | 4 | P1 自改进与自动数据收集 |
| 22 | [RoboClaw](https://arxiv.org/abs/2603.11558) / [project](https://roboclaw-agibot.github.io/) / [code](https://github.com/RoboClaw-Robotics/RoboClaw) | 2026 arXiv | system | code 可见 | 同一 VLM agent 贯穿 data collection, policy learning, deployment | 4 | 3 | 3 | P1/P2 最新 agentic lifecycle 近邻 |
| 23 | [Critic in the Loop](https://arxiv.org/abs/2603.05185) | 2026 arXiv | pure method | 代码未确认 | VLM brain + VLA cerebellum + lightweight visual critic | 4 | 2 | 3 | P2 概念近邻; 代码/评测需核查 |
| 24 | [AutoRT](https://arxiv.org/abs/2401.12963) / [project](https://auto-rt.github.io/) | 2024 arXiv/OpenReview | system | 官方代码未确认 | VLM/LLM orchestrate robot fleet data collection and safety | 4 | 3 | 4 | P2 大规模 agent orchestration 背景 |

## 3. Benchmark / 数据集表

| Benchmark | 年份/来源 | 代码/数据 | 任务属性 | 与两篇 PDF 的关系 | 使用建议 |
|---|---|---|---|---|---|
| [LIBERO](https://libero-project.github.io/main.html) / [code](https://github.com/Lifelong-Robot-Learning/LIBERO) | NeurIPS 2023 Datasets & Benchmarks | GitHub/demos | language-conditioned manipulation, Spatial/Object/Goal/Long | Agentic Robot 主评测 | P0; 先跑 LIBERO-Long 2-4 个任务 |
| [RMBench](https://rmbench.github.io/) / [code](https://github.com/robotwin-Platform/rmbench) | 2026 arXiv | GitHub | memory-dependent manipulation, 9 tasks | Goal2Skill 主评测 | P0/P1; memory/recovery 必跑 |
| [VLABench](https://vlabench.github.io/) / [code](https://github.com/OpenMOSS/VLABench) | ICCV 2025 | GitHub | 100 task categories, long-horizon reasoning, VLA/VLM/workflow eval | 可测 agent workflow 而非只测 VLA | P1; 做泛化/隐式意图压力测试 |
| [RoboCerebra](https://arxiv.org/html/2506.06677v1) / [code](https://github.com/buaa-colalab/RoboCerebra) | NeurIPS 2025 D&B | GitHub | System-2 long-horizon robotic manipulation benchmark | 检验 planning, reflection, memory | P1/P2; 适合后续 agentic reasoning benchmark |
| [BEHAVIOR-1K](https://proceedings.mlr.press/v205/li23a.html) / [code](https://github.com/StanfordVL/BEHAVIOR-1K) | CoRL 2022 | GitHub/assets | 1000 everyday household activities, mobile manipulation | 更真实但复现重 | P2; 不建议第一阶段主跑 |
| [CALVIN](http://calvin.cs.uni-freiburg.de/) | 常用长程 manipulation benchmark | code/data 可见 | multi-step language-conditioned manipulation | CLOVER/HELM 等会用 | P1; 作为 LIBERO 外验证 |
| [VIMA-Bench](https://github.com/vimalabs/VIMABench) | ICML 2023 | code/data | multimodal prompt task suite | prompt generalization 参考 | P2; 适合 prompt-agent 消融 |

协议注意:

- LIBERO-Long 和 RMBench 的优势才是本方向证据; 单步 pick/place 不足以支撑 agentic robot claim。
- RMBench 必须区分 M(1) 与 M(n); Goal2Skill 的收益主要来自 memory-dependent setting。
- VLABench/RoboCerebra 更像“能不能做 System-2/agent workflow”的新压力测试, 不适合作为第一周起跑。

## 4. Closest-work clusters

### 4.1 闭环验证与恢复

代表工作: Agentic Robot, Code-as-Monitor, HELM, SV-VLA, DoReMi, CoPAL, Critic in the Loop, CLOVER.

已经覆盖:

- planner/executor 解耦已不是新颖点。
- “VLM 看图判断成功/失败”也不是新颖点。
- 2025-2026 近邻已经把 verifier/critic 放入长程 loop, 并开始强调 proactive failure detection、rollback、dynamic routing。

仍然开放:

- verifier 如何从 `yes/no` 变成可执行约束、可解释失败类型和恢复动作选择。
- verifier 如何利用几何/深度/3D keypoint, 而不只是 RGB VQA。
- recovery 不能只有 retry/lift gripper; 需要 typed recovery, 如 rollback, adjust-parameter, re-segment, re-grasp, replan。

可做路线:

- 用 Code-as-Monitor/ReKep 式约束作为 Agentic Robot 的 verifier, 替换简单 VLM binary verifier。
- 把 Goal2Skill 的 `error register` 与 verifier 输出绑定, 让失败类型驱动恢复策略。
- 做 proactive monitor: 在子任务执行前判定潜在失败, 而不是失败后再问 VLM。

### 4.2 程序化规划与几何约束

代表工作: SayCan, Inner Monologue, ProgPrompt, Code as Policies, Instruct2Act, VoxPoser, ReKep, MOKA.

已经覆盖:

- LLM 选 skill / 写代码 / 生成 task plan 已有充分先例。
- 3D value maps、relational keypoint constraints、mark-based keypoints 都已经证明 “LLM/VLM -> 可执行空间表示” 是可行路线。

仍然开放:

- 这些方法多半关注 single task 或 open-set instruction, 对长程 memory/recovery 的系统评测不足。
- constraint planner 与 VLA executor 的接口还不统一: subgoal 是语言、代码、keypoint cost, 还是 post-condition?
- MDE/深度信号如何成为 verifier/constraint 的 first-class input, 仍有空间。

可做路线:

- 采用 Goal2Skill 的 structured subtask tuple: `instruction, precondition, postcondition, constraint, horizon, recovery`.
- 让 ReKep/VoxPoser/MOKA 产生子任务级几何约束, 再用 OpenVLA/DP 执行。
- 把几何约束同时用于 pre-execution feasibility check 和 post-execution verification。

### 4.3 记忆与长程上下文

代表工作: Goal2Skill, HELM, RMBench, RoboCerebra, VLABench, Agentic Robot.

已经覆盖:

- “拉长上下文”不是充分解法。HELM 明确把 memory gap、verification gap、recovery gap 分开讨论。
- RMBench 已把 memory-dependent manipulation 单独做成评测。

仍然开放:

- working summary 可能丢细节; Goal2Skill 原文 ablation 显示 raw history 很关键。
- memory 应该服务 planner、verifier 还是 recovery, 需要消融拆开。
- 失败记忆如何跨 episode 使用仍不清楚。

可做路线:

- 最小记忆设计: raw keyframes + object-state table + error register。
- 消融: no memory / raw keyframes only / summary only / raw + summary / raw + error register。
- 指标: success rate, recovery success, verifier false positive/false negative, replan count, failed subgoal cascade length。

### 4.4 自动数据、任务与自改进

代表工作: GenSim, RoboGen, SOAR, AutoRT, RoboClaw.

已经覆盖:

- LLM 生成任务/仿真代码/训练监督已有 CCF-A 论文。
- VLM 作为 task proposer 与 success detector 已被 SOAR/AutoRT 使用。

仍然开放:

- 生成数据和运行时 agentic control 的连接不够紧。
- failure/recovery 数据集仍少, verifier 训练数据通常是瓶颈。

可做路线:

- 用 GenSim/RoboGen 生成 long-horizon task variants 和 failure cases。
- 用 Agentic Robot / Goal2Skill harness 采集 verifier/recovery 标注。
- 把失败片段做成 `LIBERO-Recovery` 风格 perturbation protocol。

## 5. 推荐复现与研究方案

### 5.1 先复现的系统骨架

```text
State:
  observation: RGB/RGB-D frames
  task_memory: raw keyframes + object state + subgoal history
  error_register: failed subgoal, failure type, attempted recovery

Planner:
  input: instruction + observation summary + task_memory + error_register
  output: typed subgoal tuple
    - instruction
    - precondition
    - postcondition
    - geometric/semantic constraints
    - executor hint
    - max horizon
    - recovery candidates

Executor:
  OpenVLA / Diffusion Policy / ACT / scripted primitive

Verifier/Monitor:
  fast checks: object/keypoint/constraint state
  VLM checks: subgoal completion, semantic mismatch, stuck
  memory-conditioned checks: whether current step contradicts prior task context

Recovery:
  retry
  adjust parameter
  rollback to previous safe state
  re-perceive/re-segment
  replan from error_register
```

### 5.2 最小实验矩阵

| Claim | Benchmark | Baselines | Ablations | Metrics |
|---|---|---|---|---|
| verifier gate 减少长程级联错误 | LIBERO-Long | OpenVLA/DP, Agentic Robot-style binary verifier | no verifier, VLM yes/no, constraint verifier, constraint+VLM | SR, subgoal SR, false advance rate |
| structured memory 帮助 memory-dependent manipulation | RMBench | ACT/DP/OpenVLA, Goal2Skill-style planner | no memory, summary, raw keyframes, error register | SR M(1)/M(n), recovery success |
| geometry-aware monitor 比纯 RGB VLM 更稳 | LIBERO/RMBench hard cases | VLM verifier, Code-as-Monitor-style monitor, ReKep constraint | no depth, RGB constraints, RGB-D constraints | verifier F1, replan precision, latency |
| recovery policy 不是装饰 | perturbation protocol / LIBERO-Recovery-style | retry only, fixed lift, typed recovery | no recovery, retry, adjust, rollback, replan | recovered SR, extra steps, failure loop count |

### 5.3 复现优先级

| 优先级 | 动作 | 具体论文/组件 |
|---|---|---|
| P0-1 | 跑环境和 executor | LIBERO + DP/OpenVLA |
| P0-2 | 搭 SAP loop | Agentic Robot 的 planner-executor-verifier-recovery |
| P0-3 | 加强 verifier | Code-as-Monitor 约束思想 + VLM binary verifier |
| P0-4 | 加 memory/recovery | Goal2Skill/RMBench + error register |
| P1-1 | 加几何 planner | ReKep/VoxPoser/MOKA 的 keypoint/value-map/affordance 表示 |
| P1-2 | 加 reflection | Reflective Planning 或 CLOVER 的 imagined future / visual plan feedback |
| P2 | 扩 benchmark | VLABench/RoboCerebra/BEHAVIOR-1K |

## 6. 与 VLA 论文的正确关系

VLA 论文仍然重要, 但位置要改:

| 类别 | 代表 | 在本方向中的位置 |
|---|---|---|
| executor baseline | OpenVLA, Octo, DP, ACT | 作为低层执行器, 评估 agentic harness 是否提升同一 executor |
| strong threat | SpatialVLA, TraceVLA, pi0/pi0.5, Long-VLA | 如果它们裸模型已解决长程任务, agentic harness 的必要性会被削弱 |
| data/model scaling | Open X-Embodiment, DROID, RoboCasa, UMI | 背景/数据源, 不作为第一贡献 |
| model-sculpting routes | tokenization, phase mask, 3D-aware VLA | 暂不主攻; 除非 harness 路线失败 |

写作边界:

- 可以说: 本工作不追求训练更大的 VLA, 而是研究如何将现有 robot policies 组织成可验证、可恢复、带记忆的 agentic robot system。
- 不能说: 本工作全面优于 VLA foundation models。
- 必须报告: 同 executor 下加/不加 harness 的差异, 否则 reviewer 会认为收益来自模型或数据差异。

## 7. 最值得模仿的三类设计

### 7.1 Agentic Robot/HELM/Code-as-Monitor 式 verifier 设计

可模仿:

- verifier 输入不只是当前图像, 还包括 subgoal、post-condition、memory、constraints。
- verifier 输出不只是 yes/no, 而是 `success / still-trying / stuck / semantic-mismatch / unsafe / impossible`。
- verifier 触发 recovery/replan, 而不是只做离线评价。

需要新增证据:

- verifier false advance rate: 上一步失败却放行下一步的比例。
- verifier false block rate: 子任务成功却阻塞的比例。
- recovery precision: 被触发的恢复是否真的提升成功率。

### 7.2 Goal2Skill 式 memory design

可模仿:

- `episodic history`: 保留关键帧和动作结果, 不只保留摘要。
- `working memory`: 当前任务相关对象、位置、约束、未完成子目标。
- `error register`: 失败类型、触发条件、恢复动作、是否有效。

需要新增证据:

- raw history vs summary 的消融。
- memory 参与 planner vs verifier vs recovery 的拆分。
- memory 错误或过期时的失败分析。

### 7.3 ReKep/VoxPoser/Code-as-Monitor 式约束接口

可模仿:

- 用 LLM/VLM 生成空间约束或监控代码, 让 subgoal 有可执行判据。
- 约束从语言落到 keypoint/3D value map/constraint element。
- geometry/depth 信号进入 verifier, 解决“看起来完成但空间上错误”的问题。

需要新增证据:

- RGB-only verifier vs RGB-D/geometric verifier。
- spatial conflict hard cases, 如相同物体、遮挡、目标放置冲突。
- constraint 生成错误的失败案例和 fallback。

## 8. 检索记录与来源策略

安全公开检索关键词:

- `agentic robot long-horizon manipulation planner executor verifier recovery`
- `robot manipulation VLM verifier monitor failure recovery long horizon`
- `LLM robot task planning code policies constraints keypoint value maps`
- `memory-dependent robotic manipulation benchmark RMBench Goal2Skill`
- `closed-loop VLA verifier recovery long-horizon manipulation`

来源策略:

- 主证据使用官方项目页、arXiv/OpenReview/CVF/PMLR/IEEE/GitHub。
- ResearchGate、博客、awesome list 只作为发现线索, 不作为主证据。
- MDPI 来源不纳入主表。
- 会议标注保持诚实: CVPR/ICCV/NeurIPS/ICML/ICLR 归 CCF-A 视角; RSS/CoRL/ICRA/IROS 标为机器人顶会/强会。

主要来源链接:

- Agentic Robot: [arXiv](https://arxiv.org/abs/2505.23450), [project](https://agentic-robot.github.io/), [GitHub](https://github.com/Agentic-Robot/agentic-robot)
- Goal2Skill: [arXiv](https://arxiv.org/abs/2604.13942)
- Code-as-Monitor: [project](https://zhoues.github.io/Code-as-Monitor/), [CVF PDF](https://openaccess.thecvf.com/content/CVPR2025/papers/Zhou_Code-as-Monitor_Constraint-aware_Visual_Programming_for_Reactive_and_Proactive_Robotic_Failure_CVPR_2025_paper.pdf)
- Reflective Planning: [project](https://reflect-vlm.github.io/), [GitHub](https://github.com/yunhaif/reflect-vlm)
- CLOVER: [NeurIPS](https://proceedings.neurips.cc/paper_files/paper/2024/hash/fad8962279154544ed69bb63eb14d677-Abstract-Conference.html), [GitHub](https://github.com/OpenDriveLab/CLOVER)
- ReKep: [project](https://rekep-robot.github.io/), [PMLR](https://proceedings.mlr.press/v270/huang25g.html), [GitHub](https://github.com/huangwl18/ReKep)
- VoxPoser: [project](https://voxposer.github.io/), [OpenReview](https://openreview.net/forum?id=9_8LF30mOC), [GitHub](https://github.com/huangwl18/VoxPoser)
- SayCan: [project](https://say-can.github.io/), [arXiv](https://arxiv.org/abs/2204.01691)
- Inner Monologue: [PMLR](https://proceedings.mlr.press/v205/huang23c.html), [project](https://innermonologue.github.io/)
- Code as Policies: [project](https://code-as-policies.github.io/), [IEEE](https://ieeexplore.ieee.org/document/10160591/)
- ProgPrompt: [project](https://progprompt.github.io/), [arXiv](https://arxiv.org/abs/2209.11302)
- MOKA: [project](https://moka-manipulation.github.io/), [RSS](https://roboticsconference.org/2024/program/papers/62/), [GitHub](https://github.com/moka-manipulation/moka)
- GenSim: [OpenReview](https://openreview.net/forum?id=OI3RoHoWAN), [GitHub](https://github.com/liruiw/GenSim)
- RoboGen: [PMLR](https://proceedings.mlr.press/v235/wang24cc.html), [project](https://robogen-ai.github.io/), [GitHub](https://github.com/Genesis-Embodied-AI/RoboGen)
- SOAR: [PMLR](https://proceedings.mlr.press/v270/zhou25b.html), [project](https://auto-improvement.github.io/), [GitHub](https://github.com/rail-berkeley/soar)
- LIBERO: [project](https://libero-project.github.io/main.html), [GitHub](https://github.com/Lifelong-Robot-Learning/LIBERO)
- RMBench: [project](https://rmbench.github.io/), [GitHub](https://github.com/robotwin-Platform/rmbench)
- VLABench: [project](https://vlabench.github.io/), [GitHub](https://github.com/OpenMOSS/VLABench)
- RoboCerebra: [arXiv HTML](https://arxiv.org/html/2506.06677v1), [GitHub](https://github.com/buaa-colalab/RoboCerebra)

## 9. 当前 go/no-go 判断

GO, 但必须把 claim 收窄到 agentic harness。

可主张:

- 长程机器人操作的主要瓶颈之一是执行环缺少显式记忆、验证和恢复。
- 在同一 executor 上, 结构化 planner/verifier/memory/recovery 可以减少级联错误。
- 几何/约束型 verifier 是比普通 VLM yes/no 更强的可研究切口。

不可主张:

- 不要声称提出新 VLA foundation model。
- 不要声称替代 OpenVLA/pi0/SpatialVLA。
- 不要只用单步任务或平均 SR 支撑长程 agentic claim。

下一步应做:

1. 先复现 LIBERO-Long 小集 executor baseline。
2. 用最小 SAP harness 复刻 Agentic Robot 的推进逻辑。
3. 在 RMBench 上加入 raw memory + error register。
4. 引入 Code-as-Monitor/ReKep 式约束 verifier, 做 RGB-only vs geometric verifier 消融。
