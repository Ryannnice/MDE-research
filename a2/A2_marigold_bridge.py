"""
A② Marigold/E2E-FT 桥接 —— 把 skeleton 的 stub backbone 接到真实权重
=================================================================
A2_ccf_depth_skeleton.py 用 _StubBackbone 跑通了机制逻辑。本文件把那套接口
(predict / to_x0 / encode_cond / init_noise / decode)实现成**真实 diffusers backbone**,
并额外提供 bias-variance 诊断(A2_diag_bias_var.py)需要的 draw_z / tweedie_x0。

真实接口(2026-06-23 WebFetch 核实 diffusers v0.38 + E2E-FT README):
  · Marigold v1-1:diffusers.MarigoldDepthPipeline,DDIM,1–4 步,prediction∈[0,1] affine-invariant
       __call__ 支持 latents=(注入初始 latent)、generator=、output_latent=True、output_type='pt'
  · E2E-FT:DiffusionPipeline.from_pretrained(custom_pipeline=...),单步确定性
       denoise_steps=1, ensemble_size=1, timestep_spacing=trailing, noise=zeros
  · prediction_type 从 scheduler.config 读(epsilon / v_prediction / sample),**不硬编码**
  · VAE scaling factor 从 vae.config.scaling_factor 读;depth 编解码用 Marigold 标准做法(3通道复制/取均值)

🔴 深挖发现(2026-06-23,写进 §4.9 弹药)——E2E-FT zeros 最优性 与 CCF 多噪声平均的张力:
  E2E-FT 实证 noise=zeros(确定性单步)最优;而 CCF 的 num_noise>1 需**主动加噪**才能平均。
  推论:L0 的 arm_c(纯多噪声平均)在单步框架下很可能无增益甚至变差。
  → CCF 的真价值只能落在**时间维平均**(多去噪时间点 t),不是噪声维。
  → 这精确化 L0 三臂:arm_b(多 t)vs arm_c(多 noise)隔离的正是"时间平均 vs 重采样",
     若 arm_b>arm_c 而 arm_c≈arm_a,则"OT 时间平滑"非装饰(§4.9 最毒攻击被反驳)。

🔴 几何锚的施加空间(latent vs depth):
  CCF 在 latent 空间走;几何锚是**像素空间米制深度**约束。二者不在同一空间。
  正确做法:Tweedie 出 latent x0 → decode 成 depth x0 → 在 depth 空间施加几何锚(软约束)
            → re-encode 回 latent 继续。本桥接提供 decode_depth / encode_depth 两端,
            几何锚的 depth 空间投影在 driver 里组合(见 A2_run_grid.py)。

依赖:torch(硬)、diffusers+transformers(仅真实路径)。mock 自检不下权重、不需 GPU。
"""
import torch
import torch.nn.functional as F


# ===========================================================================
# Tweedie / x0 投影:按 prediction_type 分型(三种,数学可验证)
#   z_t = sqrt(ab)·x0 + sqrt(1-ab)·ε,   ab = alphas_cumprod[t]
#   epsilon:      x0 = (z - sqrt(1-ab)·ε) / sqrt(ab)
#   v_prediction: x0 = sqrt(ab)·z - sqrt(1-ab)·v       (v = sqrt(ab)·ε - sqrt(1-ab)·x0)
#   sample:       x0 = model_output(直接预测 x0)
# ===========================================================================
def tweedie_from_output(model_output, z_t, alpha_bar, prediction_type):
    """统一 Tweedie 投影。alpha_bar 标量张量(=alphas_cumprod[t])。返回 x0 估计。
    这是『统一映射系数』的实处:无论骨干预测 ε/v/x0,都投影到同一 x0(§4.7 骨干无关)。
    """
    sqrt_ab = alpha_bar.clamp(min=1e-8).sqrt()
    sqrt_1mab = (1.0 - alpha_bar).clamp(min=0.0).sqrt()
    if prediction_type == "epsilon":
        return (z_t - sqrt_1mab * model_output) / sqrt_ab
    if prediction_type == "v_prediction":
        return sqrt_ab * z_t - sqrt_1mab * model_output
    if prediction_type == "sample":
        return model_output
    raise ValueError(f"未知 prediction_type: {prediction_type}")


