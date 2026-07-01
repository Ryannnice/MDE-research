# Agentic Robot 与 Goal2Skill 方向调研

日期: 2026-07-01  
对象: `agentic_robot/Agentic Robot.pdf`, `agentic_robot/Goal2Skill.pdf`  
方向名: 面向长程机器人操作的 agentic VLA/VLM 闭环系统, 重点是任务分解、记忆、验证、反思与恢复。  
调研原则: CCFA standard mode; 优先官方论文页、项目页、GitHub、arXiv/OpenReview/CVF/PMLR/IEEE/ACM; 不纳入 MDPI; 未复现实验一律写原文报告或待跑。

## 0. 一页结论

这两篇 PDF 属于同一条新方向: 不再把 VLA 当作一次性端到端策略, 而是在 VLA 外面包一个高层 agentic 控制环。高层用 LLM/VLM 做任务分解、记忆、验证、反思与重规划; 低层用 VLA 或 diffusion policy 执行可验证的子任务。核心 claim 不是单个 grasp/pick/place 更强, 而是长程任务中少积累错误、能检测失败、能 retry/replan。

复现优先级建议:

| 优先级 | 目标 | 原因 | 复现风险 |
|---|---|---|---|
| P0 | Agentic Robot on LIBERO | 论文给项目页/GitHub, 基准 LIBERO 开源, executor 直接基于 OpenVLA | GPT-4o/Qwen2.5-VL verifier 与 500 条 verifier 标注数据是否完整公开需核查 |
| P1 | Goal2Skill-style framework on RMBench | RMBench 公开, 任务明确考记忆/恢复, 与后续 agentic 复现最贴近 | Goal2Skill PDF 未给官方 GitHub/项目页, 可能需要自行搭框架 |
| P2 | 加入深度/几何信号的 verifier 或 filtered observation | 与本 MDE 工作区天然相连: 深度可作为空间约束、遮挡判断、失败诊断输入 | 需要证明深度不是普通 RGB verifier 的附庸, 必须做 L0/L1/L2 式门控实验 |

当前可引用的 benchmark 结论:

- `Agentic Robot` 原文报告 LIBERO 四套平均 SR 为 79.6%, LIBERO-Long 为 61.6%, 高于 SpatialVLA 的 78.1% 平均和 55.5% LIBERO-Long。该结果来自本地 PDF, 未复跑。
- `Goal2Skill` 原文报告 RMBench 五个任务平均 SR 为 32.4%, 高于 ACT 和 X-VLA 的 9.8%; 在 M(n) 记忆任务上为 38.7%, 高于 X-VLA 的 9.0%。该结果来自本地 PDF, 未复跑。
- 两者都证明的是 benchmark-specific SOTA, 不能直接概括为所有机器人操作 SOTA。

## 1. 两篇 PDF 论文卡

### 1.1 Agentic Robot

| 项 | 内容 |
|---|---|
| 标题 | Agentic Robot: A Brain-Inspired Framework for Vision-Language-Action Models in Embodied Agents |
| arXiv | arXiv:2505.23450v2, 2025-06-11 |
| 作者 | Zhejian Yang, Yongchao Chen, Xueyang Zhou, Jiangyue Yan, Dingjie Song, Yinuo Liu, Yuting Li, Yu Zhang, Pan Zhou, Hechang Chen, Lichao Sun |
| 项目页/GitHub | PDF 写明 `https://agentic-robot.github.io`; 项目页链接到官方 GitHub `https://github.com/Agentic-Robot/agentic-robot` |
| 核心范式 | SAP, Standardized Action Procedure: Planner -> Executor -> Verifier -> Recovery 的标准化闭环 |
| 高层模块 | GPT-4o 类 LRM/VLM planner, 把任务分成 2-5 个 atomic skill subgoals |
| 低层模块 | OpenVLA executor, 输入子目标和双视角 RGB, 输出 7-DoF 连续动作加 gripper |
| 验证模块 | Qwen2.5-VL-3B-Instruct + LoRA, 用约 500 个 `(frame buffer, subgoal, yes/no)` triplets 微调 |
| 恢复策略 | verifier 判断 No 后再判 Stuck/StillTrying; Stuck 时执行简单 recovery, 如 lift gripper |
| 数据/评测 | LIBERO-Spatial/Object/Goal/Long, 每套 10 tasks, 每 task 50 teleoperated demos |
| Baselines | Diffusion Policy, Octo-Base, OpenVLA, TraceVLA, SpatialVLA |
| 关键风险 | verifier 训练数据规模小且是否公开不明; recovery 策略非常简单; 只在模拟 LIBERO, 无真实机器人 |

