#!/usr/bin/env python3
"""Generate the concise seven-slide transparent-depth project deck."""

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE, MSO_CONNECTOR
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


HERE = Path(__file__).resolve().parent
ASSET_DIR = HERE / "assets"
OUTPUT = HERE / "透明物体多层深度_简洁汇报_2026-08-08.pptx"

SLIDE_W = 13.333
SLIDE_H = 7.5
FONT = "Microsoft YaHei"

INK = "172331"
MUTED = "667381"
TEAL = "0F766E"
BLUE = "2563EB"
GREEN = "15805D"
ORANGE = "C46B16"
RED = "B7443E"
LINE = "DDE3E8"
SOFT = "F5F8FA"
SOFT_TEAL = "EAF6F4"
SOFT_BLUE = "EEF4FF"
SOFT_ORANGE = "FFF4E8"
WHITE = "FFFFFF"


def color(value):
    return RGBColor.from_string(value)


def crop_image(source, target, relative_box):
    source_path = ASSET_DIR / source
    target_path = ASSET_DIR / target
    image = Image.open(source_path)
    width, height = image.size
    left, top, right, bottom = relative_box
    image.crop((
        int(left * width), int(top * height),
        int(right * width), int(bottom * height),
    )).save(target_path)
    return target_path


def textbox(slide, text, x, y, w, h, size=14, fill=INK, bold=False,
            align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP, margin=0.02):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(margin)
    frame.margin_right = Inches(margin)
    frame.margin_top = Inches(margin)
    frame.margin_bottom = Inches(margin)
    frame.vertical_anchor = valign
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color(fill)
    return shape


def rect(slide, x, y, w, h, fill=WHITE, outline=LINE, rounded=False, width=0.8):
    kind = MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE if rounded else MSO_AUTO_SHAPE_TYPE.RECTANGLE
    shape = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = color(fill)
    shape.line.color.rgb = color(outline)
    shape.line.width = Pt(width)
    return shape


def line(slide, x1, y1, x2, y2, stroke=LINE, width=1.0):
    connector = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2)
    )
    connector.line.color.rgb = color(stroke)
    connector.line.width = Pt(width)
    return connector


def circle(slide, x, y, diameter, fill, label=None, label_color=WHITE):
    shape = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.OVAL, Inches(x), Inches(y), Inches(diameter), Inches(diameter)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color(fill)
    shape.line.color.rgb = color(fill)
    if label is not None:
        textbox(slide, label, x, y + diameter * 0.29, diameter, diameter * 0.3,
                10, label_color, True, PP_ALIGN.CENTER)
    return shape


def picture_contain(slide, path, x, y, w, h):
    with Image.open(path) as image:
        image_w, image_h = image.size
    scale = min(w / image_w, h / image_h)
    draw_w = image_w * scale
    draw_h = image_h * scale
    draw_x = x + (w - draw_w) / 2
    draw_y = y + (h - draw_h) / 2
    slide.shapes.add_picture(
        str(path), Inches(draw_x), Inches(draw_y), Inches(draw_w), Inches(draw_h)
    )
    border = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    border.fill.background()
    border.line.color.rgb = color(LINE)
    border.line.width = Pt(0.7)


def background(slide):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color(WHITE)


def title(slide, text, index):
    textbox(slide, f"0{index}", 0.56, 0.37, 0.50, 0.20, 9, TEAL, True)
    textbox(slide, text, 1.05, 0.31, 11.4, 0.42, 24, INK, True)
    line(slide, 0.56, 0.93, 12.74, 0.93, LINE, 0.9)


def footer(slide, text):
    textbox(slide, text, 0.57, 7.18, 11.9, 0.15, 7.2, MUTED)


def chip(slide, text, x, y, w, fill_color, text_color):
    rect(slide, x, y, w, 0.32, fill_color, fill_color, rounded=True)
    textbox(slide, text, x, y + 0.075, w, 0.13, 8.8, text_color, True, PP_ALIGN.CENTER)


