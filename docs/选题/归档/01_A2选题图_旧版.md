# 2026-06-26 CCFA Idea Map: 扩散模型 × 单目深度估计

> 目标:围绕 MDE 主攻线生成可推进的 CCF-A 选题。  
> 默认 venue family:CVPR / ICCV / ECCV。  
> 约束:不要求用户自采双目/LiDAR/事件相机数据;可使用公开数据集与公开模型。  
> 证据状态:本文件是 idea map,不是实验结果报告。所有性能结论均为待验证。

---

## 0. 收敛建议

当前最值得推进的是一个组合路线:

```
主方法:Proxy-Anchored CCF for Near-Single-Step Metric Diffusion Depth
主机制证据:Anchor Propagation Radius
保底资产:Metric-vs-Affine / NFE-real / Failure-slice Protocol
```

一句话:

> 冻结扩散深度骨干,用 Tweedie 代理锚构造 proxy-anchored CCF,并把单目几何锚烘焙进 1-2 步采样轨迹,验证采样期注入是否比 patch-wise 后处理更能把 metric 修正传播到无锚区域。

这条路线直接继承现有 A② 实验包,且能用最便宜的 L0/L1/L2/diag 证伪。

---

## 1. Idea 1: Proxy-Anchored CCF for Near-Single-Step Metric Diffusion Depth

### Problem

Marigold 类扩散深度模型具有强生成先验,但原始推理慢,且输出 affine-invariant relative depth。E2E-FT 说明修正推理调度后未微调 Marigold 也能单步很强,但它不解决 metric grounding,也没有轨迹控制机制。GeoDiff/Defocus-Marigold/AnchorD 等近邻又分别从 stereo、散焦或后处理角度抬高了米制化门槛。

### Gap

尚需回答:

1. 推理期 OT/CCF 时间平滑是否能从图像编辑迁移到稠密深度回归。
2. 几何锚是否必须进入采样过程,还是解码后 patch-wise affine 后处理已经足够。
3. 1-2 步下能否同时保持单步效率和 metric grounding 质量。

### Core Insight

深度条件生成的目标端未知,不能直接复制 ChordEdit 的两端锚设定。可用骨干自身 Tweedie / x0 prediction 产生目标代理锚,再在去噪时间窗内对指向该代理锚的位移场做 CCF 时间平均。几何锚不作为事后 scale/shift,而是烘焙进采样期的等效方向,让骨干在下一步重去噪时把局部 metric 修正传播到无锚区域。

### Method Sketch

```
RGB I
  -> frozen Marigold/E2E-FT image condition
  -> z_T depth latent
  -> Tweedie x0(t_s), x0(t_s-delta)
  -> proxy-anchored CCF u_hat
  -> decode depth, apply shared metric grounding primitive
  -> encode back to latent
  -> optional second denoise step for anchor propagation
  -> metric depth
```

### Central Claims

| Claim | Reviewer Question | Required Evidence |
|---|---|---|
| CCF 不是装饰 | 不就是单点 x0 或多噪声平均? | L0: `b_ccf < a_single` 且 `b_ccf < c_multinoise` |
| CCF 有纠偏作用 | 时间平均只能降方差,压不掉有偏 Tweedie 锚 | `diag`: `abs_bias(b_ccf) < abs_bias(c_multinoise)` 或证明几何锚纠偏 |
| 采样期注入优于后处理 | 为什么不用 AnchorD 式 patch-affine? | L1: `C_sample_geo_local < Bp_postproc_patch_ccf` |
| 近单步可行 | 几何 guidance 天然要多步 | L2: NFE-real <= 2 接近高 NFE |
| 非假米制 | 是否只是 affine 对齐好看? | metric 协议主表 + affine 对齐收益 `align_gain` |

### Fatal Risks

- `L0` 失败:CCF 退化为 E2E-FT 单步,方法新意塌。
- `L1` 失败:采样期注入不如同源 patch-wise 后处理,米制卖点塌。
- `L2` 失败:几何锚需要多步迭代,单步/近单步卖点塌。
- VAE decode/encode 往返残差过大:几何锚在 latent 往返中被抹掉。

### Minimum Experiments

直接复用 `a2/A2_run_grid.py`:

