"""
A② 几何锚构造 —— L1 命门的"锚一致性"地基
=================================================================
立项卡 §4.8 Linchpin-1:采样期几何锚注入 必须 > 后处理几何标定。
要让这个对照干净(单变量),臂A(全局 scale+shift)、臂B(patch-affine,AnchorD 式)、
臂C(采样期注入)三臂必须消费**同一组锚**。本文件就是那唯一的锚来源(single source of truth)。

设计:一个规范容器 AnchorSet,统一三种锚源 ——
  (1) oracle 稀疏锚:从 GT 按 FPS/random 采 K 点(Phase 1 立项,先用 oracle 证机制)
  (2) 地平面解析稠密锚:内参 + RANSAC 拟合地面,给地面区域一张**米制稠密深度**
      —— 这是 L1 的真子弹:它约束的是局部结构(地面倾斜/梯度),后处理全局 scale+shift 复现不了
  (3) 真实尺寸锚:已知物体尺寸(车牌/A4/瞳距63mm)+ 像素跨度 + 焦距 → 单点米制深度(无 GT,Phase 3 上)

再提供两个转换器,把同一个 AnchorSet 喂给两类消费者:
  · to_sparse_constraints() → (uv, depth) 供后处理臂 A/B 最小二乘拟合
  · to_field(H,W)           → (mask, target_metric) 供采样期注入臂 C(对接 skeleton.bake_geo_anchor)

依赖:torch(与 A2_ccf_depth_skeleton.py 一致)。自检用合成数据,秒级,无需 GPU/权重/数据集。
ponytail: 自检里的 GT 是解析合成的;真实实验把 depth_gt 换成数据集 GT(NYU/KITTI),intrinsics 换成数据集内参。
"""
import math
import torch


# ===========================================================================
# 规范容器:全库唯一的锚来源。三臂都从这里取锚,保证 L1 对照单变量。
# ===========================================================================
class AnchorSet:
    """统一锚容器。
    sparse_uv:    [N,2] long,稀疏锚像素坐标 (u=col, v=row)
    sparse_depth: [N]   float,对应米制深度
    dense_mask:   [H,W] float in [0,1] 或 None,稠密锚(地平面)的支撑权重
    dense_depth:  [H,W] float 或 None,稠密锚的米制深度(仅 dense_mask>0 处有意义)
    src:          str,锚源标签(oracle_fps / ground_plane / object_size / ...)便于消融分组
    """
    def __init__(self, H, W, sparse_uv=None, sparse_depth=None,
                 dense_mask=None, dense_depth=None, src="unknown"):
        self.H, self.W = H, W
        self.sparse_uv = sparse_uv if sparse_uv is not None else torch.zeros((0, 2), dtype=torch.long)
        self.sparse_depth = sparse_depth if sparse_depth is not None else torch.zeros((0,))
        self.dense_mask = dense_mask
        self.dense_depth = dense_depth
        self.src = src

    @property
    def n_sparse(self):
        return self.sparse_uv.shape[0]

    # --- 转换器 1:喂后处理臂(A 全局 / B patch-affine)---------------------
    def to_sparse_constraints(self, include_dense=False, dense_stride=8):
        """返回 (uv [M,2] long, depth [M] float) 供最小二乘拟合。
        include_dense=True 时把稠密地平面也下采样成约束点(供后处理臂"公平地"也用上地面锚)。
        关键公平性:臂A/B 拿到的约束点集 = 臂C 注入的锚点集,差异只在'用法'(后处理 vs 采样期)。
        """
        uv, d = self.sparse_uv, self.sparse_depth
        if include_dense and self.dense_mask is not None:
            sel = self.dense_mask[::dense_stride, ::dense_stride] > 0.5
            vv, uu = torch.where(sel)
            vv, uu = vv * dense_stride, uu * dense_stride
            dd = self.dense_depth[vv, uu]
            uv2 = torch.stack([uu, vv], dim=1).long()
            uv = torch.cat([uv, uv2], dim=0)
            d = torch.cat([d, dd], dim=0)
        return uv, d

    # --- 转换器 2:喂采样期注入臂 C(对接 skeleton.bake_geo_anchor)--------
    def to_field(self, sigma_px=2.0, hard=False):
        """返回 (mask [H,W] in [0,1], target_metric [H,W]) 供采样期烘焙。
        稀疏锚 → 以 sigma_px 为半径的软支撑盘(模拟车牌/A4 这种小局部锚)。
        稠密锚(地平面)→ 直接并入。同坐标取深度优先稀疏(更可信)。
        """
        H, W = self.H, self.W
        mask = torch.zeros((H, W))
        tgt = torch.zeros((H, W))
        if self.dense_mask is not None:
            mask = self.dense_mask.clone()
            tgt = self.dense_depth.clone()
        if self.n_sparse > 0:
            yy = torch.arange(H).view(H, 1).float()
            xx = torch.arange(W).view(1, W).float()
            for i in range(self.n_sparse):
                u, v = self.sparse_uv[i, 0].item(), self.sparse_uv[i, 1].item()
                if hard:
                    w = ((xx - u).abs() <= sigma_px) & ((yy - v).abs() <= sigma_px)
                    w = w.float()
                else:
                    d2 = (xx - u) ** 2 + (yy - v) ** 2
                    w = torch.exp(-d2 / (2 * sigma_px ** 2))
                    w = (w > 0.05).float() * w   # 截断小尾巴,支撑局部化
                # 稀疏锚覆盖:在其支撑区写入目标深度,权重取大者
                upd = w > mask
                tgt = torch.where(upd, torch.full_like(tgt, self.sparse_depth[i].item()), tgt)
                mask = torch.maximum(mask, w)
        return mask, tgt


