# DepthHypothesisPack v1：强编码器、teacher 与尺度诊断

更新日期：2026-08-31

状态：**本轮受控实验全部完成；DINOv2-S、Depth Anything V2-S、SeeGroup teacher、尺度锚定、ShellBench 与冻结 planner 均已有结论。**

## 一句话结论

DINOv2-S 把真实 LayeredDepth 的 mixed-quad 从 20.45% 提高到 25.12%，说明
`K=4` head 能从更强特征中学到更多跨层排序；但它直接迁移到 TablewareNet 时
interface F1 只有 0.422%。即使用带 GT union mask 的渲染背景深度做 oracle
尺度锚定，F1 也只到 1.693%。因此当前主要问题不是“还缺一个更强的通用
encoder”，而是 **LayeredDepth-Syn 到操作域的米制尺度、外观和界面监督不对齐**。

本轮到此按 gate 停止：不训练 transition/planner head，不把 SeeGroup 的劣质
synthetic metric 输出硬蒸馏进模型，也不在 test GT 上拟合可报告方法。下一项
有信息量的实验应当是只用 TablewareNet training/validation 的域对齐多域训练，
现有 test 保持冻结。

## 1. 本轮回答了哪三个问题

1. **换强 encoder 是否足够？** 部分有用：DINOv2-S 明显提高 mixed-layer，
   但 ShellBench 更差，因此不够。
2. **SeeGroup 能否直接当输出 teacher？** 不能：它在真实 LayeredDepth 排序很强，
   但在抽查的 LayeredDepth-Syn metric target 上尺度与 presence 明显不可靠。
3. **问题是否只是一个全局 scale？** 不是：oracle 全局 affine 仍有约 8.8 cm
   前层 MAE；逐帧背景 affine 虽提高 interface F1，却仍离可用水平很远。

所有真实 LayeredDepth、TablewareNet test 与 ShellBench 数据都没有参与模型训练或
presence 阈值选择。背景锚定单独标为 oracle diagnostic，因为它在 test 输入中使用
渲染背景深度，而且背景掩码来自 GT union object mask。

## 2. 强 encoder 的受控筛选

### 2.1 先通过可拟合性检查

冻结 DINOv2-S 和官方 Depth Anything V2-S 都能在 4 张样本上拟合，说明接线、
梯度和输出 contract 正常：

| Encoder | 4-sample depth MAE ↓ | Front MAE ↓ | Presence F1 ↑ |
|---|---:|---:|---:|
| DINOv2-S frozen | **0.1087 m** | **0.0791 m** | 0.9491 |
| Depth Anything V2-S frozen | 0.1363 m | 0.0882 m | **0.9766** |
| DINOv2-S last block trainable | 0.1141 m | 0.0822 m | 0.9437 |

最后一块微调没有优于 frozen DINO，因此没有扩大该分支。

### 2.2 同一 1,000 张 pilot 决定是否扩大

DINOv2-S 与 Depth Anything V2-S 使用相同的 cache、seed、split、head、loss、
optimizer、20 epochs 和 frozen encoder：

| Encoder | Depth MAE ↓ | Front MAE ↓ | Raw presence F1 ↑ | 校准后 pooled F1 ↑ |
|---|---:|---:|---:|---:|
| **DINOv2-S** | **0.5222 m** | **0.4648 m** | **0.9005** | **0.8799** |
| Depth Anything V2-S | 0.5371 m | 0.4772 m | 0.8755 | 0.8678 |

Depth Anything 的校准后 pooled F1 低于预先使用的 0.87 pilot 下限，也全面低于
DINO；因此没有浪费一次 14,800 张正式训练。这里使用的是官方 Depth Anything
代码和严格加载的 175/175 keys checkpoint，checkpoint SHA-256 为
`715fade13be8f229f8a70cc02066f656f2423a59effd0579197bbf57860e1378`。

曾尝试把该权重转换到 Hugging Face DINO，但即使 state keys 完整，patch features
仍因 forward/positional interpolation 实现差异而不一致；该转换在任何训练前就被
废弃，正式 pilot 没有使用它。

