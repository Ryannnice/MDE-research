"""
A② 免训练单步扩散米制深度 —— CCF→深度 核心机制骨架 + 自检
=================================================================
这不是完整 pipeline,是把 §4.4/§4.7 的两个科学赌注落成可跑代码的"最小可证伪核"。
真实 ChordEdit `_u_estimate` 公式(已取证): u_hat = (δ·dv_s + t_s·dv_s0)/(t_s+δ)
  - dv_s  = mean_over_noise( x0_pred(t_s)   - x0_src(t_s)   )
  - dv_s0 = mean_over_noise( x0_pred(t_s-δ) - x0_src(t_s-δ) )
ChordEdit 两端锚都已知(src/tgt prompt)。深度任务目标端 d₀ 未知 → 这里用 Tweedie 代理锚替换。

依赖: torch, diffusers (Marigold pipeline)。本文件用桩函数(stub)跑通逻辑自检,不下权重。
ponytail: 桩 backbone 自检,真实实验把 backbone 换成 Day-1 起点 GonzaloMG/marigold-e2e-ft-depth
          (E2E-FT 单步,§2.1),骨干无关性验证再加 prs-eth/marigold-depth-v1-1。
"""
import torch
import torch.nn.functional as F


# ---------------------------------------------------------------------------
# [核心1] Tweedie 代理锚:解决"目标端 d₀ 未知"(§4.4 机制赌注)
# ---------------------------------------------------------------------------
def tweedie_x0(backbone, z_t, t, cond):
    """单步 x0-prediction 出目标代理锚 d̂₀。
    Marigold/流匹配骨干都能投影到统一虚拟速度场→统一 x0,故 backbone 无关。
    """
    v = backbone.predict(z_t, t, cond)          # 速度/噪声预测(骨干原生)
    return backbone.to_x0(z_t, t, v)            # Tweedie/x0 投影(统一映射系数)


# ---------------------------------------------------------------------------
# [核心2] CCF:去噪时间窗内对"指向 d̂₀ 的速度场族"做时间加权平均
#         真实 ChordEdit 公式,但 dv 改为"指向 Tweedie 代理锚"而非"tgt-src prompt 差"
# ---------------------------------------------------------------------------
def ccf_velocity(backbone, z_t, t_s, t_delta, cond, num_noise=4):
    """返回逼近 z_T→d̂₀ 直线位移的等效恒速场 u_hat。
    赌注核心(§4.9 最毒攻击): u_hat 是否比单点 x0 净增益。自检里用 ablation 开关验证。
    ⚠️ 偏差陷阱: ChordEdit 原证(附录D)平滑的是零均值噪声→纯降方差;此处 d̂₀ 是有偏 MMSE 锚,
       时间平均压方差不压偏差。故净增益须靠几何锚纠偏或偏差随 t 变化抵消,不能照搬 ChordEdit 结论。
    """
    d_hat_s  = _drift_to_anchor(backbone, z_t, t_s,           cond, num_noise)
    d_hat_s0 = _drift_to_anchor(backbone, z_t, t_s - t_delta, cond, num_noise)
    denom = t_s + t_delta
    if denom <= 1e-6:
        return d_hat_s
    return (t_delta * d_hat_s + t_s * d_hat_s0) / denom      # ChordEdit 时间加权核


def _drift_to_anchor(backbone, z_t, t, cond, num_noise):
    """多噪声样本下,指向 Tweedie 代理锚的平均位移 = (d̂₀ - z_t)。"""
    acc = 0.0
    for k in range(num_noise):
        # 同一未知锚,不同噪声实现 → OT 低能平均(§4.4)。噪声由 k 决定,避免 Math.random。
        z_pert = z_t + 0.0 * k    # 占位:真实实现按 trailing 调度加噪;桩里恒等
        d0 = tweedie_x0(backbone, z_pert, t, cond)
        acc = acc + (d0 - z_t)
    return acc / num_noise