# ===========================================================================
# 真实桥接:实现 skeleton 接口 + 诊断接口
# ===========================================================================
class MarigoldBridge:
    """把 diffusers Marigold/E2E-FT 组件包成 skeleton/diag 通用 backbone。
    组件(真实路径):vae, unet, scheduler, text_encoder, tokenizer。
    mode: 'marigold'(randn init, DDIM)| 'e2eft'(zeros init, trailing 单步)。
    """

    def __init__(self, vae, unet, scheduler, empty_text_emb, mode="e2eft",
                 device="cuda", dtype=torch.float16):
        self.vae = vae
        self.unet = unet
        self.scheduler = scheduler
        self.empty_text_emb = empty_text_emb        # [1,77,1024] 空 prompt CLIP 嵌入(预算一次)
        self.mode = mode
        self.device = device
        self.dtype = dtype
        self.prediction_type = getattr(scheduler.config, "prediction_type", "v_prediction")
        self.vae_scale = getattr(vae.config, "scaling_factor", 0.18215)
        self.alphas_cumprod = scheduler.alphas_cumprod.to(device)
        self._img_latent = None                     # encode_cond 时缓存条件 image latent

    # --- 工厂:真实加载(GPU 服务器用)----------------------------------
    @classmethod
    def from_pretrained(cls, model_id="GonzaloMG/marigold-e2e-ft-depth",
                        mode="e2eft", device="cuda", dtype=torch.float16):
        """真实加载。E2E-FT 走 custom_pipeline;Marigold v1-1 走 MarigoldDepthPipeline。
        ponytail: GPU 服务器首跑这里。无 diffusers 环境会 ImportError —— 那是预期,mock 自检走另一路。
        """
        from diffusers import DiffusionPipeline, MarigoldDepthPipeline  # noqa
        if mode == "e2eft":
            pipe = DiffusionPipeline.from_pretrained(
                model_id, custom_pipeline=model_id, torch_dtype=dtype).to(device)
        else:
            pipe = MarigoldDepthPipeline.from_pretrained(
                model_id, variant="fp16", torch_dtype=dtype).to(device)
        # 预算空 prompt 嵌入(Marigold 用空文本条件,全程不变 → 算一次)
        empty = cls._encode_empty_text(pipe)
        return cls(pipe.vae, pipe.unet, pipe.scheduler, empty, mode, device, dtype)

    @staticmethod
    def _encode_empty_text(pipe):
        tok = pipe.tokenizer("", padding="max_length",
                             max_length=pipe.tokenizer.model_max_length,
                             truncation=True, return_tensors="pt")
        with torch.no_grad():
            emb = pipe.text_encoder(tok.input_ids.to(pipe.device))[0]
        return emb

    # --- skeleton 接口 ---------------------------------------------------
    def encode_cond(self, image):
        """RGB → image VAE latent(条件)。image: [B,3,H,W]∈[0,1] 或 [-1,1]。
        Marigold:image 归一化到 [-1,1] 后 VAE encode,乘 scaling_factor。
        """
        img = image.to(self.device, self.dtype)
        if img.min() >= 0.0:                          # [0,1] → [-1,1]
            img = img * 2.0 - 1.0
        with torch.no_grad():
            lat = self.vae.encode(img).latent_dist.mode() * self.vae_scale
        self._img_latent = lat
        return lat

    def init_noise(self, image):
        """初始 depth latent z_T。e2eft:zeros(确定性,E2E-FT 最优);marigold:randn。
        形状跟随 image latent 的空间尺寸,4 通道。
        """
        if self._img_latent is None:
            self.encode_cond(image)
        shape = self._img_latent.shape
        if self.mode == "e2eft":
            return torch.zeros(shape, device=self.device, dtype=self.dtype)
        g = torch.Generator(device=self.device).manual_seed(0)
        return torch.randn(shape, generator=g, device=self.device, dtype=self.dtype)

    def predict(self, z_t, t, cond):
        """UNet 速度/噪声预测。输入拼接 [image_latent ; depth_latent](Marigold 条件方式)。
        t 标量(int 或 0-d tensor)。返回 model_output(ε/v/x0,由 prediction_type 定义)。
        """
        img_lat = cond if cond is not None else self._img_latent
        unet_in = torch.cat([img_lat, z_t], dim=1)    # [B,8,h,w]
        t_t = torch.as_tensor(t, device=self.device).reshape(1).expand(z_t.shape[0])
        with torch.no_grad():
            out = self.unet(unet_in, t_t, encoder_hidden_states=self.empty_text_emb).sample
        return out

    def to_x0(self, z_t, t, v):
        """Tweedie 投影到 x0(latent 空间)。t → alphas_cumprod 索引。"""
        ab = self.alphas_cumprod[int(t)]
        return tweedie_from_output(v, z_t, ab, self.prediction_type)

    def decode(self, z):
        """latent → depth [0,1](affine-invariant)。= decode_depth 的别名(skeleton 用)。"""
        return self.decode_depth(z)

    # --- depth ↔ latent 编解码(几何锚 depth 空间施加用)-----------------
    def decode_depth(self, z):
        """depth latent → 单通道深度图 [0,1]。Marigold:VAE decode 取 3 通道均值,clamp。"""
        with torch.no_grad():
            dec = self.vae.decode(z / self.vae_scale).sample      # [B,3,H,W]∈[-1,1]
        depth = dec.mean(dim=1, keepdim=True)                     # 3→1 通道
        depth = (depth + 1.0) / 2.0                               # [-1,1]→[0,1]
        return depth.clamp(0.0, 1.0)

    def encode_depth(self, depth):
        """单通道深度 [0,1] → depth latent。几何锚在 depth 空间改完后 re-encode 回 latent。
        Marigold:depth 复制成 3 通道,[0,1]→[-1,1],VAE encode ×scaling。
        """
        d = depth.to(self.device, self.dtype)
        if d.shape[1] == 1:
            d = d.repeat(1, 3, 1, 1)
        d = d * 2.0 - 1.0
        with torch.no_grad():
            lat = self.vae.encode(d).latent_dist.mode() * self.vae_scale
        return lat

    def vae_roundtrip_residual(self, depth):
        """🔴 M2 风险检查(2026-06-23):VAE 往返不保形会侵蚀几何锚注入的局部结构。
        返回 encode→decode 往返后 depth 的相对残差。**真机 Phase 0 必跑**:
        若残差大(经验阈 >5%),arm C 每步 decode/encode 往返会抹掉锚修正,
        需改"latent 空间直接施加锚"或"仅末步 decode 后施加"(见 §4.9 风险表)。
        """
        lat = self.encode_depth(depth)
        back = self.decode_depth(lat)
        d = depth if depth.dim() == 4 else depth.view(1, 1, *depth.shape)
        return ((back - d).abs() / (d.abs() + 1e-3)).mean().item()

    # --- 诊断接口(A2_diag_bias_var.py 用)------------------------------
    def draw_z(self, z0, t, seed):
        """在时间 t 用 seed 决定的噪声实现构造 z_t。z0=干净 latent(诊断用 GT-encode)。
        z_t = sqrt(ab)·z0 + sqrt(1-ab)·ε(seed)。e2eft 诊断时 z0 来自 GT depth encode。
        """
        ab = self.alphas_cumprod[int(t)]
        g = torch.Generator(device=self.device).manual_seed(int(seed))
        eps = torch.randn(z0.shape, generator=g, device=self.device, dtype=self.dtype)
        return ab.sqrt() * z0 + (1.0 - ab).sqrt() * eps

    def tweedie_x0(self, z_t, t, cond):
        """诊断用:一步 Tweedie 出 x0(latent)。包 predict + to_x0。"""
        v = self.predict(z_t, t, cond)
        return self.to_x0(z_t, t, v)