```bash
cd a2
python A2_run_grid.py --phase L0 --backbone e2eft --dataset nyu --root ../data/nyu --seeds 0 1 2 --num_noise 4 --out ../runs/L0_nyu.csv
python A2_run_grid.py --phase diag --backbone e2eft --dataset nyu --root ../data/nyu --K 8 --seeds 0 1 2 --num_noise 4 --out ../runs/diag_nyu.csv
python A2_run_grid.py --phase L1 --backbone marigold --model_id prs-eth/marigold-depth-v1-1 --dataset nyu --root ../data/nyu --K 1 2 4 8 16 32 --seeds 0 1 2 --out ../runs/L1_nyu.csv
python A2_run_grid.py --phase L2 --backbone marigold --model_id prs-eth/marigold-depth-v1-1 --dataset nyu --root ../data/nyu --nfe 1 2 4 8 --seeds 0 1 2 --out ../runs/L2_nyu.csv
```

---

## 2. Idea 2: Anchor Propagation Radius in Foundation Depth Models

### Problem

metric anchors 的价值不只在锚点处对齐,而在于它们能否把尺度/结构修正传播到无锚区域。AnchorD 式 patch-wise affine 后处理已经很强,但它没有解释采样期注入是否能产生更远、更结构化的传播。

### Core Insight

把“采样期注入 vs 后处理”的争论改写成可测量的问题:

> metric correction 的传播半径是多少? 它在语义边界、深度不连续、地平面、反光/透明区域如何衰减?

### Method

构造不同 K、不同锚分布、不同 anchor distance bucket:

```
distance-to-anchor: 0-4 px / 4-16 px / 16+ px
depth range: near / mid / far
surface type: normal / reflective / transparent
geometry type: plane / discontinuity / object interior
```

比较:

- global affine
- patch-wise affine
- factor-graph / AnchorD-style baseline
- diffusion sample-time injection
- diffusion injection without second denoise step

### Evidence

核心图不是普通主表,而是:

```text
AbsRel vs distance-to-anchor
delta(C - Bp) vs distance-to-anchor
failure slices under reflective / far / discontinuity regions
```

### Why It Helps A②

如果采样期注入真的有价值,优势应在 `far_anchor` 或 patch 锚不足区域体现。若只在锚点附近赢,那更像硬投影或后处理复杂度,不是扩散采样机制。

---

## 3. Idea 3: Bias-Calibrated Diffusion Depth

### Problem

ChordEdit 的 CCF 成立部分依赖零均值噪声降方差;深度任务中的 Tweedie 代理锚可能存在系统偏差。直接套 CCF 容易被 reviewer 攻击为“降方差不纠偏”。

### Core Insight

把多时间点 x0 prediction 当作诊断信号,显式估计:

```text
bias(t), variance(t), curvature(t), disagreement(t)
```

然后自适应选择 t-window、CCF 权重、几何锚权重,而不是固定使用一个时间窗。

### Contribution Type

empirical finding + adaptive inference procedure。

### Minimum Evidence

- `A2_diag_bias_var.py` 在真实 Marigold/E2E-FT 上的 bias-var 分解。
- 固定 CCF vs adaptive CCF。
- 区分方差下降和结构偏差下降。

### Risk

如果只做诊断没有精度或可靠性闭环,主会力度不足。需要至少产生 adaptive t-window 或 confidence-aware geo weighting 的实际收益。

---

## 4. Idea 4: Recoverability-Guided Diffusion Depth under HDR / RAW Exposure

### Problem

sRGB 的 clip/quantization 会破坏 shading、texture gradient、defocus 等深度线索。RAW/linear HDR 中部分区域仍保留几何相关信号,但硬饱和区域不可恢复。现有低光/HDR/RAW 方向多数不以单图前馈 MDE 的 metric/relative depth 鲁棒性为核心。

### Core Insight

不要笼统声称 RAW 更好,而是显式建模 recoverability:

```text
可恢复带: sRGB 已损坏,RAW/linear 仍有残余梯度
不可恢复带: 传感器也饱和或噪声淹没
正常带: 不应因 RAW 前端退化
```

### Method

RAW/HDR 输入 -> recoverability map -> depth-oriented front-end 或 diffusion guidance -> robust depth。