# ===========================================================================
# 锚源 1:oracle 稀疏锚(Phase 1 立项用,FPS 给空间铺开 → 对照稳定可复现)
# ===========================================================================
def _fps(coords, K, seed):
    """最远点采样,coords [N,2] float。返回选中索引 list,长度 min(K,N)。
    用 FPS 而非随机:避免聚簇,保证空间覆盖 → L1 对照在不同 K 下方差小、可复现。
    """
    N = coords.shape[0]
    if N == 0:
        return []
    K = min(K, N)
    g = torch.Generator().manual_seed(seed)
    start = torch.randint(0, N, (1,), generator=g).item()
    selected = [start]
    dist = torch.full((N,), float("inf"))
    for _ in range(K - 1):
        last = coords[selected[-1]]
        d = ((coords - last) ** 2).sum(-1)
        dist = torch.minimum(dist, d)
        nxt = int(torch.argmax(dist).item())
        selected.append(nxt)
    return selected


def sample_sparse_oracle(depth_gt, valid_mask, K, method="fps", seed=0):
    """从 GT 采 K 个稀疏米制锚。模拟"已知 K 处真实米制线索"。
    method: 'fps'(默认,空间铺开)| 'random'(消融:验证 FPS 不是结果的关键变量)
    """
    H, W = depth_gt.shape
    vv, uu = torch.where(valid_mask > 0)
    if vv.numel() == 0:
        return AnchorSet(H, W, src=f"oracle_{method}_K{K}")
    coords = torch.stack([uu.float(), vv.float()], dim=1)
    if method == "fps":
        idx = _fps(coords, K, seed)
    elif method == "random":
        g = torch.Generator().manual_seed(seed)
        perm = torch.randperm(coords.shape[0], generator=g)[:K]
        idx = perm.tolist()
    else:
        raise ValueError(f"未知采样法 {method}")
    sel_u = uu[idx].long()
    sel_v = vv[idx].long()
    uv = torch.stack([sel_u, sel_v], dim=1)
    d = depth_gt[sel_v, sel_u]
    return AnchorSet(H, W, sparse_uv=uv, sparse_depth=d, src=f"oracle_{method}_K{K}")


