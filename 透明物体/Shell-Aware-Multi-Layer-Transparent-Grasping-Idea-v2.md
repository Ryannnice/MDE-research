# Shell-Aware Multi-Layer Transparent Grasping：统一 Idea v2

日期：2026-07-19
状态：**当前主版本 / single source of truth**
中文名：面向多层透明薄壳几何的机器人抓取
工作简称：`SMTG`
表示名：`LayeredShellGeometry`

> 本文已吸收并取代此前的 Layer-Aware ToM 与 Thin-Shell 历史草稿。实验细节以 `Shell-Aware-Multi-Layer-Transparent-Grasping-Experiment-v1.md` 为准。

## 0. 当前结论

这个方向值得继续，但原始说法需要做一处关键修正：

- **不能说**“多层透明物体抓取是空白”。T²SQNet 已研究透明餐具的识别与操作，ASGrasp 已把两层透明重建接到 6-DoF 抓取，Trans2Occ 也已从单图预测透明物体占据并执行抓取。
- **可以研究的明确缺口**是：现有方法通常以单张 completed depth、普通点云、低维完整形状、两层重建或体素占据作为机器人几何；尚未形成一个统一的、面向接触与碰撞的表示，显式区分物理外壁、内壁、rim、开口、壁厚、腔体自由空间及其不确定性，并验证这些薄壳量是否真正决定抓取成败。

因此，主线不是“再补一张更好看的透明深度图”，也不是“透明餐具抓取首次被提出”，而是：

> **把透明空心物体的多界面薄壳几何定义成独立的抓取表示、评测协议与可证伪的机器人证据链。**

当前 novelty 状态：`grounded-but-not-proven`。相关工作边界已完成第一轮检索；是否足以形成论文贡献，必须通过 G0 失败诊断和 GT 可行性验证。

## 1. 一句话 Idea

透明杯、瓶、碗、试管和酒杯不是实心透明块。我们从单视角 RGB-D 与实例 mask 中恢复带界面语义和不确定性的有序多层薄壳几何，包括外壁、内壁、rim、开口、壁厚与腔体自由空间，再让抓取器显式选择可接触表面并避开错误侧、空腔和碰撞风险。

英文工作版：

> Transparent hollow objects should be represented as uncertain, ordered physical interfaces rather than a single completed surface. We recover grasp-relevant layered shell geometry and test whether explicit outer/inner surfaces, rims, thickness, and cavity free space improve contact safety under a fixed grasping pipeline.

## 2. 研究问题

### 2.1 任务输入

第一版采用与 ReMake 尽量接近、部署成本较低的输入：

```text
RGB image
+ raw RGB-D depth
+ transparent-object instance mask
+ optional frozen monocular relative-depth prior
```

mask 是显式外部条件，不暗示免费获得；实验必须报告 GT mask、预测 mask 和扰动 mask。

ASGrasp 的主动双目、GraspNeRF / Dex-NeRF 的多视角信息作为更强传感器上界，不与单视角主表混排。

### 2.2 任务输出

对每条相机射线 \(r\)，输出可变数量的物理界面事件：

\[
\mathcal{I}(r)=\{(z_k,\tau_k,p_k,\sigma_k)\}_{k=1}^{K_r},\qquad
z_1<z_2<\cdots<z_{K_r}.
\]

其中：

- \(z_k\)：第 \(k\) 个界面的米制深度；
- \(\tau_k\)：界面转移语义，例如 `air→shell`、`shell→cavity/liquid`、`cavity/liquid→shell`、`shell→air`；
- \(p_k\)：该界面存在的概率；
- \(\sigma_k\)：深度或界面类型的不确定性。

一条穿过透明杯壁的光线不一定只有“两层”，可能依次遇到：

```text
front outer wall
→ front inner wall
→ back inner wall
→ back outer wall
→ background
```

因此，`D_outer + D_inner` 只能作为消融，不能作为完整表示。

### 2.3 LayeredShellGeometry

由多界面事件进一步构造：

