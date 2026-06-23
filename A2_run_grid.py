"""
A② 网格 driver —— GPU 服务器执行入口
=================================================================
串联全部模块,把 (backbone × 臂 × seed × 数据集 × K) 网格刷成 results.csv。
  · 几何锚    A2_geo_anchor          (锚一致性:三臂同源)
  · 后处理臂  A2_baselines_postproc  (L1 臂A/B)
  · 采样机制  A2_ccf_depth_skeleton  (L0/L1 臂C/D 的 CCF + 几何烘焙逻辑)
  · 桥接      A2_marigold_bridge     (真实 Marigold/E2E-FT)
  · 评测      A2_eval_protocol       (metric/affine 双协议)
  · 诊断      A2_diag_bias_var       (L0 最毒攻击 bias-var)

用法(GPU 服务器):
  # Phase 1 L1:patch-affine 对照 vs 采样期注入,扫 K 阶梯
  python A2_run_grid.py --phase L1 --backbone e2eft --dataset nyu \\
      --K 1 2 4 8 16 32 --seeds 0 1 2 --out runs/L1_nyu.csv
  # Phase 1 L0:CCF vs 单点 x0 vs 多噪声,三 seed
  python A2_run_grid.py --phase L0 --backbone e2eft --dataset nyu \\
      --seeds 0 1 2 --out runs/L0_nyu.csv
  # Phase 2 L2:NFE 对齐曲线
  python A2_run_grid.py --phase L2 --backbone e2eft --dataset nyu \\
      --nfe 1 2 4 8 --out runs/L2_nyu.csv

无 GPU 验证流水线(本地秒级,不下权重):
  python A2_run_grid.py --mock          # 跑全 phase 的合成自检,校验 CSV 完整性

🔴 真实机制决策(latent/depth 空间切换,写进 §4.7):
  CCF 在 latent 空间走;几何锚是 depth 空间米制约束。arm C 必须:
    decode(z+u)→d_rel → ground 成米制 → 支撑区软投影纠偏 → 回 relative → encode → latent 修正量
  本文件 bake_geo_latent() 实现这一往返;skeleton.bake_geo_anchor 是其空间无关的逻辑参照。
"""
import argparse
import csv
import os
import torch

from A2_geo_anchor import (sample_sparse_oracle, ground_plane_anchor,
                           merge_anchors, _ray_dirs)
from A2_baselines_postproc import (ground_global_affine, ground_patch_affine,
                                   ground_to_metric, solve_affine_ridge)
from A2_eval_protocol import evaluate, dual_protocol_report, DATASET_CAP


# ===========================================================================
# 几何锚的 latent-空间烘焙(arm C 的真实实现,非 stub)
# ===========================================================================
def bake_geo_latent(bridge, z_latent, u_latent, anchor, ground_grid=(4, 4),
                    pin_anchors=False, pin_weight=1.0):
    """把 depth 空间的几何锚烘焙成 latent 修正量。返回新的 u(含几何方向)。
    流程(§4.7 latent/depth 空间切换):
      1. d_rel = decode(z+u)               当前等效落点(相对深度 [0,1])
      2. d_metric = ground_to_metric        🔴 与 arm B 共用唯一接地原语(B1 修复:锚信息量一致)
      3. d_rel' = (d_metric - t)/s          回相对域(用全局 s,t 反映射)
      4. u_geo = encode(d_rel') - z         latent 修正量

    🔴 B1 修复(2026-06-23):此前 arm C 在 ground_patch_affine 之外**额外**把锚真值软投影进支撑区,
       而 arm B 没有 → arm C 偷看答案,L1 对照不公平(立项卡头号坑复发)。
       现在 arm B/C 都走 ground_to_metric(pin_anchors 同值),锚信息量一致。
       🔴 round-2 #2 补:与 arm B' (B_postproc_patch_ccf, 同源 CCF 基底) 相比,arm C 唯一差异
       = 几何锚施加位置(采样期烘焙 + decode→encode 往返传播到无锚区 vs 解码后一次性后处理)。
       这才是 §4.7 卖点本体的**干净单变量**对照(C-vs-B');C-vs-B 含 base predictor 差,是全系统对比。
       pin_anchors 默认 False(纯拟合,零泄漏);若 driver 开,则各臂同开。
    """
    d_rel = bridge.decode_depth(z_latent + u_latent)         # [B,1,H,W]∈[0,1]
    B = d_rel.shape[0]
    out_u = u_latent.clone()
    for b in range(B):
        dr = d_rel[b, 0]
        d_metric = ground_to_metric(dr, anchor, grid=ground_grid, use_dense=True,
                                    pin_anchors=pin_anchors, pin_weight=pin_weight)
        # 回相对域:用全局 affine 反映射(s,t 来自锚的全局拟合)
        s, t = _global_affine_params(dr, anchor)
        d_rel_corr = (d_metric - t) / s.clamp(min=1e-6)
        d_rel_corr = d_rel_corr.clamp(0.0, 1.0).unsqueeze(0).unsqueeze(0)
        z_corr = bridge.encode_depth(d_rel_corr)
        out_u[b] = z_corr[0] - z_latent[b]
    return out_u


def _global_affine_params(d_rel, anchor):
    """从锚拟合全局 s,t(供 latent 烘焙的相对↔米制反映射)。
    🔴 round-3:用 ridge 解(solve_affine_ridge)防秩亏崩溃。"""
    uv, d = anchor.to_sparse_constraints(include_dense=True)
    if uv.shape[0] < 2:
        return torch.tensor(1.0), torch.tensor(0.0)
    pv = d_rel[uv[:, 1], uv[:, 0]]
    return solve_affine_ridge(pv, d)


