# Shell-Aware Multi-Layer Transparent Grasping：统一实验设计 v1

日期：2026-07-19
状态：**当前实验设计 / 所有结果均为待跑**
对应 idea：`Shell-Aware-Multi-Layer-Transparent-Grasping-Idea-v2.md`

## 0. 实验目标

实验不是单纯证明网络能把 depth RMSE 降低，而是依次回答三个问题：

1. 现有表示是否真的丢失空心透明物体的抓取关键薄壳几何？
2. `LayeredShellGeometry` 是否比单深度、固定双层、通用多层和粗粒度完整形状更准确？
3. 在固定抓取管线中，这些几何差异是否会改变真实抓取安全性与成功率？

当前没有任何真实结果。表格中的数值全部保持 `TBD`；原论文报告与本项目复现结果必须分列。

## 1. Claims—Evidence 对照

| Claim | 最小必要证据 | 关键反例 | Gate |
|---|---|---|---|
| H1：现有表示存在抓取相关的薄壳缺口 | 多对象、多视角下的 shell GT；至少两类强 baseline；几何错误与固定规划器失败的对应关系 | T²SQNet / Trans2Occ / ReMake 已保留足够几何，或误差不影响规划 | G0 |
| H2：语义多界面表示改善薄壳恢复 | 匹配输入与预算的主表；嵌套表示消融；OOD 和扰动测试 | 固定双层或无序 \(K\) 层等价 | G1 |
| H3：薄壳几何改善机器人抓取 | 固定 planner / gripper / candidate set；成对真实执行；失败类型记录 | 离线指标提高但机器人表现不变 | G2/G3 |

## 2. 实验分阶段

### P0-A：GT 与数据可行性审计

目标：确认现有数据能否标注物理薄壳，而不是只提供视觉前表面。

对每个候选数据源检查：

- mesh 是否含独立外壁和内壁；
- rim / opening 是否真实存在；
- 壁厚是否为物理量，还是渲染器中的零厚度面；
- mesh、相机、RGB-D 和 pose 是否同坐标系；
- 是否能沿像素射线生成所有界面及转移类型；
- 液体、标签、把手和底座如何定义；
- 真实物体 CAD 与实物偏差是否可接受。

优先审计：

1. TablewareNet；
2. LayeredDepth-Syn；
3. TransCG mesh + pose；
4. ClearGrasp / ReMake 所用数据；
5. 自建 CAD / Blender 小集。

交付物：GT audit 表、至少 5–8 个对象的可视化、ray-interface sanity check、可用/不可用字段清单。

### P0-B：现有表示失败诊断

先不训练新模型。对同一批已知薄壳对象运行：

- raw RGB-D；
- GT-mask 约束下的 single-depth completion；
- ReMake；
- T²SQNet；
- Trans2Occ；
- 可运行时加入 ASGrasp 或 ShellGrasp-Net；
- GT shell oracle。

需要观察而不是预设的失败类型：

- cavity 被填成占据；
- opening 被封闭；
- front outer / front inner 混淆；
- back inner / back outer 缺失；
- rim 偏移或断裂；
- 壁厚为负、为零或严重偏差；
- 抓取候选落在错误侧；
- 碰撞检测将空腔当实心或将玻璃壁当空。

G0 go 条件：

- GT 可可靠生成；
- 至少两类强表示出现可重复的薄壳错误；
- 错误能映射到固定规划器中的明确失败模式；
- 最近工作没有已直接解决同一协议。

若任一条件不成立，停止新模型开发并重新定位。

### P1：受控数据与协议

构建或整理 `ShellBench` 工作集，最终名称待定。

因子至少包括：

- 类别：cup、bowl、bottle、test tube、wine glass；
- 拓扑：开口 / 窄口 / 把手 / 底部厚化；
- 壁厚；
- 曲率；
- 透明度、折射率和粗糙度；
- 空 / 有液体；
- 视角和遮挡；
- 背景纹理与光照；
- 单物体 / 轻度杂乱；
- solid transparent control 与 opaque twin control。