# ===========================================================================
# mock 自检:不下权重、不需 GPU。验证接口契约 + Tweedie 三型数学正确
# ===========================================================================
class _Cfg:
    def __init__(self, **kw): self.__dict__.update(kw)


class _MockVAE:
    """恒等近似 VAE:encode/decode 往返保形。仅供契约自检。"""
    def __init__(self): self.config = _Cfg(scaling_factor=0.18215)
    def encode(self, x):
        # 3通道→4通道 latent(空间 /8),mock 用 avgpool + 通道复制
        lat = F.avg_pool2d(x, 8)
        lat = lat.mean(1, keepdim=True).repeat(1, 4, 1, 1)
        class _Dist:                                  # 仿 diffusers: .latent_dist.mode()
            def __init__(s, l): s._l = l
            def mode(s): return s._l
            def sample(s, generator=None): return s._l
        class _Enc:
            def __init__(s, l): s.latent_dist = _Dist(l)
        return _Enc(lat)
    def decode(self, z):
        up = F.interpolate(z.mean(1, keepdim=True).repeat(1, 3, 1, 1),
                           scale_factor=8, mode="nearest")
        class _S:
            def __init__(s, v): s.sample = v
        return _S(up.clamp(-1, 1))


class _MockUNet:
    """按指定 prediction_type 返回与已知 (x0,eps) 一致的 model_output。验证 to_x0 还原。"""
    def __init__(self, x0_true, eps_true, ab, ptype):
        self.x0, self.eps, self.ab, self.ptype = x0_true, eps_true, ab, ptype

    def __call__(self, unet_in, t, encoder_hidden_states=None):
        z = unet_in[:, 4:]                          # 后4通道是 depth latent
        if self.ptype == "epsilon":
            out = self.eps
        elif self.ptype == "v_prediction":
            out = self.ab.sqrt() * self.eps - (1 - self.ab).sqrt() * self.x0
        else:
            out = self.x0
        class _O:
            def __init__(s, v): s.sample = v
        return _O(out)


