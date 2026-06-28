# CLAUDE.md

## 仓库性质

这是单目深度估计科研工作区。当前活跃主线只有 **A2: 免训练 1-2 步扩散米制深度**。新增研究文档默认用简体中文。

## 当前入口

- `docs/00_A2.md`: 当前主线短说明。
- `a2/`: 当前实验代码。
- `docs/目录.md`: 文档总入口。
- `docs/选题/01_代理锚定CCF近单步米制扩散深度.md`: I1/A2 主攻立项卡。
- `docs/选题/02_几何世界模型标定信念图.md`: I2 新主攻候选。
- `docs/文献调研/前沿专题/00_前沿专题索引.md`: 文献调研前沿专题入口。
- `papers/`: 论文 PDF 归档目录,按 G1 三幕组织。

## 命令

```bash
cd a2
python A2_ccf_depth_skeleton.py
python A2_run_grid.py --phase L1 --mock
```

改动 A2 代码后重跑:

```bash
cd a2
for f in A2_ccf_depth_skeleton A2_geo_anchor A2_eval_protocol \
         A2_baselines_postproc A2_diag_bias_var A2_marigold_bridge \
         A2_failure_slices A2_run_grid; do
  python "$f.py" || exit 1
done
```

## 研究约束

- 不伪造实验结果;真实数字必须来自 `runs/*.csv`。
- A2 claim 只能围绕 L0/L1/L2/diag gates 展开。
- 必须区分 metric 协议与 affine-invariant 协议。
- 必须区分 `nfe` 与 `nfe_real`。
- 不接受需要用户本人自采双目/LiDAR/事件相机数据的 idea;公开数据集可以。

## 文献归档

`papers/` 按 G1 三幕归档:专用任务时代、基础模型时代、几何/世界模型时代。A2 相关论文在 `papers/G1_03_几何世界模型时代_2024-2026_前馈可微生成式几何FM_4D几何导出量/01_免训练近单步扩散深度_A2威胁与基线/`。下载工具是 `tools/rec.py`。
