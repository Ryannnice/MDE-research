"""
A② bias-variance 诊断 —— §4.9「最毒攻击」的可量化弹药
=================================================================
立项卡 §4.9 最毒攻击(更深一层):
  「Tweedie 锚有偏,时间平均压方差≠纠偏,ChordEdit 成功不可外推。」
  ChordEdit 测量模型 R=u_t+ε,ε 零均值(Eq 4.2)→ 时间平均纯降方差(Jensen-L²)。
  A② 的 Tweedie d̂₀ 是 MMSE **有偏** 估计 → 时间平均压方差,**压不掉偏差**。

本文件把这场口水仗变成**可量化诊断**:对每个估计器,跨噪声实现做
  MSE = bias² + variance
分解。三臂(= L0 消融三臂)严格对应:
  arm_a  单点 x0,num_noise=1            —— 高方差,bias=b(t_s)
  arm_c  单点 x0,num_noise=N(平均)     —— 降方差,bias 不变(同一时间点,纯多样本)
  arm_b  CCF 多时间点加权,num_noise=N    —— 降方差 + bias=跨 t 加权(可能抵消)

判 §4.9 攻击的存活:
  · Δvar = var(arm_a) − var(arm_b) > 0   → CCF 降方差(弱命题,ChordEdit 已有)
  · Δbias = |bias(arm_c)| − |bias(arm_b)| —— **核心**:
        >0 → CCF 比"纯多样本"额外**纠了偏** → 攻击被反驳,OT 时间平均非装饰
        ≤0 → CCF 相对 arm_c 只是降方差 → §4.9 攻击坐实,necessity 须靠几何锚
  · Δbias_geo = |bias(arm_b)| − |bias(arm_b+geo)| > 0 → 几何锚纠偏(防守的另一条腿)

⚠️ 诚实声明:本文件的自检用**合成有偏估计器**验证"诊断仪器本身正确"——
   即给定已知 bias/var,分解能精确还原,且能区分"bias 随 t 变化可抵消"与"bias 恒定不可抵消"两种世界。
   **真实 Marigold 落在哪个世界,是 GPU 服务器跑出来的经验问题,本文件不预判结论。**

依赖:torch。自检秒级,无 GPU/权重。
"""
import torch


# ===========================================================================
# 核心仪器:bias-variance 分解。samples [S,H,W](S 个噪声实现),truth [H,W]
# ===========================================================================
def bias_variance_decomp(samples, truth, mask=None, align_affine=False):
    """返回 dict:bias(逐点偏差均值)、var(逐点方差)、mse,以及恒等式残差。
    bias_map = E_s[sample] - truth        (有符号)
    var_map  = Var_s[sample]
    MSE      = E_s[(sample-truth)²] = bias² + var(逐点成立)
    标量汇总在 mask 内取均值;|bias| 用 abs 后再平均(避免正负相消掩盖偏差)。

    🔴 round-2 #3 修复(2026-06-23 复核):align_affine=True 时,先对每个样本做全局
       (s,t) 最小二乘对齐到 truth 再分解。理由:Marigold 出 **affine-invariant** 相对深度,
       全局 scale/shift 是模型合法自由度,不是"偏差";不剥离它,bias 绝对量被未知 affine 污染,
       §4.9 的"结构偏差"判据失真。
    ⚠️ round-3 诚实修正(过度声称已删):全局对齐**只在偏差有空间结构时**保留 geo 纠偏信号
       (实测结构化偏差世界 geo_corrects 仍 True);若偏差是**空间恒定**的纯仿射,对齐会把它整体吸收,
       geo_corrects 翻 False——这其实可接受(恒偏=纯仿射,几何锚本不该额外加分)。即:align_affine
       后度量的是**对齐后残余结构偏差/方差**,不是原始量。真机判据看 C-vs-B 方向,不看 abs_bias 绝对值。
    """
    if align_affine:
        samples = torch.stack([_affine_align_to(samples[i], truth, mask)
                               for i in range(samples.shape[0])], 0)
    S = samples.shape[0]
    mean = samples.mean(0)                              # [H,W]
    bias_map = mean - truth
    var_map = samples.var(0, unbiased=False)
    mse_map = ((samples - truth) ** 2).mean(0)
    if mask is None:
        mask = torch.ones_like(truth, dtype=torch.bool)
    m = mask if mask.dtype == torch.bool else mask > 0.5

    def _avg(x):
        return x[m].mean().item() if m.any() else float("nan")

    abs_bias = _avg(bias_map.abs())
    var = _avg(var_map)
    mse = _avg(mse_map)
    # 恒等式校验:mean(bias²+var) 应 == mean(mse)
    identity_res = abs(_avg(bias_map ** 2 + var_map) - mse)
    return {
        "abs_bias": abs_bias,          # 偏差大小(攻击的核心量)
        "var": var,                    # 方差(ChordEdit 平滑的量)
        "mse": mse,
        "rmse": mse ** 0.5,
        "identity_residual": identity_res,
        "bias_map": bias_map,
        "var_map": var_map,
    }


