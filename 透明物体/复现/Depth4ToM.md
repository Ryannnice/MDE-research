# Depth4ToM P0 复现记录

日期：2026-07-19

官方仓库：<https://github.com/CVLAB-Unibo/Depth4ToM-code>

固定 commit：`5de0f869d66edc48b79d2f9f197756e71b342f9a`

## 当前状态

- 官方代码已克隆到 `透明物体/external/depth4tom/official/`。
- `run.py`、`evaluate_mono.py`、`scripts/table2.sh`、`scripts/table3.sh` 已核验。
- 独立 conda 环境 `depth4tom` 已完成，实测为 Python 3.10.20、PyTorch 2.8.0+cu128。
- 官方 pretrained weights 与 Trans10K/MSD virtual-depth data 的 OneDrive 短链均在 2026-07-19 返回 HTTP 403。
- 用户侧也无法取得微调权重，因此当前不能声称 Table 2/3 的 FT 行已复现。经用户确认，P0 改为先复现 Table 2 的 MiDaS/DPT Base 行，并用 DPT-Large Base 做 LayeredDepth 单深度诊断。
- `dpt_large-base.pt`：1,376,378,527 bytes，SHA-256 `2f21e586477d90cb9624c7eef5df7891edca49a1c4795ee2cb631fd4daa6ca69`。
- `midas_v21-base.pt`：422,509,849 bytes，SHA-256 `f6b980704cfd7259c7cc2b058c2f160159c55e84b3b6c08331b4156a84629f70`。
- 两个本地文件大小与 MiDaS 官方 GitHub release assets 一致。
- Booster 官方 `booster_gt.zip` 已完整下载并通过 ZIP CRC：
  - bytes：`19,262,416,889`；
  - entries：`2,538`；
  - local SHA-256：`d7ffc44623f5279d9ff7435765399019bcf9054b505ec374742d82327415b50e`。
- 解包后的 `train/balanced` 为 8.3 GB；官方 `train_stereo.txt` 的 228 个样本已逐项核对 RGB、GT disparity、类别 mask 和 calibration，缺失数为 0。
- 两个 Base 模型均已用官方 `run.py` + `evaluate_mono.py` 完成 228/228 全量复现：

| Model | Source | All RMSE | ToM RMSE | Other RMSE | ToM δ1.05 |
| --- | --- | ---: | ---: | ---: | ---: |
| MiDaS v2.1 Base | local | 120.53 mm | 140.40 mm | 119.86 mm | 36.30% |
| MiDaS v2.1 Base | paper Table 2 | 120.51 mm | 140.31 mm | 119.86 mm | 36.28% |
| DPT-Large Base | local | 100.68 mm | 136.28 mm | 95.63 mm | 37.69% |
| DPT-Large Base | paper Table 2 | 100.68 mm | 136.28 mm | 95.63 mm | 37.70% |

最大 RMSE 偏差为 0.09 mm，两个模型均通过预注册容差。原始结果位于 `透明物体/runs/depth4tom/table2_base/metrics/`，完整 stdout 位于同级 `logs/`；`runs/` 不入库。
项目独立 `evaluate_booster.py` 又重算了两组 228 张预测；All/ToM/Other 的像素数、全部未四舍五入指标与官方 evaluator 一致，产物为同目录的 `midas_v21.json` 和 `dpt_large.json`。

## 官方脚本的真实协议

`scripts/table2.sh` 和 `scripts/table3.sh` 都假设从 `scripts/` 目录执行，因为第一行是 `cd ..`；同时把 Booster 写死为：

```text
/media/data2/Booster/train/balanced
```

数据清单是 `datasets/booster/train_stereo.txt`，共 228 个 RGB 样本。

`evaluate_mono.py` 并非直接比较 raw metric prediction。它会：

1. 把 prediction 归一化；
2. 对每张图用 GT disparity 做 scale-and-shift；
3. 再由 focal/baseline 转成 depth；
4. 报 `All / ToM / Other` 的 delta、MAE、AbsRel、RMSE。

所以复现记录必须把该表称为 `per-image affine-aligned disparity protocol`，不能和 raw metric 输出混写。

