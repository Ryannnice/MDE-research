"""
A② 失败模式切片 —— CV 顶会硬要求(最小可信包第 4 项)
=================================================================
evidence-design.md CV 族:必须有 qualitative failure cases + per-category/hard-case analysis。
立项卡 §4.9 攻击 + A② 物理特性 → 三个**必然失败带**,正面切片报指标,定位边界(诚实 > 藏拙):

  (1) 透明/反光面:VAE 生成先验对玻璃/镜面/水面失效 → 深度先验本身错,几何锚救不了
  (2) 远距离:米制相对误差随深度放大;KITTI 远端(>40m)是 metric 协议的天然难区
  (3) 无锚距离衰减:几何锚在支撑区准,但传播到远离锚的区域会衰减
      —— 这是 L1 卖点"局部结构修正"的**对偶失败**:修正能传多远?切片量化传播半径。

每个切片 = 在一个布尔掩膜子集上重算 §A2_eval_protocol 的指标,与全图对比。
输出进 results.csv 的扩展(加 slice 列),写作时做 per-slice 表(Idea 5 诊断切片纪律)。

依赖:torch + A2_eval_protocol。自检合成数据,秒级。
ponytail: 透明/反光掩膜真实实验来自数据集语义标注(ScanNet)或反射检测;此处自检用合成掩膜。
"""
import torch
from A2_eval_protocol import compute_metrics, build_eval_mask, ALIGN_FNS, DATASET_CAP


# ===========================================================================
# 切片掩膜构造器:返回布尔 [H,W],标出"难区"
# ===========================================================================
def slice_by_depth_range(gt, lo, hi):
    """远/近距离切片:lo ≤ gt < hi。远端(KITTI >40m)是 metric 难区。"""
    return (gt >= lo) & (gt < hi)


def slice_by_anchor_distance(anchor_mask, lo_px, hi_px):
    """无锚距离衰减切片:到最近锚的像素距离 ∈ [lo,hi)。
    量化"局部结构修正能传多远"——L1 卖点的对偶失败带。
    """
    H, W = anchor_mask.shape
    dist = _dist_to_support(anchor_mask)
    return (dist >= lo_px) & (dist < hi_px)


def slice_by_semantic(semantic_mask, class_ids):
    """透明/反光切片:语义标注属于指定类(玻璃/镜面/水)。真实用数据集标注。"""
    out = torch.zeros_like(semantic_mask, dtype=torch.bool)
    for c in class_ids:
        out = out | (semantic_mask == c)
    return out


def _dist_to_support(mask, max_iter=None):
    """到 mask>0 区域的欧氏距离(像素)。返回 [H,W] float。
    m3 修复(2026-06-23):优先 scipy.ndimage.distance_transform_edt(C 实现,KITTI 全分辨率可用);
    无 scipy 时回退到 chamfer 两遍扫描(纯 torch,近似 L1,够切片分桶)。
    """
    H, W = mask.shape
    if (mask > 0.5).sum() == 0:
        return torch.full((H, W), float(H + W))
    try:
        from scipy.ndimage import distance_transform_edt
        import numpy as np
        # EDT 算的是"到最近 0 的距离",我们要"到最近锚(1)的距离",故对锚取反
        d = distance_transform_edt((mask <= 0.5).numpy().astype(np.uint8))
        return torch.from_numpy(d.astype("float32"))
    except Exception:
        return _dist_chamfer(mask)


def _dist_chamfer(mask):
    """回退:chamfer 两遍扫描(纯 torch,近似 L1 距离)。"""
    H, W = mask.shape
    INF = float(H + W)
    dist = torch.where(mask > 0.5, torch.zeros(H, W), torch.full((H, W), INF))
    for _ in range(2):
        for i in range(H):
            for j in range(W):
                v = dist[i, j]
                if i > 0:
                    v = min(v, dist[i - 1, j] + 1)
                if j > 0:
                    v = min(v, dist[i, j - 1] + 1)
                dist[i, j] = v
        for i in range(H - 1, -1, -1):
            for j in range(W - 1, -1, -1):
                v = dist[i, j]
                if i < H - 1:
                    v = min(v, dist[i + 1, j] + 1)
                if j < W - 1:
                    v = min(v, dist[i, j + 1] + 1)
                dist[i, j] = v
    return dist