def _affine_align_to(x, truth, mask):
    """对 x 拟合全局 (a,b) 使 a*x+b 最小二乘逼近 truth(mask 内),返回对齐后的 x。
    🔴 round-2 #3:Marigold 输出 affine-invariant 相对深度,全局 scale/shift 是模型合法自由度,
       不应计入"偏差"。对齐后剩下的才是 §4.9 关心的结构偏差。
    ⚠️ round-3:仅当偏差有空间结构时 geo 纠偏信号才保留(恒偏会被整体吸收,见上)。
    🔴 round-3 robustness:用 ridge 正规方程解,避免秩亏(近共线锚深度)时 MKL lstsq 崩。"""
    m = (mask if mask.dtype == torch.bool else mask > 0.5) if mask is not None \
        else torch.ones_like(truth, dtype=torch.bool)
    if not m.any():
        return x
    xv, tv = x[m], truth[m]
    A = torch.stack([xv, torch.ones_like(xv)], dim=1)         # [N,2]
    # ridge 正规方程 (AᵀA + λI)⁻¹ Aᵀt,λ 极小只为数值稳定(秩亏时不崩)
    AtA = A.t() @ A + 1e-6 * torch.eye(2, dtype=A.dtype, device=A.device)
    sol = torch.linalg.solve(AtA, A.t() @ tv.unsqueeze(1)).squeeze(1)
    a, b = sol[0], sol[1]
    return a * x + b


# ===========================================================================
# 采样:给定"产生一个估计样本"的可调用,跨 seed 收集 [S,H,W]
# ===========================================================================
def collect_samples(sample_fn, seeds):
    """sample_fn(seed)->[H,W]。返回堆叠 [S,H,W]。seed 决定噪声实现(不用 Math.random)。"""
    outs = [sample_fn(s) for s in seeds]
    return torch.stack(outs, 0)


# ===========================================================================
# 三臂估计器适配器(把 backbone + CCF 配置包成 sample_fn)
#   真实实验:backbone = A2_marigold_bridge 的真 Marigold;truth = GT 深度(诊断用 oracle)
#   自检:backbone = 下面的 _BiasedStub,bias 可控
# ===========================================================================
def make_arm_a(backbone, z0, t_s, cond):
    """arm_a:单点 x0,单噪声。每个 seed 一次独立 Tweedie。"""
    def fn(seed):
        z = backbone.draw_z(z0, t_s, seed)
        return backbone.tweedie_x0(z, t_s, cond)
    return fn


def make_arm_c(backbone, z0, t_s, cond, num_noise=4):
    """arm_c:单点 x0,num_noise 平均(同一时间点)。隔离"多样本 vs 时间平均"。"""
    def fn(seed):
        acc = 0.0
        for k in range(num_noise):
            z = backbone.draw_z(z0, t_s, seed * 100 + k)
            acc = acc + backbone.tweedie_x0(z, t_s, cond)
        return acc / num_noise
    return fn


def make_arm_b(backbone, z0, t_s, t_delta, cond, num_noise=4):
    """arm_b:CCF 多时间点加权(ChordEdit 时间核),num_noise 平均。"""
    def fn(seed):
        d_s = _avg_x0(backbone, z0, t_s, cond, num_noise, seed)
        d_s0 = _avg_x0(backbone, z0, t_s - t_delta, cond, num_noise, seed + 7)
        denom = t_s + t_delta
        if denom <= 1e-6:
            return d_s
        return (t_delta * d_s + t_s * d_s0) / denom    # ChordEdit u_hat 时间核
    return fn