Agentic Robot 的主张可以压缩为: OpenVLA 不是替换掉, 而是作为 Executor 被高层 SAP 管起来。SAP 贡献在于让进度推进必须经过 verifier gate, 不允许上一子任务失败后盲目进入下一子任务。

原文主表:

| Method | LIBERO-Spatial | LIBERO-Object | LIBERO-Goal | LIBERO-Long | Average |
|---|---:|---:|---:|---:|---:|
| Diffusion Policy | 78.3 ± 1.1 | 92.5 ± 0.7 | 68.3 ± 1.2 | 50.5 ± 1.3 | 72.4 ± 0.7 |
| Octo-Base (FT) | 78.9 ± 1.0 | 85.7 ± 0.9 | 84.6 ± 0.9 | 51.1 ± 1.3 | 75.1 ± 0.6 |
| OpenVLA (FT) | 84.7 ± 0.9 | 88.4 ± 0.8 | 79.2 ± 1.0 | 53.7 ± 1.3 | 76.5 ± 0.7 |
| TraceVLA (FT) | 84.6 ± 0.2 | 85.2 ± 0.4 | 75.1 ± 0.3 | 54.1 ± 1.0 | 74.8 ± 0.5 |
| SpatialVLA (FT) | 88.2 ± 0.5 | 89.9 ± 0.7 | 78.6 ± 0.6 | 55.5 ± 1.0 | 78.1 ± 0.7 |
| Agentic Robot | 85.8 ± 0.6 | 89.0 ± 0.8 | 81.8 ± 0.8 | 61.6 ± 1.2 | 79.6 ± 0.8 |

LIBERO-Long 10 个场景中, 相比 OpenVLA 的总体成功率变化:

| Task | OpenVLA SR | Agentic Robot SR | 差值 |
|---|---:|---:|---:|
| Soup-Sauce | 0.46 | 0.67 | +0.21 |
| Cheese-Butter | 0.64 | 0.78 | +0.14 |
| Stove-Moka | 0.64 | 0.71 | +0.07 |
| Bowl-Drawer | 0.32 | 0.56 | +0.24 |
| Mug-Mug | 0.44 | 0.63 | +0.19 |
| Book-Caddy | 0.82 | 0.84 | +0.02 |
| Mug-Pudding | 0.54 | 0.60 | +0.06 |
| Soup-Cheese | 0.60 | 0.64 | +0.04 |
| Moka-Moka | 0.22 | 0.17 | -0.05 |
| Mug-Wave | 0.46 | 0.58 | +0.12 |

重要 ablation:

| Setting | LIBERO-Long SR |
|---|---:|
| No Visual Input | 57.4 |
| No Recovery Mechanism | 59.7 |
| No Fine-tuned VLM | 35.3 |
| No Subgoal Decomposition | 53.7 |
| Full System | 61.8 |

解读:

- 最大贡献来自 fine-tuned verifier。zero-shot VLM verifier 掉到 35.3%, 说明“会看图”的通用 VLM 不等于会判机器人子任务完成。
- Subgoal decomposition 比 recovery 更关键。恢复策略只有 lift gripper, 但分解和 gate 能显著减少级联错误。
- Moka-Moka 反例重要: 相同物体的空间占位冲突没有被计划器提前建模。后续做深度/几何时, 这是切入点。

### 1.2 Goal2Skill

| 项 | 内容 |
|---|---|
| 标题 | Goal2Skill: Long-Horizon Manipulation with Adaptive Planning and Reflection |
| arXiv | arXiv:2604.13942v1, 2026-04-15 |
| 作者 | Zhen Liu, Xinyu Ning, Zhe Hu, XinXin Xie, Weize Li, Zhipeng Tang, Chongyu Wang, Zejun Yang, Hanlin Wang, Yitong Liu, Zhongzhu Pu |
| 项目页/GitHub | PDF 未给项目页/GitHub; 2026-07-01 外部检索未找到明确官方代码仓库 |
| 核心范式 | Dual-system: 高层 VLM planner + structured memory + verifier/reflection; 低层 VLA/diffusion skill executor |
| 高层模块 | VLM 规划器, 输出子任务 tuple: instruction, pre/post-condition, horizon, distractor constraints, skill id |
| 记忆模块 | `M_t = {H_t, W_t, E_t}`: episodic history, working memory, error register |
| 反思模块 | `Phi_reflect` 给失败诊断 `d_k` 与恢复建议 `rho_k in {retry, adjust-param, replan}` |
| 低层模块 | Geometry-preserving filtered observation + diffusion-based skill library |
| 数据/评测 | RMBench 5 个代表任务, 50 expert demos/task, 100 rollout episodes |
| Baselines | DP, ACT, Pi0.5, X-VLA |
| 关键风险 | 无官方代码; executor/skill library 细节不足; 使用 RMBench 子集而非全量; 很多 baseline 数值取自 RMBench |