# ===========================================================================
# 锚源 2:地平面解析稠密锚 —— L1 的真子弹(约束局部结构,后处理复现不了)
# ===========================================================================
def _backproject(depth, intrinsics):
    """像素+深度 → 相机坐标 3D 点。intrinsics=(fx,fy,cx,cy)。返回 [H,W,3]。"""
    H, W = depth.shape
    fx, fy, cx, cy = intrinsics
    vv = torch.arange(H).view(H, 1).float().expand(H, W)
    uu = torch.arange(W).view(1, W).float().expand(H, W)
    X = (uu - cx) / fx * depth
    Y = (vv - cy) / fy * depth
    Z = depth
    return torch.stack([X, Y, Z], dim=-1)


def _ray_dirs(H, W, intrinsics):
    """每像素射线方向 (u-cx)/fx, (v-cy)/fy, 1。返回 [H,W,3]。"""
    fx, fy, cx, cy = intrinsics
    vv = torch.arange(H).view(H, 1).float().expand(H, W)
    uu = torch.arange(W).view(1, W).float().expand(H, W)
    rx = (uu - cx) / fx
    ry = (vv - cy) / fy
    rz = torch.ones_like(rx)
    return torch.stack([rx, ry, rz], dim=-1)


def fit_ground_plane(depth_gt, valid_mask, intrinsics, region_frac=0.5,
                     thresh=0.05, iters=200, seed=0):
    """RANSAC 在图像下 region_frac 区域拟合地平面 a*X+b*Y+c*Z+d=0(单位法向)。
    返回 (plane[4] 或 None, inlier_mask[H,W])。
    oracle 版用 GT 点;真实版(Phase 3)把点云来源换成相机位姿/消失线 + 单尺度锚。
    """
    H, W = depth_gt.shape
    pts3d = _backproject(depth_gt, intrinsics)           # [H,W,3]
    region = torch.zeros((H, W))
    region[int(H * (1 - region_frac)):, :] = 1.0          # 下半区为地面候选
    cand = (valid_mask > 0) & (region > 0)
    vv, uu = torch.where(cand)
    if vv.numel() < 3:
        return None, torch.zeros((H, W))
    P = pts3d[vv, uu]                                     # [M,3]
    M = P.shape[0]
    g = torch.Generator().manual_seed(seed)
    best_inliers, best_plane = -1, None
    for _ in range(iters):
        ridx = torch.randint(0, M, (3,), generator=g)
        p0, p1, p2 = P[ridx[0]], P[ridx[1]], P[ridx[2]]
        n = torch.cross(p1 - p0, p2 - p0, dim=0)
        nn = n.norm()
        if nn < 1e-8:
            continue
        n = n / nn
        d = -(n * p0).sum()
        dist = (P @ n + d).abs()
        ninl = int((dist < thresh).sum().item())
        if ninl > best_inliers:
            best_inliers, best_plane = ninl, torch.cat([n, d.view(1)])
    if best_plane is None:
        return None, torch.zeros((H, W))
    # 用内点最小二乘精修(对法向做 SVD)
    n, d = best_plane[:3], best_plane[3]
    dist = (P @ n + d).abs()
    inl = dist < thresh
    if int(inl.sum().item()) >= 3:
        Q = P[inl]
        c = Q.mean(0)
        _, _, Vt = torch.linalg.svd(Q - c)
        n = Vt[-1]
        n = n / n.norm()
        d = -(n * c).sum()
        best_plane = torch.cat([n, d.view(1)])
    inlier_mask = torch.zeros((H, W))
    final_dist = (P @ best_plane[:3] + best_plane[3]).abs()
    fin = final_dist < thresh
    inlier_mask[vv[fin], uu[fin]] = 1.0
    return best_plane, inlier_mask


