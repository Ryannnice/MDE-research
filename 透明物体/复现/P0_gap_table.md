# P0 Gap Table

状态：公开 Base 路线的两个 gap diagnostic 已完成；Depth4ToM FT 行因上游权重不可得保持 blocked。任何论文报告值与本地复现值必须分列。

## A. LayeredDepth validation

| Method | Checkpoint | Hypotheses | Subset | Pair acc. ↑ | Triplet acc. ↑ | Quadruplet acc. ↑ | Samples | Status |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| Depth4ToM-DPT FT Virtual Depth | official Table 2 | 1 | `layer_first` | TBD | TBD | TBD | 300 | blocked: official weight URL 403 |
| Depth4ToM-DPT FT Virtual Depth | official Table 2 | 1 + absent deeper layers | `layer_all` | TBD | TBD | TBD | 300 | blocked: official weight URL 403 |
| DPT-Large Base | official MiDaS release | 1 | `layer_first` | 77.999% | 61.888% | 56.198% | 300 | local full run |
| DPT-Large Base | official MiDaS release | 1 + absent deeper layers | `layer_all` | 44.800% | 32.754% | 29.954% | 300 | local full run |
| SeeGroup | official release | up to 4 | `layer_first` | 90.525% | 82.282% | 78.372% | 300 | local full run |
| SeeGroup | official release | up to 4 | `layer_all` | 83.161% | 75.687% | 72.411% | 300 | local full run; official-function equality verified |

附加诊断必须保存各层与 `mixed` 的 correct/count，不能只填总 accuracy。

## B. Booster train/balanced（Depth4ToM Table 2/3 protocol）

| Method/readout | Calibration | All RMSE ↓ | ToM RMSE ↓ | Other RMSE ↓ | ToM AbsRel ↓ | ToM δ1.05 ↑ | Samples | Status |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Depth4ToM-DPT FT Virtual Depth | official per-image affine in disparity | TBD | TBD | TBD | TBD | TBD | 228 | blocked: official weight URL 403 |
| DPT-Large Base | official per-image affine in disparity | 100.68 mm | 136.28 mm | 95.63 mm | 0.10 | 37.69% | 228 | local full reproduction; pass |
| MiDaS v2.1 Base | official per-image affine in disparity | 120.53 mm | 140.40 mm | 119.86 mm | 0.12 | 36.30% | 228 | local full reproduction; pass |
| SeeGroup closest valid layer | raw output directly interpreted as metric | 5759.18 mm | 3372.31 mm | 5972.56 mm | 3.7827 | 0.00018% | 228 | local full cross-protocol diagnostic |
| SeeGroup closest valid layer | same affine protocol as Depth4ToM | 95.06 mm | 65.54 mm | 98.46 mm | 0.0642 | 44.24% | 228 | local full run; wrapper calibrated against DPT official eval |

### 论文 Table 2 对照值（非本地结果）

| Method | All RMSE ↓ | ToM RMSE ↓ | Other RMSE ↓ | ToM AbsRel ↓ | ToM δ1.05 ↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| MiDaS Base | 120.51 mm | 140.31 mm | 119.86 mm | 0.12 | 36.28% |
| DPT Base | 100.68 mm | 136.28 mm | 95.63 mm | 0.10 | 37.70% |
| DPT Ft. Virtual Depth | 85.93 mm | 83.06 mm | 85.57 mm | 0.06 | 54.67% |

来源为 [ICCV 2023 论文](https://openaccess.thecvf.com/content/ICCV2023/papers/Costanzino_Learning_Depth_Estimation_for_Transparent_and_Mirror_Surfaces_ICCV_2023_paper.pdf) Table 2；这里只作为本地复现的容差参照，不能填入上方 local-reproduced 行。

## 预注册诊断

- `single-depth gap`：当前以 DPT-Large Base 的 `layer_all/quads/all` 作为 provisional 单层对照。它比 SeeGroup 低至少 5 个百分点记为强 gap；低 2–5 个百分点记为弱 gap；小于 2 个百分点不支持主张。该结果不能外推成已复现的 Depth4ToM-FT 结论。
- `single-depth bridge gap`：SeeGroup raw-metric ToM RMSE 相比其 affine-aligned RMSE 的比值至少为 1.25，说明多层结构可用但不能直接回到 metric single-depth；比值不超过 1.10 则该桥接动机弱。
- 上述阈值只作 P0 go/no-go，不写成统计显著性；正式实验仍需 bootstrap CI 或多 seed（若训练发生）。

当前 `single-depth bridge gap = 3372.31 / 65.54 ≈ 51.46×`，通过强 gap 阈值。上方四个非 FT Booster 行均来自本地 228 样本完整运行；其余 TBD 单元格仍须来自真实本地运行或在协议严格匹配时单独标注的论文值。

解释边界：SeeGroup 官方训练配置的 intensity/gradient losses 都使用 `alignment='normalization'`，因此 raw 行不是其原生 benchmark 主张，也不能写成“SeeGroup metric depth 失败”；它只衡量未经适配的输出直接进入 Booster 米制 readout 时的跨协议错位。

当前 `single-depth gap = 72.411% - 29.954% = 42.457` 个百分点，通过强 gap 阈值。尤其是 mixed-layer quadruplet：DPT Base 为 `0/195800 = 0%`，SeeGroup 为 `130397/195800 = 66.597%`，直接暴露单一 front hypothesis 无法回答跨层 tuple；这仍是 Base fallback 证据，不能冒充 Depth4ToM-FT 证据。