Goal2Skill 与 Agentic Robot 的最大差异是“记忆”从辅助上下文升级为一等公民。Agentic Robot 的 verifier 主要决定能不能进入下一步; Goal2Skill 的 planner 会把 episodic history、working summary、error register 都喂回 planner/reflection, 让失败诊断影响后续计划。

原文主表:

| Method | Observe and Pick Up | Rearrange Blocks | Battery Try | Blocks Ranking Try | Press Button | M(1) Avg | M(n) Avg | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DP | 1% | 0% | 10% | 10% | 0% | 0.5% | 6.7% | 4.2% |
| ACT | 1% | 29% | 19% | 0% | 0% | 15.0% | 6.3% | 9.8% |
| Pi0.5 | 9% | 13% | 16% | 6% | 0% | 11.0% | 7.3% | 8.8% |
| X-VLA | 9% | 13% | 26% | 1% | 0% | 11.0% | 9.0% | 9.8% |
| Goal2Skill/Ours | 8% | 38% | 46% | 60% | 10% | 23.0% | 38.7% | 32.4% |

记忆 ablation:

| Setting | Observe and Pick Up | Rearrange Blocks | Blocks Ranking Try | Avg |
|---|---:|---:|---:|---:|
| Base | 4% | 10% | 6% | 6.7% |
| + episodic history `H_t` | 8% | 21% | 54% | 27.7% |
| + `H_t + W_t` | 6% | 36% | 42% | 28.0% |
| Full model | 8% | 38% | 60% | 35.3% |

恢复 ablation:

| Setting | Battery Try | Press Button | Avg |
|---|---:|---:|---:|
| Base | 16% | 0% | 8.0% |
| + verifier | 30% | 5% | 17.5% |
| + verifier + reflection | 38% | 10% | 24.0% |
| Full model | 46% | 10% | 28.0% |

解读:

- episodic history 是最大单项收益来源, 尤其 Blocks Ranking Try 从 6% 到 54%。
- working memory 不是单调增益, 可能会压缩掉任务关键细节。复现时要保留 raw history window, 不要只喂总结。
- reflection 的作用不是检测失败, 而是把失败信号转成 retry、adjust-param、replan 的动作选择。

## 2. 两篇文章的共同范式与差异

| 维度 | Agentic Robot | Goal2Skill | 复现含义 |
|---|---|---|---|
| 主战场 | LIBERO 长程任务 | RMBench 记忆依赖任务 | 至少要跑一个 LIBERO 和一个 RMBench 小集, 不能只跑单步 pick/place |
| Planner | GPT-4o 类 LRM/VLM 分解 atomic subgoals | VLM planner 生成带 pre/post-condition 和 constraints 的 subtask tuple | Goal2Skill 的 plan representation 更适合工程复现 |
| Executor | OpenVLA | VLA/diffusion skill library | Agentic Robot 更容易先跑通 |
| Verifier | Qwen2.5-VL-3B LoRA yes/no + stuck diagnosis | VLM verifier 判断 post-condition, 给 success/fail/timeout | verifier 数据集是复现成败点 |
| Memory | 未显式做复杂长期记忆 | episodic history + working memory + error register | RMBench 必须做 memory ablation |
| Recovery | 固定 lift/retry 类简单恢复 | retry/adjust-param/replan | Goal2Skill 更像完整 agentic 系统 |
| 开源 | 官方项目/GitHub 可见 | 未找到官方代码 | 先复现 Agentic Robot, 后仿 Goal2Skill |
| 弱点 | 空间占位冲突、真实机器人缺失 | 细节/代码不足、baseline 多来自 RMBench | 后续研究机会集中在可解释 verifier 与几何记忆 |

## 3. 方向知识图谱

### 3.1 基线执行器: VLA 与 visuomotor policies

