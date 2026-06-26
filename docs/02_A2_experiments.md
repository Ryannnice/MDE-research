# A② 实验方案 —— 免训练单步扩散米制深度

> 配套立项卡:`docs/04_MDE_ideas.md` §4。本文件 = 从立项卡到可执行实验的工程落地层。
> 生成:2026-06-22 · 扩充执行层:2026-06-23(深挖 + 全套可跑脚本)
> 方法:代码资产取证(WebFetch 实锤 5 库 repo/license/权重)+ 两 Linchpin 转最便宜先证伪序列 + CCF→深度核机制代码自检
> 一句话定位:**这是一个算力极轻、科学风险极重的项目。瓶颈不是 GPU,是 §4.4/§4.7 两个赌注能否实证成立。整个方案围绕"用最便宜的实验最快证伪"组织。**
>
> **§8–14 是执行层(2026-06-23 新增):显卡服务器可直接接手。** 七个模块 + 一个 driver 全部本地 `_self_check` 跑通(无 GPU/权重),GPU 服务器换数据集与权重即真跑。脚本清单见 §8.1,逐 Phase 命令见 §11,目录结构见 §8.2。

---

## 0. 核心结论(先看这个再决定要不要投人)

| 维度 | 结论 | 取证 |
|------|------|------|
| **代码可跑性** | ✅ 全绿。Marigold/E2E-FT/ChordEdit/米制基线/评测脚本全部官方开源、权重在 HF、Apache/MIT 为主 | repo 逐个 WebFetch 确认(§2) |
| **算力门槛** | ✅ 极低。纯推理,单图 <4GB 显存、~0.1–0.5s。你的计算服务器用于**并行刷消融网格**,不是训练 | E2E-FT 121ms/图@4090;米制基线 33–139ms@A100 |
| **CCF 可迁移性** | ⚠️ 半绿。ChordEdit `_u_estimate` 是真的、极简(一行时间加权),但**两端锚已知**;深度目标端未知,必须 Tweedie 代理锚重定义——这是新增工作量,非复制 | `pipeline_chord.py` 取证 + 骨架自检 |
| **科学风险** | 🔴 高。两个 Linchpin 任一塌则 idea 散架。L1 门槛已被 AnchorD 抬高,L2 有 CoSIGN 撑但非定论 | §3 |
| **命名诚实** | ⚠️ 改判(2026-06-22 精读 ChordEdit 全文)。**"Chord Control Field (CCF)" 是 ChordEdit 原论文术语**(出现 33 次,p.7 §6.1 正式定义缩写),"smoothed variance-reduced editing field" 只是摘要并行描述——**不是本库提炼词,可直接沿用并引用**。但原 CCF 定义 = **两 prompt drift 的时间加权平均**;A② 是 **指向 Tweedie 代理锚的位移场平均**,机制结构不同。诚实做法:沿用 CCF 名 + 引 ChordEdit + 明示"重定义到深度",或起区分名(如 proxy-anchored CCF) | PDF 33 处取证(p2/p4/p7/p12) |
| **去/留建议** | **GO,但按 B2(1–2步)立项,且第 1 周先跑 L1 证伪。** 严格 1-NFE(B1)与 CCF 机制本身冲突(CCF 至少采 2 时间点),只能当冲刺目标不当前提 | §3.3 |

---

## 1. 项目的真实科学结构(去包装)

立项卡 §4.10 已诚实定级"机制迁移 + 组合创新"。落到实验,只有**三个数字**决定论文成不成,其余都是陪衬:

```
                   ┌─ L1: 采样期注入 vs 后处理标定(patch-affine 档) ── 决定"米制"卖点
论文活 ⟺ 三个都赢 ─┼─ L2: 单步注入几何锚 vs 多步 energy guidance ───── 决定"单步"卖点
                   └─ A : CCF 时间平均 vs 纯单点 x0(§4.9 最毒攻击) ── 决定"OT 不是装饰"
```

- A 没单列在立项卡 Linchpin 里,但 §4.9 把它标为**最毒攻击(requires-new-result)**。它和 L1/L2 同级,且**最便宜**——同一套推理代码加个 ablation 开关即可。故本方案把它提为 **L0**,Phase 1 一起跑。
- 三者关系:L0 守 method 新意(对 E2E-FT),L1 守米制(对 GeoDiff/后处理),L2 守单步(对多步引导)。**任一为否,对应卖点删除,但不一定全塌**——B2 退路就是为 L2 留的。

---

## 2. 代码资产盘点(全部 WebFetch 取证,2026-06-22)

### 2.1 扩散深度骨干

| 库 | repo | License | 权重(HF) | 单步? | 角色 |
|----|------|---------|----------|-------|------|
| **Marigold** | prs-eth/Marigold | Apache-2.0(代码)/ OpenRAIL++(v1.1权重) | `prs-eth/marigold-depth-v1-1` | v1.1 默认 trailing 单步 | **主骨干** |
| **E2E-FT** | VisualComputingInstitute/diffusion-e2e-ft | ⚠️无 LICENSE 文件,投稿前须问作者 | `GonzaloMG/marigold-e2e-ft-depth` | `denoise_steps=1 timestep_spacing=trailing noise=zeros`,121ms@4090 | **头号基线 + Day-1 起点** |
| **DepthFM** | CompVis/depth-fm | MIT | `wget .../depthfm-v1.ckpt`(非HF) | 1–2步,非 diffusers 格式 | **骨干无关性证据**(放最后) |
| **Lotus** | EnVision-Research/Lotus | Apache-2.0 | `jingheya/lotus-depth-d-v2-0-disparity` | t=1000 单步 | 备用骨干无关性 |
| Marigold-DC | prs-eth/Marigold-DC | Apache-2.0 | 复用 v1-0 | ❌ 50步 guidance | 仅 related work 区分用 |

### 2.2 机制类(CCF + 单步注入)

| 库 | repo | License | 可用性 | 用法 |
|----|------|---------|--------|------|
| **ChordEdit** | ChordEdit/ChordEdit (330★) | MIT | ✅ `pipeline_chord.py` 含 `_u_estimate` | **CCF 核心参照**。公式实锤:`u_hat=(δ·dv_s+t_s·dv_s0)/(t_s+δ)`,两次时间点,无外部 OT 求解器 |
| **Defocus-Marigold** | chinmay0301ucsd/DiffusionCam | ⚠️无标注 | ✅ 可运行 | **最强方法先例**:latent 优化+球面归一化注入物理线索→米制。把散焦 loss 换成几何 loss |
| **CoSIGN** | BioMed-AI-Lab-U-Michgan/cosign | ⚠️无标注 | 部分(软约束需训ControlNet) | **L2 机制弹药**:硬约束 DDNM 闭式投影 training-free 可借;证明 1–2 NFE 能注入约束 |
| GeoDiff | ❌未开源 | — | 仅论文 | 算法清晰,需自实现;且需立体→违背单目,只作对照概念 |
| ReCFG / DSG / PGDM | 各异 | 部分 | 与 EDM2/DPS 耦合 | 不推荐直接接,理论参考 |