划分必须按 object instance 隔离，不能把同一 CAD 的相邻渲染泄漏到训练和测试。主报告包含：

- in-distribution；
- unseen instance；
- unseen category；
- unseen material / lighting；
- real transfer；
- solid control。

### P2：离线薄壳几何

主问题：

1. 单深度与多界面差异多大？
2. 固定双层是否足够？
3. 界面语义和拓扑损失分别贡献什么？
4. shell metric 是否跨类别、材质和视角稳定？

所有方法先输出或转换到统一的 shell evaluation API。无法转换的 baseline 只报告它支持的指标，并明确写 `N/A`，不以零代替。

### P3：固定规划器抓取代理

使用同一对象、同一 grasp candidates、同一 gripper model 和同一碰撞检测设置，仅替换几何表示。

评估：

- grasp candidate 是否接触真实外 / 内壁；
- 两指接触是否落在同一可行 shell pair；
- approach path 是否穿过真实壳体；
- cavity 是否被错误占据；
- predicted collision 与 GT collision 的 precision / recall；
- top-1 与 top-k 候选是否有可执行解；
- uncertainty-aware rejection 的 risk–coverage 曲线。

该阶段可证明几何对规划有意义，但不能替代真实机器人结果。

### P4：真实机器人抓取

硬件、相机、夹爪和控制器当前均为 `TBD`，不在文档中虚构。

首轮采用小而受控的 protocol：

- 已知 CAD / 可测量物体与若干未知实例；
- 同一摆放状态配对比较不同几何表示；
- 固定候选生成与运动规划；
- 平行夹爪；
- 每次执行前记录 RGB、raw depth、mask、预测几何、候选和规划轨迹；
- 每次执行后记录成功与失败 taxonomy；
- exact trial count 在硬件 pilot 后预注册。

成功定义必须在运行前固定，例如：无破坏地建立抓取、抬离支撑面、保持指定时间并放置到目标区。保持时间和高度由硬件条件确定后写入 protocol。

### P5：鲁棒性与系统边界

- mask 腐蚀、膨胀、边界抖动；
- depth missing / flying points / bias；
- 外观、背景与强反射；
- 视角减少；
- 壁厚超出训练范围；
- 类别 OOD；
- liquid / label / handle；
- clutter 与遮挡；
- inference latency、显存和拒抓率。

## 3. Baseline 设计

### A. 匹配输入的主 baseline

主表以单视角 RGB-D + mask 为统一输入；额外模块单独计入系统成本。

| Baseline | 输出类型 | 作用 | 复现状态 |
|---|---|---|---|
| Raw sensor depth | 单深度 | 无补全下界 | 待跑 |
| ClearGrasp | 单 completed depth | 经典 RGB-D 透明补全 | 待跑 |
| LIDF | 单 completed depth / implicit surface | 强局部补全 | 待跑 |
| TransCG DFNet | 单 completed depth | 真实数据与抓取基线 | synthetic smoke 已有，真实待下载 |
| ReMake | 单 completed depth | 最直接的 MDE + mask 抓取近邻 | synthetic smoke 已有，完整真实待跑 |
| Fixed two-layer head | 两张有序深度 | 最小多层替代 | 待实现 |
| Unordered \(K\)-depth events | 通用多假设 | 隔离语义与拓扑贡献 | 待实现 |
| Proposed LayeredShellGeometry | 语义多界面薄壳 | 主方法 | G0 后才实现 |

### B. 结构表示与 novelty threat

这些方法输入、先验或输出不同，应单列，不强行做同输入排名。

| 方法 | 角色 | 公平处理 |
|---|---|---|
| T²SQNet | 透明餐具低维完整形状与抓取强近邻 | 用官方输入与模型；报告其可计算的 shell / grasp 指标 |
| Trans2Occ | 单 RGB 体素占据与抓取近邻 | 作为体积表示强威胁；报告分辨率和 cavity error |
| ShellGrasp-Net | entry/exit object shell + grasp | 明确其一般物体深度输入，不冒充透明同输入 baseline |
| LayeredDepth / SeeGroup | 多层感知基础 | 在其协议上评多界面；转到抓取时注明适配方式 |
| MDA / DepthFocus | 多假设 / 可控层选择 | 主要用于表示消融与 reviewer threat |

