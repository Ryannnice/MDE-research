# DepthHypothesisPack v0 实验记录

更新日期：2026-08-31

状态：**14,800 张正式训练、校准、LayeredDepth、ShellBench 和冻结 planner 评测已全部完成。**

> 后续的 DINOv2-S、Depth Anything V2-S、SeeGroup teacher 与尺度诊断已完成；
> 最新结论见
> [DepthHypothesisPack v1 强编码器与尺度诊断](DepthHypothesisPack_v1_强编码器与尺度诊断_2026-08-31.md)。

## 一句话结论

`K=4` 最小模型证明了多层表示能产生 single-depth 无法产生的
mixed-layer 信号，但**主性能 gate 未通过**：LayeredDepth all-quad 仍低于
MiDaS Base，ShellBench interface F1 只有 0.924%，K-event planner 相比同模型
front-conservative 仅多恢复 1 个安全选择。继续只扩大 ResNet-18 v0
训练量不是下一步的合理选择。

## 1. 我们做了什么

- 输入：单张 RGB。
- 输出：最多 4 个严格有序的米制深度、逐层 presence probability 和
  uncertainty。
- 结构：ImageNet ResNet-18 + 轻量 FPN + 全分辨率 RGB refinement。
- 监督：只使用 `LayeredDepth-Syn/train`。
- 真实 LayeredDepth、Booster、TransCG 和 TablewareNet 全部保持 evaluation-only。
- 稀疏层：使用条件 gate 的逐层类平衡 BCE，避免模型永远只输出第一层。
- 阈值：只在 synthetic held-out split 上逐层校准，之后冻结。
- ShellBench v0 不预测 transition type；所有 transition 保持 `UNKNOWN/N/A`。

## 2. 数据与正式训练

| 项目 | 值 |
|---|---:|
| LayeredDepth-Syn revision | `78fd900929879332e60d7190d9bd423b8432669b` |
| 完整缓存 | 14,800 张 / 56 shards / 约 5.2 GB |
| 数据完整性 | 14,800/14,800 PASS |
| 训练 / synthetic held-out | 13,320 / 1,480 |
| 随机种子 | 42 |
| 训练轮数 | 5 |
| batch / crop | 4 / 192 |
| decoder / encoder LR | `3e-4` / `3e-5` |
| 训练时间 | 55.2 分钟 |
| 真实评测数据泄漏 | 否 |

最优 checkpoint 是第 5 轮（zero-based epoch 4），SHA-256 为
`8fe83b695bb30ecbec1baa035ee0f954218fc9b4683fcc9ca54f9a02d03a76e8`。

### Synthetic held-out 指标

| 指标 | 结果 |
|---|---:|
| 全层 depth MAE | 0.5228 m |
| front depth MAE | 0.4728 m |
| pooled presence F1（阈值 0.5） | 0.8909 |
| Layer 2/3/4 F1（阈值 0.5） | 0.6024 / 0.4229 / 0.0158 |

只在 1,480 张 synthetic held-out 上校准得到阈值
`[0.9045, 0.6825, 0.4265, 0.2690]`；校准后各层 F1 为
`[0.9994, 0.6296, 0.4466, 0.2837]`。`real_evaluation_data_used=false`。

### 代码与协议回归

| 测试集 | 结果 |
|---|---:|
| DHP 数据/模型/loss/校准/adapter | 9/9 PASS |
| benchmark manifest | 3/3 PASS |
| 冻结文件与 denominator 验证 | PASS |
| LayeredDepth evaluator | 9/9 PASS |
| ShellBench ray/planner/adapter | 16/16 PASS |
| 共用 interface evaluator 集成测试 | 1/1 PASS |

## 3. LayeredDepth real validation（300 张）

以下是本项目统一 evaluator 的分数，不是不同论文原表之间的跨协议比较。

| 方法 | First quad ↑ | All quad ↑ | Mixed quad ↑ |
|---|---:|---:|---:|
| DPT-Large Base | 56.20% | 29.95% | 0.00% |
| MiDaS v2.1 Base | 66.17% | **34.84%** | 0.00% |
| DHP v0，1,000 张 pilot | 39.42% | 32.31% | 23.91% |
| **DHP v0，14,800 张 formal** | **41.63%** | **32.04%** | **20.45%** |
| SeeGroup released checkpoint | 78.37% | 72.41% | 66.61% |

正式模型的完整指标：

| subset | Pair ↑ | Trip ↑ | Quad ↑ |
|---|---:|---:|---:|
| layer_first | 70.33% | 50.77% | 41.63% |
| layer_all | 57.30% | 39.91% | 32.04% |
| mixed | 48.54% | 29.53% | 20.45% |

解读：

- mixed 从 single-depth 的 0 变为 20.45%，证明 `K=4` 确实表达了跨层信号。
- formal 的 front quad 比 pilot 高 2.21 个百分点。
- formal 的 all/mixed quad 分别比 pilot 低 0.27/3.46 个百分点。
- 它略高于 DPT Base，但仍低于 MiDaS Base，远低于 SeeGroup；主性能 gate 未通过。

## 4. ShellBench interface（98 个空心场景）

adapter 与 single-depth diagnostic 使用同样的 GT object identity/association 和
rendered-front visibility，用来隔离深度表示质量。它不是端到端部署分数。