> **CCF 迁移工作量(已有 ChordEdit 代码下)**:复用时间加权逻辑近零改造;真正新工作 = ① `dv` 从"tgt-src prompt 差"改为"指向 Tweedie 代理锚"(§4.4 重定义,已在骨架实现);② 适配 Marigold VAE latent。估 **1 周工程**。骨架 `A2_ccf_depth_skeleton.py` 已把 ①③ 的逻辑核跑通自检。

### 2.3 米制基线(metric 协议横比对象)

| 库 | repo | License | 权重 | 显存/耗时@A100-FP16 |
|----|------|---------|------|---------------------|
| UniDepth | lpiccinelli-eth/UniDepth | CC BY-NC 4.0 | `lpiccinelli/unidepth-v2-vitl14` | 1.1–1.8GB / 33–50ms |
| Metric3D v2 | YvanYin/Metric3D | BSD-2 | `JUGGHM/Metric3D` | 1.4GB / 87ms |
| Depth Pro | apple/ml-depth-pro | Apple AMLR | `apple/DepthPro-hf` | 3.7GB / 139ms |
| ZoeDepth | isl-org/ZoeDepth | MIT | torch.hub `ZoeD_N` | ~170ms@A40 |

### 2.4 评测脚本(区分真/假米制的命门)

- **affine-invariant 协议**(对齐 scale+shift):`prs-eth/Marigold` 的 `script/depth/eval/`,5 数据集成对 infer/eval 脚本,被引最广。
- **metric 协议**(零对齐):`DepthAnything/Depth-Anything-V2/metric_depth/util/metric.py`,直接算 `abs_rel/rmse/log10/d1/d2/d3`。
- **本项目命门做法**:同一组预测**两套脚本各跑一遍**,差值 = scale+shift 对齐收益。本 idea 主打几何锚→米制,**必须在 metric 协议(零对齐)下不被对齐收益吃掉**,否则即"假米制"。

### 2.5 数据集获取难度(冒烟测试取数序)

1. **NYUv2** 测试集 654 帧,单个 2.8GB `.mat`,`wget` 无注册 → **首选冒烟**
2. **DIODE** 验证集,官网直下无注册 → 次选(含室外)
3. **ETH3D** ~5.5GB 直下
4. **KITTI** Eigen 697 帧:官网需注册,Kaggle 镜像可绕(Garg crop + 80m cap)
5. **ScanNet** 必须机构邮箱申请审批 → 最后处理

---

## 3. 实验序列(cheapest-falsification-first + GATE)

> 原则:**先花最少的钱去杀死 idea**。每个 Phase 一个 GATE,FAIL 就停下诚实分析,不硬冲。立项卡 §4.8 已点名"第一周先跑 L1 后处理对照"——本序列把它具体化,并把同样便宜的 L0 拼进同一周。

### Phase 0 — 基线复现冒烟(2–3 天,零风险)
**目的**:确认环境与基线数字可复现,建立 metric/affine 双协议评测脚手架。
1. 装 diffusers,跑 `GonzaloMG/marigold-e2e-ft-depth` 单步,NYUv2 654 帧出深度。
2. 接 Marigold eval(affine)+ DA-V2 `metric.py`(metric)两套脚本。
3. 复现 E2E-FT 单步数:**NYUv2 AbsRel≈5.2 / δ1≈96.6,KITTI≈9.6 / 91.9**(affine 协议)。
4. 跑 UniDepth/Metric3D v2 出 metric 协议锚点:KITTI/NYU AbsRel≈0.042、δ1≈0.98。

**GATE-0**:复现数字落在论文 ±10% 内 → PASS。否则先修环境(WSL cuDNN/换行符坑见 §6),不进 Phase 1。

### Phase 1 — L0 + L1 联合证伪(第 1 周,最便宜、最致命)
**这是 go/no-go 的真命门。两个测试共用一套推理,加 ablation 开关即可。**

**L0(OT 不是装饰)**:同一骨干、同一 t_schedule,三臂对比:
- 臂a 纯单点 Tweedie x0(`use_ccf=False`)
- 臂b CCF 时间加权(`use_ccf=True`,2 时间点)
- 臂c 单点但多噪声平均(隔离"是 OT 时间平均的功 vs 仅多样本的功")
- **判据**:臂b 在 affine AbsRel 上**净优于** a 和 c,且增益不被噪声方差吞没(跑 3 seed 报均值±std)。

**L1(米制非后处理能做)**:固定相对深度预测,四臂接地对比:
- 臂A 全局 scale+shift(2-DOF 后处理)
- 臂B **patch-wise affine**(AnchorD 式,门槛升级后的真对照)
- 臂C 采样期几何锚烘焙(本工作,`use_geo=True`)
- 臂D = C 但锚只用全局(消融"局部结构修正"是否真起作用)
- 几何锚来源:NYU/KITTI 用 GT 稀疏采样模拟"已知尺寸/地平面"(立项阶段先用 oracle 锚证机制,真实锚源 Phase 3 再上)
- **判据(Linchpin-1)**:臂C 在 **metric 协议(零对齐)**下 AbsRel 优于臂B。若 C ≈ B,则"采样期注入"是花架子,米制卖点删除。

**GATE-1(双判)**:
- L0 PASS ∧ L1 PASS → 进 Phase 2,士气满。
- L0 FAIL → §4.9 最毒攻击坐实,idea 退化为 E2E-FT,**建议止损或转 A①**。
- L1 FAIL(C 追不平 B)→ 米制卖点死,**退路**:转纯加速 idea(只卖 L0+单步),或转 A①。
- 仅一个 PASS → 见 §5 退路矩阵,大概率降级为 workshop/短文。

> ⚠️ 诚实:Phase 1 就是设计来**尽早杀死 idea** 的。这周拿到红灯是省钱不是失败。

### Phase 2 — L2 单步 vs 多步(第 2–3 周)
仅在 GATE-1 PASS 后做。
- 臂1 多步 energy guidance(慢基线,DPS 式,N=20–50 步)
- 臂2 本工作单步烘焙 CCF(B2:1–2 步)
- 臂3 CoSIGN 式硬投影注入(机制弹药对照)
- **NFE 对齐曲线**:横轴 NFE∈{1,2,4,8,…},纵轴 metric AbsRel,看单步烘焙能否逼近多步。
- **判据(Linchpin-2)**:单步/近单步(NFE≤2)的 metric 精度 ≈ 多步(差距 <X%,X 投稿前定)。

**GATE-2**:
- PASS → 进 Phase 3 主实验,B1(严格1步)可尝试冲刺。
- FAIL → 退 **B2**:主打"1–2 步",新意略减但稳(立项卡 §4.11 已备此退路)。仍可成文。

### Phase 3 — 主实验 + 真实几何锚(第 4–6 周)
- 真实锚源替换 oracle:已知物体尺寸(车牌/A4/瞳距63mm)、地平面+内参 EXIF。
- 全基准:NYUv2 / KITTI(Eigen+Garg+80m)/ ETH3D / ScanNet / DIODE。
- 骨干无关性:Marigold → + Lotus → + DepthFM(证 §4.7 统一映射系数)。
- 全基线 metric 横比:UniDepth / Metric3D v2 / Depth Pro / ZoeDepth / E2E-FT / GeoDiff(概念)。
- 报 NFE + 墙钟(单步硬证据)。

