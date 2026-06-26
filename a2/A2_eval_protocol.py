"""
A② 双协议评测 —— 区分"真米制"与"假米制"的命门
=================================================================
立项卡 §4.10 / §4.9 最毒攻击之一:「假米制(其实是 affine 对齐)」。
防守方式 = 同一组预测,**两套协议各跑一遍**,差值暴露对齐收益:

  · affine 协议(对齐 scale+shift):衡量"相对深度结构"上界。Marigold/DepthFM 走这条。
  · metric  协议(零对齐):衡量"绝对米制"。UniDepth/Metric3D/本工作的米制卖点走这条。

本 idea 主表必须在 **metric 协议** 不被对齐收益吃掉,否则即"假米制"。

⚠️ 职责边界(不要混):
  · 本文件的 align_* = 用**稠密 GT**估对齐参数 → 这是"评测协议",衡量预测的结构上限。
  · L1 对照臂(A2_baselines_postproc.py)的接地 = 用**稀疏锚**拟合 → 那是"米制接地方法",是被评测对象。
  两者都叫"scale+shift",但一个是评测器、一个是方法,绝不可混用同一段代码。

协议陷阱(立项卡 §4.10,逐项落码):
  · KITTI:Eigen split + Garg crop + cap 80m
  · NYU:官方 Eigen crop
  · metric 协议 = 不做任何对齐;affine 协议 = least-squares scale+shift(对齐用 GT)
  · 指标方向:absrel/rmse/log10 越小越好(↓);d1/d2/d3 越大越好(↑)

依赖:torch。自检合成数据,秒级。
ponytail: 自检用解析构造的 pred/gt;真实实验把它们换成 pipeline 输出与数据集 GT。
"""
import torch


# ===========================================================================
# crop:KITTI Garg / Eigen,NYU 官方。返回布尔 mask [H,W]
# ===========================================================================
def garg_crop_mask(H, W):
    """KITTI Garg crop(Eigen 评测惯例)。比例来自原始 375×1242。"""
    m = torch.zeros((H, W), dtype=torch.bool)
    y0 = int(0.40810811 * H)
    y1 = int(0.99189189 * H)
    x0 = int(0.03594771 * W)
    x1 = int(0.96405229 * W)
    m[y0:y1, x0:x1] = True
    return m


def eigen_crop_mask(H, W):
    """KITTI Eigen crop(另一惯例,比 Garg 略大)。"""
    m = torch.zeros((H, W), dtype=torch.bool)
    y0 = int(0.3324324 * H)
    y1 = int(0.91351351 * H)
    x0 = int(0.0359477 * W)
    x1 = int(0.96405229 * W)
    m[y0:y1, x0:x1] = True
    return m


def nyu_eigen_crop_mask(H, W):
    """NYUv2 官方 Eigen crop(640×480 的固定边框,按比例缩放)。"""
    m = torch.zeros((H, W), dtype=torch.bool)
    y0 = int(45.0 / 480 * H)
    y1 = int(471.0 / 480 * H)
    x0 = int(41.0 / 640 * W)
    x1 = int(601.0 / 640 * W)
    m[y0:y1, x0:x1] = True
    return m


CROP_FNS = {
    "garg": garg_crop_mask,
    "eigen": eigen_crop_mask,
    "nyu": nyu_eigen_crop_mask,
    "none": lambda H, W: torch.ones((H, W), dtype=torch.bool),
}


def build_eval_mask(pred, gt, dataset, min_depth=1e-3, max_depth=None):
    """组合:有效 GT(>min,<cap)∧ crop。返回布尔 mask [H,W]。
    dataset: 'kitti'(garg+80m)| 'nyu'(nyu crop+10m)| 其它(none crop)。
    """
    H, W = gt.shape
    valid = (gt > min_depth)
    if max_depth is not None:
        valid = valid & (gt < max_depth)
    crop_key = {"kitti": "garg", "nyu": "nyu"}.get(dataset, "none")
    crop = CROP_FNS[crop_key](H, W)
    return valid & crop


