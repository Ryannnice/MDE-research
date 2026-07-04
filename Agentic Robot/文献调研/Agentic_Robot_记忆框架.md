# Agentic Robot 记忆与长程上下文专题调研

日期：2026-07-04

调研目的：围绕 Agentic Robot 中的“记忆与长程上下文”方向做更深入调研，优先考虑顶会、机器人强会、可复现 benchmark/code，并为后续可发表研究设计提供依据。

目标会议/领域：CCF-A 视角（CVPR/ICCV/ICML/NeurIPS/ICLR）+ 机器人顶会/强会（CoRL/RSS/ICRA/IROS）。

来源质量策略：已应用。主证据使用官方项目页、arXiv、CVF、PMLR、OpenReview、NeurIPS proceedings、GitHub；MDPI、ResearchGate、非主源解读站不进入主表。

## 总结

- 结论：这个方向仍然可以做，但中心 claim 不能再是“给 VLA 加记忆”或“拉长上下文”。2026 年已经出现 RMBench、RoboMME、RoboMemArena、EventVLA、KEMO、GMP、Chameleon 等一批直接竞争工作。
- 最稳切口：把 memory 明确做成 agentic harness 的服务层，并拆开服务对象：规划器（planner）、验证器（verifier）、恢复控制器（recovery）和执行器（executor）。现有工作多证明“记忆有用”，但很少把“记忆为什么有用、给谁用、何时写入、何时遗忘、失败记忆如何跨 episode 迁移”完整拆开。
- 最强近邻风险：HELM 已经提出 memory gap、verification gap、recovery gap，并用 episodic keyframe memory + learned verifier + rollback/replan 打到非常近；Goal2Skill 已经有 episodic history、working memory、error register；RoboMME 已经系统比较 symbolic / perceptual / recurrent memory。
- 最小可复现路线：RMBench + LIBERO-Long/LIBERO-Recovery + RoboMME 子集。先做不训练大模型的 harness-level memory，再逐步接入 EventVLA/KEMO/GMP 等 executor-level memory baseline。
- 推荐问题表述：不是“memory-augmented VLA”，而是“面向可验证与可恢复长程操作的类型化记忆”（typed memory for verifiable and recoverable long-horizon manipulation）。

## 研究边界

本专题只纳入与以下问题直接相关的工作：

1. 长程 manipulation 中历史信息不可见、遮挡、计数、阶段歧义、动作-观察延迟。
2. 记忆如何影响 planner、verifier、recovery 或 low-level executor。
3. 可复现实验：公开 benchmark、代码、数据、模型、可运行 repo 或清晰评测协议。
4. 顶会/强会优先；最新 arXiv 只作为 frontier threat 或可复现组件，而不是已审定顶会证据。

## 论文主表