## 3. DINOv2-S 正式训练

| 项目 | 值 |
|---|---:|
| 训练数据 | LayeredDepth-Syn train 14,800 张 |
| train / held-out | 13,320 / 1,480 |
| seed | 42 |
| encoder | `facebook/dinov2-small`，frozen |
| Hugging Face revision | `ed25f3a31f01632728cabb09d1542f84ab7b0056` |
| head / crop / batch | 与 v0 相同，64 / 192 / 4 |
| epochs | 5 |
| 训练时间 | 52.8 分钟 |
| 真实评测泄漏 | 否 |

最优 checkpoint 是 zero-based epoch 4：

- depth MAE：0.4715 m；front MAE：0.4184 m；
- raw presence F1：0.9076；validation loss：0.6944；
- synthetic held-out 阈值：`[0.8720, 0.6715, 0.4060, 0.2255]`；
- 校准后 pooled presence F1：0.8951；
- checkpoint SHA-256：
  `479359af35b977fc7f55bcf6713558dbdb3513203e88263dce5ec11f690d13c4`。

ResNet-18 formal 的 encoder 是 fine-tuned，而 DINO formal 保持 frozen，因此二者
不是“只换一行 encoder”的严格训练策略消融；严格 frozen encoder 对照是上一节的
DINO 与 Depth Anything 1k pilot。它们仍共享同一 head、监督和统一评测协议。

## 4. 真实 LayeredDepth validation（300 张）

下表全部是本项目统一 evaluator 的读数，不是把不同论文原表直接拼在一起。

| 方法 | First quad ↑ | All quad ↑ | Mixed quad ↑ | 结果性质 |
|---|---:|---:|---:|---|
| DPT-Large Base | 56.20% | 29.95% | 0.00% | single-depth unified baseline |
| MiDaS v2.1 Base | 66.17% | 34.84% | 0.00% | single-depth unified baseline |
| DHP ResNet-18 formal | 41.63% | 32.04% | 20.45% | 本项目 v0 |
| **DHP DINOv2-S formal** | **39.59%** | **32.91%** | **25.12%** | 本项目 v1 |
| SeeGroup released checkpoint | 78.37% | 72.41% | 66.61% | native multi-layer baseline |

DINO 的完整 tuple 指标：

| subset | Pair ↑ | Trip ↑ | Quad ↑ |
|---|---:|---:|---:|
| layer_first | 69.29% | 48.08% | 39.59% |
| layer_all | 59.51% | 39.92% | 32.91% |
| mixed | 56.49% | 32.39% | 25.12% |

相对 ResNet，DINO 的 all/mixed quad 分别提高 0.87/4.67 个百分点，但 first
下降 2.03 个百分点；相对 single-depth，它高于 DPT 2.96 个百分点，仍低于
MiDaS 1.93 个百分点，并远低于 SeeGroup。因此它通过了“更强 mixed signal”
小 gate，没有通过主性能 gate。

## 5. 为什么不直接蒸馏 SeeGroup

SeeGroup 的 released ViT-L checkpoint 本身仍是最强 baseline：真实
LayeredDepth all/mixed quad 为 72.41%/66.61%。但“baseline 很强”不等于“它在
我们的 synthetic metric target 上是好 teacher”。

在不使用 real validation 的前提下，以官方 518 分辨率、CPU FP32 审计
LayeredDepth-Syn train 的前 8 张样本：

| Teacher target 诊断 | 结果 |
|---|---:|
| paired metric depth MAE | **5.6499 m** |
| presence F1 | **0.5928** |
| predicted valid fraction | 每张约 98.9% |
| 8 张逐样本 depth MAE | 4.690 / 7.066 / 5.257 / 5.570 / 4.758 / 8.288 / 5.527 / 5.588 m |

