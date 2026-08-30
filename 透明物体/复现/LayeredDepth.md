# LayeredDepth P0 复现记录

日期：2026-07-19

官方仓库：<https://github.com/princeton-vl/LayeredDepth>

固定 commit：`5db6cefe76fd63f04517f9476a7c42b5d9ed486f`

## 数据与协议

- Hugging Face dataset revision：`a2aad776030144950f8cbc2f12e2903b26316ff8`。
- validation：300 张，dataset bytes `4,313,552,685`。
- test：1,200 张，dataset bytes `15,151,980,964`。
- P0 只用 validation；9 个 parquet 已固定到
  `透明物体/data/layereddepth/repo/data/`，不下载 test。
- 评测分为 `layer_first` 与 `layer_all`，tuple 类型为 pair/triplet/quadruplet。

## 当前状态

- 官方代码已克隆到 `透明物体/external/layereddepth/official/`。
- conda 环境 `layereddepth` 已建立。
- 官方 `python evaluate.py --help` 已通过。
- 项目 wrapper 的 9 个 synthetic/unit tests 已通过；本轮全部相关工具集中回归为 32 tests passed。
- 已确认真实样本字段为 `__key__ / __url__ / image.png / tuples.json`，且 `tuples.json` 同时含 `layer_first` 与 `layer_all`。
- `--subset both` 已在 8 个真实样本上与两次独立 subset 运行交叉核对，24 个 metric key 及全部 correct/total 逐项相同。
- DPT-Large Base 与 SeeGroup released checkpoint 均已完成 300 张真实 validation。
- SeeGroup `layer_all` wrapper 总指标与直接调用官方 tuple 函数逐位相同；完整评测成功读取全部 300 个 NPZ。

按官方 loader 丢弃非法坐标与非 `1/3/5/7` layer label 后，完整 denominator 为：

| Subset | Pairs | Triplets | Quadruplets |
| --- | ---: | ---: | ---: |
| `layer_first` | 126,504 | 298,815 | 293,790 |
| `layer_all` | 256,109 | 610,443 | 599,143 |

## 为什么需要 protocol wrapper

当前官方 `evaluate.py` 有四个复现易错点：

1. prediction path 硬编码为作者机器路径；
2. README 用 `i_1/i_3/i_5/i_7`，代码却读 `i_0/i_1/i_2/i_3`；
3. NPY 被无条件解释成 inverse depth 并取倒数，PNG 则按毫米 depth；
4. 固定堆叠四层，无法公平表示 single-depth 方法“不存在更深层”。

项目不修改官方仓库，而使用：

```text
透明物体/复现/tools/layereddepth/evaluate_predictions.py
```

wrapper 明确：

- `--npy-space depth|inverse_depth|relative_inverse_depth`；其中最后一种只做
  保序的正比例归一化，供任意尺度的 MiDaS/DPT relative inverse depth 使用；
- `--layer-naming odd|ordinal`；
- `--prediction-format layer-files|seegroup-npz`；
- `--subset both` 可在一次 cache 读取中同时累计 `layer_first` 与 `layer_all`；
- 缺失文件/非正值表示 absent layer；
- 与官方一致地忽略 `<= 0.02 m` 的预测层；
- 保存每项 accuracy 以及 correct/total。

## 验证命令

```bash
conda run -n layereddepth python -m unittest \
  透明物体/复现/tools/layereddepth/test_evaluate_predictions.py
```

真实输出命令见 [`P0_三件套.md`](P0_三件套.md)。