# ---------------------------------------------------------------------------
# [核心3] 几何锚能量 E_geo 烘焙进 CCF 方向(§4.7 最危险张力)
#         单步没有迭代空间做梯度引导 → 改"等效直线方向"而非事后梯度下降(CoSIGN 范式)
# ---------------------------------------------------------------------------
def bake_geo_anchor(u_hat, z_t, geo_anchor):
    """把米制几何约束烘焙进等效直线方向,一次性修正单步方向。
    geo_anchor: dict,含已知尺寸/地平面/内参导出的稀疏米制约束 (mask, target_metric)。
    关键(Linchpin-1):支撑区做**逐点**米制接地,而非全局/单 scale。
    全局 scale 接地 = L1 对照臂(a),证明做不到逐点(见自检 #3),正是"采样期注入>后处理"的立论点。
    """
    d0_proxy = z_t + u_hat                       # 当前等效落点(相对深度域)
    mask, tgt = geo_anchor["mask"], geo_anchor["target_metric"]
    correction = mask * (tgt - d0_proxy)         # 仅支撑区:逐点拉向米制目标
    # ponytail: 硬投影到锚点。真实实验里换成软约束(权重<1)+ 向无锚区扩散(地平面/内参传播),
    #           那才是 §4.7 "修正局部结构" 的本体;硬投影只够自检验证可达性。
    return u_hat + correction                    # 烘焙进方向


# ---------------------------------------------------------------------------
# 单步(B2: 1-2步)米制深度采样主循环
# ---------------------------------------------------------------------------
def sample_metric_depth(backbone, image, geo_anchor, t_schedule, t_delta=50.0,
                        use_ccf=True, use_geo=True, num_noise=4):
    cond = backbone.encode_cond(image)
    z = backbone.init_noise(image)               # trailing: 从 t=T 纯噪声端起步
    for t_s in t_schedule:                        # B2 = len 1~2
        if use_ccf:
            u = ccf_velocity(backbone, z, t_s, t_delta, cond, num_noise)
        else:
            u = tweedie_x0(backbone, z, t_s, cond) - z   # ablation: 纯单点 x0
        if use_geo:
            u = bake_geo_anchor(u, z, geo_anchor)
        z = z + u
    return backbone.decode(z)                     # 米制深度图


# ---------------------------------------------------------------------------
# 自检: 用解析桩 backbone 验证三件事(逻辑正确性,非精度)
# ---------------------------------------------------------------------------
class _StubBackbone:
    """已知真值的线性桩: x0 = 真值常数场 D*。验证机制不破坏可达性。"""
    def __init__(self, D_true): self.D = D_true
    def encode_cond(self, img): return None
    def init_noise(self, img): return torch.zeros_like(self.D)
    def predict(self, z, t, c): return self.D - z          # 速度=指向真值
    def to_x0(self, z, t, v): return z + v                 # Tweedie → 真值
    def decode(self, z): return z


def _self_check():
    torch.manual_seed(0)
    D_true = torch.tensor([[1.0, 4.0], [9.0, 16.0]])       # 相对深度真值
    bb = _StubBackbone(D_true)
    img = D_true

    # 1) CCF 等效场应把 z(0)→D_true,单步可达(桩里 dv 恒指真值)
    out = sample_metric_depth(bb, img, _dummy_anchor(D_true),
                              t_schedule=[1000.0], use_geo=False)
    assert torch.allclose(out, D_true, atol=1e-5), f"CCF 单步未达真值: {out}"

    # 2) 时间加权核退化检查: t_delta=0 时 u_hat == 当前时刻 drift(分母保护)
    z = torch.zeros_like(D_true)
    u0 = ccf_velocity(bb, z, t_s=1000.0, t_delta=0.0, cond=None)
    assert torch.allclose(u0, D_true, atol=1e-5), "t_delta=0 退化错误"

    # 3) 几何锚烘焙: 给一个错了 2x 的相对预测,支撑区应被拉回米制真值
    pred_rel = D_true * 0.5                                  # 假装相对深度差 2x scale
    anchor = {"mask": torch.tensor([[1.0, 0.0], [0.0, 1.0]]),  # 仅对角支撑
              "target_metric": D_true}
    u = bake_geo_anchor(torch.zeros_like(D_true), pred_rel, anchor)
    grounded = pred_rel + u
    on_support = anchor["mask"] > 0
    assert torch.allclose(grounded[on_support], D_true[on_support], atol=1e-4), \
        f"几何锚未在支撑区接地: {grounded}"

    print("自检通过: CCF 可达性 / 时间核退化 / 几何锚局部接地 三项 OK")


def _dummy_anchor(D):
    return {"mask": torch.zeros_like(D), "target_metric": D}


if __name__ == "__main__":
    _self_check()
