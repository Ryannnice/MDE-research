# I1: Proxy-Anchored CCF for Near-Single-Step Metric Diffusion Depth

## 一句话

冻结扩散深度骨干,用 Tweedie 代理锚构造 proxy-anchored CCF,并把单目几何锚烘焙进 1-2 步采样轨迹,验证采样期注入是否比 patch-wise 后处理更能把 metric 修正传播到无锚区域。

## 目标与边界

| 项 | 内容 |
|---|---|
| 目标任务 | 单图输入,免训练推理期输出米制深度 |
| 骨干 | Marigold / E2E-FT,后续可扩展 Lotus / DepthFM |
| 约束 | 冻结权重;主张 1-2 步;必须报告 `nfe_real` |
| 非目标 | 不声称首个单步扩散深度;不声称首个 training-free metric depth |
| 当前状态 | A2 代码骨架已存在,真实 CSV 待跑 |

## Problem

Marigold 类扩散深度模型有强生成先验,但原始推理慢,并且输出 affine-invariant relative depth。E2E-FT 说明修正推理调度后未微调 Marigold 也能单步很强,但它不解决 metric grounding,也没有轨迹控制机制。GeoDiff、Defocus-Marigold、AnchorD 又分别从立体、散焦或后处理角度抬高了米制化门槛。

核心问题:

```text
能否在不训练权重的前提下,把扩散深度从慢速相对深度
变成 1-2 步、单目、可米制锚定的深度先验?
```

## Gap

1. 推理期 OT/CCF 时间平滑尚未被验证能迁移到稠密深度回归。
2. 几何锚进入采样期是否真的优于解码后 patch-wise affine 后处理,仍未证明。
3. 1-2 步下几何引导是否能接近多步 guidance,仍是科学赌注。

## Core Insight

ChordEdit 的 CCF 依赖“源端-目标端”传输方向,但深度条件生成的目标端 `d0` 正是未知输出。因此不能直接复制图像编辑设定。I1 的非平凡重定义是:

```text
用骨干自身的 Tweedie / x0 prediction 产生目标代理锚 d_hat0,
再在去噪时间窗内对指向 d_hat0 的位移场做 CCF 时间平均。
```

几何锚不作为事后 scale/shift,而是进入 CCF 方向构造,让 metric 修正通过骨干去噪过程传播到无锚区域。

## Method Blueprint

```text
RGB I
  -> frozen diffusion depth backbone
  -> image condition z(I)
  -> depth noise latent z_T
  -> Tweedie proxy d_hat0 at one or more denoising times
  -> proxy-anchored CCF:
       average velocity / displacement fields across denoising time
  -> inject monocular geometry energy into CCF direction
       object-size / ground-plane / EXIF intrinsics / oracle sparse anchors for mechanism test
  -> 1-step or 2-step denoising trajectory
  -> metric depth
```

建议先用 oracle sparse GT anchors 做机制验证,再替换为真实单目几何锚。否则早期会把“锚源质量”和“采样期传播机制”混在一起。

## Linchpins

| Gate | 要证明什么 | 判据 |
|---|---|---|
| L0 | CCF 不是单点 x0 或多噪声平均的装饰 | `b_ccf < a_single` 且 `b_ccf < c_multinoise` |
| diag | CCF 不只是降方差,还要抵抗 Tweedie 有偏代理锚攻击 | `abs_bias(b_ccf) < abs_bias(c_multinoise)` |
| L1 | 采样期注入优于同源 patch-wise 后处理 | `C_sample_geo_local < Bp_postproc_patch_ccf` |
| L2 | 近单步可行 | `nfe_real <= 2` 接近高 NFE |

失败解释:

- L0 失败:退化为 E2E-FT 风格单步调度修正。
- diag 失败:ChordEdit 的零均值平均假设无法外推到有偏 Tweedie 代理。
- L1 失败:米制改进不需要采样期注入,后处理足够。
- L2 失败:几何引导需要多步,只能降级为 2+ 步 guidance。

## Baselines

| 类别 | Baseline | 作用 |
|---|---|---|
| 扩散相对深度 | Marigold | 原始 affine-invariant 骨干 |
| 单步扩散 | E2E-FT / Lotus / DepthFM | 证明 I1 不是只卖单步 |
| 米制 SOTA | UniDepth / Metric3D v2 / Depth Pro / ZoeDepth | metric 协议横比 |
| 免训练米制近邻 | GeoDiff / Defocus-Marigold / AnchorD | 区分锚源、采样期、后处理 |
| 内部消融 | single x0 / multinoise / CCF / postproc global / postproc patch-wise | 机制证据 |

## Evaluation Protocol

主表必须是 metric protocol:

```text
不做 median scaling
不做 affine scale+shift alignment
报告 AbsRel / RMSE / log10 / delta1 / delta2 / delta3
```

另报 affine protocol 作为诊断:

```text
align_gain = metric_error - affine_aligned_error
```

若 `align_gain` 很大,说明模型仍是假米制。

## Phase Plan

| Phase | 目标 | 数据 | 状态 |
|---|---|---|---|
| 0 | 复现 E2E-FT / Marigold 单步冒烟 | NYU 小子集 | 待跑 |
| 1 | L0 + diag + L1 小 K | NYU | 待跑 |
| 2 | L2 NFE 曲线 | NYU / KITTI | 待跑 |
| 3 | 跨数据集主表 | NYU / KITTI / ETH3D / ScanNet / DIODE | 待跑 |
| 4 | failure slices 与锚传播半径 | far / reflective / far-from-anchor | 待跑 |

## Commands

当前命令仍以 A2 driver 为准:

```bash
cd a2
python A2_run_grid.py --phase L0 --backbone e2eft --dataset nyu \
  --root ../data/nyu --seeds 0 1 2 --num_noise 4 --out ../runs/L0_nyu.csv

python A2_run_grid.py --phase diag --backbone e2eft --dataset nyu \
  --root ../data/nyu --K 8 --seeds 0 1 2 --num_noise 4 --out ../runs/diag_nyu.csv

python A2_run_grid.py --phase L1 --backbone marigold --model_id prs-eth/marigold-depth-v1-1 --dataset nyu \
  --root ../data/nyu --K 1 2 4 8 16 32 --seeds 0 1 2 --out ../runs/L1_nyu.csv

python A2_run_grid.py --phase L2 --backbone marigold --model_id prs-eth/marigold-depth-v1-1 --dataset nyu \
  --root ../data/nyu --nfe 1 2 4 8 --seeds 0 1 2 --out ../runs/L2_nyu.csv
```

## Reviewer Risks

| 风险 | 类型 | 防守 |
|---|---|---|
| CCF 不就是 x0 prediction | requires-new-result | L0 消融必须赢 |
| Tweedie 锚有偏,时间平均只降方差 | requires-new-result | diag 必须显示纠偏或承认退化 |
| 采样期注入不如 patch-wise 后处理 | requires-new-result | L1 必须赢 patch-wise affine |
| 单步无法承载几何引导 | evidence-fixable | L2 曲线;必要时主张 1-2 步而非严格 1 步 |
| 假米制 | design-fixable | metric 主表 + align_gain |

## Related Literature

- `../文献调研/前沿专题/02_扩散深度与近单步米制化.md`
- `../文献调研/前沿专题/05_评测协议与可比性.md`
- 历史全文:`../文献调研/归档/03_MDE前沿追踪_全文.md` B3

## Current Verdict

条件推进。第一优先级不是扩主表,而是用 L0 / diag / L1 便宜证伪。如果 L1 赢不了 patch-wise 后处理,这个 idea 不应继续按主攻写。