| 工作 | 年份 | 类型 | 代码/模型 | 数据/基准 | 为什么重要 |
|---|---:|---|---|---|---|
| ACT/ALOHA | 2023 | imitation, action chunking, bimanual | ALOHA 项目开源 | ALOHA 数据公开程度较高 | RMBench baseline; 低成本双臂操作基础线 |
| Diffusion Policy | 2023/2025 IJRR | diffusion visuomotor policy | 官方代码/项目公开 | 多个 manipulation demos | LIBERO/RMBench 都把它当传统强基线 |
| RT-2 | 2023 CoRL | proprietary VLA | 未开源权重 | Google robot data 未完整开放 | VLA foundation 起点, 但不适合直接复现 |
| Octo | 2024 | open-source generalist robot policy, 93M | 官方代码/模型公开 | Open X-Embodiment 800k trajectories | 开源 generalist policy baseline |
| OpenVLA | 2024 | open-source 7B VLA | 官方代码/模型公开 | Open X-Embodiment 970k robot demos | Agentic Robot executor; 必跑基线 |
| TraceVLA | 2024/2025 | OpenVLA + visual trace prompting | 项目页/GitHub 可见 | LIBERO 等 | LIBERO 中强 baseline, 处理时空提示 |
| SpatialVLA | 2025 | spatial representation VLA, 4B | 项目页/GitHub 可见 | 1.1M real-world robot episodes | Agentic Robot 对比中最强 LIBERO-Long baseline |
| pi0/pi0.5 | 2024/2025 | flow matching VLA | `openpi` 公开代码/部分模型 | Physical Intelligence 数据不完全开源 | Goal2Skill baseline; 当前真实机器人泛化强威胁 |
| RDT-1B | 2024/2025 | diffusion foundation model for bimanual manipulation | 项目页/GitHub 可见 | bimanual manipulation datasets | 对双臂/灵巧操作是强威胁 |
| X-VLA | 2025/2026 | cross-embodiment VLA | 检索到论文, 官方代码需再核验 | RMBench baseline | Goal2Skill 中最强/并列最强 baseline |

复现时至少包含:

1. OpenVLA-FT: 对 Agentic Robot 是最直接消融。
2. SpatialVLA 或 TraceVLA: 对 LIBERO-Long 的 reviewer threat。
3. DP/ACT: 对 RMBench 或低层 skill library 的传统 policy 下界。
4. pi0.5/X-VLA: 对最新 VLA 泛化能力的威胁, 即使不能完整复现也要在 Related Work 中正面处理。

### 3.2 Planner, program, verifier 与 recovery 先驱

| 工作 | 年份 | 类型 | 开源状态 | 与本方向关系 |
|---|---:|---|---|---|
| SayCan | 2022/2023 | LLM + affordance grounding | 论文/项目公开, 完整 Google robot stack 不完全开源 | 把语言规划和可执行性评分结合, 是 planner-executor 解耦起点 |
| Inner Monologue | 2022 | language feedback loop for embodied planning | 项目页公开, 复现实物栈受限 | 把环境反馈写回语言上下文 |
| Code as Policies | 2023 ICRA | LLM 生成机器人 policy code | 项目/代码公开 | 高层语言程序控制的代表, 但缺少 VLA verifier gate |
| VoxPoser | 2023 CoRL | LLM/VLM 生成 3D value maps | 代码公开 | 以 3D value map 做空间 grounding, 是几何约束路线强先例 |
| ECoT | 2024 | embodied chain-of-thought for policies | 项目/GitHub 可见 | 把中间推理过程引入 VLA, 但不是显式 memory/recovery 系统 |
| Reflective Planning | 2025 | VLM reflective planning for multi-stage manipulation | arXiv/代码需核验 | Agentic Robot 引用的近邻, reviewer 会问差异 |
| RoboClaw | 2026 | agentic framework for scalable long-horizon tasks | 项目页可见 | 与 Goal2Skill 同期 agentic 长程操作威胁 |
| Critic in the Loop | 2026 | tri-system VLA, critic/verifier loop | arXiv/代码需核验 | 验证器/critic 显式入环, 与 SAP/Goal2Skill 直接竞争 |

关键脉络:

- SayCan/Code as Policies/VoxPoser 证明了“LLM 高层 + 低层 skill”可行, 但多是 open-loop 或弱闭环。
- Agentic Robot/Goal2Skill 的新意在于 verifier/reflection 成为任务推进的 gating signal, 不是只做 caption 或规划提示。
- VoxPoser 与 Goal2Skill 的 filtered observation 都说明几何/空间约束会变成下一轮 agentic robot 的核心竞争点。

### 3.3 记忆增强 VLA 与长程上下文

| 工作 | 年份 | 类型 | 代码/数据状态 | 核心点 | 对 Goal2Skill 的威胁 |
|---|---:|---|---|---|---|
| MemoryVLA | 2025 | perceptual-cognitive memory in VLA | GitHub 公开 | 给 VLA 加感知/认知记忆 | 直接撞“memory-aware VLA” |
| MAP-VLA | 2025 | memory-augmented prompting for VLA | 官方代码需核验 | 检索 memory 作为 prompt | 如果无需训练也有效, 会削弱复杂框架必要性 |
| MemER | 2025 | experience retrieval memory for robot control | 项目/代码需核验 | 从经验库检索相似片段 | 对 episodic history 是强基线 |
| ReMem-VLA | 2026 | dual-level recurrent queries | 官方代码未确认 | recurrent queries 注入记忆 | 与 Goal2Skill 的 memory module 直接竞争 |
| MEM/Multi-Scale Embodied Memory | 2026 | multi-scale embodied memory for VLA | 项目/代码需核验 | 多尺度 recent/long-term memory | 必须在 Related Work 中区别“被动上下文”与“主动 verifier/recovery” |
| RoboMME/RoboMemArena | 2025/2026 | memory benchmark/evaluation | GitHub/项目页需核验 | 专测 robot memory | 若复现 Goal2Skill, 可以作为补充评测候选 |