| # | 工作 | 年份 | 来源/会议 | 可复现性 | 类型 | Insight | Completeness | 数值证据 | 总体 | 备注 |
| ---: | --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| 1 | [HELM: Harness-Enhanced Long-horizon Memory for VLA Manipulation](https://arxiv.org/abs/2604.18791) | 2026 | arXiv | 声称释放 LIBERO-Recovery protocol；本次未验证官方代码 | pure method | 5 | 3 | 4 | Risk/A | 直接拆分 memory、verification、recovery 三类 gap；是 harness-level 贡献的最近风险。 |
| 2 | [Goal2Skill: Long-Horizon Manipulation with Adaptive Planning and Reflection](https://arxiv.org/html/2604.13942v1) | 2026 | arXiv | 未验证官方代码；使用 RMBench 任务 | pure method | 4 | 2 | 3 | Risk | 已有 episodic history、working memory、error register、verifier 和 reflection recovery。 |
| 3 | [Agentic Robot](https://agentic-robot.github.io/) / [code](https://github.com/Agentic-Robot/agentic-robot) | 2025 | arXiv/project | GitHub 可访问；面向 LIBERO | system/tool | 4 | 3 | 4 | A | SAP 式 planner-executor-verifier 闭环；记忆部分弱于 Goal2Skill/HELM，因此适合作为扩展骨架。 |
| 4 | [RMBench](https://arxiv.org/abs/2603.01229) / [code](https://github.com/RoboTwin-Platform/RMBench) | 2026 | arXiv | GitHub 可访问；基于 RoboTwin 2.0 | pure benchmark | 4 | 4 | N/A benchmark | A | 9 个 memory-dependent task 和 Task Memory Complexity；本方向 P0 benchmark。 |
| 5 | [RoboMME](https://robomme.github.io/) / [code](https://github.com/RoboMME/robomme_benchmark) | 2026 | ICML 2026 Oral / arXiv | benchmark、policy code、dataset、models 均有链接 | method + benchmark | 5 | 5 | N/A benchmark | A/Risk | 最强记忆分类体系：temporal、spatial、object、procedural；比较 14 种 memory-augmented VLA variants。 |
| 6 | [RoboMemArena](https://robomemarena.github.io/) / [code](https://github.com/OpenHelix-Team/RoboMemArena) | 2026 | arXiv/project | code 和 dataset 链接可见 | method + benchmark | 4 | 4 | N/A benchmark | A | 26 个任务、keyframe annotation、recent/keyframe memory buffer；是 RMBench 之外的强 benchmark 候选。 |
| 7 | [SAM2Act](https://proceedings.mlr.press/v267/fang25c.html) / [code](https://github.com/sam2act/sam2act) | 2025 | ICML / PMLR | PMLR 链接官方软件；GitHub 可访问 | method + benchmark | 4 | 5 | 4 | A | 引入 MemoryBench 与 spatial-memory architecture；顶会可复现 anchor。 |
| 8 | [MemoryVLA](https://arxiv.org/abs/2508.19236) / [code](https://github.com/shihao1895/MemoryVLA) | 2026 | ICLR 2026 comment / arXiv | GitHub 可访问 | pure method | 4 | 4 | 4 | A/Risk | Cognition-memory-action 框架；强 executor-level memory baseline，但不是 harness 贡献。 |
| 9 | [OptimusVLA](https://openaccess.thecvf.com/content/CVPR2026/html/Li_Global_Prior_Meets_Local_Consistency_Dual-Memory_Augmented_Vision-Language-Action_Model_for_CVPR_2026_paper.html) / [code](https://github.com/JiuTian-VL/OptimusVLA) | 2026 | CVPR | 官方 CVF 论文；GitHub 可访问 | pure method | 4 | 4 | 4 | A/Risk | VLA 内部双记忆：global prior memory + local consistency memory。对简单 harness 增益是强威胁。 |
| 10 | [Gated Memory Policy](https://arxiv.org/abs/2604.18933) / [project](https://gated-memory-policy.github.io/) | 2026 | arXiv/project | project 声称 code/data/deployment instructions 可用，repo 可访问 | pure method | 5 | 4 | 4 | A | 学习何时 recall、recall 什么；对避免有害长历史和 memory overuse 很重要。 |
| 11 | [EventVLA](https://arxiv.org/html/2606.20092v2) / [code](https://github.com/InternRobotics/EventVLA) | 2026 | arXiv | 论文称 code、models、datasets 可用，repo 可访问 | method + benchmark | 5 | 4 | 4 | Risk/A | 最新强威胁：sparse visual evidence memory 与 RoboTwin-MeM，专打 transient intermediate evidence。 |
| 12 | [KEMO](https://arxiv.org/abs/2606.23589) | 2026 | arXiv | 本次未找到官方代码 | pure method | 4 | 3 | 3 | Risk/B | 用 kinematics + visual filtering 做 event-driven keyframe memory；适合借鉴 memory-write policy，但可复现性弱。 |
| 13 | [Chameleon](https://arxiv.org/abs/2603.24576) / [code](https://github.com/gxyes/MARS_Chameleon) | 2026 | arXiv | GitHub 可访问 | method + benchmark | 4 | 4 | 4 | A | control-indexed prospective memory；围绕 observation-action delay 和最终场景视觉歧义建模，问题定义干净。 |
| 14 | [Learning Long-Context Diffusion Policies via Past-Token Prediction](https://long-context-dp.github.io/) / [code](https://github.com/long-context-dp/ldp) | 2025 | CoRL 2025 / project | GitHub 可访问 | pure method | 4 | 4 | 4 | B | 作为反例很重要：长上下文需要 regularization 和 self-verification，不能直接拼历史。 |
| 15 | [RoboCerebra](https://arxiv.org/html/2506.06677v1) / [code](https://github.com/buaa-colalab/RoboCerebra) | 2025 | NeurIPS Datasets & Benchmarks | GitHub 可访问 | pure benchmark | 4 | 4 | N/A benchmark | A | System-2 benchmark，覆盖 planning、reflection、memory 维度；适合 P1 压力测试。 |
| 16 | [VLABench](https://openaccess.thecvf.com/content/ICCV2025/html/Zhang_VLABench_A_Large-Scale_Benchmark_for_Language-Conditioned_Robotics_Manipulation_with_Long-Horizon_ICCV_2025_paper.html) / [code](https://github.com/OpenMOSS/VLABench) | 2025 | ICCV | CVF 论文；code/data 有链接 | pure benchmark | 4 | 4 | N/A benchmark | A | long-horizon、implicit instruction、reasoning benchmark；不是纯 memory benchmark，但适合作泛化压力测试。 |
| 17 | [LIBERO](https://libero-project.github.io/main.html) / [code](https://github.com/Lifelong-Robot-Learning/LIBERO) | 2023 | NeurIPS Datasets & Benchmarks | code 和 documentation 可见 | pure benchmark | 4 | 5 | N/A benchmark | A | P0 基础设施；适合同 executor 加/不加 harness 的对照。 |
| 18 | [Code-as-Monitor](https://zhoues.github.io/Code-as-Monitor/) / [paper](https://arxiv.org/abs/2412.04455) | 2025 | CVPR | project 和 paper 可见；未验证官方代码 repo | pure method | 5 | 3 | 4 | B/Risk | 不是 memory paper，但对 memory-conditioned verifier 很关键：constraint-aware reactive/proactive monitor。 |
| 19 | [ReKep](https://rekep-robot.github.io/) / [code](https://github.com/huangwl18/ReKep) | 2024 | CoRL / PMLR | GitHub 可访问 | pure method | 5 | 4 | 4 | B | 用 3D/keypoint constraints 让 object-state memory 和 verifier condition 变得可执行，而不是只保留文本摘要。 |

## 近邻工作分组

### 1. 记忆 benchmark 正在成为主战场

代表工作：RMBench、RoboMME、RoboMemArena、SAM2Act MemoryBench、VLABench、RoboCerebra、LIBERO。

已经覆盖：

- RMBench 通过多个 memory-complexity level 把 memory-dependent manipulation 显式化。
- RoboMME 目前分类最强：temporal counting、spatial permanence、object/reference memory、procedural imitation，并包含 14 个 memory-VLA variant。
- RoboMemArena 加入 keyframe annotation 和更长 trajectory，适合研究 memory formation，而不只是 memory usage。
- SAM2Act MemoryBench 是顶会 spatial memory benchmark，并有公开代码。

仍然开放：

- benchmark 大多评估“带记忆的 policy 是否更会动作”，很少评估 memory 是否真正服务 verifier 和 recovery。
- 跨 episode 的失败记忆仍缺少标准定义：failed subgoal、failure signature、有效 recovery action 如何存储和复用还没有成为通用指标。
- memory staleness 和 harmful retrieval 测得不够。长历史可能伤害性能，但普通 success rate 表经常隐藏原因。

可做路线：

- 在现有环境上定义 harness-facing memory protocol：
  - `M_plan`：选择下一个 subgoal 所需的记忆。
  - `M_verify`：判断 subgoal 是否真正完成所需的记忆。
  - `M_recover`：失败后选择 recovery action 所需的记忆。
  - `M_execute`：low-level executor 解决当前动作歧义所需的记忆。
- 对同一 memory store 做四类用途评估，而不是只报告一个 end-to-end success rate。

对本方向的影响：

- RMBench/RoboMME 用于 memory isolation。
- LIBERO-Long/LIBERO-Recovery 用于 harness/recovery。
- VLABench/RoboCerebra 适合在 P0 机制跑通之后做 P1/P2 压力测试。

### 2. Executor-level memory 已经拥挤，但适合作为 baseline

代表工作：MemoryVLA、OptimusVLA、SAM2Act+、Gated Memory Policy、EventVLA、KEMO、Chameleon、Long-Context DP。

已经覆盖：

- raw 或 compressed historical visual evidence 对 non-Markovian manipulation 有帮助。
- selective memory writing 比 dense history retention 更可信。EventVLA、KEMO、Chameleon、GMP 都从不同角度反对 naive history concatenation。
- executor-level memory 已经可以很强：MemoryVLA 和 OptimusVLA 都报告了仿真和真实任务上的广泛收益。

仍然开放：

- 这些方法多数把 memory 内化到 policy 内部，难以解释 planner、verifier 或 recovery controller 为什么需要某条 memory。
- event selection 多数为 action success 优化，不一定适合 post-condition verification 或 failure diagnosis。
- 很多最新工作仍是 arXiv frontier，完整复现实验成本可能较高。

可做路线：

- 不要先正面竞争“再训练一个 memory VLA”。更稳的做法是把这些工作当作 strong executor baseline 或 threat model，然后问：
  - 一个 lightweight harness memory 能否提升 frozen executor？
  - 当 executor 已经有 recurrent/keyframe memory 时，哪些记忆仍然对 verifier 和 recovery 有用？
  - 失败恢复 episode 能否沉淀成 reusable procedural memory？

对本方向的影响：

- reviewer 可能会问为什么不用 MemoryVLA/OptimusVLA/EventVLA。回答必须是：本工作贡献在 model-agnostic、可解释、面向 verifier/recovery 的记忆机制，而不是新的 action backbone。

### 3. Harness-level memory、verification、recovery 是最好切口

代表工作：HELM、Goal2Skill、Agentic Robot、Code-as-Monitor、ReKep。

已经覆盖：

- Agentic Robot 说明 planner-executor-verifier coordination protocol 能提升长程执行。
- Goal2Skill 已经提出 structured memory：episodic history、working memory、error register。
- HELM 是最近邻：memory-conditioned verifier + rollback/replan，并明确指出扩展 context length 不足。
- Code-as-Monitor 和 ReKep 能把 verifier 输出变成更可执行的 constraints / 3D keypoints。

仍然开放：

- HELM 和 Goal2Skill 仍未充分拆分 memory utility by consumer。如果 memory 被所有模块共用，很难判断收益来自 planning、verification、recovery 还是 action selection。
- error register 通常只在 episode 内使用。failure signature 如何跨 episode 复用仍然开放。
- verifier 指标太薄。需要 false advance、false block、recovery precision、cascade length，而不只是最终 success rate。

可做路线：

- 把 memory 做成 typed、inspectable service，并设置访问边界：
  - planner 读取 `object_state_table`、`subgoal_trace`、`cross_episode_cases`。
  - verifier 读取 `raw_keyframes`、`postconditions`、`object_state_table`、`constraint_state`。
  - recovery 读取 `error_register`、`last_safe_state`、`recovery_outcome_table`。
  - executor 可选读取 selected raw keyframes 或 event tokens。
- 做 consumer-specific ablation：
  - memory only for planner；
  - memory only for verifier；
  - memory only for recovery；
  - shared memory for all；
  - 注入 wrong/stale memory。

对本方向的影响：

- 这是最稳的贡献边界。它避免“提出新 VLA”的高成本竞争，并直接延展 Agentic Robot / Goal2Skill / HELM 的核心问题。

### 4. Cross-episode failure memory 仍明显不足

代表工作：Goal2Skill、HELM、Gated Memory Policy、RoboMME procedural-memory suite、VLA-Pro-like procedural memory transfer。

已经覆盖：

- GMP 把 cross-trial memory 和 in-trial working memory 区分开。
- RoboMME 包含 procedural imitation task，可评估 prior demonstration 是否影响后续执行。
- Goal2Skill/HELM 已经存储 episode 内的失败和恢复上下文。

仍然开放：

- failure memory 很少被表示成可复用 case：
  - failure signature；
  - 失败前的 precondition；
  - verifier evidence；
  - 尝试过的 recovery action；
  - recovery 是否有效；
  - task/object/context validity range。
- 目前还缺少标准指标来评估：过去失败 episode 是否减少未来 false advance 或 repeated failed subgoal。

可做路线：

- 增加 `failure_case_memory` 表：

```text
case_id
task_family
subgoal_type
precondition_snapshot
failure_signature
verifier_evidence
recovery_recipe
outcome
validity_scope
decay_or_confidence
```

- 在 repeated task families 上评估，并 hold out objects/layouts：
  - first-pass success；
  - 使用 failure memory 后的 second-pass success；
  - repeated failure rate；
  - recovery selection accuracy；
  - harmful transfer rate。

对本方向的影响：

- 这比“再做一个 keyframe memory module”更有 novelty，也更符合 agentic robot system 的结构。

## 机会图

| 分组 | 状态 | 开放缺口 | 可做方向 | 需要的证据 | 风险 |
| --- | --- | --- | --- | --- | --- |
| Memory-dependent benchmarks | crowded but open | benchmark 多隔离 action memory，但不隔离 planner/verifier/recovery consumers | 在 RMBench/RoboMME/LIBERO-Recovery 上增加 consumer-specific memory protocol | 同 executor、同 task、memory 分别路由给不同 consumer | RoboMME 已覆盖很多 memory representation；贡献必须保持 harness-level。 |
| Executor-level memory VLA | covered central claim | “memory improves VLA” 已经不够新 | 把 MemoryVLA/OptimusVLA/EventVLA/GMP 作为 baseline 或 threat model，而不是主 novelty | 比较 frozen executor + harness memory 与 memory-trained executor | 重训练强 baseline 可能很贵；优先用可用 checkpoint/code。 |
| Memory-conditioned verifier | mechanism gap | verifier 需要历史，但论文很少测 verifier-specific error | typed memory for post-condition checking and constraint verification | false advance、false block、verifier F1、memory retrieval precision | HELM 很近；必须给出更细的 verifier 分析。 |
| Recovery memory | benchmark gap | recovery 常是 retry/replan，缺少可复用失败知识 | error register + cross-episode failure cases | recovery success、recovery precision、repeated failure reduction | 需要 perturbation protocol；可用 LIBERO-Recovery 或自定义扰动。 |
| Raw vs summary memory | mechanism gap | summary 丢细节，raw frames 贵，retrieval 可能有害 | raw keyframes + object-state table + summary + error register 的混合记忆 | raw-only、summary-only、raw+summary、raw+state、raw+error ablation | EventVLA/KEMO 已覆盖 selective keyframes；必须用 consumer/recovery 区分。 |
| Geometry-aware memory | deployment/system gap | 文本摘要不能保留空间约束 | 带 3D/keypoint/constraint fields 的 object-state table，接 ReKep/Code-as-Monitor verifier | spatial hard cases、occlusion、distractor、placement-conflict tasks | 感知可靠性是瓶颈；先用仿真 ground-truth 或 oracle-assisted states。 |

## Benchmark 与数据集候选

| 名称 | 链接 | 任务 | 指标 | baseline | 适配度 | 风险 |
| --- | --- | --- | --- | --- | --- | --- |
| RMBench | https://rmbench.github.io/ | 9 个 memory-dependent RoboTwin tasks | task success、memory complexity levels、subtask success | Mem-0、existing VLA/policies | P0 memory-isolation benchmark | 2026 arXiv；精确复现依赖 RoboTwin setup。 |
| RoboMME | https://robomme.github.io/ | 16 个 temporal/spatial/object/procedural memory tasks | memory suite task success | 14 个 pi0.5-based memory variants | P0/P1 taxonomy 和强 baseline suite | 比 RMBench 更重，可能需要更多 compute。 |
| RoboMemArena | https://robomemarena.github.io/ | 26 个任务、keyframe annotations、long trajectories | memory task success、keyframe/trajectory annotations | PrediMem 和 variants | P1 memory-formation benchmark | 很新，集成成本可能较高。 |
| EventVLA / RoboTwin-MeM | https://github.com/InternRobotics/EventVLA | transient visual-evidence memory | event-keyframe tasks success、intermediate memory demand | EventVLA、memory VLAs | P1 selective write stress test | 最新 arXiv，代码可能仍在变化。 |
| SAM2Act MemoryBench | https://sam2act.github.io/ | spatial memory and action recall | MemoryBench success | SAM2Act/SAM2Act+ | 顶会强 anchor | 主要测 spatial memory，不直接测 recovery。 |
| LIBERO-Long | https://libero-project.github.io/main.html | long-horizon language-conditioned manipulation | task success、subgoal success | OpenVLA、DP、ACT、Agentic Robot-style harness | P0 harness comparison | 本身不是 memory-isolated。 |
| LIBERO-Recovery | https://arxiv.org/abs/2604.18791 | HELM 声称的 perturbation-injection recovery protocol | recovery success、rollback/replan outcome | HELM、OpenVLA | 若代码/protocol 可用，则是 P0 recovery benchmark | 使用前必须核查 release 细节。 |
| VLABench | https://vlabench.github.io/ | 100 task categories，long-horizon reasoning 与 implicit instructions | progress、success、action sequence matching | VLA、workflow、VLM baselines | P1/P2 generalization stress test | 不是纯 memory benchmark。 |
| RoboCerebra | https://github.com/buaa-colalab/RoboCerebra | System-2 planning/reflection/memory long-horizon tasks | planning、reflection、memory、task success | HPE framework、VLM/VLA combinations | P1/P2 system-level benchmark | benchmark 较重，不适合作为第一阶段复现起点。 |

## 推荐研究切片

工作标题建议：

```text
Typed Episodic Memory for Verifiable and Recoverable Long-Horizon Robot Manipulation
```

中文表述：

```text
面向可验证、可恢复长程机器人操作的类型化情节记忆
```

核心 claim：

```text
长程机器人操作不只是需要更多上下文；
它需要类型化记忆，并把不同记忆路由给正确的 agentic consumer：
planner、verifier、recovery controller，以及可选的 executor。
```

最小记忆设计：

```text
EpisodeMemory:
  raw_keyframes:
    - frame_id
    - timestamp
    - active_subgoal
    - observation_ref
    - action_summary
    - event_type
    - confidence

  object_state_table:
    - object_id
    - last_seen_pose_or_region
    - relations
    - visibility
    - source_frame_id
    - confidence
    - stale_after

  subgoal_trace:
    - subgoal_id
    - instruction
    - precondition
    - postcondition
    - executor
    - start_frame
    - end_frame
    - verifier_result

  error_register:
    - failed_subgoal_id
    - failure_type
    - verifier_evidence
    - hypothesized_cause
    - recovery_action
    - recovery_outcome

  failure_case_memory:
    - task_family
    - failure_signature
    - precondition_snapshot
    - recovery_recipe
    - outcome_statistics
    - validity_scope
```

## Consumer-specific 消融

| 变体 | Planner memory | Verifier memory | Recovery memory | Executor memory | 目的 |
| --- | --- | --- | --- | --- | --- |
| V0 no memory | no | no | no | no | 下界 |
| V1 summary only | yes | yes | yes | no | 测 compressed natural-language memory |
| V2 raw keyframes only | yes | yes | no | optional | 测 raw evidence，但不加 structured state |
| V3 object-state table | yes | yes | no | no | 测 symbolic/spatial state 的作用 |
| V4 raw + object state | yes | yes | no | optional | 测 perceptual + structured memory hybrid |
| V5 raw + object state + error register | yes | yes | yes | optional | 主 within-episode 系统 |
| V6 plus cross-episode failure memory | yes | yes | yes | optional | 主 novelty candidate |
| V7 stale/noisy memory injection | yes | yes | yes | optional | robustness 与 harmful-memory analysis |

## 指标

- 最终执行：task success rate、subgoal success rate、stage completion rate。
- Verifier：false advance rate、false block rate、verifier F1、post-condition accuracy。
- Recovery：recovery success、recovery precision、rollback/replan success、repeated failure rate。
- Memory：task-relevant keyframe retrieval precision/recall、memory write precision、stale-memory error rate、harmful transfer rate。
- 长程稳定性：replan count、failed subgoal cascade length、repeated failed subgoal loops、extra step cost。
- 系统成本：latency、token/call count、memory size、VLM query count。

## P0 复现计划

| 周期 | 目标 | 最小实验 | 成功条件 |
| --- | --- | --- | --- |
| Week 1 | 建立 executor baseline | LIBERO-Long 或 RMBench 小子集 + DP/OpenVLA/ACT baseline | rollout 和日志稳定；不追完整 SOTA |
| Week 2 | 搭 typed memory logger | 记录 raw keyframes、object-state table、subgoal trace、verifier result | 能 replay failed episode 并检查 memory state |
| Week 3 | 加 memory-conditioned verifier | 对比 no memory / summary / raw / raw+object-state 的 post-condition check | false advance 降低，false block 不显著上升 |
| Week 4 | 加 error register recovery | 根据 failure type 和 memory 选择 retry/adjust/replan | recovery success 提升，failure cascade 变短 |
| Week 5 | 加 cross-episode failure cases | 存储 failure case 后重跑相关 task | repeated failure 下降，harmful transfer 不明显 |
| Week 6 | 扩 benchmark | 增加 RoboMME 或 RoboMemArena 子集 | 机制在 LIBERO/RMBench 外仍成立 |

## Novelty 与定位风险

- HELM 是最近风险。它已经说明 context-length extension 不足，并提出 memory-conditioned verifier + rollback/replan。新工作必须展示更细的 memory-consumer decomposition 或 cross-episode failure memory。
- Goal2Skill 已经使用 structured memory 和 error register。不能把 episodic history / working memory / error register 本身说成新贡献。
- RoboMME 可能削弱“记忆分类体系”的 novelty。应把 RoboMME 的 taxonomy 当作证据和 baseline，而不是重新发明 temporal/spatial/object/procedural memory。
- EventVLA/KEMO/Chameleon 可能削弱 selective keyframe novelty。应把 event keyframes 当作一个 memory field，真正 novelty 放在 typed routing to verifier/recovery 和 failure-case reuse。
- OptimusVLA/MemoryVLA 可能削弱 harness memory 的必要性，尤其当强 memory executor 可用时。防守点应是 model-agnostic improvement、可解释性、同 executor 下的 failure recovery。

## 引用与写作注意

- HELM、Goal2Skill、EventVLA、KEMO、Chameleon、GMP 除非有已验证官方 venue page，否则写作时应标为 arXiv/frontier。
- RoboMME 可根据 project/arXiv 证据写为 ICML 2026 Oral，但最终投稿前应重新核查 official proceedings。
- Code-as-Monitor 是 CVPR 2025，对 verifier design 很关键，但本次没有验证官方 code repo，因此可复现性需保守表述。
- VLABench 和 RoboCerebra 是强 long-horizon/System-2 benchmark，但不是纯 memory benchmark；适合作 stress test，不适合作 memory causality 的主证据。
- 不要声称全面优于 VLA foundation models。应声称在同 executor 或 model-agnostic harness 条件下，通过显式 memory/verifier/recovery 指标获得提升。

## 建议下一步

下一步建议使用 `ccf-experiment-designer` 把本调研转成具体实验设计：

- benchmark 子集；
- baseline 表；
- ablation matrix；
- log schema；
- metric definitions；
- paper-ready result table templates。