# ===========================================================================
# 单步骨干前向 → 相对深度(L0 的结构层,affine-invariant)
# ===========================================================================
def predict_relative(bridge, image, t_s=None, use_ccf=False, t_delta=None,
                     num_noise=1, seed=0):
    """单步(或 CCF 时间加权)出相对深度 [0,1]。
    use_ccf=False, num_noise=1 → arm_a 单点 x0
    use_ccf=False, num_noise=N → arm_c 多噪声平均
    use_ccf=True              → arm_b CCF 多时间点加权
    """
    cond = bridge.encode_cond(image)
    z = bridge.init_noise(image)
    T = len(bridge.alphas_cumprod) - 1
    t_s = T if t_s is None else t_s
    t_delta = (T * 0.5) if t_delta is None else t_delta

    if use_ccf:
        d_s = _avg_x0_latent(bridge, z, t_s, cond, num_noise, seed)
        d_s0 = _avg_x0_latent(bridge, z, max(t_s - t_delta, 0), cond, num_noise, seed + 7)
        denom = t_s + t_delta
        x0_lat = (t_delta * d_s + t_s * d_s0) / denom if denom > 1e-6 else d_s
    else:
        x0_lat = _avg_x0_latent(bridge, z, t_s, cond, num_noise, seed)
    return bridge.decode_depth(x0_lat)


def _avg_x0_latent(bridge, z0, t, cond, num_noise, seed_base):
    """num_noise 个噪声实现的 Tweedie x0(latent)平均。num_noise=1 即纯单点。
    ⚠️ 语义:z0 是【起点 latent】(纯噪声端或 init_noise)。num_noise=1 时直接对 z0 投影;
       num_noise>1 时对 z0 **再加噪**取多实现平均。**不要**把"已是干净 x0、需重去噪一步"的
       latent 喂进来——那会被当起点再加噪,造成双重加噪(round-5 B5 坑)。重去噪走 _renoise_denoise。"""
    if num_noise == 1:
        return bridge.tweedie_x0(z0, t, cond)
    acc = 0.0
    for k in range(num_noise):
        z = bridge.draw_z(z0, t, seed_base * 100 + k)
        acc = acc + bridge.tweedie_x0(z, t, cond)
    return acc / num_noise


def _renoise_denoise(bridge, x0_clean, t_s, cond, num_noise, seed_base):
    """把【干净】x0 重加噪到 t_s 再原生去噪。多步采样第 ≥2 步专用(§4.7 机制本体)。
    🔴 round-5 B5 修复:此前先 draw_z(x0)→z_re,再把 z_re 喂 _avg_x0_latent,
       而后者 num_noise>1 会**再次** draw_z(z_re) → 双重加噪。烘焙锚到达骨干的信号系数从
       预期 √ab 退化成 ab(t=499 处 0.28→0.078,~3.6× 衰减),机制被严重欠驱动。
       正解:对**同一个干净 x0** 做 num_noise 个独立"再加噪→Tweedie"实现取平均(只加噪一次)。
    """
    acc = 0.0
    for k in range(num_noise):
        z_re = bridge.draw_z(x0_clean, t_s, seed_base * 100 + k)   # 干净 x0 → t_s,仅一次
        acc = acc + bridge.tweedie_x0(z_re, t_s, cond)
    return acc / num_noise


# ===========================================================================
# 臂注册:每臂 (bridge, sample, anchor, cfg) → metric_depth [H,W]
# ===========================================================================
def _relative_for_arm(bridge, sample, cfg, use_ccf):
    """统一的相对深度基底。🔴 round-2 #2 修复:让后处理臂能与采样臂取**同源**相对深度,
    把 L1 的 base predictor 从对照里消掉。use_ccf=False → 单步单噪(便宜基线);
    use_ccf=True → 与 arm C 同源的 CCF 多噪多时点基底。"""
    return predict_relative(bridge, sample["image"], use_ccf=use_ccf,
                            num_noise=(cfg.get("num_noise", 4) if use_ccf else 1),
                            t_delta=cfg.get("t_delta", None),
                            seed=cfg.get("seed", 0))[0, 0]


def arm_postproc_global(bridge, sample, anchor, cfg):
    dr = _relative_for_arm(bridge, sample, cfg, use_ccf=False)
    return ground_global_affine(dr, anchor, use_dense=True)


def arm_postproc_patch(bridge, sample, anchor, cfg):
    """arm B:后处理 patch-affine(单步单噪基底,便宜基线)。
    🔴 B1 修复:走 ground_to_metric(与 arm C 同一接地原语,pin_anchors 同值 → 锚信息量一致)。
    ⚠️ 与 arm C 的 base predictor 不同(单步 vs CCF)→ B-vs-C 是**全系统**对比。
       纯"注入位置"单变量对照见 arm B'(B_postproc_patch_ccf)。"""
    dr = _relative_for_arm(bridge, sample, cfg, use_ccf=False)
    return ground_to_metric(dr, anchor, grid=cfg.get("grid", (4, 4)), use_dense=True,
                            pin_anchors=cfg.get("pin_anchors", False),
                            pin_weight=cfg.get("pin_weight", 1.0))


def arm_postproc_patch_ccf(bridge, sample, anchor, cfg):
    """arm B':patch-affine 后处理,作用在**与 arm C 逐位匹配的 CCF 多步相对深度**上。
    🔴 round-2 #2 + round-4 B4 修复:C 与 B' 共享同一采样例程 `_sample_relative_latent`,
       唯一差异 = `bake`(B'=False 不在采样期注入锚,只末步后处理;C=True 采样期烘焙 + 骨干重去噪)。
       同骨干、同 t_schedule、同 CCF、同 num_noise、同末步 ground_to_metric → Linchpin-1 **干净单变量**。
    判据:C < B' 才证"采样期注入 > 后处理"。C < B 只证"全系统更好"(含 CCF 多步基底之功)。"""
    d_rel = _sample_relative_latent(bridge, sample, cfg, anchor=anchor, bake=False)
    return ground_to_metric(d_rel, anchor, grid=cfg.get("grid", (4, 4)), use_dense=True,
                            pin_anchors=cfg.get("pin_anchors", False),
                            pin_weight=cfg.get("pin_weight", 1.0))