写作区分点:

- 被动记忆: 只是保存或检索历史, 让 policy 有更长上下文。
- 主动记忆: 记忆参与 verifier、failure diagnosis、replan decision。Goal2Skill 应强调这个区别。
- 机制风险: working memory summary 可能丢细节。Goal2Skill ablation 已显示 `H_t + W_t` 不总是优于 `H_t`。

## 4. 常见数据集与基准

| 数据集/基准 | 开源状态 | 任务类型 | 典型指标 | 与两篇 PDF 关系 | 复现建议 |
|---|---|---|---|---|---|
| LIBERO | 官方 GitHub 开源 | simulated instruction-following manipulation; Spatial/Object/Goal/Long | success rate, 每套 10 tasks, 每 task 50 demos | Agentic Robot 主评测 | P0 必跑。先跑 LIBERO-Long 小任务和 OpenVLA baseline |
| RMBench | 官方项目页/GitHub/数据下载可见 | memory-dependent robotic manipulation, M(1)/M(n) | SR@100, memory-task average | Goal2Skill 主评测 | P1。先复现 5 个任务子集 |
| RoboTwin/RoboTwin 2.0 | 官方 GitHub/项目页开源 | dual-arm simulation, scalable data generation | task SR | RMBench 建在其生态上 | 作为 RMBench 环境依赖核查 |
| Open X-Embodiment | 官方数据集/项目公开 | large-scale multi-robot demos | pretraining corpus, 不是单一 eval | OpenVLA/Octo 预训练来源 | 不建议从头训, 用作模型来源说明 |
| DROID | 官方数据集公开 | large real-world robot manipulation | dataset/pretrain | VLA 预训练常用 | 若需要 real robot泛化讨论, 作为数据源 |
| CALVIN | 官方数据/代码公开 | long-horizon language-conditioned manipulation | multi-step success, sequence length | memory/VLA papers 常用 | 可作为附加长程基准, 但与两篇主结果不直接可比 |
| ManiSkill | 官方代码/benchmark 开源 | scalable simulated manipulation | success rate | 可替代/扩展 benchmark | 如果 LIBERO/RMBench 安装受阻, 可做工程预研 |
| RoboCasa | 官方代码/数据公开 | kitchen-like long-horizon manipulation | success rate | 更接近真实 household 场景 | 适合作为后续泛化验证 |
| BridgeData V2 | 官方数据公开 | real robot manipulation demos | pretrain/finetune corpus | OpenVLA 等模型生态 | 不作为第一阶段评测 |
| ALOHA/ACT data | 官方项目公开 | bimanual real robot imitation | task SR | ACT baseline | RMBench 里的 ACT 只是算法 baseline, 不是直接用 ALOHA 数据 |

协议注意:

- LIBERO 的 Spatial/Object/Goal/Long 四套不是同一难度, 不应只报平均。Agentic Robot 的优势主要在 LIBERO-Long。
- RMBench 的 M(1) 与 M(n) 必须分开报。Goal2Skill 的主要优势来自 M(n), 不是所有短程任务都强。
- success rate 的 episode 数要写清。Agentic Robot 表中说 500 evaluation trials/三随机种子; Goal2Skill 表中说 100 rollouts。
- baseline 数值若来自原论文而非自己复跑, 必须标“原文报告/来自 RMBench”。

## 5. SOTA 与近作威胁清单

### 5.1 当前最接近的 benchmark SOTA

| 结论 | 证据 | 置信度 | 复现前口径 |
|---|---|---|---|
| Agentic Robot 在原文 LIBERO 平均和 LIBERO-Long 上优于列出的 baselines | 本地 PDF Table 1 | 中 | 写“原文报告 SOTA”, 不写“已验证 SOTA” |
| Goal2Skill 在原文 RMBench 5 任务子集上优于 DP/ACT/Pi0.5/X-VLA | 本地 PDF Table 1 | 中低 | 无代码, 写“原文报告”, 复现需自建 |
| 最新 VLA/flow/diffusion policies 对低层 executor 是强威胁 | openpi, RDT, OpenVLA, SpatialVLA 项目 | 高 | 复现至少保留 OpenVLA 与一个最新强 VLA |
| 记忆增强 VLA 会挑战“agentic wrapper 必要性” | MemoryVLA, ReMem-VLA, MEM, MAP-VLA | 中 | Related Work 必须区分 memory-as-context 与 memory-for-verification/recovery |