def build():
    # Paper figures cropped from the local PDFs.
    transcg = crop_image("transcg_p1.png", "transcg_core.png", (0.50, 0.24, 0.94, 0.46))
    depth4tom = crop_image("depth4tom_p1.png", "depth4tom_core.png", (0.52, 0.28, 0.94, 0.59))
    remake = crop_image("remake_p1.png", "remake_core.png", (0.49, 0.46, 0.94, 0.65))
    layered = crop_image("layereddepth_p2.png", "layereddepth_core.png", (0.08, 0.055, 0.92, 0.37))
    seegroup = crop_image("seegroup_p2.png", "seegroup_core.png", (0.08, 0.055, 0.92, 0.25))

    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W)
    prs.slide_height = Inches(SLIDE_H)
    blank = prs.slide_layouts[6]

    # Slide 1 — thesis
    slide = prs.slides.add_slide(blank)
    background(slide)
    textbox(slide, "透明物体抓取", 0.72, 0.72, 3.3, 0.28, 11, TEAL, True)
    textbox(slide, "从单一深度到多界面几何", 0.72, 1.35, 10.8, 0.60, 32, INK, True)
    textbox(slide, "相关工作 · Idea · 复现进度 · 下一步", 0.74, 2.12, 8.0, 0.28, 15, MUTED)
    line(slide, 0.74, 2.82, 12.56, 2.82, LINE, 1.0)

    # One-ray diagram, deliberately minimal.
    textbox(slide, "普通深度", 0.82, 3.58, 1.35, 0.22, 12, MUTED, True)
    line(slide, 2.18, 3.68, 5.15, 3.68, BLUE, 2.0)
    circle(slide, 3.10, 3.56, 0.24, BLUE)
    textbox(slide, "一个像素 = 一个 z", 2.45, 4.07, 2.45, 0.23, 14, BLUE, True, PP_ALIGN.CENTER)

    textbox(slide, "我们的目标", 6.10, 3.58, 1.45, 0.22, 12, MUTED, True)
    line(slide, 7.55, 3.68, 11.83, 3.68, TEAL, 2.0)
    for offset, label in [(0.45, "外壁"), (1.25, "内壁"), (2.55, "内壁"), (3.35, "外壁")]:
        circle(slide, 7.55 + offset, 3.55, 0.26, TEAL)
        textbox(slide, label, 7.40 + offset, 4.02, 0.56, 0.18, 8.5, MUTED, False, PP_ALIGN.CENTER)
    textbox(slide, "一个像素 = 有序界面事件", 8.05, 4.41, 3.42, 0.25, 14, TEAL, True, PP_ALIGN.CENTER)
    rect(slide, 1.05, 5.57, 11.20, 0.62, SOFT_TEAL, SOFT_TEAL, rounded=True)
    textbox(slide, "核心假设：保留外壁、内壁和空腔，能减少抓取规划中的穿壁与“实心化”错误。",
            1.24, 5.76, 10.82, 0.23, 15, INK, True, PP_ALIGN.CENTER)
    textbox(slide, "阶段汇报 · 2026.08", 0.73, 6.84, 2.5, 0.17, 8.3, MUTED)

    # Slide 2 — hardware progress
    slide = prs.slides.add_slide(blank)
    background(slide)
    title(slide, "硬件进度：从 D455 深度到 PIPER-X 基座已打通", 2)
    textbox(slide, "PIPER-X + AGILE.X 夹爪 + Intel RealSense D455 · 实机验证 2026.08.09",
            0.66, 1.13, 9.60, 0.24, 12, MUTED)
    chip(slide, "同步快照已通过", 10.82, 1.08, 1.80, SOFT_TEAL, GREEN)

    hardware_chain = [
        (0.72, "末端 D455", "RGB-D 848×480 @ 30 Hz\nUSB 3.2 · eye-in-hand", BLUE),
        (3.75, "彩色对齐深度", "camera_p\n24 / 24 角点有效", BLUE),
        (6.78, "手眼外参", "flange_T_camera\nPark · 15 + 3 姿态", TEAL),
        (9.81, "PIPER-X 基座", "base_T_flange\n法兰反馈 + FK", GREEN),
    ]
    for x, heading, body, accent in hardware_chain:
        rect(slide, x, 1.62, 2.42, 1.42, WHITE, LINE, rounded=True)
        rect(slide, x, 1.62, 0.07, 1.42, accent, accent)
        textbox(slide, heading, x + 0.22, 1.90, 1.98, 0.25,
                13, INK, True, PP_ALIGN.CENTER)
        textbox(slide, body, x + 0.20, 2.34, 2.02, 0.42,
                9.7, MUTED, False, PP_ALIGN.CENTER)
    for x in (3.25, 6.28, 9.31):
        arrow = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.CHEVRON, Inches(x), Inches(2.04), Inches(0.32), Inches(0.48)
        )
        arrow.fill.solid()
        arrow.fill.fore_color.rgb = color(LINE)
        arrow.line.color.rgb = color(LINE)

    rect(slide, 1.46, 3.34, 10.40, 0.58, SOFT_TEAL, SOFT_TEAL, rounded=True)
    textbox(slide, "base_p = base_T_flange @ flange_T_camera @ camera_p",
            1.69, 3.51, 9.94, 0.22, 14, TEAL, True, PP_ALIGN.CENTER)

    metrics = [
        (0.72, "统一时间戳", "5.420 ms", "相机曝光 ↔ 法兰反馈", GREEN),
        (3.84, "手眼独立留出", "3.660 mm / 0.663°", "3 个未参与求解姿态", TEAL),
        (6.96, "深度板面拟合", "0.692 mm RMS", "30 mm 边长误差 0.307 mm", BLUE),
        (10.08, "基座位姿一致性", "3.469 mm / 0.513°", "深度点 → 机器人 Base", ORANGE),
    ]
    for x, heading, value, note, accent in metrics:
        rect(slide, x, 4.28, 2.53, 1.24, WHITE, LINE, rounded=True)
        textbox(slide, heading, x + 0.18, 4.48, 2.17, 0.19,
                10.2, MUTED, True, PP_ALIGN.CENTER)
        textbox(slide, value, x + 0.14, 4.82, 2.25, 0.23,
                13.2, accent, True, PP_ALIGN.CENTER)
        textbox(slide, note, x + 0.14, 5.18, 2.25, 0.16,
                8.3, MUTED, False, PP_ALIGN.CENTER)

    rect(slide, 0.95, 5.91, 11.43, 0.71, SOFT_BLUE, SOFT_BLUE, rounded=True)
    textbox(slide, "下一步", 1.21, 6.14, 1.05, 0.20, 11.5, BLUE, True)
    textbox(slide, "连续多帧记录 + 法兰位姿插值，接透明物体 mask、目标位姿与抓取。",
            2.20, 6.10, 9.78, 0.28, 12.8, INK, True)
    footer(slide, "统一静态快照已输出 308,677 点 Base PLY；相机支架不可松动。")

    # Slide 3 — single-depth work
    slide = prs.slides.add_slide(blank)
    background(slide)
    title(slide, "相关论文①：单层深度路线", 3)
    cards = [
        (0.60, "TransCG", "RGB-D 深度补全 + 抓取数据", transcg, "RAL 2022"),
        (4.48, "Depth4ToM", "透明 / 镜面单目深度估计", depth4tom, "ICCV 2023"),
        (8.36, "ReMake", "mask 辅助的 metric depth + 抓取", remake, "2026"),
    ]
    for x, name, desc, image, year in cards:
        textbox(slide, name, x, 1.25, 2.4, 0.27, 16, INK, True)
        chip(slide, year, x + 2.51, 1.21, 0.75, SOFT_BLUE, BLUE)
        textbox(slide, desc, x, 1.63, 3.36, 0.40, 10.8, MUTED)
        picture_contain(slide, image, x, 2.16, 3.36, 2.65)
    rect(slide, 0.82, 5.41, 11.70, 0.76, SOFT, SOFT, rounded=True)
    textbox(slide, "共同点", 1.10, 5.64, 1.12, 0.20, 12, TEAL, True)
    textbox(slide, "都把输出压缩成一张深度图；对透明物体有用，但无法直接表达内壁与空腔。",
            2.18, 5.61, 9.87, 0.24, 14, INK, True)
    textbox(slide, "这也是 DepthHypothesisPack 要突破的表示瓶颈。",
            1.10, 6.43, 10.5, 0.25, 13, TEAL, True)
    footer(slide, "图片截自本地论文 PDF：TransCG、Depth4ToM、ReMake。")

    # Slide 4 — multi-layer work
    slide = prs.slides.add_slide(blank)
    background(slide)
    title(slide, "相关论文②：多层深度路线", 4)
    textbox(slide, "LayeredDepth", 0.66, 1.22, 2.4, 0.28, 16, INK, True)
    textbox(slide, "提出真实 / 合成 multi-layer benchmark，并定义 layer_first 与 layer_all 评测。",
            0.66, 1.60, 5.75, 0.42, 11, MUTED)
    picture_contain(slide, layered, 0.66, 2.12, 5.72, 3.26)

    textbox(slide, "SeeGroup", 6.91, 1.22, 2.4, 0.28, 16, INK, True)
    textbox(slide, "沿同一条 ray 预测多个深度，并让模型自适应地组织这些层。",
            6.91, 1.60, 5.75, 0.42, 11, MUTED)
    picture_contain(slide, seegroup, 6.91, 2.12, 5.72, 3.26)

    rect(slide, 1.18, 5.84, 10.98, 0.67, SOFT_TEAL, SOFT_TEAL, rounded=True)
    textbox(slide, "它们证明“多界面可以被感知”；仍未回答“多界面能否让抓取规划更可靠”。",
            1.42, 6.04, 10.50, 0.23, 14, INK, True, PP_ALIGN.CENTER)
    footer(slide, "图片截自本地论文 PDF：LayeredDepth、SeeGroup。")

    # Slide 5 — idea
    slide = prs.slides.add_slide(blank)
    background(slide)
    title(slide, "Idea：DepthHypothesisPack", 5)
    textbox(slide, "把感知模型输出变成规划器能直接使用的薄壳事件。",
            0.61, 1.18, 8.8, 0.26, 14, MUTED)

    steps = [
        (0.74, 2.09, 2.34, "输入", "RGB-D + mask", BLUE),
        (4.03, 2.09, 4.04, "DepthHypothesisPack", "[d¹, d², d³, d⁴] + 类型 / 置信度", TEAL),
        (9.03, 2.09, 3.56, "Shell-aware planner", "碰撞、空腔、可达性检查", GREEN),
    ]
    for x, y, w, heading, body, accent in steps:
        rect(slide, x, y, w, 2.10, WHITE, LINE, rounded=True)
        rect(slide, x, y, 0.07, 2.10, accent, accent)
        textbox(slide, heading, x + 0.25, y + 0.32, w - 0.48, 0.29, 15, INK, True, PP_ALIGN.CENTER)
        textbox(slide, body, x + 0.25, y + 1.00, w - 0.48, 0.50, 12, MUTED, False, PP_ALIGN.CENTER)
    # Chevron arrows between the three modules.
    for x in (3.34, 8.34):
        arrow = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.CHEVRON, Inches(x), Inches(2.82), Inches(0.40), Inches(0.54)
        )
        arrow.fill.solid()
        arrow.fill.fore_color.rgb = color(LINE)
        arrow.line.color.rgb = color(LINE)

    textbox(slide, "d¹", 4.50, 3.30, 0.52, 0.22, 13, BLUE, True, PP_ALIGN.CENTER)
    textbox(slide, "d²", 5.17, 3.30, 0.52, 0.22, 13, TEAL, True, PP_ALIGN.CENTER)
    textbox(slide, "d³", 5.84, 3.30, 0.52, 0.22, 13, ORANGE, True, PP_ALIGN.CENTER)
    textbox(slide, "d⁴", 6.51, 3.30, 0.52, 0.22, 13, GREEN, True, PP_ALIGN.CENTER)

    rect(slide, 0.89, 5.02, 11.58, 1.22, SOFT, SOFT, rounded=True)
    textbox(slide, "关键不是“多输出几张 depth map”", 1.18, 5.29, 4.10, 0.26, 15, INK, True)
    textbox(slide, "而是保留事件顺序与几何语义，让 planner 知道哪里是壁、哪里是空腔。",
            5.09, 5.28, 6.97, 0.45, 13, TEAL, True)
    textbox(slide, "当前状态：Idea 已确定；Head 尚未训练，先通过下游可行性 Gate。",
            1.18, 5.83, 10.6, 0.22, 10.8, MUTED)
    footer(slide, "本页为本项目方法设计。")

    # Slide 6 — reproduction status
    slide = prs.slides.add_slide(blank)
    background(slide)
    title(slide, "目前复现进度：哪些是论文协议，哪些是我们的诊断", 6)

    textbox(slide, "官方协议 / benchmark", 0.66, 1.26, 3.1, 0.24, 14, INK, True)
    chip(slide, "可直接引用", 3.24, 1.21, 1.16, SOFT_TEAL, GREEN)
    rows_left = [
        ("Depth4ToM Base path", "Booster 228", "DPT ToM RMSE 136.28 mm", "与论文一致"),
        ("DPT Base vs SeeGroup", "LayeredDepth val 300", "layer_all 29.95% → 72.41%", "+42.46 pp"),
    ]
    for i, (method, scope, result, tag) in enumerate(rows_left):
        y = 1.79 + i * 1.37
        rect(slide, 0.66, y, 5.89, 1.10, WHITE, LINE, rounded=True)
        textbox(slide, method, 0.92, y + 0.18, 2.42, 0.20, 11.5, INK, True)
        textbox(slide, scope, 0.92, y + 0.56, 2.42, 0.18, 9.0, MUTED)
        textbox(slide, result, 3.34, y + 0.18, 2.73, 0.22, 11.6, TEAL, True, PP_ALIGN.RIGHT)
        textbox(slide, tag, 3.34, y + 0.58, 2.73, 0.18, 9.2, GREEN, True, PP_ALIGN.RIGHT)

    textbox(slide, "我们的诊断 / oracle", 6.86, 1.26, 3.1, 0.24, 14, INK, True)
    chip(slide, "不能冒充论文分数", 10.76, 1.21, 1.70, SOFT_ORANGE, ORANGE)
    rows_right = [
        ("T²SQNet + GT mask", "TablewareNet 100 scenes", "Shell interface F1 79.15%", "受控几何 oracle"),
        ("TransCG full test", "52 scenes / 23,524 samples", "当前已取得 40 / 52 scenes", "尚无 full metric"),
    ]
    for i, (method, scope, result, tag) in enumerate(rows_right):
        y = 1.79 + i * 1.37
        rect(slide, 6.86, y, 5.81, 1.10, WHITE, LINE, rounded=True)
        textbox(slide, method, 7.12, y + 0.18, 2.48, 0.20, 11.5, INK, True)
        textbox(slide, scope, 7.12, y + 0.56, 2.48, 0.18, 9.0, MUTED)
        textbox(slide, result, 9.56, y + 0.18, 2.63, 0.22, 11.3, ORANGE, True, PP_ALIGN.RIGHT)
        textbox(slide, tag, 9.56, y + 0.58, 2.63, 0.18, 9.2, ORANGE, True, PP_ALIGN.RIGHT)

    rect(slide, 0.86, 4.92, 11.58, 1.16, SOFT_BLUE, SOFT_BLUE, rounded=True)
    textbox(slide, "当前能说", 1.15, 5.17, 1.26, 0.22, 12, BLUE, True)
    textbox(slide, "多层表示在感知协议上优势显著；受控条件下能够恢复大量薄壳界面。",
            2.28, 5.16, 9.65, 0.24, 13, INK, True)
    textbox(slide, "当前不能说", 1.15, 5.62, 1.26, 0.22, 12, RED, True)
    textbox(slide, "已经提升 planner / robot success；Depth4ToM-FT 与 TransCG full test 仍未完成。",
            2.28, 5.61, 9.65, 0.24, 12.2, MUTED)
    footer(slide, "本地完整运行：Booster 228、LayeredDepth validation 300、TablewareNet test 100 scenes。")

    # Slide 7 — next work
    slide = prs.slides.add_slide(blank)
    background(slide)
    title(slide, "下一步：先证明规划收益，再训练新 Head", 7)
    stages = [
        (1, "Planner oracle", "同一 planner 下比较", "GT-front\nvs GT-events", TEAL),
        (2, "补齐 native baselines", "完成 TransCG 余下 12 scenes", "DFNet + ReMake\n23,524 samples", BLUE),
        (3, "统一 failure slice", "按场景报告置信区间", "穿壁 / 空腔 /\n遮挡 / mask", ORANGE),
        (4, "训练我们的 Head", "仅在 Gate 1 成立后", "DepthHypothesisPack", GREEN),
    ]
    for i, (number, heading, subheading, detail, accent) in enumerate(stages):
        x = 0.72 + i * 3.10
        circle(slide, x + 0.99, 1.60, 0.52, accent, str(number))
        if i < 3:
            line(slide, x + 1.51, 1.86, x + 3.02, 1.86, LINE, 1.5)
        textbox(slide, heading, x, 2.43, 2.52, 0.42, 13, INK, True, PP_ALIGN.CENTER)
        textbox(slide, subheading, x, 3.05, 2.52, 0.38, 10.2, MUTED, False, PP_ALIGN.CENTER)
        rect(slide, x + 0.10, 3.74, 2.32, 0.82, SOFT, SOFT, rounded=True)
        textbox(slide, detail, x + 0.20, 3.95, 2.12, 0.38, 10.3, accent, True, PP_ALIGN.CENTER)

    rect(slide, 1.12, 5.29, 11.08, 0.78, SOFT_TEAL, SOFT_TEAL, rounded=True)
    textbox(slide, "Go / No-Go", 1.39, 5.55, 1.36, 0.20, 12, TEAL, True)
    textbox(slide, "若 GT-events 不能改善固定 planner，就先修 planner / benchmark，而不是继续堆模型。",
            2.64, 5.51, 9.16, 0.29, 14, INK, True)
    textbox(slide, "我们真正要证明的是：多层几何 → 更少的抓取规划错误。",
            2.28, 6.48, 8.76, 0.27, 16, TEAL, True, PP_ALIGN.CENTER)
    footer(slide, "TransCG 下载仍以断点续传方式轮询 Google Drive 配额。")

    prs.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
