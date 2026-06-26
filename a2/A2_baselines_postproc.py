"""
A② L1 后处理对照臂 —— 立项卡 §4.8 Linchpin-1 的"必须打败的对手"
=================================================================
Linchpin-1:采样期几何锚注入(臂C) 必须 > 后处理几何标定。
本文件实现后处理臂,它们用**稀疏锚**(来自 A2_geo_anchor.AnchorSet,与臂C 同源)把
相对深度 pred_rel 接地成米制。臂C 要赢的就是这里的臂B。

四臂(与 A2_实验方案.md / skeleton 对齐):
  臂A  global_affine       —— 全局 scale+shift,2-DOF。最弱对照(GeoDiff 那侧的下界)
  臂B  patch_affine        —— AnchorD 式,patch 网格各拟合 affine + 双线性平滑。**真对照,门槛**
  臂C  采样期注入          —— 在 A2_ccf_depth_skeleton.sample_metric_depth(use_geo=True),不在本文件
  臂D  = C 但锚只用全局    —— 消融"局部结构修正",在 driver 里用 geo_mode='global' 实现

⚠️ 与 A2_eval_protocol 的区别(再次强调,这是审稿命门):
  · 这里用**稀疏锚**(车牌/地面采样点,N 个)拟合 → 这是"米制接地方法",是被评测对象。
  · eval_protocol 用**稠密 GT** 对齐 → 那是"评测协议"。
  绝不能用稠密 GT 来给后处理臂接地——那等于偷看答案,假米制。

依赖:torch。自检合成数据,秒级。
"""
import torch
from A2_geo_anchor import AnchorSet, sample_sparse_oracle, ground_plane_anchor, _ray_dirs


# ===========================================================================
# 臂A:全局 scale+shift。用 N 个稀疏锚最小二乘解 s,t 使 s*pred_rel+t ≈ d_anchor
# ===========================================================================
def solve_affine_ridge(pv, d, ridge=1e-3):
    """ridge 正则的 2-DOF (s,t) 闭式解:(AᵀA+λI)⁻¹Aᵀd。
    🔴 round-3 robustness:替裸 lstsq,防锚点近共线/近恒定深度时 MKL SGELSY 秩亏崩溃
       (实测真机近恒定深度场景会抛异常 → 整轮 CSV 被 _report_errors 中止)。
    """
    A = torch.stack([pv, torch.ones_like(pv)], dim=1)
    AtA = A.t() @ A + ridge * torch.eye(2, dtype=A.dtype, device=A.device)
    Atb = A.t() @ d.unsqueeze(1)
    sol = torch.linalg.solve(AtA, Atb).squeeze(1)
    return sol[0], sol[1]


def ground_global_affine(pred_rel, anchor: AnchorSet, use_dense=True):
    """全局 2-DOF 接地。返回米制深度 [H,W]。
    锚来自稀疏点(+可选地平面下采样点)。这是最弱对照:全图一个 (s,t),无局部修正能力。
    """
    uv, d = anchor.to_sparse_constraints(include_dense=use_dense)
    if uv.shape[0] < 2:
        return pred_rel.clone()
    pv = pred_rel[uv[:, 1], uv[:, 0]]                  # [N] 锚点处相对深度
    s, t = solve_affine_ridge(pv, d)
    return s * pred_rel + t