### 5.2 代表工作质量评分

CCFA 评分只评价该工作作为本方向证据的强弱, 不是接收概率。

| 工作 | 类型 | Insight | Completeness | Numeric evidence | Overall | 备注 |
|---|---|---:|---:|---:|---|---|
| Agentic Robot | method + benchmark | 4 | 3 | 4 | A/Risk | 思路清晰且有 LIBERO 表, 但 verifier 数据和真实机器人缺失 |
| Goal2Skill | method + benchmark | 4 | 2 | 3 | Risk | 记忆/反思设计完整, 但无代码且实现细节不足 |
| OpenVLA | pure method/tool | 4 | 4 | 4 | A | 直接 executor baseline, 开源生态好 |
| SpatialVLA | pure method | 4 | 3 | 4 | A/Risk | Agentic Robot 的最强 baseline 威胁 |
| TraceVLA | pure method | 3 | 3 | 3 | B | 时空 trace prompting, 必须纳入 LIBERO 对比 |
| Octo | system/tool | 4 | 4 | 4 | B | 开源 generalist policy, 规模小于 OpenVLA |
| Diffusion Policy | pure method | 5 | 5 | 5 | A | 经典低层 policy baseline |
| ACT | pure method | 4 | 4 | 4 | B | RMBench baseline, 双臂 imitation 基础线 |
| Code as Policies | system/tool | 5 | 4 | 3 | B | 高层语言程序先例, 非 VLA verifier |
| VoxPoser | method + system | 5 | 4 | 4 | A/Risk | 3D value map 可能比纯语言子目标更强 |
| MemoryVLA | pure method | 4 | 3 | 3 | Risk | 直接 memory-VLA 威胁 |
| RoboClaw/Critic-in-the-loop | system/tool | 4 | 2 | 2 | Risk | 同期 agentic 长程系统, 需复查代码与评测 |

## 6. 开源状态核验表

| 名称 | 论文/项目链接 | 代码 | 数据/模型 | 备注 |
|---|---|---|---|---|
| Agentic Robot | `https://agentic-robot.github.io` | 是, `https://github.com/Agentic-Robot/agentic-robot` | verifier 标注数据未确认; LIBERO 开源 | 第一复现目标 |
| Goal2Skill | arXiv:2604.13942 | 未找到官方代码 | RMBench 开源; 自身预处理子任务数据未确认 | 需要仿实现 |
| LIBERO | `https://github.com/Lifelong-Robot-Learning/LIBERO` | 是 | 是 | Agentic Robot 主基准 |
| RMBench | `https://rmbench.github.io/` | 是, 项目页指向 GitHub | 是, 项目页给数据下载 | Goal2Skill 主基准 |
| OpenVLA | `https://openvla.github.io/` | 是 | 模型权重公开 | Agentic Robot executor |
| Octo | `https://octo-models.github.io/` | 是 | 模型公开 | open generalist baseline |
| Open X-Embodiment | `https://robotics-transformer-x.github.io/` | 数据集/工具公开 | 数据公开 | 预训练语料 |
| openpi/pi0 | `https://github.com/Physical-Intelligence/openpi` | 是 | 部分模型/配置公开 | 最新 VLA/flow baseline |
| RDT-1B | `https://rdt-robotics.github.io/rdt-robotics/` | 项目页/GitHub 可见 | 模型/数据以项目页为准 | 双臂强威胁 |
| Code as Policies | `https://code-as-policies.github.io/` | 是 | N/A | planner/program 先例 |
| VoxPoser | `https://voxposer.github.io/` | 是 | N/A | 3D value map 先例 |
| MemoryVLA | `https://github.com/shihao1895/MemoryVLA` | 是 | 依赖公开基准 | memory VLA 威胁 |

待复查:

- Goal2Skill 是否有私下/后续官方 repo。当前 PDF 没有项目页, 搜索未命中明确官方仓库。
- Agentic Robot repo 是否包含 verifier fine-tune 数据、LoRA 权重、prompt、LIBERO evaluation scripts。
- RMBench 的 5 任务子集是否与 Goal2Skill 完全一致, 包括 seed、expert demos、episode termination、SR 计算。

## 7. 复现路线

### 7.1 最小可行复现: Agentic Robot on LIBERO

目标: 先证明 SAP wrapper 相对 OpenVLA 在 LIBERO-Long 上有正收益。不要一开始追全表平均。

步骤:

