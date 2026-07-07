# Agentic Robot 方向可完整复现工作二次筛选

日期: 2026-07-06

本文档基于 `Agentic_Robot_复现筛选.md` 重新筛选。筛选重点从“方向相关”改为“能否完整复现”: 是否有公开代码、可获得数据/权重、明确 benchmark、可在本地仿真或通用 GPU 环境中跑出可审计指标。

2026-07-06 修订: 后续工作必须优先建立在社区公认 benchmark 上。使用自建 benchmark 的工作即使代码完整，也不再作为主复现目标，只保留为机制参考。

## 1. 筛选口径

| 等级 | 含义 | 是否建议作为主复现 |
|---|---|---|
| A | 代码、数据/权重、评测脚本、社区公认 benchmark 基本齐全；不依赖实体机器人或私有组件 | 是 |
| B | 核心机制可复现，但论文主表需要补训练、补环境或重建部分 glue code | 可以作为主线补充 |
| C | 有代码但只是 demo / 物理机器人栈 / 隐藏依赖 / 自建小 benchmark；不能支撑社区可比主结论 | 不作为完整复现目标 |
| D | 未找到可用官方代码或关键模型/数据缺失 | 只做思想参考 |

“完整复现”这里指能跑出论文核心 protocol 的结果，而不是只跑一个 demo notebook。

## 2. 最建议复现的工作

| 优先级 | 工作 | 等级 | 为什么保留 | 主要风险 | 建议定位 |
|---|---|---:|---|---|---|
| P0 | Agentic Robot | B | 官方代码、LIBERO、OpenVLA checkpoint 都可用；我们已经完成 OpenVLA executor baseline；SAP 思路与目标完全一致 | 官方 README 只给了 LRM 一次调用 + hard-coded plan 的测试方式，没有完整自动 SAP 主表脚本；fine-tuned verifier / recovery 细节不足 | 主目标，但要明确是“基于官方代码重建 SAP 复现”，不是一键官方复现 |
| P2 | Reflective Planning / ReflectVLM | C | 官方 repo 提供仿真环境、Hugging Face 模型、100 个 procedural test tasks、base/reflection eval 脚本；真正关注 reflection / long-horizon | 使用作者自建 MuJoCo procedural assembly benchmark，不是 LIBERO/CALVIN/RMBench/VLABench 这类社区公认 benchmark；机制是 future imagination + reflection，不是 SAP planner-verifier | 只作为 reflection 机制参考，不作为主复现目标 |
| P0 | RMBench + Mem-0 / DP / ACT / Pi0.5 / X-VLA baselines | A | RMBench 官方 benchmark、assets、数据、policy 插件入口完整；我们本地已恢复环境并跑通 DP/ACT/Pi0.5/X-VLA 入口 | 这是 benchmark / baseline，不是 Goal2Skill 官方 full system | 作为 memory-dependent benchmark 和低层策略 baseline 继续保留 |
| P1 | SV-VLA | B | 与 Agentic Robot 的 verifier loop 很贴近：重 VLA 低频规划，轻 verifier 高频监控；代码和 LIBERO 命令模板公开 | repo 规模较小，未见完整发布的 temporal-fusion checkpoint；需要自己训练 verifier 参数 | 作为 verifier/replanning 近邻基线，适合接在 Agentic Robot 之后 |
| P1 | CLOVER | B | NeurIPS 2024，闭环视觉计划 + feedback policy；代码、CALVIN 方向和权重入口可见 | 依赖 CALVIN，环境重；README 仍保留部分 TODO 文案，需要实际验证权重/评测链 | 作为 closed-loop visuomotor 对照，不作为第一优先级 |
| P1 | RoboCerebra | A | 官方 benchmark repo、数据下载、OpenVLA evaluation pipeline 清楚；长程推理评测更贴近 agent workflow | 这是 benchmark，不是方法；需要额外下载较大数据 | 后续做 Agentic Robot 泛化评测 |

## 3. 不建议作为“完整复现主目标”的工作

| 工作 | 等级 | 排除原因 | 可复用部分 |
|---|---:|---|---|
| Goal2Skill | D | 未找到明确官方 full-system 代码；目前只能复现 RMBench baseline，不能严格复现其 planner-memory-reflection 实现 | 论文机制、RMBench 任务、memory/recovery 消融设计 |
| Code-as-Monitor | D | 项目页有论文和 demo，但未找到可用官方代码仓库；不能完整复现主表 | constraint-aware verifier 思想，适合我们自实现为 Agentic Robot verifier |
| HELM | D | 公开信息主要是论文；未找到代码、模型和训练数据 | episodic memory + state verifier + rollback/replan 结构 |
| ReKep | C | 官方明确是 demo code；缺真实实验 perception pipeline，主要运行单个 OmniGibson demo | 3D keypoint constraint / geometric verifier |
| VoxPoser | C | 官方明确说明 repo 是 demo implementation，不是 evaluation benchmark；真实 perception pipeline 缺失 | 3D value map / LMP planning 表达 |
| MOKA | C | 需要 Grounded-SAM、Detectron2、DROID/Franka 机器人平台；本地不能复现论文机器人主表 | mark-based visual prompting / affordance frontend |
| RoboClaw | C | 公开 release 主要面向 Agibot G01；README 写明完整 VLA deployment wheel 需私信获取 | agent loop across data collection/training/deployment 思路 |
| SOAR | C | 代码和数据有，但 autonomous data collection 依赖 WidowX 实体机器人；不是当前仿真 agent-control 主线 | 自动数据收集、success detector、RLDS 数据 |
| GenSim / RoboGen | B/C | 代码可用，但重点是任务/数据/技能生成，不是运行时 agentic manipulation 闭环 | 生成长程任务和失败样本 |
| Instruct2Act / Code as Policies / ProgPrompt | C | 更多是 programmatic planning 祖先工作，评测与当前 VLA/LIBERO 长程闭环不一致 | typed subgoal、API 调用、程序化 verifier 表达 |
| VIMA | B/C | benchmark/算法完整，但偏 multimodal prompt manipulation，不是 planner-verifier-recovery agent 框架 | prompt-conditioned benchmark 与多模态任务接口 |