# 数据集默认 cap(立项卡 §4.10:KITTI 80m,NYU 10m)
DATASET_CAP = {"kitti": 80.0, "nyu": 10.0, "eth3d": 72.0, "diode": 300.0, "scannet": 10.0}


# ===========================================================================
# 对齐(评测协议侧,用稠密 GT)。none/global/patch 三档。
# ===========================================================================
def align_none(pred, gt, mask):
    """metric 协议:零对齐,原样返回。"""
    return pred.clone()


def align_global_lstsq(pred, gt, mask):
    """affine 协议:最小二乘解 s,t 使 s*pred+t ≈ gt(仅 mask 内)。
    Marigold 官方 affine-invariant 评测的标准做法。
    """
    p = pred[mask].reshape(-1)
    g = gt[mask].reshape(-1)
    if p.numel() < 2:
        return pred.clone()
    A = torch.stack([p, torch.ones_like(p)], dim=1)   # [M,2]
    # 🔴 round-4 minor:用 ridge 正规方程而非裸 lstsq。CUDA 'gels' 驱动遇秩亏(近恒定
    #    预测)会出 NaN/崩;(AᵀA+λI) 解恒稳定。λ 极小只为数值稳定,不偏离最小二乘解。
    AtA = A.t() @ A + 1e-6 * torch.eye(2, dtype=A.dtype, device=A.device)
    sol = torch.linalg.solve(AtA, A.t() @ g.unsqueeze(1)).squeeze(1)
    s, t = sol[0], sol[1]
    if not (torch.isfinite(s) and torch.isfinite(t)):     # 退化兜底:近恒定预测
        return pred.clone()
    return s * pred + t


def align_median(pred, gt, mask):
    """affine 协议变体:仅 median scale 对齐(ZoeDepth/部分 metric 论文用)。"""
    p = pred[mask]
    g = gt[mask]
    if p.numel() == 0 or p.median().abs() < 1e-8:
        return pred.clone()
    s = g.median() / p.median()
    return s * pred


ALIGN_FNS = {
    "none": align_none,           # metric 协议
    "global": align_global_lstsq,  # affine 协议(scale+shift)
    "median": align_median,        # affine 协议(仅 scale)
}


# ===========================================================================
# 6 指标。absrel/rmse/log10 ↓,d1/d2/d3 ↑
# ===========================================================================
def compute_metrics(pred, gt, mask, eps=1e-6):
    """返回 dict。pred/gt [H,W],mask 布尔。所有指标只在 mask 内算。"""
    p = pred[mask].clamp(min=eps)
    g = gt[mask].clamp(min=eps)
    if p.numel() == 0:
        return {k: float("nan") for k in
                ["absrel", "rmse", "log10", "rmse_log", "d1", "d2", "d3"]}
    absrel = ((p - g).abs() / g).mean().item()
    rmse = torch.sqrt(((p - g) ** 2).mean()).item()
    log10 = (torch.log10(p) - torch.log10(g)).abs().mean().item()
    rmse_log = torch.sqrt(((torch.log(p) - torch.log(g)) ** 2).mean()).item()
    ratio = torch.maximum(p / g, g / p)
    d1 = (ratio < 1.25).float().mean().item()
    d2 = (ratio < 1.25 ** 2).float().mean().item()
    d3 = (ratio < 1.25 ** 3).float().mean().item()
    return {"absrel": absrel, "rmse": rmse, "log10": log10,
            "rmse_log": rmse_log, "d1": d1, "d2": d2, "d3": d3}


def evaluate(pred, gt, dataset, protocol="metric", align="auto"):
    """一次完整评测:建 mask → 对齐 → 算指标。
    protocol: 'metric'(align=none)| 'affine'(align=global)。
    align='auto' 时按 protocol 选;也可显式传 none/global/median 做协议陷阱对比。
    返回 (metrics dict, 实际用的 align 名)。
    """
    cap = DATASET_CAP.get(dataset, None)
    mask = build_eval_mask(pred, gt, dataset, max_depth=cap)
    if align == "auto":
        align = "none" if protocol == "metric" else "global"
    pred_a = ALIGN_FNS[align](pred, gt, mask)
    if dataset in DATASET_CAP:                       # 对齐后再 clamp 到 cap,防溢出污染指标
        pred_a = pred_a.clamp(min=1e-3, max=DATASET_CAP[dataset])
    m = compute_metrics(pred_a, gt, mask)
    return m, align


