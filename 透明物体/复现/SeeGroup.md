# SeeGroup P0 复现记录

日期：2026-07-19

官方仓库：<https://github.com/princeton-vl/SeeGroup>

论文：<https://arxiv.org/abs/2605.28735>

固定 commit：`765cbe45f218553a146f8f887c09310c1e96998e`

## 当前状态

- 官方代码已克隆到 `透明物体/external/seegroup/official/`。
- conda 环境 `seegroup` 已完成，实测为 Python 3.10.20、PyTorch 2.8.0+cu128。
- 官方 checkpoint 已下载到 `透明物体/weights/seegroup/seegroup.pth`。
- checkpoint bytes：`4,266,170,584`。
- SHA-256：`c21ccdd1595fbf7bbf6045c5825314cae5d302ad95a9f862c1088bbc4d7b9c77`，与 Hugging Face `x-linked-etag` 一致。
- 官方 `val.py` 的 1 样本与 8 样本端到端 validation 已通过；两者只作为升级门，不写进最终 gap table。
- 300 样本 teacher cache 已完整生成：300 个可读取 NPZ、300 个唯一样本 id，平均有效像素比例为 `99.569%`，最小值为 `85.387%`。最终 `--cache-only` canonical 重算覆盖 300/300 张，全部 NPZ 解压可读且标记 `reused=true`。
- cache 重算直接调用官方 `layereddepth_tuple_correct`，`layer_all` 为 pair `83.159%`、triplet `75.688%`、quadruplet `72.414%`；项目统一评测器的三项浮点值与官方函数结果精确相等。分片运行的临时 metrics 不作为最终汇总。

曾在查看 300 样本结果前把 README 的 `70.09%` 预注册为 validation quadruplet 参照；核对论文后确认该数值来自 **test split**（Table 1），因此该验收参照在用于 G1 判断前撤回，不能拿它和本地 validation 直接比较。论文 Table 2 的 validation 架构消融报告 RD (Ours) 为 pair/triplet/quadruplet `83.21/76.54/71.50%`，但它仍不替代 release checkpoint 的直接复现。最终验收采用与 `val.py` 相同的模型入口和官方 tuple 函数，同时缓存输出；并要求统一 evaluator 的总指标逐位相同、manifest 恰为 300 且每个 NPZ 可完整读取。

| Subset | Pair acc. | Triplet acc. | Quadruplet acc. |
| --- | ---: | ---: | ---: |
| `layer_first` | 90.525% | 82.282% | 78.372% |
| `layer_all` | 83.159% | 75.688% | 72.414% |

## 官方 validation 路径

```bash
python val.py --checkpoint-path checkpoints/seegroup.pth
```

当前 release 额外支持：

- `--max-samples`：适合 1/8 样本 smoke；
- `--num-workers`；
- Hugging Face validation streaming；
- `layer_all` tuple evaluation。

执行采用 1 → 8 → 300 样本三级验收，命令见 [`P0_三件套.md`](P0_三件套.md)。

## Teacher cache

项目脚本：

```text
透明物体/复现/tools/seegroup/cache_validation.py
```

每个 validation 样本保存：

```text
layers_m: float32 [4,H,W]  # 历史字段名；raw depth heads，未做跨数据集米制标定
valid_mask: bool [4,H,W]
beta: float32 [4,H,W]
layer_labels: [1,3,5,7]
```

层按有效 depth head 从近到远排序；无效层保存为 0，并用 `valid_mask`
区分。LayeredDepth tuple 只使用层的远近次序；不把这些值额外声称为跨数据集
已标定的 metric depth。缓存目录 `透明物体/teacher/` 已忽略入库。
最终产物位于 `透明物体/teacher/seegroup/layereddepth/validation/`；manifest、官方函数 metrics、统一 evaluator 的 SHA-256 依次为 `2d7876cf…`、`2d0992ed…`、`ca4c4f64…`。

缓存脚本同时按官方 `layer_all` tuple 函数累计指标，并支持复用已存在的有效
`.npz`，因此长任务中断后不会重复推理已经缓存的样本。新写入使用临时文件
原子替换；已有 NPZ 若不可读则自动重算。`--start-index` 与 `--max-samples`
可把 300 张 validation 切成互不重叠的多 GPU 分片；分片完成后使用
`--cache-only` 严格要求 300 个缓存全部可读，并统一重算官方指标与 manifest。

## Booster closest-layer bridge

按与 LayeredDepth evaluator 相同的规则，在每个像素将有效 SeeGroup heads 按深度排序并取最近层，228 张完整结果为：

| Calibration | All RMSE | ToM RMSE | Other RMSE | ToM AbsRel | ToM δ1.05 |
| --- | ---: | ---: | ---: | ---: | ---: |
| raw output directly interpreted as metric | 5759.18 mm | 3372.31 mm | 5972.56 mm | 3.7827 | 0.00018% |
| Booster per-image affine in disparity | 95.06 mm | 65.54 mm | 98.46 mm | 0.0642 | 44.24% |

ToM RMSE 比值约为 `51.46×`，显著超过预注册 `1.25×` bridge-gap 阈值。affine wrapper 已用 DPT-Large Base 的 228 张预测校准，三类 RMSE 四舍五入后与官方 `evaluate_mono.py` 完全一致。原始输出在 `透明物体/runs/seegroup/booster_{raw,affine}.json`，SHA-256 为 `9eca24c2…` 与 `3a1152cc…`；228 张预测的严格汇总 manifest 为 `86e8dddf…`。

SeeGroup 官方训练配置的 intensity 与 gradient losses 都使用 `alignment='normalization'`；因此 raw 行是“把未校准数值强行按米读取”的跨协议诊断，不是 SeeGroup 原生任务的 metric-depth claim。它支持的是“需要显式 bridge/calibration”，而不是“SeeGroup 本身失效”。

预测命令：

```bash
CUDA_VISIBLE_DEVICES=0 conda run --no-capture-output -n seegroup python \
  透明物体/复现/tools/seegroup/predict_booster.py \
  --official-root 透明物体/external/seegroup/official \
  --checkpoint-path 透明物体/weights/seegroup/seegroup.pth \
  --input-root 透明物体/data/booster/train/balanced \
  --dataset-txt 透明物体/external/depth4tom/official/datasets/booster/train_stereo.txt \
  --output-dir 透明物体/runs/seegroup/booster_closest_layer
```

正式运行可用 `--start-index` / `--max-samples` 分片到多张 GPU；全部 NPY
完成后再用 `--cache-only` 做 228/228 严格汇总。分片只改变调度，不改变模型、
closest-layer readout 或评测协议。

评测时使用 `透明物体/复现/tools/depth4tom/evaluate_booster.py`，分别指定 `--prediction-space depth --alignment none` 与 `--prediction-space depth --alignment least_squares`。