| 指标 | 1,000 pilot | 14,800 formal |
|---|---:|---:|
| 对象-视角 event maps | 1,813 | 1,813 |
| 平均事件数 / predicted ray | 2.025 | 1.477 |
| Interface precision @ 5 mm | 1.794% | 1.600% |
| Interface recall @ 5 mm | 0.998% | 0.649% |
| Interface F1 @ 5 mm | 1.282% | **0.924%** |
| Matched-interface MAE | 2.280 mm | 2.295 mm |
| Transition F1 | N/A | N/A |

对照的 rendered-front 单层上界 interface F1 为 43.10%。formal 不仅没有超过
它，还低于 pilot；这表明核心瓶颈是 synthetic → TablewareNet 的外观域差异、
绝对 metric scale/位置和 presence 泛化，而不是单纯缺少合成样本。

`interface_count_accuracy=97.87%` 主要被大量无物体背景射线支配，不能当作成功证据。

## 5. 冻结 planner（244 个对象，7,983 个候选）

候选只来自同一套 T²SQNet GT-mask 对象和官方 primitive planner；DHP 只用于
冲突判定。

| DHP 几何策略 | Safe selected ↑ | Collision selected ↓ | Rejected ↓ |
|---|---:|---:|---:|
| Front optimistic | 223 | 21 | 0 |
| Front conservative | 197 | 5 | 42 |
| **K-event fixed parity** | **198** | **5** | **41** |
| GT front conservative | 240 | 0 | 4 |
| GT full events | 244 | 0 | 0 |

K-event parity 的 candidate collision recall 为 56.95%，所有对象的无碰撞选择率为
81.15%（95% scene-bootstrap CI: 75.42%–86.92%）。

- 比 1,000-pilot parity 的 147 安全 / 1 碰撞 / 96 拒绝，formal 恢复了更多选择，
  但将碰撞增加到 5。
- 比同一 formal 模型的 front-conservative，K-event 只多 1 个安全选择、
  少 1 个拒绝，碰撞数不变。
- Dish failure slice 中 K-event 为 20 安全 / 5 碰撞 / 4 拒绝，而 GT full 为
  29/0/0。

因此“多层表示会改变动作决策”有弱信号，但“已经带来有意义的动作改善”不成立。

## 6. Gate 判定

| Gate | 判定 | 理由 |
|---|---|---|
| 表示信号 | **部分通过** | mixed-layer 从 0 变为非零，K-event 确实改变了 1 个 planner 决策 |
| LayeredDepth 主性能 | **未通过** | all-quad 32.04% < MiDaS 34.84% ≪ SeeGroup 72.41% |
| ShellBench interface | **未通过** | F1 0.924% ≪ rendered-front 43.10% |
| 动作效用 | **未通过** | parity 仅比 front-conservative 多 1 个安全选择，且仍有 5 次碰撞 |
| 扩大 v0 数据量 | **未通过** | front/planner coverage 提高，但 mixed 和 interface F1 比 pilot 更低 |
| Transition/topology | **延后** | v0 不预测 transition type，指标保持 N/A |

## 7. 现在不该做什么

- 不再为 ResNet-18 v0 只增加 epoch 或堆小工程补丁。
- 不在真实 LayeredDepth/TablewareNet 上搜阈值或拟合 scale。
- 不现在训练 planner head：上游 interface 质量还没有过 gate。
- 不继续扩建 benchmark：v0.1 已能清楚暴露失败模式，先改模型更有信息量。

## 8. 下一步实验顺序

1. **DINOv2 / Depth-Anything feature baseline**：保留完全相同的 `K=4` head、loss、
   split 和 evaluator，只替换 RGB encoder，判断是特征不足还是 head/监督问题。
2. **SeeGroup teacher distillation**：只在 synthetic training split 上缓存 teacher，蒸馏有序深度和
   presence，真实评测集仍不参与训练。
3. **跨域 metric-scale 方案**：使用训练域可得的相机/尺度信息或不依赖评测 GT
   的 self-calibration，禁止在真实 validation 上拟合。
4. 只有 LayeredDepth 和 ShellBench interface 都过 gate 后，才加 transition-type head
   和下游 planner head。

## 9. 关键产物

- 机器可读正式结果：
  `透明物体/复现/depth_hypothesis_pack_results_2026-08-31.json`
- 代码：`透明物体/depth_hypothesis_pack/`
- 冻结协议：`透明物体/benchmarks/v0.1/benchmark.json`
- 正式训练：
  `透明物体/runs/depth_hypothesis_pack/train14800_balanced_highres_v3_seed42/`
- LayeredDepth 结果：
  `透明物体/runs/depth_hypothesis_pack/layereddepth_validation_formal14800_v3_seed42/evaluation_both.json`
- ShellBench 结果：
  `透明物体/runs/depth_hypothesis_pack/tablewarenet_events_formal14800_v3_seed42/evaluation.json`
- Planner 结果：
  `透明物体/runs/depth_hypothesis_pack/tablewarenet_events_formal14800_v3_seed42/grasp_collision.json`

`runs/`、`data/` 和 checkpoint 是本地大文件，不进入 Git；实现、冻结协议、
实验记录和结果摘要可进入 Git。