def ground_plane_anchor(depth_gt, valid_mask, intrinsics, region_frac=0.5,
                        thresh=0.05, seed=0):
    """构造地平面稠密米制锚。对地面内点区域,用平面方程解析出每像素米制深度。
    深度 = -d / (n·r),r 为像素射线方向。这给的是**带正确局部梯度**的稠密深度,
    正是后处理全局 scale+shift 给不出的(L1 立论点)。
    """
    H, W = depth_gt.shape
    plane, inlier_mask = fit_ground_plane(depth_gt, valid_mask, intrinsics,
                                          region_frac, thresh, seed=seed)
    if plane is None:
        return AnchorSet(H, W, src="ground_plane_FAILED")
    n, d = plane[:3], plane[3]
    r = _ray_dirs(H, W, intrinsics)                       # [H,W,3]
    ndotr = (r * n).sum(-1)
    ndotr = torch.where(ndotr.abs() < 1e-6, torch.full_like(ndotr, 1e-6), ndotr)
    dense_depth = -d / ndotr                              # [H,W] 平面解析深度
    dense_depth = torch.clamp(dense_depth, min=0.0)
    dense_mask = inlier_mask * (dense_depth > 0).float()
    return AnchorSet(H, W, dense_mask=dense_mask, dense_depth=dense_depth,
                     src="ground_plane")


# ===========================================================================
# 锚源 3:真实尺寸锚(无 GT,Phase 3 上)—— 已知物体尺寸 → 单点米制深度
# ===========================================================================
def object_size_anchor(H, W, bbox, real_size_m, focal_px, axis="height"):
    """已知物体真实尺寸 + 像素跨度 + 焦距 → 该物体处米制深度。
    针孔模型:depth = focal_px * real_size_m / pixel_size。
    bbox=(u0,v0,u1,v1)。axis='height' 用 (v1-v0),'width' 用 (u1-u0)。
    例:车牌高 0.11m、A4 短边 0.21m、瞳距 0.063m。
    """
    u0, v0, u1, v1 = bbox
    pix = (v1 - v0) if axis == "height" else (u1 - u0)
    if pix <= 0:
        return AnchorSet(H, W, src="object_size_INVALID")
    depth = focal_px * real_size_m / float(pix)
    uc = int(round((u0 + u1) / 2))
    vc = int(round((v0 + v1) / 2))
    uv = torch.tensor([[uc, vc]], dtype=torch.long)
    d = torch.tensor([depth])
    return AnchorSet(H, W, sparse_uv=uv, sparse_depth=d, src="object_size")


# ===========================================================================
# 合并:多锚源拼成一个 AnchorSet(真实场景常同时有尺寸锚 + 地平面)
# ===========================================================================
def merge_anchors(anchors):
    """合并多个 AnchorSet(同 H,W)。稀疏拼接,稠密取并集(后者覆盖前者支撑区)。"""
    assert len(anchors) > 0
    H, W = anchors[0].H, anchors[0].W
    uvs, ds = [], []
    dense_mask, dense_depth = None, None
    srcs = []
    for a in anchors:
        if a.n_sparse > 0:
            uvs.append(a.sparse_uv)
            ds.append(a.sparse_depth)
        if a.dense_mask is not None:
            if dense_mask is None:
                dense_mask = a.dense_mask.clone()
                dense_depth = a.dense_depth.clone()
            else:
                upd = a.dense_mask > dense_mask
                dense_depth = torch.where(upd, a.dense_depth, dense_depth)
                dense_mask = torch.maximum(dense_mask, a.dense_mask)
        srcs.append(a.src)
    uv = torch.cat(uvs, 0) if uvs else None
    d = torch.cat(ds, 0) if ds else None
    return AnchorSet(H, W, sparse_uv=uv, sparse_depth=d,
                     dense_mask=dense_mask, dense_depth=dense_depth,
                     src="+".join(srcs))


