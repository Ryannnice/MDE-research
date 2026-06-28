# MDE

单目深度估计科研工作区。当前按“代码、选题、文献、论文 PDF”四类资产组织。

## 当前入口

| 路径 | 作用 |
|---|---|
| [`docs/00_A2.md`](docs/00_A2.md) | A2/I1 当前执行入口:短说明、Gate 和命令 |
| [`a2/`](a2/) | A2 实验代码和依赖 |
| [`docs/目录.md`](docs/目录.md) | 文档总入口 |
| [`docs/选题/01_代理锚定CCF近单步米制扩散深度.md`](docs/选题/01_代理锚定CCF近单步米制扩散深度.md) | I1/A2 主攻立项卡 |
| [`docs/选题/02_几何世界模型标定信念图.md`](docs/选题/02_几何世界模型标定信念图.md) | I2 新主攻候选 |
| [`docs/文献调研/前沿专题/00_前沿专题索引.md`](docs/文献调研/前沿专题/00_前沿专题索引.md) | 文献调研前沿专题入口 |
| [`tools/`](tools/) | 辅助脚本 |

## 项目结构

```text
a2/                 A2 代码和 requirements
docs/
  00_A2.md          A2 兼容执行入口
  目录.md           文档总入口
  选题/             当前 idea、实验路线、归档旧选题
  文献调研/         综述基础、前沿专题、历史长文归档
papers/             PDF,按单目深度三幕归档
tools/              下载/整理辅助脚本
```

## 常用命令

```bash
cd a2
for f in A2_ccf_depth_skeleton A2_geo_anchor A2_eval_protocol \
         A2_baselines_postproc A2_diag_bias_var A2_marigold_bridge \
         A2_failure_slices A2_run_grid; do
  python "$f.py" || exit 1
done
```

依赖:

```bash
cd a2
pip install -r requirements.txt
```

真实实验输出写到项目根目录的 `runs/`，真实数据放 `data/`。这些目录已被 `.gitignore` 忽略。