# ===========================================================================
# 切片评测:在每个切片子集上算指标 + 全图对照
# ===========================================================================
def evaluate_slices(pred, gt, dataset, anchor_mask=None, semantic_mask=None,
                    protocol="metric"):
    """返回 dict[slice_name] -> metrics。固定 affine/metric 协议(与主表一致)。
    切片只缩小 mask,不改对齐参数(对齐用全图估,切片内评——避免每切片重对齐作弊)。
    """
    cap = DATASET_CAP.get(dataset, None)
    base_mask = build_eval_mask(pred, gt, dataset, max_depth=cap)
    align = "none" if protocol == "metric" else "global"
    pred_a = ALIGN_FNS[align](pred, gt, base_mask)     # 对齐用全图(公平)
    if dataset in DATASET_CAP:
        pred_a = pred_a.clamp(min=1e-3, max=DATASET_CAP[dataset])

    slices = {"full": base_mask}

    # 距离分桶(自适应 cap)
    top = cap if cap else float(gt[base_mask].max().item() if base_mask.any() else 10.0)
    edges = [0, 0.25 * top, 0.5 * top, top]
    for k in range(len(edges) - 1):
        nm = f"depth_{edges[k]:.0f}-{edges[k+1]:.0f}m"
        slices[nm] = base_mask & slice_by_depth_range(gt, edges[k], edges[k + 1])

    # 无锚距离衰减
    if anchor_mask is not None:
        for lo, hi, nm in [(0, 4, "near_anchor"), (4, 16, "mid_anchor"),
                           (16, 1e9, "far_anchor")]:
            slices[nm] = base_mask & slice_by_anchor_distance(anchor_mask, lo, hi)

    # 透明/反光
    if semantic_mask is not None:
        slices["reflective"] = base_mask & slice_by_semantic(semantic_mask, [1])

    out = {}
    for nm, m in slices.items():
        n = int(m.sum().item())
        met = compute_metrics(pred_a, gt, m) if n > 0 else {"absrel": float("nan")}
        met["n_px"] = n
        out[nm] = met
    return out


def degradation_report(slice_metrics, key="absrel"):
    """每切片相对全图的退化倍数。>1 = 该切片更难(失败带)。写作时挑最大退化做 qualitative。"""
    full = slice_metrics.get("full", {}).get(key, float("nan"))
    rep = {}
    for nm, m in slice_metrics.items():
        if nm == "full":
            continue
        v = m.get(key, float("nan"))
        rep[nm] = (v / full) if (full and full == full and v == v) else float("nan")
    return rep


# ===========================================================================
# 自检:合成 pred/gt + 受控失败带,验证切片确实抓到退化
# ===========================================================================
def _self_check():
    torch.manual_seed(0)
    H, W = 40, 56
    gt = torch.rand(H, W) * 9 + 1                       # [1,10]m

    # 构造:近处准、远处差(模拟远距离失败带)
    pred = gt.clone()
    far = gt > 7.0
    pred[far] = gt[far] * 1.5                           # 远处 50% 误差

    sl = evaluate_slices(pred, gt, "nyu", protocol="metric")
    deg = degradation_report(sl)
    # 1) 远距离桶退化倍数应 > 近距离桶
    near_key = [k for k in deg if k.startswith("depth_0")][0]
    far_key = [k for k in deg if k.startswith("depth_7") or k.startswith("depth_5")][-1]
    assert deg[far_key] > deg[near_key], f"远距离切片未抓到退化: {deg}"
    assert deg[far_key] > 1.5, f"远距离退化倍数不足: {deg[far_key]}"

    # 2) 无锚距离切片:近锚准、远锚差。锚极稀疏(单点中心,贴合 L1 小 K 场景)
    anchor_mask = torch.zeros(H, W); anchor_mask[H // 2, W // 2] = 1.0
    dist = _dist_to_support(anchor_mask)
    pred2 = gt.clone()
    pred2[dist > 8] = gt[dist > 8] * 1.4               # 远离锚处误差大
    sl2 = evaluate_slices(pred2, gt, "nyu", anchor_mask=anchor_mask, protocol="metric")
    assert sl2["far_anchor"]["absrel"] > sl2["near_anchor"]["absrel"], \
        f"无锚距离切片未抓到衰减: near={sl2['near_anchor']['absrel']:.3f} far={sl2['far_anchor']['absrel']:.3f}"

    # 3) 透明/反光语义切片
    sem = torch.zeros(H, W); sem[5:10, 5:15] = 1       # 标 1 类为反光
    pred3 = gt.clone(); pred3[sem == 1] = gt[sem == 1] * 2.0
    sl3 = evaluate_slices(pred3, gt, "nyu", semantic_mask=sem, protocol="metric")
    assert sl3["reflective"]["absrel"] > sl3["full"]["absrel"], "反光切片未抓到失败"

    # 4) 距离图正确性:锚点(中心)处 dist=0,远点 dist 大
    assert dist[H // 2, W // 2] == 0, "锚点距离应为 0"
    assert dist[0, 0] > 0, "远离锚的角点距离应 >0"

    # 5) 切片像素数守恒:各深度桶像素和 == full(分桶不重不漏)
    bucket_sum = sum(sl[k]["n_px"] for k in sl if k.startswith("depth_"))
    assert bucket_sum == sl["full"]["n_px"], \
        f"深度分桶不守恒: {bucket_sum} vs {sl['full']['n_px']}"

    print("自检通过: 远距离退化 / 无锚衰减 / 反光失败 / 距离图 / 分桶守恒 五项 OK")
    print(f"  [示例] 退化倍数(absrel/full): {near_key}={deg[near_key]:.2f}x, {far_key}={deg[far_key]:.2f}x")


if __name__ == "__main__":
    _self_check()