## 4. 复现路线建议

### 4.1 当前主线

继续推进 Agentic Robot，但汇报口径要更严格:

1. 已完成: OpenVLA executor baseline。
2. 可继续完成: SAP-style planner + Qwen verifier + recovery 的本地重建版。
3. 不应声称: 官方完整 SAP 主表已经复现，除非后续拿到或自行重建全部 planner/verifier/recovery protocol 并跑完整 LIBERO protocol。

### 4.2 最小完整复现实验组合

| 阶段 | 工作 | 目标 |
|---|---|---|
| 1 | Agentic Robot OpenVLA baseline | 已完成，用作主线对照 |
| 2 | Agentic Robot SAP 重建 | 在 LIBERO-Long 上跑 planner / verifier / recovery 消融 |
| 3 | CALVIN / VLABench / RMBench | 选择社区公认 benchmark 扩展 Agentic Robot-style agent loop |
| 4 | RMBench baselines + Mem-0 | 完整跑 memory-dependent benchmark baseline |
| 5 | SV-VLA | 复现 lightweight verifier / replanning，对 Agentic Robot verifier 做强对照 |
| 6 | RoboCerebra | 扩展到长程推理 benchmark，检验泛化 |

### 4.3 最终推荐清单

可以投入“完整复现”的清单:

1. `Agentic Robot`: 主目标，但需要本地重建 SAP 自动评测逻辑。
2. `RMBench`: 作为 Goal2Skill 相关 benchmark 与 baseline 复现目标。
3. `CALVIN`: 作为经典长程语言条件机器人操作 benchmark。
4. `SV-VLA`: 作为 verifier/replanning 近邻基线。
5. `CLOVER`: 作为 closed-loop visuomotor 近邻基线，排在 SV-VLA 之后。
6. `RoboCerebra`: 作为后续 benchmark，而不是第一阶段方法复现。

只做思想借鉴的清单:

1. `Goal2Skill`: 没有官方 full-system code。
2. `ReflectVLM`: 使用自建 procedural assembly benchmark；reflection 机制可参考，但不作为主 benchmark 证据。
3. `Code-as-Monitor`: 没有可用官方代码，但 verifier 思想非常值得复用。
4. `HELM`: 没有代码，但 memory/verifier/recovery 结构值得复用。
5. `ReKep` / `VoxPoser`: 适合作为几何约束组件参考，不适合作为完整论文复现。
6. `MOKA` / `RoboClaw` / `SOAR`: 依赖实体机器人或私有/平台组件，不适合当前本地完整复现。

## 5. 对当前项目的决策

下一步不应横向铺开太多仓库。最稳妥路线是:

1. 继续完成 `Agentic Robot` 的 SAP 重建复现。
2. 保留 `RMBench` 作为 memory benchmark；Goal2Skill full system 暂不作为严格复现目标。
3. 扩展 benchmark 时优先选 `CALVIN` 或 `VLABench`，而不是自建任务集。
4. 如果 Agentic Robot 的 verifier 效果仍不稳定，再引入 `SV-VLA` 做 verifier/replanning 对照。

## 6. 公认 benchmark 优先级

| 优先级 | Benchmark | 为什么适合当前工作 | 建议用途 |
|---|---|---|---|
| P0 | LIBERO | Agentic Robot 主评测；OpenVLA / SpatialVLA 等 VLA 工作常用；我们已经完成 OpenVLA executor baseline | 主实验，复现 SAP / verifier / recovery |
| P0 | CALVIN | 经典 long-horizon language-conditioned manipulation benchmark，很多 VLA / imitation / planning 工作使用 | 第二主 benchmark，验证长程连续技能链 |
| P1 | RMBench | memory-dependent manipulation benchmark，直接服务 Goal2Skill 类记忆问题；我们已恢复环境和数据 | 记忆、反思、错误恢复实验 |
| P1 | VLABench | ICCV 2025，长程语言条件操作，强调隐式意图、常识、world knowledge 和 VLA/workflow 评测 | 后续泛化与 reasoning 压力测试 |
| P2 | VIMA-Bench | ICML 2023，multimodal prompt manipulation，协议成熟 | 如果要强调多模态 prompt 泛化再引入 |

主论文证据建议至少落在 `LIBERO + CALVIN`，memory claims 再补 `RMBench`。`ReflectVLM` 这类自建 benchmark 只适合证明某个 reflection idea 能跑通，不适合作为核心 claim 的主要证据。