def dual_protocol_report(pred, gt, dataset):
    """命门做法:同一预测两套协议各跑一遍,返回三行 + 对齐收益。
    metric 与 affine 的 AbsRel 差 = scale+shift 对齐吃掉的收益。
    若一个方法只在 affine 协议好看、metric 协议崩 → 假米制实锤。
    """
    m_metric, _ = evaluate(pred, gt, dataset, protocol="metric")
    m_affine, _ = evaluate(pred, gt, dataset, protocol="affine")
    gain = m_metric["absrel"] - m_affine["absrel"]   # >0 表示对齐确实在帮忙
    return {"metric": m_metric, "affine": m_affine, "align_gain_absrel": gain}


# ===========================================================================
# 自检:合成 pred/gt,验证协议逻辑(非精度)
# ===========================================================================
def _self_check():
    torch.manual_seed(0)
    H, W = 60, 80
    gt = torch.rand(H, W) * 9.0 + 1.0                # 米制 GT ∈ [1,10]

    # 1) 完美预测:两协议 absrel≈0,d1≈1
    m, _ = evaluate(gt.clone(), gt, "nyu", protocol="metric")
    assert m["absrel"] < 1e-4 and m["d1"] > 0.999, f"完美预测 metric 错: {m}"

    # 2) 假米制:pred = 2*gt + 3(纯相对结构对、尺度全错)
    pred_fake = 2.0 * gt + 3.0
    rep = dual_protocol_report(pred_fake, gt, "nyu")
    #   affine 协议应几乎完美(global lstsq 能解出 s=1/2? 不,解 s*pred+t=gt → s=0.5,t=-1.5)
    assert rep["affine"]["absrel"] < 1e-3, f"affine 未还原仿射: {rep['affine']}"
    #   metric 协议应明显差(尺度错)→ 对齐收益为正且显著
    assert rep["metric"]["absrel"] > 0.3, f"假米制 metric 未暴露: {rep['metric']}"
    assert rep["align_gain_absrel"] > 0.3, "对齐收益未被检出(假米制核心判据)"

    # 3) global lstsq 确实解出闭式解 s=0.5,t=-1.5
    mask = build_eval_mask(pred_fake, gt, "nyu", max_depth=10.0)
    aligned = align_global_lstsq(pred_fake, gt, mask)
    assert torch.allclose(aligned[mask], gt[mask], atol=1e-3), "lstsq 对齐不闭合"

    # 4) Garg crop 行数符合比例(80m KITTI 尺寸)
    Hk, Wk = 375, 1242
    gm = garg_crop_mask(Hk, Wk)
    rows = torch.where(gm.any(1))[0]
    assert abs(rows[0].item() - int(0.408 * Hk)) <= 1, "Garg crop 上界错"

    # 5) cap 生效:KITTI 把 >80m 的 GT 排除出 mask
    gt_far = gt.clone(); gt_far[0, 0] = 120.0
    mk = build_eval_mask(gt_far, gt_far, "kitti", max_depth=80.0)
    assert not mk[0, 0], "80m cap 未排除远点"

    # 6) 指标方向:更差的预测 absrel 更大、d1 更小
    pred_bad = gt + torch.randn(H, W).abs() * 2.0
    m_bad, _ = evaluate(pred_bad, gt, "nyu", protocol="metric")
    m_ok, _ = evaluate(gt + 0.05, gt, "nyu", protocol="metric")
    assert m_bad["absrel"] > m_ok["absrel"] and m_bad["d1"] < m_ok["d1"], "指标方向错"

    print("自检通过: 完美预测 / 假米制暴露 / lstsq闭式 / Garg crop / 80m cap / 指标方向 六项 OK")


if __name__ == "__main__":
    _self_check()