这与它在 Booster 上“raw head 不是 metric calibrated、affine 对齐后才合理”的
现象一致。结论是：**保留 SeeGroup 作为真实 multi-layer strong baseline，但拒绝
直接蒸馏其 raw metric depth/presence 输出。** 本轮没有在这个失败 target 上启动
teacher training。未来若用 SeeGroup，应研究相对顺序或 feature distillation，而
不是把 raw depth 当米制真值。

## 6. ShellBench：域与尺度诊断

### 6.1 直接迁移

DINO 对 TablewareNet 100 个 test scenes 产生 700 个视角预测；98 个空心场景中，
259 个对象、1,813 个 object-view maps、2,798,936 条 predicted rays 共得到
6,871,839 个事件。ShellBench 评分 denominator 固定为 139,238,400 条射线。

| 方法 | Precision @5 mm | Recall @5 mm | Interface F1 | Matched MAE |
|---|---:|---:|---:|---:|
| DHP ResNet formal | 1.600% | 0.649% | 0.924% | 2.295 mm |
| DHP DINO raw | 0.524% | 0.354% | 0.422% | 2.276 mm |
| **DHP DINO + 背景 affine oracle** | **2.101%** | **1.417%** | **1.693%** | 2.289 mm |
| Rendered-front single-depth upper bound | 100.000% | 27.473% | 43.104% | 0.545 mm |

Matched MAE 只统计已经落入 5 mm matching 的少量界面，不能掩盖极低 recall。
`interface_count_accuracy=98.23%` 同样被大量背景射线支配，不作为成功证据。

### 6.2 不是一个简单全局 scale

只为诊断、使用 GT visible front 计算（不用于训练或阈值选择）：

| DINO front 诊断 | Bias | MAE | 5 mm 内 | 10 mm 内 |
|---|---:|---:|---:|---:|
| raw metric output | +0.3382 m | 0.3459 m | 0.617% | 1.244% |
| GT oracle global affine | — | **0.0880 m** | 3.429% | — |
| per-frame background affine | +0.1087 m | **0.1269 m** | 1.970% | 3.947% |

即使直接用 test GT 求全局最优 `GT = 0.199383 × pred + 0.520227`，仍有
8.8 cm MAE，所以错误不是单个比例常数。该全局 affine 只用于证明这一点，从未
作为方法结果。

### 6.3 背景 affine oracle 的边界

逐帧方法只在 mask-zeroed 的渲染背景有效点上做 1% 双尾裁剪和 5 次 Huber IRLS，
不使用任何 object/shell depth；同一个正 slope/offset 应用于四层深度，presence
不变。700 帧统计：

- slope：0.111 / 0.321 / **0.452** / 0.618 / 0.857
  （min/p10/median/p90/max）；
- offset：0.009 / 0.240 / **0.352** / 0.448 / 0.621 m；
- 背景 median absolute error 的帧中位数：0.1172 m → 0.0568 m。

它没有训练/阈值泄漏，也没有看物体深度，但**使用了 test 渲染背景深度与 GT
union object mask**，所以只能放在 oracle diagnostic 区，不能和纯 RGB 方法并列
声称部署性能。

## 7. 冻结 planner（244 对象 / 7,983 候选）

所有方法复用同一套 T²SQNet GT-mask 预测对象、官方 primitive candidates、
2 mm surface band、seed 0 和 2,000 次 scene bootstrap。

| 输入几何 | Optimistic（safe/collision/reject） | Conservative | K-event parity |
|---|---:|---:|---:|
| DHP ResNet formal | 223 / 21 / 0 | 197 / 5 / 42 | 198 / 5 / 41 |
| DHP DINO raw | 226 / 18 / 0 | 228 / 5 / 11 | 229 / 5 / 10 |
| **DHP DINO + 背景 affine oracle** | **227 / 16 / 1** | **206 / 2 / 36** | **211 / 2 / 31** |
| GT shell | 224 / 20 / 0 | 240 / 0 / 4 | 244 / 0 / 0 |