# ===========================================================================
# 自检:合成 GT,验证四件事(逻辑正确,非精度)
# ===========================================================================
def _self_check():
    torch.manual_seed(0)
    H, W = 48, 64
    fx = fy = 50.0
    cx, cy = W / 2.0, H / 2.0
    intr = (fx, fy, cx, cy)

    # 合成一个"倾斜地平面"GT:法向 n*,偏移 d*,解析出每像素深度
    n_true = torch.tensor([0.0, -0.8, -0.2])
    n_true = n_true / n_true.norm()
    d_true = 3.0
    r = _ray_dirs(H, W, intr)
    ndotr = (r * n_true).sum(-1)
    ndotr = torch.where(ndotr.abs() < 1e-6, torch.full_like(ndotr, 1e-6), ndotr)
    depth_plane = torch.clamp(-d_true / ndotr, min=0.1, max=50.0)
    valid = torch.ones((H, W))

    # 1) 稀疏 oracle 锚:FPS 采 K 点,目标深度精确等于 GT,数量正确
    K = 8
    a_sp = sample_sparse_oracle(depth_plane, valid, K, method="fps", seed=1)
    assert a_sp.n_sparse == K, f"FPS 采点数错: {a_sp.n_sparse}"
    for i in range(K):
        u, v = a_sp.sparse_uv[i, 0], a_sp.sparse_uv[i, 1]
        assert torch.allclose(a_sp.sparse_depth[i], depth_plane[v, u], atol=1e-5), "锚深度≠GT"

    # 2) FPS 比 random 空间铺得更开(最近邻最小间距更大)
    a_rand = sample_sparse_oracle(depth_plane, valid, K, method="random", seed=1)
    def _min_nn(a):
        c = a.sparse_uv.float()
        dm = torch.cdist(c, c) + torch.eye(c.shape[0]) * 1e9
        return dm.min().item()
    assert _min_nn(a_sp) >= _min_nn(a_rand), "FPS 未比 random 铺开"

    # 3) 地平面解析锚:RANSAC 恢复平面 → 稠密深度 ≈ GT 平面深度(支撑区)
    a_gp = ground_plane_anchor(depth_plane, valid, intr, region_frac=1.0,
                               thresh=0.02, seed=2)
    sup = a_gp.dense_mask > 0.5
    assert sup.sum() > 0.5 * H * W, f"地平面内点太少: {int(sup.sum())}"
    rel = ((a_gp.dense_depth[sup] - depth_plane[sup]).abs()
           / depth_plane[sup]).mean().item()
    assert rel < 0.02, f"地平面解析深度误差过大 AbsRel={rel:.4f}"

    # 4) 锚一致性(L1 公平性命门):to_field 在锚点处的目标深度 == to_sparse 的深度
    mask, tgt = a_sp.to_field(sigma_px=1.5)
    uv, dsp = a_sp.to_sparse_constraints()
    for i in range(uv.shape[0]):
        u, v = uv[i, 0], uv[i, 1]
        assert mask[v, u] > 0.5, "稀疏锚未进 field 支撑区"
        assert torch.allclose(tgt[v, u], dsp[i], atol=1e-4), \
            f"field 与 sparse 深度不一致 @({u},{v})"

    # 5) 真实尺寸锚:针孔反推深度 = focal*size/pix,数值正确
    a_obj = object_size_anchor(H, W, bbox=(10, 10, 14, 30),
                               real_size_m=0.11, focal_px=fx, axis="height")
    expect = fx * 0.11 / (30 - 10)
    assert torch.allclose(a_obj.sparse_depth[0], torch.tensor(expect), atol=1e-5), "尺寸锚深度错"

    # 6) 合并:稀疏+稠密合一,计数与支撑区都对
    a_merge = merge_anchors([a_sp, a_gp])
    assert a_merge.n_sparse == K and a_merge.dense_mask is not None, "合并丢锚"

    print("自检通过: 稀疏FPS / FPS>random铺开 / 地平面RANSAC解析 / 锚一致性 / 尺寸锚 / 合并 六项 OK")


if __name__ == "__main__":
    _self_check()