### Phase 4 — 消融与写作弹药(第 7–8 周)
- L0/L1/L2 三消融做全(已是 method 主体)。
- t_delta、时间点数、num_noise 敏感性。
- 失败模式切片(复用 Idea 5 纪律):透明/反光/远距离分片报。
- 协议陷阱表注:crop/cap/对齐三项逐基准核(§4.10)。

---

## 4. 评测协议(投稿前卡死,抄进每张表注)

1. **二分**:affine-invariant(对齐 scale+shift)vs metric(零对齐)。本 idea 主表必在 **metric 协议**,另附 affine 列供与 Marigold/DepthFM 同框。
2. **KITTI**:Eigen split + Garg crop + cap 80m。**NYU**:官方 crop。
3. **横比 regime 对齐**:KITTI 表 in-domain 训练行与零样本行不可混比,只取同 regime。
4. metric 锚点(零对齐):Metric3D v2 KITTI/NYU AbsRel≈0.042、δ1≈0.98;UniDepth 跨域 SUN-RGBD AbsRel≈0.087。
5. ETH3D/ScanNet/DIODE 数值分散,入表前逐篇核 crop/cap/对齐三项。

---

## 5. 风险退路矩阵

| GATE 结果 | idea 状态 | 行动 |
|-----------|----------|------|
| L0✅ L1✅ L2✅ | 满血:免训练单步米制端到端 | 冲 CVPR/ICCV 主会,尝试 B1 |
| L0✅ L1✅ L2❌ | 退 B2 | 主打"1–2 步米制",仍主会投稿 |
| L0✅ L1❌ L2— | 米制死 | 转纯加速(OT 时间平滑用于深度加速),或并入 A① |
| L0❌ | 退化为 E2E-FT | **止损**,资源转 A① HDR/RAW |
| 全❌ | — | A② 不成立,A① 是已备好的 plan B(执行风险,数据是命门) |

> A① 与 A② 风险类型互补(执行 vs 科学),A② 早期证伪成本极低(1 周)。**理性策略:先花 1 周 Phase 1 赌 A②,红灯就转 A①**,几乎无沉没成本。

---

## 6. 算力与时间线

**算力真相**:全程纯推理。单卡(A100/4090,≥8GB)够跑全部。计算服务器的价值是**并行**:Phase 1–2 的 ablation 网格(骨干×臂×seed×数据集)可一夜刷完,把"两周串行"压成"两天并行"。**不需要训练、不需要多卡通信。**

| 周 | Phase | 产出 | GPU 用量 |
|----|-------|------|----------|
| 0(2–3天)| P0 | 双协议评测脚手架 + 基线复现 | 1 卡 |
| 1 | P1(L0+L1)| **go/no-go 决策** | 网格并行 |
| 2–3 | P2(L2)| NFE 对齐曲线 | 网格并行 |
| 4–6 | P3 | 主实验全基准 | 网格并行 |
| 7–8 | P4 | 消融+写作 | 轻 |

**已知坑(Phase 0 先排)**:WSL `libcudnn_cnn_infer.so.8` → 设 `LD_LIBRARY_PATH=/usr/lib/wsl/lib`;Marigold bash 脚本 DOS 换行 → `dos2unix`;复现确定性 → `--batch_size 1` + 确定性模式。

---

## 7. 立项卡需回写的修正(本轮取证新增)