### C. 更强传感器系统上界

- ASGrasp：主动 RGB-D stereo；
- GraspNeRF / Dex-NeRF：多视角 RGB；
- GT multi-view reconstruction；
- GT CAD / mesh。

这些结果作为 system upper bound，不用于支持“单视角同条件 SOTA”。

## 4. 指标

### 4.1 多界面射线指标

| 指标 | 定义目的 |
|---|---|
| Interface Precision / Recall / F1 @ \(\delta\) | 在容差 \(\delta\) 内匹配界面事件；\(\delta\) 随数据单位预注册 |
| Ordered Interface MAE / RMSE | 匹配后的逐层米制误差 |
| Interface Count Accuracy | 每条射线的界面数量是否正确 |
| Transition-type Accuracy / F1 | air/shell/cavity 转移语义 |
| Topology-valid Ray Rate | 是否满足合法材料进入/离开次序 |
| Uncertainty NLL / calibration | 预测分布是否校准 |

界面匹配同时报告：

- order-constrained matching；
- type-constrained matching；
- unmatched prediction / GT penalty。

不能只在成功匹配的界面上算 MAE。

### 4.2 薄壳几何指标

| 指标 | 目的 |
|---|---|
| Outer / inner surface Chamfer 或 point-to-surface error | 区分两类物理表面 |
| Rim F1 与 Rim Chamfer | 开口边界的位置与完整度 |
| Opening pose error | 开口中心与法向 |
| Wall-thickness MAE | 沿局部法向的真实厚度误差 |
| Normal angular error | 抓取接触法向 |
| Shell occupancy IoU | 玻璃材料体积 |
| Cavity IoU | 空腔范围 |
| Free-space violation rate | 将真实腔体错误填成实体的比例 |
| Topology validity | 非 rim 裂缝、错误闭口、负厚度等 |

壁厚不使用简单的 `z_inner - z_outer` 作为唯一真值；应在三维局部法向上求交并报告不可匹配比例。

### 4.3 抓取与系统指标

| 指标 | 说明 |
|---|---|
| Grasp success rate | 按预注册抬升 / 保持 / 放置条件 |
| Collision rate | approach 或 closure 与真实 shell 非预期碰撞 |
| Miss / no-contact rate | 夹爪闭合但未形成有效接触 |
| Wrong-side contact rate | 计划接触面语义错误 |
| Slip / drop rate | 建立接触后滑移或掉落 |
| Damage-risk proxy | 过度闭合、厚度误判或力限触发；真实“损坏”不主动制造 |
| Planning rejection rate | 无可行抓取或不确定性拒抓 |
| Risk–coverage / success–coverage | 拒抓是否真正过滤风险 |
| Runtime / peak memory | 完整链路而非只报网络前向 |

## 5. 必做消融

### 表示消融

- single completed depth；
- `D_outer + D_inner` 固定双层；
- unordered \(K\) hypotheses；
- ordered \(K\) interfaces，无 transition type；
- 有 transition type，无 topology loss；
- 完整 `LayeredShellGeometry`。

### 几何字段消融

- no rim；
- no cavity free-space；
- no thickness；
- no normals；
- no uncertainty / rejection；
- outer-only；
- inner-only；
- no back-side interfaces。

### 输入消融

- raw depth only；
- RGB + raw depth；
- + mask；
- + frozen MDE prior；
- GT mask / predicted mask / noisy mask；
- single view / optional second view。

### 抓取消融

- 同一 planner 使用 single point cloud；
- 同一 planner 使用 shell occupancy；
- shell-aware contact label；
- + uncertainty rejection；
- GT geometry oracle。

## 6. 公平性与统计