def _sample_relative_latent(bridge, sample, cfg, anchor=None, bake=False):
    """统一的(多步)CCF 采样 → 相对深度 [0,1]。arm C(bake=True)与 arm B'(bake=False)共用。
    🔴 round-4 B4 修复:§4.7 卖点"采样期注入经骨干先验传播到无锚区"**需要烘焙后再去噪一步**
       才发生。此前 L1 单步(schedule=[T]),骨干从不重处理烘焙 latent → 机制根本没被测,
       arm C 退化成"额外 VAE 往返 + 双 affine"。现在:
         第 1 步(纯噪声端 t=T):CCF 多时间点出 x0,(bake 则)烘焙锚;
         第 ≥2 步(中段 t):把上一步 x0 **重加噪到 t_s 再原生去噪**(骨干传播锚到无锚区),
                            (bake 则)再烘焙。第 ≥2 步用**原生 Tweedie 非 CCF**,
                            避开 e2eft 低 t 未标定区(M1)。
       这正是立项卡 §4.11 B2(1 步加速 + 1 步几何近端细化)的落地。"""
    cond = bridge.encode_cond(sample["image"])
    z = bridge.init_noise(sample["image"])
    schedule = cfg.get("t_schedule", [len(bridge.alphas_cumprod) - 1])
    nn = cfg.get("num_noise", 4)
    seed = cfg.get("seed", 0)
    x0 = None
    for i, t_s in enumerate(schedule):
        if i == 0:
            x0 = _ccf_u(bridge, z, t_s, cfg, cond) if cfg.get("use_ccf", True) \
                else _avg_x0_latent(bridge, z, t_s, cond, nn, seed)
        else:
            # 把【干净】x0 重加噪到 t_s 再原生去噪(num_noise 个再加噪实现取平均)
            x0 = _renoise_denoise(bridge, x0, t_s, cond, nn, seed + 100 * i)
        if bake:
            x0 = _bake_x0(bridge, x0, anchor, cfg)              # 烘焙锚 → 下一步骨干会传播它
    return bridge.decode_depth(x0)[0, 0]                         # 相对域 [0,1]


def _bake_x0(bridge, x0, anchor, cfg):
    """把几何锚烘焙进一个 x0 latent,返回烘焙后的 x0 latent(复用 bake_geo_latent)。"""
    zeros = torch.zeros_like(x0)
    u = bake_geo_latent(bridge, zeros, x0, anchor,
                        ground_grid=cfg.get("grid", (4, 4)),
                        pin_anchors=cfg.get("pin_anchors", False),
                        pin_weight=cfg.get("pin_weight", 1.0))
    return zeros + u                                            # = 烘焙后的 x0


def arm_sample_geo_local(bridge, sample, anchor, cfg):
    """arm C:采样期几何锚注入(局部锚)。多步 CCF 采样 + 每步烘焙锚 + 末步接地。
    🔴 B1 修复:bake_geo_latent 与 arm B 共用 ground_to_metric,pin_anchors 同值 → 锚信息量一致。
    🔴 B3 修复(round-3):latent 是 affine-invariant **相对**域,decode 恒 [0,1];末步补 ground_to_metric,
       与 arm B' 同原语收尾 → 单位一致。
    🔴 B4 修复(round-4):用 `_sample_relative_latent(bake=True)` 多步采样,使骨干在烘焙后**重去噪一步**,
       §4.7"采样期注入传播到无锚区"机制才真正发生。C-vs-B'(bake=False)= 干净单变量(唯一差异=采样期是否烘焙)。
    """
    d_rel = _sample_relative_latent(bridge, sample, cfg, anchor=anchor, bake=True)
    return ground_to_metric(d_rel, anchor, grid=cfg.get("grid", (4, 4)), use_dense=True,
                            pin_anchors=cfg.get("pin_anchors", False),
                            pin_weight=cfg.get("pin_weight", 1.0))


def arm_sample_geo_global(bridge, sample, anchor, cfg):
    """arm D:= C 但 patch 网格退化为全局(消融'局部 patch 拟合'是否起作用)。
    🔴 M3 修复(2026-06-23):此前 arm D 同时丢掉地平面稠密锚 + 退 grid,改了两个变量,
       无法归因。现在**保留完整 anchor(含地平面)**,仅把 grid→(1,1),单变量消融"局部 patch"。
    """
    cfg2 = dict(cfg); cfg2["grid"] = (1, 1)               # 单 patch = 全局拟合(锚不变)
    return arm_sample_geo_local(bridge, sample, anchor, cfg2)


def _ccf_u(bridge, z, t_s, cfg, cond):
    """CCF 时间加权 u_hat。🔴 M1 修复:对 e2eft 骨干断言第二时间点不离 trailing 标定点太远。"""
    T = len(bridge.alphas_cumprod) - 1
    t_delta = cfg.get("t_delta", T * 0.5)
    t_s0 = max(t_s - t_delta, 0)
    # e2eft 单步只在 t≈T 标定;CCF 第二点过低会落在未标定区 → 警告(不硬停,留给真机判断)
    if cfg.get("backbone_mode") == "e2eft" and t_s0 < T * 0.3:
        cfg.setdefault("_warned_tdelta", False)
        if not cfg["_warned_tdelta"]:
            print(f"  [WARN] e2eft CCF 第二时间点 t_s0={t_s0:.0f} < 0.3T,可能落在未标定区"
                  f"(M1:CCF 在 e2eft 上的合法性存疑,见 §4.9)")
            cfg["_warned_tdelta"] = True
    d_s = _avg_x0_latent(bridge, z, t_s, cond, cfg.get("num_noise", 4), cfg.get("seed", 0))
    d_s0 = _avg_x0_latent(bridge, z, t_s0, cond,
                          cfg.get("num_noise", 4), cfg.get("seed", 0) + 7)
    denom = t_s + t_delta
    return (t_delta * d_s + t_s * d_s0) / denom if denom > 1e-6 else d_s