```text
LayeredShellGeometry = {
  ordered_interface_events,
  outer_surface / inner_surface,
  shell_occupancy_intervals,
  cavity_free_space,
  rim_and_opening_boundary,
  surface_normals,
  local_wall_thickness,
  contact_affordance,
  collision_and_uncertainty_risk
}
```

关键定义：

- **外壁 / 内壁**是物理材料边界，不等同于“第一层 / 第二层”；
- **壁厚**沿局部表面法向估计，不能直接用两张相机深度图相减；
- **腔体**是需要保留的自由空间，不是应被 completion 填满的缺失区域；
- **rim / 开口**是壳体拓扑终止的位置，也是夹爪接触、插入和碰撞判断的高敏感区域；
- **不确定性**用于拒抓或触发额外观测，避免把不可辨识的后壁当作确定事实。

## 3. 为什么现有输出不够

### 3.1 单张 completed depth

单深度只能为每个像素选择一个表面。它适合恢复可见接触面，但无法同时保留内外壁、后壁和腔体。ReMake 的论文也观察到生成式补全容易生成闭合表面，并可能把 beaker 一类内部空心结构重建成实心。

### 3.2 普通单点云

单点云可包含可见表面，却通常没有明确的内外配对、界面转移、开口拓扑和壁厚语义。几何看似完整，不代表夹爪知道哪一侧可接触、哪一区域必须保持为空。

### 3.3 低维完整形状或体素占据

T²SQNet 的低维超二次曲面和 Trans2Occ 的体素占据都可能为抓取提供有效的完整形状先验；它们是必须正面对比的强近邻。但本课题关心的是更细粒度的问题：物理薄壳的内外界面是否被正确配对，rim 与腔体是否被保留，壁厚和接触风险是否可度量。

### 3.4 多层深度

LayeredDepth、SeeGroup、MDA 和 DepthFocus 已证明多层或多假设深度本身不是空白。仅把输出改成 \(K\) 张深度图不构成足够贡献；必须增加：

- 界面物理语义；
- 薄壳拓扑约束；
- 壁厚、rim 与腔体推导；
- 与真实抓取错误的因果证据。

## 4. 核心假设与可证伪 Claims

### H1：表示缺口

在空心透明物体上，单 completed depth、粗粒度完整形状或无语义多层深度会系统性丢失至少一种抓取关键薄壳量；该误差与碰撞、空抓、错误侧接触或滑移相关。

**证伪方式**：若 ReMake、T²SQNet 或 Trans2Occ 已能稳定恢复足够的 rim、腔体和接触面，并且薄壳误差与抓取失败无关联，则不应继续提出新模型。

### H2：几何贡献

在相同输入、训练数据和计算预算下，显式的界面语义与薄壳拓扑约束比单深度、固定双层或无序 \(K\) 层表示更准确地恢复外/内壁、rim、壁厚和腔体自由空间。

**证伪方式**：若简单双层或通用多层表示在薄壳指标上等价，则把贡献收缩为评测协议，或停止方法线。

### H3：机器人价值

在固定抓取候选生成器、碰撞检测器和执行硬件下，仅替换几何表示，`LayeredShellGeometry` 能减少因壳体误建模产生的失败，并改善安全抓取表现。

**证伪方式**：若离线几何更好但固定规划器下抓取结果无改善，则不能宣称机器人贡献。

## 5. 方法蓝图

### 5.1 多模态编码

编码 RGB、原始深度、mask 与可选 MDE 相对深度。原始传感器缺失值和有效值要分开编码，避免网络把零深度当几何。

第一版不训练新的大视觉 backbone，优先复用可复现的 RGB-D / MDE 特征，控制贡献范围和训练成本。

### 5.2 多界面事件头

每条射线预测最多 \(K_{\max}\) 个候选事件，包括：

- depth；
- presence；
- interface-transition class；
- uncertainty；
- optional surface normal。

固定两层、无序点集和有序带语义事件分别作为嵌套消融。\(K_{\max}\) 由数据中界面计数分布决定，不预设“所有杯子都是四层”。

### 5.3 薄壳拓扑与物理约束