- 主表按传感器和输入组分开；
- 同组 baseline 使用相同 train/val/test object split；
- 同一机器人场景使用配对摆放或随机化顺序，避免方法顺序偏差；
- 固定 planner、gripper、candidate budget、collision margin 和控制器；
- baseline 超参优先用官方设置，任何调参记录在案；
- 训练方法原则上运行 3 个 seed；若成本不允许，明确标注单次运行；
- 连续指标报告 mean、median、标准差和 object-level bootstrap 95% CI；
- 二元抓取结果报告成功率与置信区间，并用配对 scene/object 统计检验；
- 同时报告 per-object 与 pooled 结果，避免大量简单样本掩盖困难物体；
- failure taxonomy 由视频与日志复核；可行时盲化方法名；
- 原论文数字只放 `reported` 列，本项目数字只放 `reproduced` 列。

## 7. 结果表模板

### 表 A：G0 薄壳失败诊断

| Method | Input | Outer ↓ | Inner ↓ | Rim F1 ↑ | Cavity IoU ↑ | Free-space violation ↓ | Planner failure ↓ |
|---|---|---:|---:|---:|---:|---:|---:|
| Raw depth | RGB-D | TBD | TBD | TBD | TBD | TBD | TBD |
| ReMake | RGB-D + mask + MDE | TBD | TBD | TBD | TBD | TBD | TBD |
| T²SQNet | partial RGB + shape prior | TBD | TBD | TBD | TBD | TBD | TBD |
| Trans2Occ | RGB | TBD | TBD | TBD | TBD | TBD | TBD |
| GT shell | oracle | 0 | 0 | 1 | 1 | 0 | TBD |

### 表 B：匹配输入的几何主表

| Method | Interface F1 ↑ | Type F1 ↑ | Thickness ↓ | Rim CD ↓ | Cavity IoU ↑ | Topology valid ↑ | Runtime ↓ |
|---|---:|---:|---:|---:|---:|---:|---:|
| Single depth | TBD | N/A | N/A | TBD | TBD | TBD | TBD |
| Fixed two-layer | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| Unordered K | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| Proposed | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

### 表 C：固定规划器与真实机器人

| Geometry | Planner collision ↓ | Executed success ↑ | Collision ↓ | Miss ↓ | Wrong-side ↓ | Slip/drop ↓ | Reject ↓ |
|---|---:|---:|---:|---:|---:|---:|---:|
| Raw depth | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| ReMake | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| T²SQNet / Trans2Occ | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| Proposed | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| GT shell | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

### 表 D：消融

| Ordered | Transition semantics | Topology | Rim | Cavity | Uncertainty | Shell metric ↑ | Grasp success ↑ |
|---:|---:|---:|---:|---:|---:|---:|---:|
| ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | TBD | TBD |
| ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | TBD | TBD |
| ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | TBD | TBD |
| ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | TBD | TBD |
| ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | TBD | TBD |

## 8. Stage Gates

| Gate | 必须回答 | Go | No-go / Pivot |
|---|---|---|---|
| G0：failure + GT | 缺口真实且可测吗？ | GT 可用，强 baseline 有系统失败，且映射到规划 | 终止新模型；只保留综述/诊断或换任务 |
| G1：geometry | 表示本身更好吗？ | 匹配输入下，多项 shell 指标稳定改善且消融支持机制 | 简化为双层/通用多层，或取消方法 claim |
| G2：planning | 几何改善会改变动作吗？ | 固定 planner 下错误率下降，risk–coverage 有效 | 不做机器人主张 |
| G3：robot | 真实执行有价值吗？ | 成对实验支持 H3，失败类型与离线证据一致 | 诚实报告负结果并重新定位 |

具体数值阈值不在看到 pilot 后反向设定；应在 pilot 只用于估计方差后预注册，并冻结测试集。

## 9. 当前执行顺序

```text
P0-A GT audit
→ P0-B ReMake / T²SQNet / Trans2Occ shell-failure diagnostic
→ G0 go/no-go
→ P1 protocol and data
→ P2 matched-input geometry
→ G1
→ P3 fixed-planner evidence
→ G2
→ P4 paired real-robot evaluation
→ G3
→ P5 robustness
```

当前只授权推进到 G0。已有 Depth4ToM、LayeredDepth、SeeGroup、TransCG 和 ReMake 复现资产作为支撑，不再各自竞争总项目主线。