# ===========================================================================
# 臂B:patch-wise affine(AnchorD 式)。门槛对照,臂C 必须打败它。
# ===========================================================================
def ground_patch_affine(pred_rel, anchor: AnchorSet, grid=(4, 4),
                        use_dense=True, min_pts=2, ridge=1e-3):
    """分 patch 各拟合 (s,t),再双线性平滑成逐像素 (s,t) 场,接地。
    AnchorD 核心:局部 affine 能跟随局部结构,比全局强 → 是真正要打败的对手。
    每 patch 锚点不足时回退到全局解(ridge 正则防欠定)。
    """
    H, W = pred_rel.shape
    gh, gw = grid
    uv, d = anchor.to_sparse_constraints(include_dense=use_dense)
    if uv.shape[0] < 2:
        return pred_rel.clone()
    # 全局解作回退(ridge 正则,防秩亏崩溃)
    pv_all = pred_rel[uv[:, 1], uv[:, 0]]
    glob = solve_affine_ridge(pv_all, d)

    # 每个 patch 中心估一组 (s,t)
    s_grid = torch.zeros(gh, gw)
    t_grid = torch.zeros(gh, gw)
    ph, pw = H / gh, W / gw
    u, v = uv[:, 0].float(), uv[:, 1].float()
    for i in range(gh):
        for j in range(gw):
            # 取落在(略放宽的)patch 内的锚点
            r0, r1 = i * ph, (i + 1) * ph
            c0, c1 = j * pw, (j + 1) * pw
            pad_r, pad_c = ph * 0.5, pw * 0.5
            sel = (v >= r0 - pad_r) & (v < r1 + pad_r) & \
                  (u >= c0 - pad_c) & (u < c1 + pad_c)
            if int(sel.sum().item()) >= min_pts:
                pvp = pred_rel[uv[sel, 1], uv[sel, 0]]
                dp = d[sel]
                A = torch.stack([pvp, torch.ones_like(pvp)], dim=1)
                # ridge 正则:(AᵀA+λI)⁻¹Aᵀd,防 patch 内点共线欠定
                AtA = A.t() @ A + ridge * torch.eye(2)
                Atb = A.t() @ dp.unsqueeze(1)
                sol = torch.linalg.solve(AtA, Atb).squeeze(1)
                s_grid[i, j], t_grid[i, j] = sol[0], sol[1]
            else:
                s_grid[i, j], t_grid[i, j] = glob[0], glob[1]

    # 双线性把 grid 的 (s,t) 上采样到 [H,W],逐像素 affine
    s_map = _bilinear_upsample(s_grid, H, W)
    t_map = _bilinear_upsample(t_grid, H, W)
    return s_map * pred_rel + t_map


def _bilinear_upsample(grid, H, W):
    """[gh,gw] → [H,W] 双线性。用 F.interpolate 的 align_corners=True 语义。"""
    import torch.nn.functional as F
    g = grid.unsqueeze(0).unsqueeze(0)
    up = F.interpolate(g, size=(H, W), mode="bilinear", align_corners=True)
    return up.squeeze(0).squeeze(0)


# ===========================================================================
# 臂B 的"地平面感知"加强版(可选):若锚含地平面稠密深度,patch 拟合会自动用上
#   —— 这是给后处理臂的"最强公平待遇":连地面结构也喂给它,逼臂C 真赢在机制而非信息量
# ===========================================================================
def ground_patch_affine_strong(pred_rel, anchor: AnchorSet, grid=(6, 6)):
    """更细网格 + 强制 include_dense,给后处理臂最大优势。臂C 打败这个才是硬贡献。"""
    return ground_patch_affine(pred_rel, anchor, grid=grid, use_dense=True)


# 接地臂注册表(driver 按名调度)
GROUND_FNS = {
    "global": ground_global_affine,
    "patch": ground_patch_affine,
    "patch_strong": ground_patch_affine_strong,
}


# ===========================================================================
# 🔴 唯一接地原语(2026-06-23 修 B1):arm B 与 arm C 必须共用此函数,保证锚信息量一致
#    —— L1 对照的公平性命门。审稿头号坑:某一臂偷看锚点真值。结构性杜绝:单一入口。
# ===========================================================================
def ground_to_metric(d_rel, anchor, grid=(4, 4), use_dense=True,
                     pin_anchors=False, pin_weight=1.0):
    """相对深度 → 米制。**arm B(后处理)与 arm C(采样注入)都只能调这个**,
    二者消费完全相同的锚信息,唯一差异 = 应用位置(后处理一次 vs 采样期每步+骨干重处理)。

    pin_anchors=False(默认,最干净):纯 patch-affine 拟合,锚仅通过最小二乘进入,**无信息泄漏**。
      → L1 对照最纯:C vs B 的差异纯粹是"骨干先验是否把结构传播到无锚区",这正是 §4.7 卖点。
    pin_anchors=True(CoSIGN 式硬约束):额外在锚支撑区软投影到锚真值。
      → 若启用,driver 保证 **arm B 与 arm C 同开同关**(同一 cfg['pin_anchors']),对照仍公平。
    """
    d_metric = ground_patch_affine(d_rel, anchor, grid=grid, use_dense=use_dense)
    if pin_anchors:
        mask, tgt = anchor.to_field(sigma_px=2.0)
        d_metric = torch.where(mask > 0.5,
                               (1 - pin_weight) * d_metric + pin_weight * tgt, d_metric)
    return d_metric


