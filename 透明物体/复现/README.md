# 透明物体 baseline 复现入口

当前主线是 [Shell-Aware Multi-Layer Transparent Grasping](../Shell-Aware-Multi-Layer-Transparent-Grasping-Idea-v2.md)。最新、最易读的状态与数字统一见：

- [DepthHypothesisPack v1：强编码器、teacher 与尺度诊断（2026-08-31）](DepthHypothesisPack_v1_强编码器与尺度诊断_2026-08-31.md)
- [DepthHypothesisPack v0：正式实验记录（2026-08-31）](DepthHypothesisPack_v0_实验记录_2026-08-31.md)
- [复现进度总览（2026-08-30）](复现进度总览_2026-08-30.md)
- [G0 执行总控](G0_执行总控.md)
- [P0 单层/多层 gap table](P0_gap_table.md)

## 当前结论

截至 2026-08-31：

- DepthHypothesisPack v0/v1 的 ResNet-18、DINOv2-S 与 Depth Anything V2-S 受控实验已完成。DINO 将 LayeredDepth mixed-quad 从 20.45% 提到 25.12%，但直接 TablewareNet interface F1 仅 0.422%。
- SeeGroup 继续作为真实 multi-layer strong baseline；其 synthetic raw metric/presence teacher target 未过质量 gate，因此没有启动错误蒸馏。
- 带 GT-union-mask 的背景深度 affine oracle 将 DINO interface F1 提到 1.693%，planner parity 为 211 safe / 2 collision / 31 reject，仍未过主 gate。下一步应使用 TablewareNet training/validation 做域对齐训练，test 保持冻结。

- TransCG official test 已完整下载并审计：52 scenes，23,524 samples；不再受 Google Drive 配额阻塞。
- ReMake 已按原生入口跑完 23,524 张，masked 指标在论文 Table I 报告精度内一致。
- DFNet 已跑完当前官方 release 的原生全量评测；官方明确说明当前 checkpoint 不同于论文原 checkpoint，因此不能宣称逐项复现论文旧表。
- T²SQNet 已完成 100-scene `GT-mask` 与完整 RGB/LangSAM inference；ShellBench 在其中 98 个含 hollow GT 的 scene 上评分，不能冒充 T²SQNet 论文表格指标。
- fixed-planner 表示 oracle 已完成：同一 7,983 个候选上，front optimistic 的 safe selection 为 224/244，full events 为 244/244；表示层 G0 gate `PASS`。
- DFNet、ReMake 和 rendered-front upper bound 已接入同一 ShellBench 与 frozen planner；完美 visible front 的 interface F1 仍只有 43.104%，actual OOD 模型的 optimistic 策略均产生 21/244 个 selected collision。
- Depth4ToM 的公开 Base 路径已复现；FT checkpoint 未公开可用，Base 结果不得改名为 FT。
- LayeredDepth / SeeGroup 的 P0 gap 已成立：取 MiDaS/DPT 中较强的 MiDaS Base，`layer_all` quad 与 SeeGroup 仍相差 37.572 个百分点。

## 结果应该放在哪张表

| 表 | 可放方法 | 不应混入 |
| --- | --- | --- |
| TransCG metric depth completion | DFNet current release、ReMake、raw input depth | T²SQNet ShellBench、SeeGroup cross-protocol 读数 |
| LayeredDepth multi-layer | MiDaS/DPT Base、SeeGroup | Booster ToM RMSE |
| ShellBench multi-interface | DFNet/ReMake OOD readout、T²SQNet RGB、T²SQNet GT-mask oracle、后续 Head | TransCG 论文指标 |
| fixed-planner collision diagnostic | front/events oracles、DFNet/ReMake readout、后续各方法 event readout | 机器人 task success 声明 |

## 目录导航

- P0 支撑线：[P0_三件套.md](P0_三件套.md)、[Depth4ToM.md](Depth4ToM.md)、[LayeredDepth.md](LayeredDepth.md)、[SeeGroup.md](SeeGroup.md)
- TransCG baselines：[TransCG_DFNet.md](TransCG_DFNet.md)、[ReMake.md](ReMake.md)
- 工具入口：[tools/transcg](tools/transcg)、[tools/remake](tools/remake)、[tools/t2sqnet](tools/t2sqnet)、[tools/shellbench](tools/shellbench)
- 2026-07-27 的旧总览保留为历史快照：[复现进度总览_2026-07-27.md](复现进度总览_2026-07-27.md)

权重、数据集和逐帧预测均由 `.gitignore` 排除；Git 只保存代码、协议、汇总结果和审计信息。