另一个需逐字复刻的实现细节：上游把 `cv2.INTER_CUBIC` 放在 `cv2.resize` 的第三个位置参数；该位置在 Python binding 中是 `dst`，实际插值仍为默认 bilinear。本项目 wrapper 显式使用 `INTER_LINEAR` 来匹配实际输出，而不是匹配作者可能的文字意图。

## 已发现的代码约束

- 官方 `requirements.txt` 的 `opencv==4.7.0` 不是标准 PyPI 包名；环境中改用 `opencv-python==4.7.0.72`。
- 官方 PyTorch 1.13.1 + CUDA 11.6 不支持本机 RTX 5090；P0 使用 PyTorch 2.8.0 + CUDA 12.8，并保留旧依赖差异。
- `run.run(...)` 内部读取全局 `args.it`，不是函数参数 `it`；直接 CLI 不受影响，作为库调用时需绕开。
- 输出 `.npy` 是 relative inverse depth。进入 LayeredDepth 时必须显式使用
  `--npy-space relative_inverse_depth`：wrapper 只把每张图的最大正 inverse
  depth 缩放到 1，保持全部远近排序不变，同时避免 MiDaS/DPT 的任意输出
  单位与 LayeredDepth 官方 `0.02 m` 有效阈值发生偶然耦合。

## LayeredDepth adapter

项目脚本：

```text
透明物体/复现/tools/depth4tom/predict_layereddepth.py
```

它按 `<sample_id>_1.npy` 保存唯一的 inverse-depth hypothesis，不伪造 layer 3/5/7。

## Base fallback

Booster Table 2 的两个 Base 模型可用下列封装一次跑完；它调用的仍是官方 `run.py` 与 `evaluate_mono.py`，只跳过拿不到权重的 FT 行：

```bash
conda run --no-capture-output -n depth4tom bash \
  透明物体/复现/tools/depth4tom/run_table2_base.sh \
  透明物体/data/booster/train/balanced
```

Base 复现验收在看本地结果前冻结为：相对论文 Table 2，`All/ToM/Other RMSE` 的绝对差均不超过 1.0 mm，且对应 `δ1.05` 的绝对差不超过 0.5 个百分点。超出时先排查 PyTorch/OpenCV 版本、resize 与 checkpoint，而不把“能跑完”算作复现成功。

LayeredDepth validation 预测：

```bash
HF_HOME=透明物体/data/hf-cache \
CUDA_VISIBLE_DEVICES=0 \
conda run -n depth4tom python \
  透明物体/复现/tools/depth4tom/predict_layereddepth.py \
  --official-root 透明物体/external/depth4tom/official \
  --checkpoint-path 透明物体/weights/depth4tom/Base/dpt_large-base.pt \
  --model-type dpt_large \
  --output-dir 透明物体/runs/depth4tom/dpt_large_base/layereddepth \
  --cache-dir 透明物体/data/hf-cache \
  --local-validation-dir \
    透明物体/data/layereddepth/repo/data
```

该输出必须标为 `DPT-Large Base`，不能标为 `Depth4ToM`。

300 张 validation 的本地完整结果：

| Model | Subset | Pair acc. | Triplet acc. | Quadruplet acc. |
| --- | --- | ---: | ---: | ---: |
| DPT-Large Base | `layer_first` | 77.999% | 61.888% | 56.198% |
| DPT-Large Base | `layer_all` | 44.800% | 32.754% | 29.954% |
| MiDaS v2.1 Base | `layer_first` | 81.541% | 69.379% | 66.166% |
| MiDaS v2.1 Base | `layer_all` | 46.581% | 36.421% | 34.842% |

两个模型的 `layer_all` mixed-layer tuple 均为 0%，符合“只提供 layer 1、
其余层明确 absent”的协议合同。正式结果分别保存在
`runs/depth4tom/layereddepth_validation_base_{dpt,midas}/evaluation_both.json`。

## 微调权重阻塞解除后的命令

```bash
cd 透明物体/external/depth4tom/official/scripts
bash table2.sh
bash table3.sh
```

运行前必须：

1. 把 `dataset_root` 改为项目内 Booster `train/balanced`；
2. 把官方权重解压为 README 指定的目录层级；
3. 保存原始 stdout、结果 txt、环境 lock 和 checkpoint SHA-256。