# L0 臂:出相对深度,affine 协议评(隔离 method 新意)
def arm_L0_single(bridge, sample, anchor, cfg):
    return predict_relative(bridge, sample["image"], use_ccf=False, num_noise=1)[0, 0]


def arm_L0_multinoise(bridge, sample, anchor, cfg):
    return predict_relative(bridge, sample["image"], use_ccf=False,
                            num_noise=cfg.get("num_noise", 4))[0, 0]


def arm_L0_ccf(bridge, sample, anchor, cfg):
    return predict_relative(bridge, sample["image"], use_ccf=True,
                            num_noise=cfg.get("num_noise", 4),
                            t_delta=cfg.get("t_delta", None))[0, 0]


PHASE_ARMS = {
    "L0": {  # OT 不是装饰(affine 协议)
        "a_single": arm_L0_single,
        "c_multinoise": arm_L0_multinoise,
        "b_ccf": arm_L0_ccf,
    },
    "L1": {  # 米制非后处理能做(metric 协议)
        "A_postproc_global":     arm_postproc_global,       # 下界:全局 2-DOF
        "B_postproc_patch":      arm_postproc_patch,        # 门槛:单步基底 + patch-affine(AnchorD 式,便宜基线)
        "Bp_postproc_patch_ccf": arm_postproc_patch_ccf,    # 🔴 round-2 #2:同 C 的 CCF 基底 + patch-affine 后处理
        "C_sample_geo_local":    arm_sample_geo_local,      # 本工作:CCF 基底 + 采样期注入
        "D_sample_geo_global":   arm_sample_geo_global,     # 消融:C 但 grid→全局
    },
}
# L1 两组对照(round-2 #2 修复后):
#   · 全系统对比:C vs B(本工作 vs 最便宜的后处理基线)——回答"整套管线值不值"
#   · 纯注入位置消融:C vs Bp(同 CCF 基底,唯一差异=采样期注入 vs 后处理)——回答"采样期注入本身的功"
#   §4.8 Linchpin-1 的严谨判据是 C<Bp(单变量),C<B 只是顺带的全系统证据。
# L2 在 phase 逻辑里特殊处理(NFE 扫描),复用 arm_sample_geo_local 改 t_schedule 长度


# ===========================================================================
# 数据层:mock 合成 + 真实 NYU/KITTI loader
# ===========================================================================
def load_samples(dataset, root=None, limit=None, mock=False):
    """yield dict(image[1,3,H,W], depth_gt[H,W], valid[H,W], intrinsics, id)。"""
    if mock:
        yield from _mock_samples(limit or 3)
        return
    if dataset == "nyu":
        yield from _load_nyu(root, limit)
    elif dataset == "kitti":
        yield from _load_kitti(root, limit)
    else:
        raise NotImplementedError(f"数据集 {dataset} loader 待 GPU 服务器按 §数据 接入")


def _mock_samples(n):
    """合成倾斜地平面场景。明确标 MOCK,绝不冒充真实数字。"""
    torch.manual_seed(0)
    H, W = 48, 64
    fx = fy = 50.0
    intr = (fx, fy, W / 2.0, H / 2.0)
    for i in range(n):
        n_true = torch.tensor([0.05 * i, -0.85, -0.2]); n_true = n_true / n_true.norm()
        r = _ray_dirs(H, W, intr)
        ndotr = (r * n_true).sum(-1).clamp_min(1e-6)
        depth = torch.clamp(-(3.0 + i) / ndotr, 0.5, 10.0)
        img = depth.unsqueeze(0).unsqueeze(0).repeat(1, 3, 1, 1) / 10.0
        yield {"image": img, "depth_gt": depth, "valid": torch.ones(H, W),
               "intrinsics": intr, "id": f"mock_{i}"}


def _load_nyu(root, limit):
    """NYUv2 测试集 654 帧(单 .mat,wget 无注册 → 首选冒烟)。
    🔴 M5 修复(2026-06-23):labeled.mat 是 MATLAB v7.3(HDF5),h5py 读出**轴序转置**。
       实际结构:images[N,3,640,480](即 [N,C,W,H]),depths[N,640,480](即 [N,W,H])。
       故 img 需 permute(0,2,1) 把 (C,W,H)→(C,H,W),depth 需 .t() 把 (W,H)→(H,W)。
       加形状/范围断言,轴序错会立即报错而非跑出离谱 AbsRel(GATE-0 第一道断点)。
    内参用 NYU 官方:fx=fy=518.8579, cx=325.58, cy=253.74(640×480)。
    """
    import h5py
    import numpy as np
    f = h5py.File(os.path.join(root, "nyu_depth_v2_labeled.mat"), "r")
    images = f["images"]; depths = f["depths"]
    N = images.shape[0] if limit is None else min(limit, images.shape[0])
    intr = (518.8579, 518.8579, 325.5824, 253.7362)
    # 形状自检:轴序错 = GATE-0 第一坑,提前炸
    assert images.shape[1] == 3, f"NYU images 通道轴异常: {images.shape}(期望 [N,3,W,H])"
    for i in range(N):
        img = torch.from_numpy(np.array(images[i]).astype("float32") / 255.0)
        img = img.permute(0, 2, 1).unsqueeze(0)               # (3,W,H)→(1,3,H,W)
        depth = torch.from_numpy(np.array(depths[i]).astype("float32")).t()  # (W,H)→(H,W)
        assert img.shape[-2:] == depth.shape[-2:], \
            f"NYU 第{i}帧 img/depth 空间尺寸不一致: {img.shape} vs {depth.shape}(轴序坑)"
        # 范围自检:NYU 深度应落 (0,10]m;轴序/单位错会越界
        dvalid = depth[depth > 1e-3]
        if dvalid.numel() > 0:
            assert dvalid.max() <= 12.0, \
                f"NYU 第{i}帧深度 max={dvalid.max():.1f}m 越界(>12m),疑轴序/单位错"
        valid = (depth > 1e-3) & (depth < 10.0)
        yield {"image": img, "depth_gt": depth, "valid": valid.float(),
               "intrinsics": intr, "id": f"nyu_{i}"}


