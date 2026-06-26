# MDE

单目深度估计科研工作区。当前只保留一个活跃主线:

- **A2**:免训练 1-2 步扩散米制深度。

## 入口

| 路径 | 作用 |
|---|---|
| [`docs/A2.md`](docs/A2.md) | 当前主线的短说明、判据和命令 |
| [`a2/`](a2/) | A2 实验代码和依赖 |
| [`docs/archive/`](docs/archive/) | 旧长文、调研、完整实验方案归档 |
| [`papers/`](papers/) | 论文 PDF |
| [`tools/`](tools/) | 辅助脚本 |

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