def make_arm_b_geo(backbone, z0, t_s, t_delta, cond, geo_anchor, num_noise=4,
                   eval_space=None):
    """arm_b + 几何锚烘焙:支撑区拉向米制目标(纠偏的另一条腿)。
    🔴 B2 修复(2026-06-23):几何锚 mask/tgt 是 **depth 空间**[H,W],而 arm 输出可能是 latent。
       eval_space(可调用,如 bridge.decode_depth)先把估计投到 depth 空间再投影锚。
       eval_space=None → 恒等(stub 自检用,估计本就在 truth 空间)。
    """
    base = make_arm_b(backbone, z0, t_s, t_delta, cond, num_noise)
    mask, tgt = geo_anchor

    def fn(seed):
        d = base(seed)
        d = _to_eval(d, eval_space)
        return torch.where(mask > 0.5, tgt, d)          # 硬投影(自检用;真实用软约束)
    return fn


def _to_eval(x, eval_space):
    """把臂输出投到评测空间(depth)。eval_space=None 恒等;否则调用并去 batch/通道维。"""
    if eval_space is None:
        return x
    d = eval_space(x)                                    # 期望 [B,1,H,W] 或 [H,W]
    while d.dim() > 2:
        d = d[0] if d.shape[0] == 1 else d.mean(0)
    return d


def _avg_x0(backbone, z0, t, cond, num_noise, seed_base):
    acc = 0.0
    for k in range(num_noise):
        z = backbone.draw_z(z0, t, seed_base * 100 + k)
        acc = acc + backbone.tweedie_x0(z, t, cond)
    return acc / num_noise


# ===========================================================================
# 顶层诊断:跑四臂,分解,给出对 §4.9 攻击的可量化判定
# ===========================================================================
def diagnose(backbone, z0, truth, t_s, t_delta, cond, geo_anchor=None,
             seeds=range(16), num_noise=4, mask=None, eval_space=None,
             align_affine=False):
    """返回每臂的 bias/var 分解 + 攻击判定。不下结论真伪,只报数字与判据触发。
    🔴 B2(2026-06-23):eval_space(如 bridge.decode_depth)把所有臂输出投到 **depth 空间**度量,
       因为 §4.9 攻击关心的是米制(depth)偏差,不是 latent 偏差。truth 须也在 depth 空间。
       eval_space=None → 恒等(stub 自检,估计与 truth 同空间)。
    🔴 round-2 #3(2026-06-23 复核):align_affine=True 时,分解前对每臂做全局 (s,t) 对齐到 truth,
       剥离 Marigold affine-invariant 自由度,使 abs_bias 测的是**结构偏差**而非未知 affine 偏移。
    🔴 round-3 修正(两条防守腿用不同 frame,实测发现 align 会撤销几何锚的功):
       · **攻击腿(a/c/b)**:affine-invariant 相对预测 → 用 align_affine 分解,看结构偏差。
       · **几何锚腿(b vs b_geo)**:几何锚的贡献**就是绝对接地**,align 会把它抹掉 → 几何判据
         **始终用未对齐分解**(原始 frame),且在锚支撑区度量纠偏。两腿不共用一套分解。
    """
    def wrap(fn):
        return lambda s: _to_eval(fn(s), eval_space)
    arms = {
        "a_single_1noise": wrap(make_arm_a(backbone, z0, t_s, cond)),
        "c_single_Nnoise": wrap(make_arm_c(backbone, z0, t_s, cond, num_noise)),
        "b_ccf": wrap(make_arm_b(backbone, z0, t_s, t_delta, cond, num_noise)),
    }
    geo_fn = None
    if geo_anchor is not None:
        # b_ccf_geo 内部已在 depth 空间投影 + 锚,故不再二次 wrap
        geo_fn = make_arm_b_geo(backbone, z0, t_s, t_delta, cond,
                                geo_anchor, num_noise, eval_space=eval_space)
    seeds = list(seeds)
    # 攻击腿:align_affine 按调用方(真机 True);几何腿:始终未对齐(见上)
    decomp = {name: bias_variance_decomp(collect_samples(fn, seeds), truth, mask,
                                         align_affine=align_affine)
              for name, fn in arms.items()}

    # 判据(只报触发,不替人下结论)
    verdict = {}
    a, c, b = decomp["a_single_1noise"], decomp["c_single_Nnoise"], decomp["b_ccf"]
    verdict["delta_var_a_minus_b"] = a["var"] - b["var"]            # >0 CCF 降方差
    verdict["delta_absbias_c_minus_b"] = c["abs_bias"] - b["abs_bias"]  # >0 CCF 额外纠偏
    verdict["ccf_reduces_bias_beyond_resampling"] = bool(c["abs_bias"] - b["abs_bias"] > 1e-4)
    verdict["attack_4_9_survives"] = not verdict["ccf_reduces_bias_beyond_resampling"]
    if geo_fn is not None:
        # 🔴 几何腿:b 与 b_geo 都用**未对齐**分解(几何锚=绝对接地,不能被 align 撤销)
        geo_mask = (geo_anchor[0] > 0.5)                            # 锚支撑区
        b_raw = bias_variance_decomp(collect_samples(arms["b_ccf"], seeds), truth,
                                     mask, align_affine=False)
        bg_raw = bias_variance_decomp(collect_samples(geo_fn, seeds), truth,
                                      mask, align_affine=False)
        decomp["b_ccf_geo"] = bg_raw
        # 全图 + 支撑区两个口径都报(支撑区是锚直接作用处,最敏感)
        verdict["delta_absbias_b_minus_geo"] = b_raw["abs_bias"] - bg_raw["abs_bias"]
        sup_b = b_raw["bias_map"][geo_mask].abs().mean().item() if geo_mask.any() else float("nan")
        sup_bg = bg_raw["bias_map"][geo_mask].abs().mean().item() if geo_mask.any() else float("nan")
        verdict["delta_absbias_support"] = sup_b - sup_bg
        verdict["geo_corrects_bias"] = bool((sup_b - sup_bg) > 1e-4)  # 支撑区纠偏为准
    return {"decomp": decomp, "verdict": verdict}