### Evidence

- Hypersim HDR layers + depth 为主证据。
- sRGB / exposure enhancement / RAW front-end / recoverability mask 消融。
- 按正常、过曝、欠曝、硬饱和分片报告。

### Risk

真实 RAW + dense depth 数据稀缺。需要把真实实验定位为定性/小样本外部证据,不要把“真实数据主表”作为立项前提。

---

## 5. Idea 5: Metric-vs-Affine Evaluation Trap Benchmark for Generative MDE

### Problem

生成式 MDE 文献容易混用 affine-invariant、median scaling、metric zero-alignment、ensemble、NFE 与 wall-clock。协议不统一会掩盖“假米制”和“假单步”。

### Core Insight

把评测对象从单一 AbsRel 扩展为:

```text
metric AbsRel
affine AbsRel
align_gain
nfe_real
wall-clock
failure slices
anchor distance decay
```

### Contribution

一个专门面向 generative/foundation MDE 的 protocol + toolkit,用于同时暴露真假米制、真假单步和长尾失败。

### Evidence

横向重跑 Marigold / E2E-FT / Lotus / DepthFM / UniDepth / Metric3D / Depth Pro / A② variants。该方向可以复用 `A2_eval_protocol.py` 和 `A2_failure_slices.py`。

### Risk

作为独立 CVPR 主会论文可能偏 benchmark/toolkit。更适合作为 A② 主文的强实验协议,或 workshop / reproducibility 方向。

---

## 6. 建议路线图

### Week 1: cheapest falsification

1. 复现 E2E-FT/Marigold 单步 baseline。
2. 跑 L0 和 diag。
3. 跑 L1 小 K 曲线,只看 `C` vs `Bp`。

### Week 2: 机制归因

1. 补 `C_prop`:只在非末步烘焙锚,区分“传播”与“末步注入”。
2. 画 anchor propagation radius。
3. 跑 VAE roundtrip residual。

### Week 3: 主实验扩展

1. NYU -> DIODE/ETH3D/KITTI。
2. Marigold -> E2E-FT/Lotus/DepthFM。
3. failure slices: far / reflective / far-from-anchor。

### Go / No-Go

| Gate | Pass | Fail |
|---|---|---|
| L0 | CCF 保留为主创新 | 转向 Bias-Calibrated Diagnostic |
| L1 | 采样期注入保留 | 降级为 evaluation/anchor propagation analysis |
| L2 | near-single-step 保留 | 改成 2-step proximal refinement |
| VAE residual | depth-latent 往返可用 | 改 latent-space direct anchor 或末步-only anchor |

---

## 7. 当前最近邻与边界

| 近邻 | 占了什么 | 本路线必须怎么区分 |
|---|---|---|
| Marigold | diffusion depth, affine-invariant relative depth | 本路线做 training-free metric grounding 与少步控制 |
| E2E-FT | 单步 Marigold 推理调度 | 本路线不能只卖单步,必须证明 CCF/geo 额外贡献 |
| DepthFM / Lotus | 训练式少步/单步深度 | 本路线强调 inference-time, training-free |
| ChordEdit | 图像编辑中的 CCF/OT 时间平滑 | 本路线重定义到深度条件生成,目标端由 Tweedie 代理 |
| GeoDiff | 采样期几何引导 metric depth | 本路线必须保持单目,不依赖 stereo |
| Defocus-Marigold | training-free 物理线索 metric grounding | 本路线用单目几何锚并压到 1-2 步 |
| AnchorD | patch-wise affine grounding 后处理 | 本路线必须赢同源 `Bp_postproc_patch_ccf` |

---

## 8. 写作时的诚实边界

- 不说“首个单步扩散深度”,因为 E2E-FT/Lotus/DepthFM 已经覆盖不同版本。
- 不说“首个 training-free metric depth”,因为 GeoDiff/AnchorD/Defocus 方向已有强近邻。
- 可说的窄 claim 是:推理期 proxy-anchored CCF 迁到稠密深度回归,并与单目几何锚结合,验证采样期注入对 metric anchor propagation 的作用。
- 所有“领先”“SOTA”“主会强度”都必须等真实结果后再写。
