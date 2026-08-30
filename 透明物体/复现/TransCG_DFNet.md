# TransCG / DFNet 完整复现记录

更新日期：2026-08-30

## 结论

DFNet 的当前官方 release 已在 TransCG official test **23,524 / 23,524** 张上完成原生评测和独立 cache-runner 交叉核验。它可以作为我们的 RGB-D single-depth completion baseline，但不能写成“论文旧 checkpoint 的逐项复现”：官方 README 明确说明当前发布权重与 paper checkpoint 不同。

## 数据与版本

| 项目 | 值 |
| --- | --- |
| 数据 | TransCG official test，52 scenes，23,524 samples |
| official commit | `135f9e0ad20592cb40b288c152aff5eda033a765` |
| checkpoint epoch | 12 |
| checkpoint SHA-256 | `7d706a0b3ecf94e086e46abc9e640858790bb680f8994ad6c564f7e9c4ad83fe` |
| 输入 | RGB + raw RGB-D depth |
| 网络分辨率 | 320 × 240 |
| 输出 | metric depth，m |

13 个数据分块均已下载、解压并通过样本结构审计；早期 Google Drive quota blocker 已解除。

## 当前官方 release 的完整结果

以下数字来自上游未改动的 `test.py` 原生入口：

| 指标 | all | transparent mask |
| --- | ---: | ---: |
| RMSE ↓ | 0.018456 m | 0.032787 m |
| REL ↓ | 0.020245 | 0.057680 |
| MAE ↓ | 0.009905 m | 0.025963 m |
| δ1.05 ↑ | 89.8767% | 63.2562% |
| δ1.10 ↑ | 95.2869% | 80.4670% |
| δ1.25 ↑ | 99.2927% | 97.7137% |

作为必要输入对照，同一官方预处理后的 identity raw depth 为：

| 指标 | all | transparent mask |
| --- | ---: | ---: |
| RMSE ↓ | 0.020116 m | 0.045293 m |
| REL ↓ | 0.015600 | 0.076890 |
| MAE ↓ | 0.007023 m | 0.034920 m |
| δ1.05 ↑ | 90.3389% | 52.1190% |

因此当前 DFNet 相对其实际输入，将 masked RMSE 从 45.293 mm 降到 32.787 mm；这比单看模型分数更能确认模型确实在透明区域产生了有效修复。

## 独立交叉核验

cache runner 保存了 23,524 张逐帧 metric-depth prediction，再与原生入口汇总值比较：

- sample 数一致；
- RMSE 绝对差约 `2.96e-6 m`；
- 最大差为 masked δ1.05 的 `0.0031` 个百分点；
- 在冻结容差内判定 `PASS`。

差异来自原生 loader shuffle 后浮点累加顺序不同，不改变结论。

## 执行入口

```bash
# cache + per-frame predictions
CUDA_VISIBLE_DEVICES=0 conda run -n transparent-baselines-gpu python \
  透明物体/复现/tools/transcg/run_dfnet_full.py \
  --official-root 透明物体/external/transcg/official \
  --dataset-root 透明物体/data/transcg/transcg \
  --checkpoint-path 透明物体/weights/transcg/checkpoint.tar \
  --output-dir 透明物体/runs/transcg/dfnet_release_test

# upstream native test.py cross-check
CUDA_VISIBLE_DEVICES=0 conda run -n transparent-baselines-gpu bash \
  透明物体/复现/tools/transcg/run_dfnet_native_full.sh \
  透明物体/external/transcg/official \
  透明物体/data/transcg/transcg \
  透明物体/weights/transcg/checkpoint.tar
```

逐帧预测约 7.2 GB，位于 `runs/transcg/dfnet_release_test/predictions_m`，由 Git 忽略。结果归属与其他 baseline 的横向边界见 [复现进度总览（2026-08-30）](复现进度总览_2026-08-30.md)。
