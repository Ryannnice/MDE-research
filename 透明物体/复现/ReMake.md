# ReMake 完整复现记录

更新日期：2026-08-30

## 结论

ReMake 的公开 Global Loss checkpoint 已在 TransCG official test **23,524 / 23,524** 张上完成两条独立全量路径。masked RMSE、REL、MAE 和五个 δ 指标均在论文 Table I 的报告精度内一致，因此这条可以正式称为论文 baseline 复现。

## 数据、模型与版本

| 项目 | 值 |
| --- | --- |
| 数据 | TransCG official test，52 scenes，23,524 samples |
| official commit | `4f568148c8421544136bf49bb941149e0c990a34` |
| ReMake checkpoint | epoch 39，Global Loss |
| ReMake checkpoint SHA-256 | `2e84c0474f9c6314aa910a507228dbe4dd3972e8d840dfab0c8deb32e2973d82` |
| MDE backbone | Depth Anything V2 VITS |
| MDE weight SHA-256 | `715fade13be8f229f8a70cc02066f656f2423a59effd0579197bbf57860e1378` |
| 输入 | RGB + raw depth + relative depth + transparent mask |
| 输出 | metric depth，m |

## 完整结果与论文对照

| 指标 | 本地 all | 本地 transparent mask | 论文 Table I Global Loss |
| --- | ---: | ---: | ---: |
| RMSE ↓ | 0.008392 m | **0.010854 m** | 0.011 m |
| REL ↓ | 0.007345 | **0.016906** | 0.017 |
| MAE ↓ | 0.004618 m | **0.007532 m** | 0.008 m |
| δ1.01 ↑ | 79.7857% | **47.3405%** | 47.35% |
| δ1.03 ↑ | 96.7731% | **85.1136%** | 85.12% |
| δ1.05 ↑ | 98.6712% | **93.9086%** | 93.91% |
| δ1.10 ↑ | 99.7006% | **98.6707%** | 98.67% |
| δ1.25 ↑ | 99.9906% | **99.9714%** | 99.97% |

论文主要报告 transparent-mask 行；all 行是我们为统一审计同时保留的结果。这里的“一致”指在论文有限小数位精度内一致，不是声称底层浮点逐 bit 相同。

## 两条执行路径

1. cache runner：调用官方 dataset、Depth Anything V2、ReMake checkpoint、trainer 与 metric recorder，并保存 23,524 张逐帧 metric-depth prediction。
2. upstream native：保持 `main.py --mode test` 和所有模型/数据语义不变，只将 `num_workers` 从 10 降到 2，以适配本机 4 GiB `/dev/shm`。

二者交叉核验：

- sample 数均为 23,524；
- RMSE、REL、MAE 差异约 `1e-6` 或更小；
- 最大差为 masked δ1.01 的 `0.00435` 个百分点；
- 冻结容差 `0.005` 内 `PASS`。

## 执行入口

```bash
# cache + per-frame predictions
CUDA_VISIBLE_DEVICES=0 conda run -n transparent-baselines-gpu python \
  透明物体/复现/tools/remake/run_remake_full.py \
  --official-root 透明物体/external/remake/official \
  --dataset-root 透明物体/data/transcg/transcg \
  --checkpoint-path 透明物体/weights/remake/checkpoint.tar \
  --relative-depth-weights \
    透明物体/weights/depth-anything-v2/depth_anything_v2_vits.pth \
  --output-dir 透明物体/runs/remake/release_test

# upstream native main.py cross-check
CUDA_VISIBLE_DEVICES=0 conda run -n transparent-baselines-gpu bash \
  透明物体/复现/tools/remake/run_remake_native_full.sh \
  透明物体/external/remake/official \
  透明物体/data/transcg/transcg \
  透明物体/weights/remake/checkpoint.tar \
  透明物体/weights/depth-anything-v2/depth_anything_v2_vits.pth \
  native-full
```

逐帧预测约 28 GB，位于 `runs/remake/release_test/predictions_m`，由 Git 忽略。它是强 single-depth baseline；后续必须在同一 ShellBench 读出下与 multi-interface 方法比较，不能直接拿 TransCG RMSE 与 shell F1 排名。完整边界见 [复现进度总览（2026-08-30）](复现进度总览_2026-08-30.md)。