# ===========================================================================
# 自检用桩:可控时间相关偏差 + 零均值噪声
# ===========================================================================
class _BiasedStub:
    """Tweedie 输出 = truth + bias(t) + zero-mean noise。
    bias_fn(t) 决定偏差随 t 的形状:
      · 'sign_flip':bias 跨时间窗变号 → 多时间点可抵消(CCF 应纠偏)
      · 'constant' :bias 恒定 → 多时间点抵消不了(§4.9 攻击成立的世界)
    """
    def __init__(self, truth, bias_mode="sign_flip", beta=0.5, noise_std=0.3, T=1000.0):
        self.truth = truth
        self.bias_mode = bias_mode
        self.beta = beta
        self.noise_std = noise_std
        self.T = T

    def bias(self, t):
        if self.bias_mode == "sign_flip":
            return self.beta * (t / self.T - 0.5) * 2.0   # t=T→+β, t=0→−β,过中点变号
        elif self.bias_mode == "constant":
            return self.beta                               # 恒偏,时间平均压不掉
        raise ValueError(self.bias_mode)

    def draw_z(self, z0, t, seed):
        return ("z", seed, float(t))                       # 桩:z 只携带 seed/t 供 tweedie 用

    def tweedie_x0(self, z, t, cond):
        _, seed, tt = z
        g = torch.Generator().manual_seed(int(seed))
        noise = torch.randn(self.truth.shape, generator=g) * self.noise_std
        return self.truth + self.bias(tt) + noise