def _load_kitti(root, limit):
    """KITTI Eigen 697(Garg crop + 80m)。ponytail: GPU 服务器接 Eigen split 文件列表。
    内参逐帧从 calib 读(fx 因序列而异),此处留接口。
    """
    raise NotImplementedError("KITTI loader:GPU 服务器按 Eigen split + calib 逐帧接入")


# ===========================================================================
# 锚构造(三臂同源,L1 公平性命门)
# ===========================================================================
def build_anchor(sample, K, use_ground_plane=True, seed=0):
    """构造该样本的 AnchorSet。oracle 稀疏 K 点 + 可选地平面稠密。三臂共用。"""
    parts = [sample_sparse_oracle(sample["depth_gt"], sample["valid"], K,
                                  method="fps", seed=seed)]
    if use_ground_plane:
        gp = ground_plane_anchor(sample["depth_gt"], sample["valid"],
                                 sample["intrinsics"], seed=seed)
        if gp.dense_mask is not None:
            parts.append(gp)
    return merge_anchors(parts) if len(parts) > 1 else parts[0]


# ===========================================================================
# 主循环:网格 → CSV
# ===========================================================================
CSV_FIELDS = ["backbone", "dataset", "phase", "arm", "sample_id", "seed", "K",
              "nfe", "nfe_real", "protocol", "align", "absrel", "rmse", "log10",
              "d1", "d2", "d3", "align_gain",
              "abs_bias", "var", "attack_survives"]   # 末三列:B2 诊断(仅 diag phase 填)


def run_grid(args, bridge):
    if args.phase == "diag":
        return run_diag(args, bridge)                 # B2:最毒攻击诊断独立路径
    rows = []
    dataset = "mock" if args.mock else args.dataset
    protocol = "affine" if args.phase == "L0" else "metric"   # L0 看结构,L1/L2 看米制

    for sample in load_samples(dataset, args.root, args.limit, mock=args.mock):
        Ks = args.K if args.phase in ("L1",) else [args.K[0] if args.K else 8]
        for K in Ks:
            anchor = build_anchor(sample, K, use_ground_plane=(args.phase != "L0"))
            for seed in args.seeds:
                cfgs = _phase_configs(args, seed)
                for arm_name, arm_fn, cfg, nfe in cfgs:
                    _reset_nfe(bridge)                # M4:清零 UNet forward 计数
                    try:
                        pred = arm_fn(bridge, sample, anchor, cfg)
                    except Exception as e:
                        rows.append(_row(args, dataset, arm_name, sample["id"],
                                         seed, K, nfe, _get_nfe(bridge), protocol,
                                         "ERR", {"absrel": float("nan")}, float("nan")))
                        print(f"  [ERR] {arm_name} @ {sample['id']}: {e}")
                        continue
                    nfe_real = _get_nfe(bridge)       # M4:真实 forward 次数
                    m, align = evaluate(pred, sample["depth_gt"], dataset,
                                        protocol=protocol)
                    gain = float("nan")
                    if protocol == "metric":
                        rep = dual_protocol_report(pred, sample["depth_gt"], dataset)
                        gain = rep["align_gain_absrel"]
                    rows.append(_row(args, dataset, arm_name, sample["id"], seed,
                                     K, nfe, nfe_real, protocol, align, m, gain))
    _report_errors(rows)                              # m1:ERR 行超阈值显式失败
    return rows


# ===========================================================================
# B2 修复(2026-06-23):最毒攻击 bias-variance 诊断 —— 真实 backbone 可执行路径
#   此前 A2_diag_bias_var.diagnose() 从未被调用,①' 是"待实现"而非"待 GPU"。
#   现在:truth = encode_depth(GT 深度) 当干净 latent x0,真实跑三臂分解写 CSV。
# ===========================================================================
def run_diag(args, bridge):
    from A2_diag_bias_var import diagnose
    rows = []
    dataset = "mock" if args.mock else args.dataset
    T = len(bridge.alphas_cumprod) - 1
    t_s = int(T)
    t_delta = args.t_delta if getattr(args, "t_delta", None) else T * 0.5
    for sample in load_samples(dataset, args.root, args.limit, mock=args.mock):
        K = args.K[0] if args.K else 8
        anchor = build_anchor(sample, K, use_ground_plane=True)
        cond = bridge.encode_cond(sample["image"])
        # 🔴 B2:truth 在 depth 空间(§4.9 偏差是米制偏差,非 latent 偏差)
        dg = sample["depth_gt"]
        dmin, dspan = dg.min(), (dg.max() - dg.min() + 1e-6)
        truth_depth = (dg - dmin) / dspan                 # [H,W]∈[0,1]
        z0 = bridge.init_noise(sample["image"])
        # 🔴 round-2 #1 修复:geo 锚 tgt 原为米制,须用与 truth_depth **同一** min-max
        #    归一化到 [0,1],否则米制值塞进 [0,1] 场 → geo 腿恒判失败(单位不一致 bug)。
        mask_geo, tgt_geo = anchor.to_field(sigma_px=2.0)
        tgt_geo = (tgt_geo - dmin) / dspan                # 米制 → [0,1] 同 frame
        geo = (mask_geo, tgt_geo)
        res = diagnose(bridge, z0, truth_depth, t_s, t_delta, cond,
                       geo_anchor=geo, seeds=range(max(len(args.seeds) * 8, 16)),
                       num_noise=args.num_noise,
                       eval_space=getattr(bridge, "decode_depth", None),
                       align_affine=not args.mock)        # 真机开 #3 affine 对齐,mock 关
        for arm, dec in res["decomp"].items():
            r = _blank_row(args, dataset, arm, sample["id"])
            # 🔴 round-4 minor:用 align 列标 frame,避免攻击腿(对齐)与几何腿(未对齐)
            #    在同列被跨 frame 误比。几何腿 b_ccf_geo 始终未对齐(#3-bis),其余随 align_affine。
            frame = "unaligned" if arm == "b_ccf_geo" else \
                    ("aff_aligned" if not args.mock else "unaligned")
            r.update({"align": frame, "abs_bias": dec["abs_bias"], "var": dec["var"],
                      "absrel": dec.get("rmse", float("nan")),
                      "attack_survives": int(res["verdict"]["attack_4_9_survives"])})
            rows.append(r)
        print(f"  [diag {sample['id']}] attack_survives="
              f"{res['verdict']['attack_4_9_survives']} "
              f"Δbias(c-b)={res['verdict']['delta_absbias_c_minus_b']:.4f} "
              f"geo_corrects={res['verdict'].get('geo_corrects_bias')}")
    return rows