1. **§4.11 B1 应明确标注与 CCF 机制冲突**:CCF 时间加权至少需 2 个去噪时间点(`_u_estimate` 取证),严格 1-NFE 无法构造 CCF。B1 只能当冲刺目标,**B2 是立项前提**——比立项卡现表述更强的约束。
2. **§4.3/§4.4 命名诚实(2026-06-22 改判,推翻前述)**:精读 ChordEdit 全文证实 **"Chord Control Field (CCF)" 正是原论文术语**(33 处,p.7 §6.1 定义缩写)——前一版"ChordEdit 无 CCF 字样"系误判,须删。真正要诚实标注的是**定义差异**:原 CCF = 两 prompt drift 时间加权平均;A② CCF = 指向 Tweedie 代理锚的位移场平均,机制不同。写作可沿用 CCF 名但须引 ChordEdit 并明示"重定义到深度条件生成",或改用 proxy-anchored CCF 区分。
3. **§4.4 重定义工作量被低估**:子 agent 初判"复用近零改造"是错的——ChordEdit 两端锚已知,深度目标端未知,Tweedie 代理锚替换是**真新增机制**(已在 `A2_ccf_depth_skeleton.py` 实现并自检),约 1 周工程,非复制粘贴。
4. **🔴 §4.9 新增最毒攻击维度:有偏代理锚 vs 零均值噪声(2026-06-22 精读 ChordEdit §3.2/4.1 发现)**。ChordEdit 的测量模型是 `R = u_t + ε`,**ε 严格零均值**(Eq 4.2),所以时间平均做的是**降方差**(Jensen → L² 收缩,附录 D 证)。但 A② 的 Tweedie 代理锚 `d̂₀` 是 **MMSE 估计 = 有偏**(去噪早期系统性偏离真值),其"误差"**非零均值**。**时间平均能压方差,压不掉偏差。** 推论:(i) A② 的 L0 消融比 ChordEdit 的 δ 消融**更可能失败**——你赌的是"多时间点平均净修正一个**有偏**单点 x0",ChordEdit 只需对付无偏噪声,**不能直接拿它 Fig.9 的成功当背书**;(ii) 这恰是 novelty 必须干活处:要正面论证**几何锚能纠这个偏**,或**偏差随 t 变化、多时间点可抵消**。写进 §4.9 最毒攻击的论证内核,比单引 ChordEdit Fig.9 有力。
5. **🔴 §4.7/§4.9 新增:E2E-FT `noise=zeros` 最优性 与 CCF 多噪声平均的张力(2026-06-23 WebFetch E2E-FT 接口取证)**。E2E-FT README 明确"单步确定性模型,noise 应恒为 zeros、ensemble/steps 恒为 1"。而 CCF 的 `num_noise>1` 需**主动加噪**才能平均。**推论**:L0 的 arm_c(纯多噪声平均)在单步框架下**很可能无增益甚至变差**——这反而是好事:它把"CCF 的功"逼到只能来自**时间维平均**(多去噪时间点 t),与"噪声维重采样"彻底切开。故 L0 三臂的隔离比立项卡设想的更干净:`arm_b(多t) > arm_c(多noise) ≈ arm_a(单点)` 才是"OT 时间平滑非装饰"的判据;若 arm_c 也涨,说明增益来自重采样而非 OT,新意打折。已固化进 `A2_diag_bias_var.py`(bias-var 分解)与 `A2_run_grid.py`(三臂 L0)。
6. **§4.7 latent/depth 空间切换被遗漏(2026-06-23 实现 driver 时发现)**:CCF 在 **latent 空间**走,几何锚是 **depth 空间米制约束**,二者不在同一空间。skeleton 的 `bake_geo_anchor` 是空间无关的逻辑参照,真实 arm C 必须 `decode(latent)→depth 空间纠偏→encode 回 latent`(往返一次/步)。已在 `A2_run_grid.bake_geo_latent` 实现。这是 §4.7 method 骨架须补的工程细节,不影响机制赌注但影响复现。
7. **🔴 实验包审查发现两个 blocker 并已修复(2026-06-23,独立审稿视角复核)**——两条都直接打在科学有效性上,留痕备查:
   - **B1 L1 对照偷看答案(立项卡头号坑复发)**:初版 `bake_geo_latent`(arm C)= patch-affine + 额外把锚真值软投影进支撑区,而 arm B 没有 → arm C 比 arm B 多吃一份"锚点答案",L1 对照非单变量,GATE-1 即便 PASS 也无效。**修复**:抽出唯一接地原语 `ground_to_metric`,arm B/C 共用、`pin_anchors` 同开同关,信息量一致,唯一差异回归"采样期往返传播 vs 后处理一次"。
   - **B2 最毒攻击诊断器从未接入(①' 实为"待实现")**:`A2_diag_bias_var.diagnose()` 此前只在 stub 自检里跑,driver 无任何调用,§4.9 最毒攻击(与 L1/L2 同级)在真实数据上无可执行路径。**修复**:driver 加 `--phase diag`,truth=GT 深度(depth 空间)、`eval_space=decode_depth`,真实三臂 bias-var 分解写 CSV。同时改 bias/var 在 **depth 空间**度量(§4.9 偏差是米制偏差非 latent 偏差)。
   - 同轮修 5 个 major:M1(L0 三臂 latent 同源 + CCF 在 e2eft 的 t 越界警告)、M2(VAE 往返不保形会侵蚀几何锚,加 `vae_roundtrip_residual` 检查 + 写入 §13)、M3(arm D 改为只退 patch 网格、保留地平面,消融单变量)、M4(`nfe_real` 真实 forward 计数,防假单步)、M5(NYU .mat 轴序断言)。详见 §13 已知坑与各脚本 🔴 注释。
8. **🔴 第二轮复核:修复在相邻处留的 4 个缺陷(2026-06-23,同一审稿视角复核修复 diff)**——B1/B2 病灶虽消,但修复各自在旁边留了 major,继续留痕:
   - **#1 geo 单位不一致(B2 本应修的腿反而废了)**:`run_diag` 传给诊断器的几何锚 tgt 是**米制**(1–8m+),而三臂输出与 truth 已归一化到 [0,1] → 米制值塞进 [0,1] 场,`geo_corrects_bias` 恒判 False(实证 `b_ccf_geo abs_bias` 从 base 的 0.10 爆到 1.04)。**修复**:geo tgt 用与 `truth_depth` **同一 min-max** 归一化到 [0,1] 同 frame;实证回落到 0.09(正确纠偏)。
   - **#2 L1 命门 base predictor 不对称**:arm B 单步单噪、arm C 多噪 CCF → `C<B` 含"CCF 基底更强"的功劳,非纯"注入位置"之功,Linchpin-1 头条对照不单变量。**修复**:新增 arm B'(`Bp_postproc_patch_ccf`)= 与 arm C **同源 CCF 相对深度**上做 patch-affine 后处理;`C<B'` 才是干净单变量判据(注入位置:采样烘焙 vs 解码后后处理)。B 保留为便宜全系统基线。
   - **#3 度量 frame 不一致(moderate)**:Marigold 出 affine-invariant 相对深度,与 min-max GT 差未知全局 affine;abs_bias 绝对量被污染。**修复**:`bias_variance_decomp` 加 `align_affine`,分解前对每臂做全局 (s,t) 最小二乘对齐到 truth,剥离合法 affine 自由度,剩结构偏差;局部几何锚修正是局部的,全局对齐抹不掉 → geo 腿仍显纠偏。真机开,mock 关。
   - **#4 minor**:skeleton docstring model_id 对齐 E2E-FT Day-1 起点;`a2/requirements.txt` 钉 `diffusers>=0.32,<0.40`(接口按 v0.38 核实,防未来版漂移);失败切片距离图用 `scipy.ndimage.distance_transform_edt` 替纯 Python 双循环。
9. **🔴 第三轮复核:又抓一个 blocker(B3)+ 一个 frame 修正(2026-06-23,同一审稿视角验修复 diff)**——前两轮修复在相邻处又暴露问题,继续留痕:
   - **🔴 B3 arm C 未接地,按米制协议评必输(最隐蔽)**:latent 是 affine-invariant **相对**域,`arm_sample_geo_local` 末步 `decode_depth(z)` 恒出 [0,1],却按 metric 协议与 GT 0-10m 比 → arm C 必输每个后处理臂,Linchpin-1 得**反向错误结论**(单位错,非机制)。实测同源 CCF 基底下 C(相对)absrel≈0.90 vs 接地后≈0.02。**修复**:arm C 末步补 `ground_to_metric`,与 arm B' **同原语**收尾 → C-vs-B' 唯一差异回归"采样期是否烘焙锚"。加 B3 回归自检(断言 arm C 输出落米制量程、C/B' 同量程)。
   - **#3-bis 几何锚腿不能参与 affine 对齐(frame 概念冲突)**:round-2 #3 给攻击腿加 align_affine 剥离仿射自由度是对的,但几何锚的贡献**就是绝对接地**,全局 align 会把它撤销(实测支撑区 bias 从 0.000 被 align 搬到 0.051,geo_corrects 误翻 False)。**修复**:`diagnose` 两条防守腿用**不同 frame**——攻击腿(a/c/b)用 align_affine 分解看结构偏差;几何腿(b vs b_geo)**始终未对齐**、在锚支撑区度量纠偏。docstring 过度声称("全局对齐抹不掉局部修正")改为有条件表述。加 align_affine+geo 路径自检(此前真机恒开、mock 恒关 → 该组合从未被测的覆盖盲区)。
   - **minor**:三处全局 affine 解(`ground_global_affine`/patch 回退/`_global_affine_params`/`_affine_align_to`)裸 `lstsq` → 改 ridge 正规方程(`solve_affine_ridge`),防近共线/近恒定深度锚导致 MKL SGELSY 秩亏崩溃。
   - **minor**:三处全局 affine 解(`ground_global_affine`/patch 回退/`_global_affine_params`/`_affine_align_to`)裸 `lstsq` → 改 ridge 正规方程(`solve_affine_ridge`),防近共线/近恒定深度锚导致 MKL SGELSY 秩亏崩溃。(下注:此条原写"无残留 blocker、可接手",被第四轮推翻——见第 10 条。)

10. **🔴 第四轮复核:B3 拉平量程后暴露的最深 blocker(B4)——L1 机制根本没被测(2026-06-23,同一审稿视角)**。这是"修复暴露下一层"的典型,也是最值得记的一条:
    - **病灶**:`_phase_configs` 的 L1 没给采样臂设 `t_schedule` → arm C/D 默认 `[T]` **单步**,循环只跑一次,`bake_geo_latent` 之后**骨干从未对烘焙后的 latent 再去噪**。而 §4.7 卖点"采样期注入经骨干先验把锚传播到无锚区"**恰恰需要烘焙后再去噪一步**(NFE≥2)才发生。单步下 arm C 退化成"额外 VAE 往返 + 双 affine",**Linchpin-1 测的是后处理复杂度,不是机制**。B3 之前因单位 bug 锁死 C 必输,这个更深的问题被掩盖;B3 拉平量程后才暴露。
    - **与立项卡的呼应**:reviewer 独立推出的修法 = 立项卡 §4.11 早已写下的 **B2(1 步加速 + 1 步几何近端细化)**;严格 1-NFE(B1)与 CCF 机制冲突,本就只能当冲刺目标。两处独立印证,B2 是立项前提。
    - **修复**:抽出统一采样例程 `_sample_relative_latent(bake)`,**arm C(bake=True)与 arm B'(bake=False)共用** → 同骨干/同 t_schedule/同 CCF/同 num_noise/同末步接地,唯一差异 = 采样期是否烘焙锚。L1 给采样臂 2 步机制 schedule `[T, T//2]`:第 1 步纯噪声端 CCF + 烘焙,第 2 步中段**重加噪→原生 Tweedie 去噪**(骨干传播锚),第 2 步用原生非 CCF 避开 e2eft 低 t 未标定区(M1)。**L1 机制测试主跑 Marigold**(DDIM 1–4 步天然支持),e2eft 多步属 off-distribution。顺带删 arm C 旧实现里被丢弃的 `d_s`(死 forward,曾虚增 NFE)。加 B4 回归自检(断言 L1 采样臂 schedule 长度 ≥2)。
    - **第二个一秒级证伪点(接 B3)**:真机在 L1 跑 arm C @ NFE=1 vs NFE=2。若 C 仅在 NFE≥2 才赢 B' → 机制(骨干重去噪传播)坐实;若 C 在 NFE=1 就赢 → 增益来自 VAE/双 affine 夹心而非机制,§4.7 故事被证伪,须改写 novelty。
    - **复核确认**:四轮对抗式审查后 8/8 自检通过。每轮都抓到真问题且严重度递减(2 blocker → 2 major → 1 blocker+1 major → 1 blocker)。(下注:本条原称"收敛、可接手",又被第五轮 B5 修正——B4 的多步修复在落地"重去噪"时引入了双重加噪;见第 11 条。)

11. **🔴 第五轮复核:B4 多步落地时引入双重加噪(B5,major)——机制被欠驱动 3.6×(2026-06-23)**。修复暴露下一层的又一例:
    - **病灶**:B4 的第 ≥2 步重去噪原写 `z_re=draw_z(x0); x0=_avg_x0_latent(z_re,...)`,而 `_avg_x0_latent` 在 `num_noise>1` 时把传入 latent 当**起点再加噪**——`z_re` 已是加噪态 → **加噪两次**。烘焙锚到达骨干的信号系数从预期 √ab 退化成 ab(t=499 处 0.28→0.078,**~3.6× 衰减**),且 driver 默认 `num_noise=4` **真机默认就走坏路径**。L0 不受影响(起点恒 `init_noise`);受影响的是 L1 采样臂与 L2——正是 §4.7 机制本体被测处。
    - **危害类型**:C 与 B' 同样被衰减,对照方向不翻(非 critical),但机制在严重欠驱动工作点被测,**有把"采样期注入"假阴性(C≈B')误判成"机制无用"的风险**——立项卡头号坑的反向版(把"没测到"当"没用")。
    - **为何瞒过前四轮**:`_MockBridge.draw_z` 用 `z0+0.01·randn`(非真实 √ab 加噪),双重加噪在 mock 上无可见后果。这是 mock 对"去噪动力学"类 bug 天然隐形的盲区。
    - **修复**:新增 `_renoise_denoise(x0_clean, t_s, ...)`——对**同一干净 x0** 做 `num_noise` 个独立"加噪一次→Tweedie"取平均(只加噪一次);第 ≥2 步改调它。`_avg_x0_latent` docstring 加"z0 必须是起点 latent"警告。加 **B5 回归**:用 z-敏感专用桩(真实 √ab 加噪 + 恒等 tweedie)断言重去噪信号系数 ≈√ab 且 num_noise=1/4 一致(双重加噪会让 nn>1 退化到 ab)。
    - **minor 同轮清**:eval `align_global_lstsq` 裸 lstsq → ridge + finite 兜底(CUDA 'gels' 秩亏防护);diag CSV 用 `align` 列标 frame(`b_ccf_geo`=unaligned,攻击腿随 align_affine),消除跨 frame 误比。
    - **收敛判定(五轮后)**:8/8 自检通过(B1–B5 全有回归守护)。五轮严重度单调递减(2blocker→2major→1b+1m→1blocker→1major+2minor),无新增高severity。残留仅文档级 caveat(e2eft 多步 off-distribution、bake 正反映射非严格互逆)。**可接手**。真机首跑按 cheapest-falsification 盯三点(见 §13 顶部)。

---

# 第二部分 · 执行层(2026-06-23 深挖新增)

> 上文 §0–7 是**决策与序列**;以下 §8–14 是**显卡服务器的操作手册**。原则不变:cheapest-falsification-first + 每 Phase 一个 GATE。新增价值 = 把三个 Linchpin/最毒攻击从"口号"落成**可跑代码 + 精确命令 + 判据数值化**。

## 8. 代码资产与目录

### 8.1 七个模块 + 一个 driver(全部本地 `_self_check` 跑通,无 GPU/权重)

| 脚本 | 角色 | 自检验证 | GPU 服务器改什么 |
|------|------|----------|------------------|
| `A2_ccf_depth_skeleton.py` | CCF→深度**机制核**(逻辑参照) | CCF 可达性 / 时间核退化 / 几何锚局部接地 | 不改,是 arm C 的逻辑蓝本 |
| `A2_geo_anchor.py` | **几何锚构造**(L1 命门:三臂同源) | 稀疏FPS / FPS>random / 地平面RANSAC / **锚一致性** / 尺寸锚 / 合并 | 真实 GT/内参替换合成场景 |
| `A2_eval_protocol.py` | **双协议评测**(真假米制命门) | 完美预测 / **假米制暴露** / lstsq闭式 / Garg crop / 80m cap / 指标方向 | 不改,直接调用 |
| `A2_baselines_postproc.py` | **L1 对照臂 A/B**(全局 / patch-affine) | 全局退化 / **patch>global** / 锚一致性 / patch锚点接地 | 不改 |
| `A2_diag_bias_var.py` | **L0 最毒攻击弹药**(bias-var 分解) | 恒等式 / 偏差还原 / arm_c降方差不降偏 / **恒偏攻击成立** / 变号偏差被纠 / 几何锚纠偏 | backbone 换真 Marigold |
| `A2_marigold_bridge.py` | **桥接**(stub→真实 diffusers) | **Tweedie三型还原x0** / init(zeros\|randn) / depth↔latent往返 / draw_z可复现 | `from_pretrained` 真加载 |
| `A2_failure_slices.py` | **失败模式切片**(CV 顶会硬要求) | 远距离退化 / 无锚衰减 / 反光失败 / 距离图 / 分桶守恒 | 真实语义掩膜替换合成 |
| `A2_run_grid.py` | **网格 driver**(执行入口) | L0/L1/L2 全 phase 流水线贯通,CSV 完整 | `--root` 指真数据集 |

> 验证全部自检一条命令:`cd a2 && for f in A2_ccf_depth_skeleton A2_geo_anchor A2_eval_protocol A2_baselines_postproc A2_diag_bias_var A2_marigold_bridge A2_failure_slices A2_run_grid; do python $f.py; done`
> 环境:`cd a2 && pip install -r requirements.txt`(torch 按服务器 CUDA 另装)。

### 8.2 建议目录结构

```
MDE/
├── docs/02_A2_experiments.md
├── a2/
│   ├── A2_*.py                # 七脚本 + driver(真实代码)
│   └── requirements.txt       # 依赖
├── data/                      # 数据集(GPU 服务器下载,见 §10)
│   ├── nyu/nyu_depth_v2_labeled.mat
│   ├── kitti/{eigen_test_files.txt, raw/, calib/}
│   ├── diode/val/  eth3d/  scannet/
├── weights/                   # 权重缓存(HF 自动下;离线则手动放)
├── runs/                      # results.csv 输出(driver 自动建)
│   ├── L0_nyu.csv  L1_nyu.csv  L2_nyu.csv  ...
└── analysis/                  # 汇总表/图(§12 脚本产出)
```

## 9. 三个 Linchpin 的精确臂定义(数值化判据)

> 立项卡 §4.8/§4.9 给了"赢什么";这里给"**怎么算赢**"——每个判据是 `results.csv` 上的一行比较,GATE 不靠手感。

### 9.1 L0 — OT 时间平滑非装饰(`--phase L0`,affine 协议)

| 臂 | driver 名 | 配置 | 隔离什么 |
|----|-----------|------|----------|
| a | `a_single` | 单点 x0,num_noise=1 | 基线(= E2E-FT 单步) |
| c | `c_multinoise` | 单点 x0,num_noise=N 平均 | **噪声维**重采样 |
| b | `b_ccf` | CCF 多时间点加权,num_noise=N | **时间维** OT 平均 |

- **判据(主)**:`AbsRel(b) < AbsRel(a)` 且 `AbsRel(b) < AbsRel(c)`,3 seed 均值差 > std。
- **判据(纠偏,§4.9 最毒攻击)**:`A2_diag_bias_var` 报 `|bias(b)| < |bias(c)|`(CCF 比重采样**额外纠偏**)。`verdict.attack_4_9_survives==False` 即攻击被反驳。
- **失败解读**:若 `c≈b`,增益来自重采样非 OT;若 `b≈a`,退化为 E2E-FT(§4.9 最毒攻击坐实)。

### 9.2 L1 — 米制非后处理能做(`--phase L1`,metric 协议,扫 K)

| 臂 | driver 名 | 基底 | 步数 | 接地 | 守哪侧 |
|----|-----------|------|------|------|--------|
| A | `A_postproc_global` | 单步 | 1 | 全局 scale+shift(2-DOF) | 下界 |
| B | `B_postproc_patch` | 单步 | 1 | patch-affine(AnchorD 式) | 便宜基线 |
| **B'** | `Bp_postproc_patch_ccf` | **CCF(同 C)** | **2** | patch-affine 后处理(不在采样期注入) | **单变量门槛** |
| C | `C_sample_geo_local` | CCF | **2** | 采样期烘焙锚(本工作) | — |
| D | `D_sample_geo_global` | CCF | 2 | = C 但 patch 网格退全局 | 消融"局部 patch" |

- **🔴 锚信息量公平性(B1,审稿头号坑)**:所有接地臂**共用唯一原语 `ground_to_metric`**,消费完全相同的锚信息。`--pin_anchors` 若开(CoSIGN 式硬约束),driver 保证**各臂同开同关**,对照仍单变量。默认关(纯拟合,零泄漏)。
- **🔴 多步机制测试(B4,round-4 复核发现单步退化)**:C/B'/D 跑 **2 步**(机制 schedule `[T, T//2]`,立项卡 §4.11 B2),因为 §4.7 卖点"采样期注入经骨干先验传播到无锚区"**需要烘焙后骨干再去噪一步**才发生;单步下 arm C 退化成"额外 VAE 往返 + 双 affine",机制根本没被测。C 与 B' **共用同一采样例程 `_sample_relative_latent`**,唯一差异 = `bake`(采样期是否注入锚)。第 2 步落 t≈T/2(M1-safe,避开 e2eft 低 t 未标定区);**L1 机制测试主跑 Marigold**(DDIM 1–4 步天然支持),e2eft 多步属 off-distribution。
- **🔴 两组对照(round-2 #2 修复,审稿复核发现 base predictor 混淆)**:
  - **C vs B'(单变量门槛)**:B' 与 C **同 CCF 基底、同 2 步采样、同末步接地**,唯一差异 = 几何锚在**采样期烘焙**(C,经第 2 步骨干传播到无锚区)还是**解码后一次性后处理**(B')。`AbsRel_metric(C) < AbsRel_metric(B')` 才**干净证明**"采样期注入 > 后处理"(§4.8 Linchpin-1 严谨判据)。
  - **C vs B(全系统对比)**:含 base predictor 差(CCF vs 单步),只证"整套管线 > 最便宜后处理基线",含基底功劳,不能单独支撑 Linchpin-1。
- **判据(Linchpin-1)**:`AbsRel_metric(C) < AbsRel_metric(B')`,**尤其在小 K**(K∈{1,2,4})。
- **🔴 机制证伪交叉验证(B4 推论)**:若 C 仅在 NFE≥2 时胜 B'、而 NFE=1 时 C≈B',则证增益来自"骨干重去噪传播锚"(§4.7 机制成立);若 NFE=1 时 C 已胜 B',则增益来自 VAE/双 affine 而非机制——故 L2 的 NFE 扫描同时是 §4.7 机制的直接证伪器。
- **机制性解释(比单个数字强)**:画 **K 阶梯曲线**(横轴 K,纵轴 metric AbsRel)。预期 C 的优势随 K 减小而**扩大**——锚越稀疏,骨干先验传播稀疏锚 vs patch-affine 在无锚 patch 退化的差距越大。曲线交叉点 = "采样期注入"的有效区间。
- **判据(D 消融,M3 已单变量化)**:arm D 保留完整 anchor(含地平面)、仅把 patch 网格退成 (1,1)。`C < D` → **局部 patch 拟合**真起作用(而非地平面锚的功);两因子已解耦。
- **⚠️ arm C 的两次烘焙角色(round-6 复核 caveat,归因须知)**:多步采样里 arm C 每步都烘焙锚,但两次角色不同——**非末步烘焙 = 传播**(经下一步骨干去噪扩散到无锚区,§4.7 卖点本体);**末步烘焙 = 注入**(保证锚进入,单步也有,故 L2 的 `nfe=1` 仍是合法"单步几何注入臂",不可删——删则破坏 Linchpin-2)。因此 `C<B'` 的增益里混了"末步那次不传播的注入 + VAE 往返"。要把增益**干净归因到"传播"**,可选增强:补一臂 `C_prop`(只非末步烘焙)对照 `C`,差值 = 末步注入之功。这是收紧归因、非纠错;标题结论 `C<B'`("采样期注入>后处理")不受影响(末步注入也是采样期注入)。
- **失败解读**:`C≈B'`(尤其大 K)→ 米制卖点死,退路见 §5。

### 9.3 L2 — 单步≈多步(`--phase L2`,metric 协议,扫 NFE)

- 同一臂 `C_sample_geo_local` 扫 NFE∈{1,2,4,8,…},画 **NFE 对齐曲线**。
- **🔴 真实 NFE(M4)**:CSV 的 `nfe` 列是 t_schedule 长度,`nfe_real` 列是 **UNet 实际 forward 次数**(CCF 每步取 2 时间点 ×num_noise,故 nfe_real ≫ nfe)。"单步卖点"的硬证据用 `nfe_real`,画曲线横轴也用它,否则被审稿人指"假单步"。
- **判据(Linchpin-2)**:`nfe_real`≤2 的 metric AbsRel 与高 NFE(8+)差距 <X%(X 投稿前定,建议 5%)。
- **退路**:若 NFE=1 崩但 NFE=2 平,退 **B2**(1–2 步,立项卡 §4.11)。

## 10. 数据获取(冒烟取数序,立项卡 §2.5)

按"无注册门槛优先"排序,GPU 服务器照此下载到 `data/`:

| 序 | 数据集 | 获取 | crop/cap | 角色 |
|----|--------|------|----------|------|
| 1 | **NYUv2** 测试 654 帧 | 单 `.mat` 2.8GB,`wget` 无注册 | NYU 官方 crop / 10m | **首选冒烟**(GATE-0 / Phase 1) |
| 2 | **DIODE** val | 官网直下无注册 | 含室外,逐篇核 | 次选(室内外) |
| 3 | **ETH3D** | ~5.5GB 直下 | 72m | 跨域 |
| 4 | **KITTI** Eigen 697 | 官网需注册;Kaggle 镜像可绕 | **Garg crop + 80m** | 室外主基准 |
| 5 | **ScanNet** | 机构邮箱申请审批 | 室内 | 最后处理 |

> NYU 内参已写进 `A2_run_grid._load_nyu`(fx=fy=518.86)。KITTI 逐帧 calib,`_load_kitti` 留接口待接。

## 11. 逐 Phase 精确命令(显卡服务器照抄)

```bash
# ---- Phase 0:环境 + 基线复现冒烟(2–3 天,零风险)----
cd a2
pip install -r requirements.txt
export LD_LIBRARY_PATH=/usr/lib/wsl/lib          # WSL cuDNN 坑(§13)
# 全脚本自检(无 GPU 也过)= 确认流水线逻辑未坏
for f in A2_ccf_depth_skeleton A2_geo_anchor A2_eval_protocol \
         A2_baselines_postproc A2_diag_bias_var A2_marigold_bridge \
         A2_failure_slices A2_run_grid; do
  python $f.py || { echo "FAIL $f"; exit 1; }
done
# 复现 E2E-FT 单步数(affine 协议):应得 NYU AbsRel≈5.2 / δ1≈96.6(±10% 为 GATE-0 PASS)
python A2_run_grid.py --phase L0 --backbone e2eft --dataset nyu \
    --root ../data/nyu --limit 654 --seeds 0 --out ../runs/P0_repro.csv

# ---- Phase 1:L0 + L1 联合证伪(第 1 周,最致命)----
# L0:CCF vs 单点 vs 多噪声(affine 协议),3 seed
python A2_run_grid.py --phase L0 --backbone e2eft --dataset nyu \
    --root ../data/nyu --seeds 0 1 2 --num_noise 4 --out ../runs/L0_nyu.csv
# L0 纠偏诊断(§4.9 最毒攻击 bias-var,真实 backbone 路径,B2 已接通):
python A2_run_grid.py --phase diag --backbone e2eft --dataset nyu \
    --root ../data/nyu --K 8 --seeds 0 1 2 --num_noise 4 --out ../runs/diag_nyu.csv
# (本地无 GPU 仅验仪器逻辑:python A2_diag_bias_var.py)
# L1:patch-affine 对照 vs 采样注入,扫 K 阶梯(metric 协议)
python A2_run_grid.py --phase L1 --backbone marigold --model_id prs-eth/marigold-depth-v1-1 --dataset nyu \
    --root ../data/nyu --K 1 2 4 8 16 32 --seeds 0 1 2 --out ../runs/L1_nyu.csv

# ---- Phase 2:L2 NFE 对齐曲线(第 2–3 周,仅 GATE-1 PASS 后)----
python A2_run_grid.py --phase L2 --backbone marigold --model_id prs-eth/marigold-depth-v1-1 --dataset nyu \
    --root ../data/nyu --nfe 1 2 4 8 16 --seeds 0 1 2 --out ../runs/L2_nyu.csv

# ---- Phase 3:主实验全基准 + 骨干无关性(第 4–6 周)----
for bb in e2eft marigold lotus; do
  for ds in nyu kitti eth3d diode; do
    python A2_run_grid.py --phase L1 --backbone $bb --dataset $ds \
        --root ../data/$ds --K 4 8 --seeds 0 1 2 --out ../runs/main_${bb}_${ds}.csv
  done
done
```

> **并行**:Phase 1–3 各 `(backbone×dataset×K×seed)` 组合相互独立,可拆成 N 个进程一夜刷完(立项卡 §6:不需训练、不需多卡通信)。

## 12. 结果汇总与判据(`analysis/`)

`results.csv` 字段:`backbone,dataset,phase,arm,sample_id,seed,K,nfe,nfe_real,protocol,align,absrel,rmse,log10,d1,d2,d3,align_gain,abs_bias,var,attack_survives`。

汇总(pandas 一行,GATE 自动判):
```python
import pandas as pd
df = pd.read_csv("../runs/L1_nyu.csv")
g = df.groupby(["arm","K"]).absrel.agg(["mean","std"])
# Linchpin-1 严谨判据:C 是否在小 K 优于同源后处理 B'
print(g.loc["C_sample_geo_local"] - g.loc["Bp_postproc_patch_ccf"])   # <0 即 C 赢
```

## 13. 已知坑(Phase 0 先排,立项卡 §6)

> **🔴🔴 接手后按此序做三个一秒级证伪点(cheapest-falsification,先于全网格)**:
> 1. **arm C 米制量程(B3)**:真机首跑 L1,`print(predC.min(), predC.max())` —— **必须落米制量程(NYU 0–10m),不能是 [0,1]**。arm C 末步 `decode_depth` 出相对深度,须经 `ground_to_metric` 接地才与 metric 协议 GT 同框(round-3 已修 + 回归断言)。若仍见 [0,1],L1 主表全废、且得"采样期注入=负贡献"反向错论。
> 2. **VAE 往返残差(M2)**:真 NYU 几帧跑 `bridge.vae_roundtrip_residual(gt_depth)`。>5% → arm C 每步 encode/decode 烘焙会被 VAE 噪声吃掉,机制在真权重上立不住,先于全网格暴露。改"latent 直接施锚"或"仅末步施锚"。
> 3. **L1 第 2 步真在动 + C vs B' 方向(B4/B5)**:L1 **主跑 Marigold**(e2eft 多步 off-distribution);打印 step-1 vs step-2 的 x0 latent 差范数 + `nfe_real`(应 ≈ 2×2×num_noise)。第 2 步几乎不动 = 机制没发生(B5 修后尤须复验)。再看 arm C @ NFE=1 vs NFE=2:仅 NFE≥2 才赢 B' → 机制坐实;NFE=1 就赢 → 增益来自 VAE/双 affine 夹心,§4.7 故事被证伪,须改写 novelty。`C≈B'` 现在是**可信真阴性**(B5 修后机制已在正确信号强度下被测),不再是双重加噪伪影。

- WSL `libcudnn_cnn_infer.so.8` 找不到 → `export LD_LIBRARY_PATH=/usr/lib/wsl/lib`
- Marigold 官方 bash 脚本 DOS 换行 → `dos2unix script/*.sh`
- 复现确定性 → `--batch_size 1` + 确定性模式;E2E-FT 必须 `noise=zeros, steps=1, ensemble=1`
- prediction_type **不要硬编码**:`A2_marigold_bridge` 从 `scheduler.config` 读(epsilon/v_prediction/sample),Marigold v1-1 是 v_prediction、E2E-FT 须实测
- E2E-FT 无 LICENSE 文件:投稿前须问作者授权(立项卡 §2.1)
- **🔴 NYU `.mat` 轴序坑(M5)**:labeled.mat 是 HDF5,h5py 读出轴序转置(`images[N,3,W,H]`)。`_load_nyu` 已加形状/范围断言(深度 >12m 即报错),轴序错会立即炸而非跑出离谱 AbsRel。
- **🔴 VAE 往返不保形(M2)**:arm C 每步 `decode→施加锚→encode`,真实 Marigold VAE `encode(decode(z))≠z`,会侵蚀几何锚注入的局部结构。Phase 0 必跑 `bridge.vae_roundtrip_residual(gt_depth)`;残差 >5% 则改"latent 直接施锚"或"仅末步施锚"。
- **metric 协议 clamp 表注(m2)**:`A2_eval_protocol.evaluate` 在 metric 协议也 `clamp(0,cap)`,会把爆掉的远点拉回 cap 内、隐性改善指标。主表表注须声明 clamp 策略;必要时报 clamp 前后两版。

## 14. Claim-Evidence 矩阵(投稿主张 ↔ 证据 ↔ 脚本)

| Claim | 审稿问题 | 证据(实验) | 脚本 | 协议/指标 | 状态 |
|-------|----------|--------------|------|-----------|------|
| ① OT 时间平滑迁深度有效(method 新意) | "不就是 x0 预测?" | L0 三臂:b>a 且 b>c | `A2_run_grid --phase L0` | affine AbsRel,3 seed | 待跑(已接通) |
| ①' OT 纠偏非仅降方差(§4.9 最毒) | "压方差≠纠偏" | bias-var:\|bias(b)\|<\|bias(c)\|,depth 空间 | `A2_run_grid --phase diag` | bias/var 分解 | 待跑(B2 已接通) |
| ② 采样期注入 > 后处理(米制) | "为何不后处理 patch-affine?" | L1:**C<B'**(同源 CCF 基底,单变量)+ K 阶梯曲线;C<B 为全系统对比 | `A2_run_grid --phase L1` | **metric** AbsRel | 待跑(已接通) |
| ②' 局部结构修正真起作用 | "全局缩放够了吗?" | L1:C<D 消融(D 保留地平面只退 grid) | `A2_run_grid --phase L1` | metric AbsRel | 待跑(已接通) |
| ③ 单步≈多步(单步卖点) | "单步扛得住引导?" | L2 NFE 对齐曲线,NFE≤2 ≈ 高 NFE | `A2_run_grid --phase L2` | metric AbsRel vs 真实 NFE | 待跑(已接通) |
| ④ 非假米制 | "其实是 affine 对齐?" | 双协议同表,metric 列不崩 | `A2_eval_protocol` | metric vs affine | 待跑(已接通) |
| ⑤ 骨干无关 | "只对 Marigold 成立?" | Marigold/Lotus/DepthFM 同趋势 | `A2_run_grid --backbone` | metric AbsRel | 待 GPU |
| ⑥ 边界诚实(失败带) | "什么时候失效?" | 透明反光/远距离/无锚衰减切片 | `A2_failure_slices` | per-slice AbsRel 退化倍数 | 待 GPU |

> **No-fabrication 声明**:本文件所有结果单元格均为"待 GPU"。脚本只产出真实数字到 `runs/*.csv`;`--mock` 路径明确标 `backbone=MOCK`,绝不冒充实验结论。立项阶段先用 oracle 锚(GT 采样)证机制,真实锚源(车牌/A4/地平面 EXIF)Phase 3 替换。

---

## 附:交付物清单(2026-06-23 更新)

**文档**
- `docs/02_A2_experiments.md`(本文件:§0–7 决策序列 + §8–14 执行层)
- `a2/requirements.txt`(GPU 服务器依赖)

**脚本(七个模块 + 一个 driver,全部 `_self_check` 跑通)**
- `A2_ccf_depth_skeleton.py` — CCF→深度机制核(CCF 可达性 / 时间核退化 / 几何锚局部接地)
- `A2_geo_anchor.py` — 几何锚构造,L1 锚一致性命门(6 项自检)
- `A2_eval_protocol.py` — metric/affine 双协议,假米制暴露(6 项自检)
- `A2_baselines_postproc.py` — L1 对照臂 A/B,patch-affine>global(4 项自检)
- `A2_diag_bias_var.py` — L0 最毒攻击 bias-var 分解(6 项自检)
- `A2_marigold_bridge.py` — stub→真实 diffusers,Tweedie 三型还原(4 项自检)
- `A2_failure_slices.py` — 失败模式切片(透明反光/远距离/无锚衰减),CV 顶会硬要求(5 项自检)
- `A2_run_grid.py` — 网格 driver,L0/L1/L2/diag 全 phase 贯通(diag = §4.9 最毒攻击 bias-var)

**GPU 服务器接手清单**(改三处即真跑):
1. `cd a2 && pip install -r requirements.txt` + torch(按 CUDA)
2. 下载 `data/nyu/...`(§10 序 1,无注册)
3. 冒烟:`python A2_run_grid.py --phase L1 --mock`(无 GPU 验证流水线;输出标 `backbone=MOCK`)
4. 真跑:`python A2_run_grid.py --phase L1 --backbone marigold --model_id prs-eth/marigold-depth-v1-1 --dataset nyu --root ../data/nyu --K 1 2 4 8 --seeds 0 1 2 --out ../runs/L1_nyu.csv`
5. 第 1 周 GATE-1 三连:`--phase L0`(method 新意)+ `--phase diag`(最毒攻击纠偏)+ `--phase L1`(米制),红灯即按 §5 退路矩阵止损