1. 环境: clone Agentic Robot、LIBERO、OpenVLA; 确认 CUDA/PyTorch/transformers/robomimic 版本。
2. 数据: 下载 LIBERO-Long demos; 先选 2-3 个任务, 建议 `Soup-Sauce`, `Bowl-Drawer`, `Mug-Wave`。
3. Baseline: 跑 OpenVLA-FT 或官方 checkpoint, 记录 SR@N, episode length, fail type。
4. Planner: 固定 prompt, 输出 atomic subgoal sequence; 为避免 API 变量, 先缓存 GPT-4o planner 输出。
5. Verifier: 优先用官方 LoRA/weights; 若没有, 自建 200-500 条 yes/no 标注小集, 先复现 No Fine-tuned VLM vs fine-tuned verifier 的趋势。
6. Recovery: 先实现 lift gripper + retry; 不要过早复杂化 recovery。
7. 报告: 每个任务报 OpenVLA SR、SAP SR、subgoal success、retry 次数、verifier false positive/false negative。

必须做的消融:

| 消融 | 为什么 |
|---|---|
| no verifier, 单纯子任务串行 | 区分 planner 分解和 verifier gate |
| zero-shot VLM verifier | 对应原文最大 ablation |
| no recovery | 看 simple recovery 是否真实有用 |
| cached planner vs online planner | 排除 API 不稳定影响 |

### 7.2 Goal2Skill 仿复现: RMBench memory loop

目标: 在没有官方代码时复现核心机制, 而不是照抄不可见实现。

最小系统:

```text
global goal + observation
  -> VLM planner outputs tau_k = (instruction, pre, post, horizon, distractor boxes, skill id)
  -> low-level policy executes tau_k
  -> verifier returns success/fail/timeout
  -> memory update: H_t raw recent history + W_t summary + E_t error register
  -> reflector returns retry/adjust-param/replan
```

先跑 5 任务子集:

| Task | 机制 | 预期观察 |
|---|---|---|
| Observe and Pick Up | 短程目标保持 | Goal2Skill 未明显胜过 best baseline, 用作 sanity |
| Rearrange Blocks | 中间状态追踪 | working memory 可能有帮助 |
| Battery Try | retry/recovery | verifier + reflection 应该拉升 |
| Blocks Ranking Try | 多阶段排序记忆 | episodic history 应最关键 |
| Press Button | 失败恢复 | baseline 近 0, 但绝对成功率也低 |

关键工程选择:

- `H_t` 不能只存文本 summary。至少保留最近 N 次 observation thumbnail/path、subtask、action chunk、completion signal。
- `W_t` 要做 schema 化, 如 objects, locations, completed_subtasks, remaining_constraints。
- `E_t` 要记录 failure type、失败时图像、retry 次数、上次策略, 否则 reflection 只是空话。
- distractor constraints 可以先用 Grounded-SAM/OWLv2 产生 bbox/mask, 再进入 filtered observation。
- executor 若 Goal2Skill 未开源, 先用 ACT/DP/OpenVLA 中一个可跑低层策略替代, 明确标“Goal2Skill-style”而非复现原文。

### 7.3 与 MDE/几何方向的连接

这部分是后续可做论文点, 不是已有实验结论。

| 可插入位置 | 深度/几何能做什么 | 最低证据要求 |
|---|---|---|
| Verifier 输入 | RGB + depth/normal/uncertainty 判断 subgoal 完成 | verifier F1 或 subgoal completion accuracy 高于 RGB-only |
| Stuck diagnosis | 利用 depth change/hand-object distance 判断 failed grasp/collision | failure slice 上 false negative 降低 |
| Planner constraints | 用深度估计支持空间占位和碰撞/可达性 | Moka-Moka 类空间冲突任务有提升 |
| Filtered observation | 用 mask+depth 分离 distractor/target | RMBench/ clutter tasks 成功率提升 |
| Memory | 存 object pose/depth summary 而非只存文本 | M(n) tasks 提升且 token 成本下降 |

一个值得尝试的最小研究问题:

> 在 Agentic Robot/Goal2Skill 的 verifier 中加入几何信念图, 是否能在长程操作中的空间占位冲突、遮挡、失败恢复上比 RGB-only VLM verifier 更稳?

最低实验门槛:

- Baseline: RGB-only verifier, zero-shot VLM verifier, fine-tuned RGB verifier。
- Ours: RGB + depth/normal/uncertainty verifier。
- 数据: LIBERO-Long 中 Moka-Moka/Bowl-Drawer/Soup-Sauce + RMBench Battery/Blocks。
- 指标: task SR, subgoal verification accuracy, false proceed rate, false retry rate, retry count, latency。
- 结论边界: 只 claim verifier/diagnosis 改善, 不 claim 单目深度本身提升机器人整体智能。

## 8. Reviewer threat 与写作风险

