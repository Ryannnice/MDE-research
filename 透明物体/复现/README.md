# 透明物体复现入口

## 当前项目关系

总项目主线已统一为 [Shell-Aware Multi-Layer Transparent Grasping](../Shell-Aware-Multi-Layer-Transparent-Grasping-Idea-v2.md)，实验总控见 [统一实验设计](../Shell-Aware-Multi-Layer-Transparent-Grasping-Experiment-v1.md)。

本目录原有的 DepthHypothesisPack P0 现在是**支撑感知线**：它验证单层 / 多层透明深度协议并提供 LayeredDepth、SeeGroup、Depth4ToM 工具资产，但不再单独定义总项目的 idea。

当前主项目的 G0 是：

```text
GT / mesh 薄壳可行性审计
→ ReMake / T²SQNet / Trans2Occ 等表示的 shell-failure diagnostic
→ 几何错误与固定 planner 失败的对应关系
→ go / no-go
```

## 支撑感知线：DepthHypothesisPack P0

- 总控与验收：[`P0_三件套.md`](P0_三件套.md)
- 预注册 gap table：[`P0_gap_table.md`](P0_gap_table.md)
- 单项记录：[`Depth4ToM.md`](Depth4ToM.md)、[`LayeredDepth.md`](LayeredDepth.md)、[`SeeGroup.md`](SeeGroup.md)
- 环境：[`environments/`](environments/)
- 跨协议工具：[`tools/depth4tom/`](tools/depth4tom/)、[`tools/layereddepth/`](tools/layereddepth/)、[`tools/seegroup/`](tools/seegroup/)

该支线的顺序仍为：官方基线复现 → 两个 gap diagnostics → 支撑线 go/no-go。主项目 G0 之前不实现新的完整 shell head。

2026-07-19 状态：公开 Base 路线已完成全量复现；支撑线 `G1 strong PASS`。Depth4ToM FT 权重仍是明确的上游 artifact blocker，Base 结果不得改名为 FT 结果。总项目仍受 shell GT / grasp-failure 主 G0 约束。

## 当前 shell G0 的已有 smoke 资产

- [`TransCG_DFNet.md`](TransCG_DFNet.md)
- [`ReMake.md`](ReMake.md)

注意：

- TransCG 当前只有 synthetic smoke，真实数据与 mesh 薄壳字段尚未审计；
- ReMake 当前只有 synthetic relative-depth smoke，尚未得到完整真实 baseline 结果；
- 以上记录不能写成已证明 single-depth 会导致实心化，也不能写成机器人提升。