# ===========================================================================
# 自检:验证"诊断仪器"正确(非验证 A② 成立)
# ===========================================================================
def _self_check():
    torch.manual_seed(0)
    H, W = 32, 32
    truth = torch.rand(H, W) * 5 + 1
    z0 = None
    cond = None
    t_s, t_delta = 800.0, 600.0           # t_s=800, t_s-δ=200 → 跨中点(500),sign_flip 可抵消
    seeds = range(64)

    # --- 仪器校验 1:恒等式 MSE = bias² + var 残差≈0 ---
    stub = _BiasedStub(truth, bias_mode="constant", beta=0.4, noise_std=0.3)
    fn = make_arm_a(stub, z0, t_s, cond)
    dec = bias_variance_decomp(collect_samples(fn, list(seeds)), truth)
    assert dec["identity_residual"] < 1e-4, f"bias-var 恒等式不成立: {dec['identity_residual']}"

    # --- 仪器校验 2:已知 bias 还原。constant 世界,单点 abs_bias ≈ beta ---
    assert abs(dec["abs_bias"] - 0.4) < 0.05, f"单点偏差未还原: {dec['abs_bias']}"

    # --- 仪器校验 3:arm_c 降方差但不降偏差(同一时间点) ---
    res_const = diagnose(stub, z0, truth, t_s, t_delta, cond, seeds=seeds, num_noise=8)
    dca, dcc = res_const["decomp"]["a_single_1noise"], res_const["decomp"]["c_single_Nnoise"]
    assert dcc["var"] < dca["var"] * 0.5, "arm_c 未显著降方差"
    assert abs(dcc["abs_bias"] - dca["abs_bias"]) < 0.03, "arm_c 不应改变偏差(同时间点)"

    # --- 仪器校验 4:constant 世界 → CCF 抵消不了偏差 → §4.9 攻击 survives ---
    assert res_const["verdict"]["attack_4_9_survives"], \
        "恒偏世界里攻击应成立(CCF 仅降方差)"
    assert res_const["verdict"]["delta_var_a_minus_b"] > 0, "CCF 应降方差"

    # --- 仪器校验 5:sign_flip 世界 → 跨时间点偏差抵消 → CCF 额外纠偏,攻击 NOT survive ---
    stub2 = _BiasedStub(truth, bias_mode="sign_flip", beta=0.6, noise_std=0.3)
    res_flip = diagnose(stub2, z0, truth, t_s, t_delta, cond, seeds=seeds, num_noise=8)
    assert res_flip["verdict"]["ccf_reduces_bias_beyond_resampling"], \
        "变号偏差世界里 CCF 应纠偏(多时间点抵消)"
    assert not res_flip["verdict"]["attack_4_9_survives"], "变号世界攻击应被反驳"

    # --- 仪器校验 6:几何锚硬投影把支撑区偏差清零 ---
    mask = torch.zeros(H, W); mask[::4, ::4] = 1.0
    geo = (mask, truth)                    # 支撑区目标=真值
    res_geo = diagnose(stub, z0, truth, t_s, t_delta, cond, geo_anchor=geo,
                       seeds=seeds, num_noise=4)
    assert res_geo["verdict"]["geo_corrects_bias"], "几何锚应纠偏"
    bg = res_geo["decomp"]["b_ccf_geo"]
    on = mask > 0.5
    # 支撑区偏差应接近 0(硬投影到真值)
    sub_bias = bg["bias_map"][on].abs().mean().item()
    assert sub_bias < 0.05, f"几何锚支撑区未清零偏差: {sub_bias}"

    # --- 仪器校验 7(round-3 覆盖盲区):align_affine=True 的 geo 路径(真机路径!) ---
    #    此前真机恒 align_affine=True、mock 恒 False → geo+align 组合从未被测。
    #    结构化偏差世界:对齐剥离全局仿射后,几何锚的**局部**纠偏信号应仍保留(geo_corrects=True)。
    stub_struct = _BiasedStub(truth, bias_mode="sign_flip", beta=0.6, noise_std=0.2)
    res_align = diagnose(stub_struct, z0, truth, t_s, t_delta, cond, geo_anchor=geo,
                         seeds=seeds, num_noise=4, align_affine=True)
    assert res_align["verdict"]["geo_corrects_bias"], \
        "round-3:结构化偏差 + align_affine 下几何锚仍应纠偏(局部修正抹不掉)"
    # 恒等式在对齐后仍须成立(分解数学不被对齐破坏)
    assert res_align["decomp"]["b_ccf"]["identity_residual"] < 1e-3, \
        "round-3:align_affine 后 bias²+var=MSE 恒等式破裂"

    print("自检通过: 恒等式 / 偏差还原 / arm_c降方差不降偏 / 恒偏攻击成立 / "
          "变号偏差被纠 / 几何锚纠偏 / align_affine+geo路径 七项 OK")
    print(f"  [示例] 恒偏世界: arm_c bias={dcc['abs_bias']:.3f} → arm_b bias={res_const['decomp']['b_ccf']['abs_bias']:.3f} (攻击 survives)")
    print(f"  [示例] 变号世界: arm_c bias={res_flip['decomp']['c_single_Nnoise']['abs_bias']:.3f} → arm_b bias={res_flip['decomp']['b_ccf']['abs_bias']:.3f} (CCF 纠偏)")


if __name__ == "__main__":
    _self_check()