| 风险 | 具体攻击 | 应对 |
|---|---|---|
| 只是 prompt engineering | planner/verifier 都是 LLM/VLM 拼接 | 必须有 verifier fine-tune、memory ablation、failure taxonomy |
| 与 SayCan/Code as Policies/VoxPoser 差异不清 | 都是高层 planner + low-level skill | 强调 closed-loop verification/recovery 和 long-horizon SR |
| 与 MemoryVLA/ReMem-VLA 差异不清 | 都有 memory | 区分 memory-as-context 与 memory-for-verification/replanning |
| 最新 VLA baseline 不足 | pi0.5/RDT/X-VLA/SpatialVLA 可能更强 | 至少纳入一个最新强 VLA 或解释不可获得原因 |
| 只在模拟 | LIBERO/RMBench 不能代表真实机器人 | 做 sim-to-real 小验证或明确定位为机制诊断论文 |
| verifier 数据不可复现 | 500 triplets 可能不公开 | 发布标注协议、数据 split、prompt、LoRA 权重 |
| API 模型不稳定 | GPT-4o/Qwen 版本变动 | cache planner outputs, 固定 model version, 报告 prompt |
| recovery 太简单 | lift gripper 不算真正恢复 | 把它定位为 minimal recovery, 加 adjust-param/replan 才有论文空间 |
| 任务子集选择偏 | Goal2Skill 只报 RMBench 5 任务 | 复现时补全更多任务或解释任务选择 |

## 9. 检索记录

使用的公开 query 类型:

- `"Agentic Robot" "Standardized Action Procedure" GitHub`
- `"Goal2Skill" "Long-Horizon Manipulation" GitHub`
- `"RMBench" "Memory-dependent robotic manipulation benchmark" GitHub`
- `"LIBERO" "Benchmarking Knowledge Transfer" GitHub`
- `"OpenVLA" "open-source vision-language-action model"`
- `"SpatialVLA" "TraceVLA" GitHub`
- `"MemoryVLA" "ReMem-VLA" "Multi-Scale Embodied Memory"`
- `"RoboClaw" "Critic in the Loop" "long-horizon manipulation"`

主要来源:

- 本地 PDF: `agentic_robot/Agentic Robot.pdf`
- 本地 PDF: `agentic_robot/Goal2Skill.pdf`
- Agentic Robot: https://agentic-robot.github.io
- Agentic Robot GitHub: https://github.com/Agentic-Robot/agentic-robot
- RMBench: https://rmbench.github.io/
- LIBERO: https://github.com/Lifelong-Robot-Learning/LIBERO
- OpenVLA: https://openvla.github.io/
- Octo: https://octo-models.github.io/
- Open X-Embodiment: https://robotics-transformer-x.github.io/
- RoboTwin 2.0: https://robotwin-platform.github.io/
- DROID: https://droid-dataset.github.io/
- CALVIN: https://github.com/mees/calvin
- ManiSkill: https://www.maniskill.ai/
- RoboCasa: https://robocasa.ai/
- BridgeData V2: https://rail-berkeley.github.io/bridgedata/
- ALOHA/ACT: https://tonyzhaozh.github.io/aloha/
- openpi/pi0: https://github.com/Physical-Intelligence/openpi
- RDT: https://rdt-robotics.github.io/rdt-robotics/
- Code as Policies: https://code-as-policies.github.io/
- VoxPoser: https://voxposer.github.io/
- MemoryVLA: https://github.com/shihao1895/MemoryVLA
- RoboClaw: https://roboclaw-agibot.github.io/

未解决项:

- Goal2Skill 官方代码是否稍后发布。
- Goal2Skill 使用的低层 VLA/diffusion skill library 的具体 checkpoint、skill labels、filtered observation 实现。
- Agentic Robot verifier 标注数据和 LoRA 权重是否完整公开。
- SpatialVLA、TraceVLA、X-VLA、pi0.5 在相同 LIBERO/RMBench protocol 下的可复跑性。

## 10. 给复现开始前的检查清单

1. 先选一个 benchmark: 若目标是“跑通”, 选 LIBERO; 若目标是“做记忆/反思论文点”, 选 RMBench。
2. 先选一个 executor: OpenVLA 最贴 Agentic Robot; ACT/DP 最贴 RMBench baseline; 不要同时换 planner、executor、verifier。
3. 把 planner 输出缓存到 JSON, 每个 episode 记录 subgoal list。
4. 把 verifier 输入帧、输出、ground-truth completion、最终 task outcome 全部落盘。
5. 明确报告 API 模型版本、prompt、LoRA checkpoint、verification frequency。
6. 每个失败样本标注属于 grasp fail、place fail、wrong object、spatial conflict、verifier false proceed、verifier false retry、timeout。
7. 所有表格先写 `待跑`, 只有真实 CSV/日志存在后再填数字。