锚定后的 K-event parity 相对 raw DINO 将碰撞 5→2，但 safe 229→211、reject
10→31；相对同一锚定模型的 front-conservative，它只多恢复 5 个 safe，碰撞仍为
2。其 candidate collision recall 为 70.11%，all-object collision-free selection
rate 为 86.48%（scene-bootstrap 95% CI：81.97%–90.61%）。这仍不足以开始训练
planner head。

## 8. 无效或被替代的运行

为避免日后误引用，以下均不进入正式表：

- 第一次 DINO LayeredDepth 全分辨率 GPU upsample 在第 165 张 OOM；已由
  CPU-upsample 的完整 300 张运行替代。
- 一次通用 Shell evaluator 因 metadata contract 不匹配得到 0 samples；该结果
  无效，已由动态 method metadata 与 139,238,400-ray 完整运行替代。
- Depth Anything → Hugging Face DINO 近似转换的 features 不一致；训练前废弃。
- DINO last-block overfit 不优于 frozen；不扩大。
- overfit run 的 calibrator 正确拒绝“训练样本同时当 held-out”；这是防泄漏保护，
  不是模型失败。
- SeeGroup synthetic output teacher 未过 target-quality gate；没有蒸馏训练。
- GT global affine 与背景 affine 均是 oracle 诊断，不是可报告纯 RGB baseline。

## 9. 最终 gate 与下一步

| Gate | 判定 | 证据 |
|---|---|---|
| 强 encoder mixed signal | **部分通过** | mixed quad 20.45%→25.12% |
| LayeredDepth 主性能 | **未通过** | all quad 32.91% < MiDaS 34.84% ≪ SeeGroup 72.41% |
| 直接 SeeGroup output teacher | **拒绝** | synthetic MAE 5.65 m、presence F1 0.593 |
| 简单尺度修正 | **未通过** | oracle anchor F1 仅 1.693%，仍远低于 43.104% |
| 动作效用 | **未通过** | anchor parity 211/2/31，离 GT 244/0/0 很远 |
| transition/planner head | **继续延后** | 上游界面质量未过 gate |

现在不需要继续复现更多重型 baseline，也不需要继续扩张 test benchmark；现有
LayeredDepth + ShellBench + frozen planner 已能稳定定位失败。下一项应是：

1. 从 `table_object_num_4_processed/training`（3,000 scenes）导出 physical-shell
   多界面监督，先做固定 seed 的小 pilot；
2. 用独立的 `validation` 100 scenes 做模型选择与 presence/scale 校准，现有
   `test` 100 scenes 完全不碰；
3. 保留 LayeredDepth-Syn 的多层排序监督，同时加入 TablewareNet training 的
   域内米制/interface 监督；
4. pilot 在 TablewareNet validation 的 interface F1 达到预先冻结的实质性门槛后，
   才扩大到 3,000 scenes；配置冻结后只跑一次 test；
5. 只有 test interface 与 frozen planner 同时改善，才添加 transition type 和
   learned planner head。

这比继续调 encoder、在 test 上拟合 scale 或新增 benchmark 更直接地验证核心假设。

## 10. 关键产物

- 机器可读结果：
  `透明物体/复现/depth_hypothesis_pack_v1_results_2026-08-31.json`
- 实现与运行说明：`透明物体/depth_hypothesis_pack/`
- DINO checkpoint：
  `透明物体/runs/depth_hypothesis_pack/train14800_dinov2s_frozen_v1_seed42/best.pt`
- LayeredDepth：
  `透明物体/runs/depth_hypothesis_pack/layereddepth_validation_dinov2s_formal14800_v2_cpuupsample_seed42/evaluation_both.json`
- DINO raw ShellBench：
  `透明物体/runs/depth_hypothesis_pack/tablewarenet_events_dinov2s_formal14800_v1_seed42/`
- 背景锚定 ShellBench 与 planner：
  `透明物体/runs/depth_hypothesis_pack/tablewarenet_events_dinov2s_bganchor_v1_seed42/`

`runs/`、数据和 checkpoint 均为本地大文件，不进入 Git；代码、协议、可读记录和
机器结果可以进入 Git。