候选约束包括：

- 深度次序一致；
- 材料进入 / 离开转移语法一致；
- shell interval 为正；
- 相邻外/内界面可形成局部薄壳配对；
- rim 处允许壳体终止，非 rim 区域避免无解释断裂；
- cavity 区域保持为空；
- 局部厚度与法向平滑，但允许真实突变；
- 低置信界面不被强制闭合。

这些是可检验的归纳偏置，不应被写成硬编码“真实物理完全正确”。

### 5.4 三维提升

将事件提升为带语义的 surfel / mesh / sparse volume，计算：

- 外、内接触面；
- rim 与 opening pose；
- 沿法向的局部厚度；
- 壳体占据和腔体自由空间；
- 几何置信区间。

实现形式在 G0 后确定；首版优先选择可被现有 6-DoF 抓取器和碰撞检测器直接消费的表示。

### 5.5 抓取读出

两阶段证据优先：

1. **固定规划器实验**：只替换几何，验证表示本身是否减少失败；
2. **联合 shell-aware readout**：在固定证据成立后，再加入 outer/inner/rim 接触标签、风险评分和拒抓。

这样可分清“几何恢复有效”与“更大 grasp network 带来收益”。

## 6. 与最近工作的边界

| 工作 | 已覆盖 | 本课题不能再声称 | 仍需验证的差异 |
|---|---|---|---|
| ClearGrasp / LIDF / TransCG / ReMake | RGB-D 透明深度恢复、点云/抓取 | 透明深度补全或透明抓取首次提出 | 单表面补全是否破坏空心壳体、薄壳指标是否预测失败 |
| T²SQNet | 部分 RGB 观测下的透明餐具低维完整形状与操作 | 透明杯碗酒杯操作是空白 | 显式内外界面、rim、壁厚、腔体评测是否带来额外价值 |
| ASGrasp | 主动 RGB-D 立体、两层重建、6-DoF 抓取 | 两层透明重建接抓取是空白 | 低成本单视角、语义多界面与薄壳拓扑 |
| Trans2Occ | 单 RGB 透明物体体素占据与抓取 | 从单图恢复体积并抓取是空白 | 薄壳/腔体分辨率、界面配对与接触安全 |
| ShellGrasp-Net | entry/exit object shell 与抓取预测 | “object shell”表示本身是新概念 | 透明薄壁的多次界面、物理内外壁和开口语义 |
| LayeredDepth / SeeGroup | 多层透明深度数据与模型 | 多层透明深度是空白 | 从光线事件到抓取薄壳的语义化与机器人证据 |
| MDA / DepthFocus | 多深度假设、可控穿透层 | 多假设或选层是新贡献 | 界面转移、拓扑、壁厚、rim、cavity |
| GraspNeRF / Dex-NeRF | 多视角神经重建与透明抓取 | 完整透明几何抓取无人研究 | 单视角低成本约束下的薄壳专用表示 |

表中差异是当前工作假设，不是已被实验确认的优越性。完整清单见 `literature-search-20260719-shell-aware-transparent-grasping/`。

## 7. 预期贡献

只有在对应证据通过后，才可按以下口径写论文贡献：

1. **Task / benchmark contribution**：定义透明空心物体的 grasp-relevant layered shell reconstruction，给出界面、rim、厚度、腔体和抓取错误的联合协议。
2. **Representation / method contribution**：提出带转移语义、不确定性和薄壳拓扑的 `LayeredShellGeometry`，而非单深度、固定双层或普通占据。
3. **Robot evidence contribution**：在固定规划器下证明薄壳几何误差与抓取错误相关，并通过真实机器人实验验证其实际价值。

如果只能完成第 1 项，应按诊断 benchmark / position-style work 重新定位；不能把未验证的第 2、3 项写成结果。

## 8. 数据与 GT 可行性

### 8.1 候选资源