def _make_scheduler(ptype, T=1000):
    betas = torch.linspace(1e-4, 0.02, T)
    ac = torch.cumprod(1.0 - betas, 0)
    return _Cfg(config=_Cfg(prediction_type=ptype), alphas_cumprod=ac)


def _self_check():
    torch.manual_seed(0)
    B, C, h, w = 1, 4, 6, 8
    device = "cpu"

    # --- Tweedie 三型还原 x0(核心数学正确性)---
    for ptype in ["epsilon", "v_prediction", "sample"]:
        x0_true = torch.randn(B, C, h, w)
        eps_true = torch.randn(B, C, h, w)
        sched = _make_scheduler(ptype)
        t = 500
        ab = sched.alphas_cumprod[t]
        z_t = ab.sqrt() * x0_true + (1 - ab).sqrt() * eps_true   # 前向加噪
        unet = _MockUNet(x0_true, eps_true, ab, ptype)
        br = MarigoldBridge(_MockVAE(), unet, sched,
                            empty_text_emb=None, mode="e2eft",
                            device=device, dtype=torch.float32)
        br._img_latent = torch.randn(B, C, h, w)     # 占位条件
        x0_rec = br.to_x0(z_t, t, br.predict(z_t, t, br._img_latent))
        err = (x0_rec - x0_true).abs().max().item()
        assert err < 1e-4, f"{ptype} Tweedie 还原 x0 失败 err={err}"

    # --- init_noise:e2eft=zeros,marigold=可复现 randn ---
    sched = _make_scheduler("v_prediction")
    img = torch.rand(B, 3, h * 8, w * 8)
    mock_unet = _MockUNet(torch.zeros(B, C, h, w), torch.zeros(B, C, h, w),
                          sched.alphas_cumprod[0], "v_prediction")
    br_e = MarigoldBridge(_MockVAE(), mock_unet, sched, None,
                          mode="e2eft", device=device, dtype=torch.float32)
    z_e = br_e.init_noise(img)
    assert torch.count_nonzero(z_e) == 0, "e2eft init 应为 zeros(E2E-FT 最优)"
    br_m = MarigoldBridge(_MockVAE(), mock_unet, sched, None,
                          mode="marigold", device=device, dtype=torch.float32)
    z_m1 = br_m.init_noise(img); z_m2 = br_m.init_noise(img)
    assert torch.allclose(z_m1, z_m2), "marigold init 应可复现(固定 seed)"
    assert torch.count_nonzero(z_m1) > 0, "marigold init 应为非零 randn"

    # --- depth ↔ latent 往返:形状契约(mock VAE 非精确,只验形状/范围)---
    z = torch.randn(B, C, h, w)
    depth = br_e.decode_depth(z)
    assert depth.shape == (B, 1, h * 8, w * 8) and depth.min() >= 0 and depth.max() <= 1, \
        f"decode_depth 形状/范围错: {depth.shape}"
    lat = br_e.encode_depth(depth)
    assert lat.shape == (B, C, h, w), f"encode_depth 形状错: {lat.shape}"

    # --- draw_z 可复现 + 形状 ---
    z0 = torch.randn(B, C, h, w)
    za = br_e.draw_z(z0, 500, seed=3)
    zb = br_e.draw_z(z0, 500, seed=3)
    zc = br_e.draw_z(z0, 500, seed=4)
    assert torch.allclose(za, zb) and not torch.allclose(za, zc), "draw_z seed 行为错"

    print("自检通过: Tweedie三型还原x0 / init(zeros|randn) / depth↔latent往返 / draw_z可复现 四项 OK")


if __name__ == "__main__":
    _self_check()