# ===========================================================================
# 自检:合成"相对深度 + 已知 affine 偏移"的 GT,验证接地逻辑
# ===========================================================================
def _self_check():
    torch.manual_seed(0)
    H, W = 48, 64
    fx = fy = 50.0
    intr = (fx, fy, W / 2.0, H / 2.0)

    # 构造一个倾斜地平面米制 GT
    n_true = torch.tensor([0.1, -0.85, -0.2]); n_true = n_true / n_true.norm()
    d_true = 4.0
    r = _ray_dirs(H, W, intr)
    ndotr = (r * n_true).sum(-1).clamp_min(1e-6)
    gt = torch.clamp(-d_true / ndotr, 0.5, 30.0)
    valid = torch.ones((H, W))

    # 1) 全局 affine 退化校验:pred_rel = (gt - t0)/s0,锚=GT采样 → 应能解回 gt
    s0, t0 = 0.5, 2.0
    pred_rel = (gt - t0) / s0
    anc = sample_sparse_oracle(gt, valid, K=12, method="fps", seed=1)
    out_g = ground_global_affine(pred_rel, anc, use_dense=False)
    rel_g = ((out_g - gt).abs() / gt).mean().item()
    assert rel_g < 1e-3, f"全局 affine 未解回真值 AbsRel={rel_g:.4f}"

    # 2) 局部结构:pred_rel 与 GT 之间是**空间渐变的 affine 场**(全局单一 s,t 跟不上,
    #    patch 臂分块+双线性能逼近)。这是 AnchorD patch-affine 的标准强项场景。
    torch.manual_seed(3)
    gt2 = torch.rand(H, W) * 9.0 + 1.0
    col = torch.arange(W).float() / W
    s_field = 0.5 + 1.5 * col                          # 列向 scale 渐变 0.5→2.0
    t_field = 1.0 - 0.5 * col                          # 列向 shift 渐变
    pred_local = (gt2 - t_field) / s_field             # 反推相对深度
    anc2 = sample_sparse_oracle(gt2, valid, K=96, method="fps", seed=2)
    out_glob = ground_global_affine(pred_local, anc2, use_dense=False)
    out_patch = ground_patch_affine(pred_local, anc2, grid=(2, 8), use_dense=False)
    err_glob = ((out_glob - gt2).abs() / gt2)[valid > 0].mean().item()
    err_patch = ((out_patch - gt2).abs() / gt2)[valid > 0].mean().item()
    #   patch 臂应明显优于全局臂(因为 affine 随空间渐变)
    assert err_patch < err_glob * 0.5, \
        f"patch 未优于 global: patch={err_patch:.4f} global={err_glob:.4f}"

    # 4) patch 臂经双线性平滑后不保证精确过锚点(平滑的代价),但锚点处误差应优于全局臂
    out_p = ground_patch_affine(pred_local, anc2, grid=(4, 8), use_dense=False)
    at_patch = ((out_p[anc2.sparse_uv[:, 1], anc2.sparse_uv[:, 0]] - anc2.sparse_depth).abs()
                / anc2.sparse_depth).mean().item()
    at_glob = ((out_glob[anc2.sparse_uv[:, 1], anc2.sparse_uv[:, 0]] - anc2.sparse_depth).abs()
               / anc2.sparse_depth).mean().item()
    assert at_patch < at_glob, f"patch 臂锚点处未优于全局: patch={at_patch:.4f} global={at_glob:.4f}"

    # 5) 锚一致性:同一 anchor 既能喂后处理(本文件)也能喂 field(skeleton)
    mask, tgt = anc2.to_field(sigma_px=1.5)
    uv, dsp = anc2.to_sparse_constraints()
    assert mask[uv[0, 1], uv[0, 0]] > 0.5, "锚未进 field(跨臂一致性断裂)"

    print(f"自检通过: 全局退化(AbsRel={rel_g:.1e}) / patch>global({err_patch:.3f}<{err_glob:.3f}) "
          f"/ 锚一致性 / patch锚点接地 四项 OK")


if __name__ == "__main__":
    _self_check()