- **TablewareNet / T²SQNet**：可参数化生成透明餐具形状，适合构建可控薄壳变化与强 shape-prior baseline；
- **LayeredDepth-Syn**：提供透明多层深度生成管线，适合验证光线界面事件；
- **TransCG**：真实 RGB-D、物体 mesh 与 pose 是首选真实诊断入口，但必须先核验 mesh 是否保留内壁、rim 和真实壁厚；
- **ClearGrasp / ReMake 数据协议**：适合重现 single-depth failure，不自动提供薄壳 GT；
- **自建 CAD + 仿真**：用于严格控制壁厚、开口、曲率、材质、视角和液体状态；
- **真实对象扫描或已知 CAD / opaque twin**：用于机器人阶段的接触几何校准。

### 8.2 G0 必查项

在训练任何新模型前：

1. 抽查 5–8 个空心透明物体及多个视角；
2. 核验 mesh watertightness、内外表面、rim、壁厚与坐标标定；
3. 确认现有 baseline 的实心化、闭口、错层或壁厚错误是否可重复；
4. 将几何错误映射到固定规划器的碰撞 / 接触失败；
5. 判断 T²SQNet / Trans2Occ 是否已经足以解决目标 slice。

若可靠 GT 无法取得，优先转为“薄壳失败诊断集 + 小规模已知 CAD 实验”，而不是训练无法验真的大模型。

## 9. 首版 Scope

### 包含

- 桌面场景；
- 单个或轻度遮挡的空心透明容器；
- 平行夹爪 6-DoF 抓取；
- 单视角 RGB-D + mask；
- 杯、瓶、碗、试管、酒杯等薄壳类别；
- 外壁夹取、rim 附近夹取与碰撞安全。

### 暂不包含

- 灵巧手复杂 manipulation；
- 大规模长程任务规划；
- 把透明容器内目标取出；
- 折射率 / 光学材质的完整逆渲染；
- 液体状态作为主任务；
- 宣称从单图确定性恢复所有不可见后壁。

“透明容器可见不可达取物”保留为独立支线，不与本方法的第一篇论文捆绑。

## 10. 主要风险与备选路线

| 风险 | 触发信号 | 处理 |
|---|---|---|
| 新颖性被 T²SQNet / ASGrasp / Trans2Occ 压缩 | 这些方法在薄壳指标与抓取上已足够 | 收缩为 benchmark，或停止该线 |
| 单视图不可辨识 | 后壁/厚度误差主要由先验猜测决定 | 输出分布与拒抓；引入一次主动视角作为扩展 |
| GT 不可靠 | 数据 mesh 没有真实内壁/厚度 | 自建可控 CAD + opaque twin；降低任务规模 |
| 指标不关联机器人 | shell metric 提升但抓取不变 | 删除机器人主张，重新评估任务价值 |
| 方法过大 | 同时做分割、重建、抓取难以归因 | 固定 mask、backbone 和 planner，分阶段增加模块 |
| “shell”术语撞名 | 与 ShellGrasp-Net 混淆 | 始终使用 `LayeredShellGeometry`；相关工作主动区分 |

## 11. 当前项目结构

| 层级 | 文档 | 定位 |
|---|---|---|
| 当前主 idea | 本文 | 问题、表示、方法和 claim 的唯一主版本 |
| 当前实验设计 | `Shell-Aware-Multi-Layer-Transparent-Grasping-Experiment-v1.md` | evidence package 与 gates |
| 文献边界 | `literature-search-20260719-shell-aware-transparent-grasping/` | 最近工作、检索与筛选记录 |
| 支撑感知线 | `layer_aware_tom_depth_plan.md`、`复现/P0_三件套.md` | 多层深度能力与代码资产，不再是总项目主线 |
| 独立支线 | `透明容器可见不可达取物任务-拷打与完整方案.md` | containment-aware retrieval |

## 12. 下一步

当前唯一 P0 是：

> **先证明“现有表示在薄壳抓取几何上存在可重复、可测量、会影响抓取的失败”，并确认 GT 能支持这个结论。**

P0 通过前，不实现完整 `LayeredShellGeometry` 网络，不把“多层透明薄壳抓取”写成已被证明的新任务，也不承诺真实机器人提升。