def _phase_configs(args, seed):
    """返回 [(arm_name, fn, cfg, nfe), ...]。L2 特殊:同一臂扫 NFE。"""
    mode = "e2eft" if args.backbone == "e2eft" else "marigold"
    common = {"num_noise": args.num_noise, "seed": seed, "use_ccf": True,
              "pin_anchors": args.pin_anchors, "pin_weight": args.pin_weight,
              "backbone_mode": mode}
    if args.phase == "L2":
        T = 999
        out = []
        for nfe in args.nfe:
            sched = _nfe_schedule(T, nfe)
            cfg = dict(common); cfg["t_schedule"] = sched
            out.append((f"C_nfe{nfe}", arm_sample_geo_local, cfg, nfe))
        return out
    arms = PHASE_ARMS[args.phase]
    # 🔴 B4 修复:L1 采样臂(C/D/B')须多步,骨干才会重去噪烘焙后的 latent(§4.7 机制);
    #    后处理臂(A/B)无采样,保持单步。机制 schedule = [T, T//2](第 2 步 t≈499,M1-safe,
    #    不落 e2eft 低 t 未标定区)。这正是立项卡 §4.11 B2(1 步加速 + 1 步几何近端细化)。
    sampling_arms = {"C_sample_geo_local", "D_sample_geo_global", "Bp_postproc_patch_ccf"}
    T = 999                                                   # diffusion 标准步数(bridge alphas_cumprod 长 1000)
    out = []
    for name, fn in arms.items():
        cfg = dict(common)
        if args.phase == "L1" and name in sampling_arms:
            cfg["t_schedule"] = _mechanism_schedule(T)       # 2 步(B2)
            nfe = 2
        else:
            nfe = 1
        out.append((name, fn, cfg, nfe))
    return out


def _mechanism_schedule(T):
    """L1 机制测试 schedule:[T, T//2]。第 1 步纯噪声端 CCF + 烘焙,第 2 步中段重去噪传播锚。
    🔴 B4:第 2 步落 t≈T/2(非近 0),既给骨干重处理空间,又避开 e2eft 低 t 未标定区(M1)。
       Marigold(DDIM 1–4 步)天然支持;e2eft 多步属 off-distribution,L1 机制测试建议主跑 Marigold。"""
    return [T, T // 2]


def _nfe_schedule(T, nfe):
    """trailing 风格的 NFE 步调度(E2E-FT 惯例)。
    🔴 M4 修复:末步补到接近 0(trailing 末点)+ 去重,避免 int 截断产生重复/缺末步。
    注意:这是 t_schedule 长度;**真实 NFE 由 bridge forward 计数器记录**(CCF 每步取 2 点 ×num_noise)。
    """
    if nfe <= 1:
        return [T]
    sched = [int(T * (1 - k / nfe)) for k in range(nfe)]
    sched[-1] = min(sched[-1], int(T * 0.02))         # 末步落到接近 0
    # 去重保序
    seen, out = set(), []
    for t in sched:
        if t not in seen:
            seen.add(t); out.append(t)
    return out


# --- M4:UNet forward 计数(真实 NFE 硬证据,§3 Phase3 / §4.10 卖点)---
def _reset_nfe(bridge):
    bridge._nfe_count = 0
    if not getattr(bridge, "_nfe_wrapped", False) and hasattr(bridge, "predict"):
        orig = bridge.predict
        def counted(z_t, t, cond, _orig=orig):
            bridge._nfe_count = getattr(bridge, "_nfe_count", 0) + 1
            return _orig(z_t, t, cond)
        bridge.predict = counted
        bridge._nfe_wrapped = True


def _get_nfe(bridge):
    return getattr(bridge, "_nfe_count", -1)


def _blank_row(args, dataset, arm, sid):
    """全字段缺省行(diag/ERR 用),保证 CSV 列对齐。"""
    return {k: "" for k in CSV_FIELDS} | {
        "backbone": "MOCK" if args.mock else args.backbone,
        "dataset": dataset, "phase": args.phase, "arm": arm, "sample_id": sid}


def _row(args, dataset, arm, sid, seed, K, nfe, nfe_real, protocol, align, m, gain):
    r = _blank_row(args, dataset, arm, sid)
    r.update({"seed": seed, "K": K, "nfe": nfe, "nfe_real": nfe_real,
              "protocol": protocol, "align": align,
              "absrel": m.get("absrel"), "rmse": m.get("rmse"), "log10": m.get("log10"),
              "d1": m.get("d1"), "d2": m.get("d2"), "d3": m.get("d3"),
              "align_gain": gain})
    return r


def _report_errors(rows, max_frac=0.05):
    """m1 修复:统计 ERR 行,超阈值显式失败(避免一张全 NaN 但'看起来跑完'的 CSV)。"""
    n_err = sum(1 for r in rows if r.get("align") == "ERR")
    if rows and n_err / len(rows) > max_frac:
        raise RuntimeError(f"🔴 ERR 行 {n_err}/{len(rows)} 超 {max_frac:.0%},"
                           f"CSV 不可信,先排查异常(常见:VAE OOM / t 越界)")
    if n_err:
        print(f"  [警告] {n_err}/{len(rows)} 行 ERR(在阈值内,但请核查)")


def write_csv(rows, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"写出 {len(rows)} 行 → {path}")


# ===========================================================================
# mock bridge:无 GPU 验证流水线。返回 GT 的相对深度(已知 affine 畸变),标 MOCK
# ===========================================================================
class _MockBridge:
    """合成 backbone:把 GT 编成相对深度 + 受控畸变,跑通整条流水线。
    ⚠️ 不是真实 Marigold;产出仅供校验 CSV/评测/臂调度贯通,不可当实验结论。
    """
    def __init__(self):
        self.alphas_cumprod = torch.cumprod(1 - torch.linspace(1e-4, 0.02, 1000), 0)
        self._scene = None

    def encode_cond(self, image):
        # mock:image 第0通道×10 复原 GT 深度,存为场景
        self._scene = image[0, 0] * 10.0
        return image

    def init_noise(self, image):
        return torch.zeros(1, 1, *self._scene.shape)

    def tweedie_x0(self, z, t, cond):
        # 返回 GT 归一化到 [0,1] 的相对深度(latent 占位 = 直接 depth),加微噪
        dr = (self._scene - self._scene.min()) / (self._scene.max() - self._scene.min() + 1e-6)
        return dr.unsqueeze(0).unsqueeze(0)

    def draw_z(self, z0, t, seed):
        g = torch.Generator().manual_seed(int(seed))
        return z0 + 0.01 * torch.randn(z0.shape, generator=g)

    def decode_depth(self, z):
        return z.clamp(0, 1) if z.dim() == 4 else z.unsqueeze(0).unsqueeze(0).clamp(0, 1)

    def encode_depth(self, depth):
        return depth if depth.dim() == 4 else depth.unsqueeze(0).unsqueeze(0)


def _self_check():
    """跑全 phase 的 mock,校验 CSV 完整性、臂齐全、指标有限、B1 公平性、B2 诊断路径。"""
    class A:  # 伪 args
        mock = True; backbone = "MOCK"; dataset = "mock"; root = None; limit = 2
        seeds = [0, 1]; K = [4, 8]; nfe = [1, 2, 4]; num_noise = 2
        pin_anchors = False; pin_weight = 1.0; t_delta = None
    bridge = _MockBridge()

    for phase in ["L0", "L1", "L2", "diag"]:
        A.phase = phase
        rows = run_grid(A, bridge)
        assert len(rows) > 0, f"{phase} 无输出行"
        arms = set(r["arm"] for r in rows)
        if phase == "L0":
            assert {"a_single", "c_multinoise", "b_ccf"} <= arms, f"L0 臂缺: {arms}"
        elif phase == "L1":
            assert {"A_postproc_global", "B_postproc_patch", "Bp_postproc_patch_ccf",
                    "C_sample_geo_local", "D_sample_geo_global"} <= arms, f"L1 臂缺: {arms}"
        elif phase == "L2":
            assert any("nfe" in a for a in arms), f"L2 NFE 臂缺: {arms}"
        else:  # diag:三臂 bias-var(B2)
            assert {"a_single_1noise", "c_single_Nnoise", "b_ccf"} <= arms, f"diag 臂缺: {arms}"
            assert all(r["abs_bias"] != "" for r in rows), "diag 未填 bias"
        # CSV 字段完整(键集一致)
        for r in rows:
            assert set(r.keys()) == set(CSV_FIELDS), \
                f"{phase} 行字段不齐: {set(r.keys())^set(CSV_FIELDS)}"
        print(f"  [{phase}] {len(rows)} 行,臂={sorted(arms)} OK")

    # 🔴 B1 公平性回归:pin_anchors=False 时,arm B 与 arm C 在锚点处的"信息接触"应一致
    #    (不能 C 偷看锚真值而 B 没有)。验证:两臂都只经 ground_to_metric,无额外 tgt 注入。
    import inspect
    src_c = inspect.getsource(bake_geo_latent)
    assert "ground_to_metric" in src_c, "B1 回归:arm C 必须走 ground_to_metric"
    assert "to_field" not in src_c, "B1 回归:arm C 不应再直接注入 tgt(偷看答案)"

    # 🔴 B3 回归(round-3):arm C 必须末步接地成**米制**,不能停在相对深度 [0,1]
    #    (否则按 metric 协议评 → 与 GT 0-10m 错位,L1 反向错误结论)。
    #    用非退化合成样本(深度有真实变化范围,模拟 NYU 1-8m),避免 mock 第0帧的常数场。
    H, W = 32, 32
    gt = torch.linspace(1.0, 8.0, H * W).reshape(H, W)         # 米制 1-8m,非退化
    smp = {"image": (gt / 8.0).unsqueeze(0).unsqueeze(0).repeat(1, 3, 1, 1),
           "depth_gt": gt, "valid": torch.ones(H, W),
           "intrinsics": (50.0, 50.0, W / 2, H / 2), "id": "b3probe"}
    anchor = build_anchor(smp, K=8, use_ground_plane=False)
    cfg = {"num_noise": 2, "seed": 0, "use_ccf": True, "grid": (4, 4),
           "pin_anchors": False, "pin_weight": 1.0}
    predC = arm_sample_geo_local(bridge, smp, anchor, cfg)
    assert predC.max().item() > 1.5, \
        f"B3 回归:arm C 输出停在相对域(max={predC.max():.3f}≤1.5),未接地米制"
    # arm B'(同源 CCF + 后处理)应同量程 → C/B' 单变量对照合法
    predBp = arm_postproc_patch_ccf(bridge, smp, anchor, cfg)
    assert predBp.max().item() > 1.5, "B3 回归:arm B' 也须米制"
    assert abs(predC.max().item() - predBp.max().item()) < 0.6 * predBp.max().item(), \
        f"B3 回归:C({predC.max():.2f})/B'({predBp.max():.2f}) 量程差过大,非同单位对照"

    # 🔴 B4 回归(round-4):L1 采样臂(C/D/B')必须多步(≥2),骨干才会重去噪烘焙后的 latent,
    #    §4.7"采样期注入传播到无锚区"机制才真正被测。单步退化 = 仅 VAE 往返,机制没测到。
    A.phase = "L1"
    cfgs = {name: cfg for name, _, cfg, _ in _phase_configs(A, seed=0)}
    for name in ("C_sample_geo_local", "D_sample_geo_global", "Bp_postproc_patch_ccf"):
        sched = cfgs[name].get("t_schedule", [999])
        assert len(sched) >= 2, f"B4 回归:L1 采样臂 {name} 仍单步({sched}),机制未被测"
    # 后处理臂(A/B)应保持单步(无采样,不需重去噪)
    assert len(cfgs["A_postproc_global"].get("t_schedule", [999])) == 1, "A 应单步"

    # 🔴 B5 回归(round-5):多步第 ≥2 步"重去噪"不得依赖 num_noise(双重加噪坑)。
    #    用 z-敏感桩(tweedie 恒等回传 z,real √ab 加噪公式)测烘焙 latent 到达骨干的信号系数:
    #    应 ≈ √ab 且 num_noise=1 与 4 一致(双重加噪会让 nn>1 退化成 ab,远小于 √ab)。
    #    注意:_MockBridge.draw_z 用 z0+0.01randn(非真实加噪),测不出此坑,故另起专用桩。
    class _ZSensBridge:
        def __init__(s):
            s.alphas_cumprod = torch.cumprod(1 - torch.linspace(1e-4, 0.02, 1000), 0)
        def draw_z(s, z0, t, seed):
            ab = s.alphas_cumprod[int(t)]
            g = torch.Generator().manual_seed(int(seed))
            return ab.sqrt() * z0 + (1 - ab).sqrt() * torch.randn(z0.shape, generator=g)
        def tweedie_x0(s, z_t, t, cond):
            return z_t                                   # 恒等:输出携带的信号系数即被测量
    zb = _ZSensBridge()
    # 🔴 round-6 复核:latent 须够大,否则 t=499 处系数估计方差大 → 正确实现也有 ~15% 假失败率
    #    (实测 (1,4,8,8)=14.8% vs (1,4,32,32)=0.8%)。32×32 锁住脆性,buggy 仍 100% 被抓。
    x0c = torch.randn(1, 4, 32, 32)                      # 干净 x0(够大,降估计方差)
    t2 = 499
    sqrt_ab = zb.alphas_cumprod[t2].sqrt().item()
    def _coeff(nn):
        out = _renoise_denoise(zb, x0c, t2, None, nn, seed_base=1)
        return (out * x0c).sum().item() / (x0c * x0c).sum().item()
    c1, c4 = _coeff(1), _coeff(4)
    assert abs(c1 - sqrt_ab) < 0.1 and abs(c4 - sqrt_ab) < 0.1, \
        f"B5 回归:重去噪信号系数偏离 √ab={sqrt_ab:.3f}(c1={c1:.3f} c4={c4:.3f}),疑双重加噪复发"
    assert abs(c1 - c4) < 0.08, \
        f"B5 回归:重去噪系数随 num_noise 变(c1={c1:.3f} c4={c4:.3f}),双重加噪坑复发"

    # M4 回归:nfe_real 列存在
    A.phase = "L2"; rows = run_grid(A, bridge)
    assert all("nfe_real" in r for r in rows), "M4:nfe_real 列缺失"

    print("自检通过: L0/L1/L2/diag 贯通,CSV 完整,B1 公平性(无偷看),"
          "B3 米制接地(C/B' 同量程),B4 L1采样臂多步(机制可测),"
          "B5 重去噪无双重加噪(信号系数√ab、num_noise无关),M4 NFE 列就位")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["L0", "L1", "L2", "diag"], default="L1")
    ap.add_argument("--backbone", default="e2eft",
                    help="e2eft | marigold | lotus | depthfm")
    ap.add_argument("--model_id", default="GonzaloMG/marigold-e2e-ft-depth")
    ap.add_argument("--dataset", default="nyu")
    ap.add_argument("--root", default=None, help="数据集根目录")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--K", type=int, nargs="+", default=[1, 2, 4, 8, 16, 32])
    ap.add_argument("--nfe", type=int, nargs="+", default=[1, 2, 4, 8])
    ap.add_argument("--num_noise", type=int, default=4)
    ap.add_argument("--t_delta", type=float, default=None, help="CCF 第二时间点间隔")
    ap.add_argument("--pin_anchors", action="store_true",
                    help="CoSIGN 式硬约束:锚支撑区软投影到真值。**arm B/C 同开,对照仍公平**")
    ap.add_argument("--pin_weight", type=float, default=1.0)
    ap.add_argument("--out", default="runs/results.csv")
    ap.add_argument("--mock", action="store_true", help="无 GPU 流水线自检")
    args = ap.parse_args()

    if args.mock:
        _self_check()
        return

    from A2_marigold_bridge import MarigoldBridge
    mode = "e2eft" if args.backbone == "e2eft" else "marigold"
    bridge = MarigoldBridge.from_pretrained(args.model_id, mode=mode)
    rows = run_grid(args, bridge)
    write_csv(rows, args.out)


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 1:
        _self_check()        # 无参 = 自检(与其他脚本一致)
    else:
        main()
