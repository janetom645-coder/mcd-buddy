"""生成「麦门四重奏 McQuartet」宣传视频（16:9 横屏 + 9:16 竖屏）。

设计取舍
--------
不用录屏，而是**用真实数据重新排版成设计过的画面**。原因：
  - Windows 自带的等宽中文字体（MS Gothic / SimSun）会把 emoji 渲染成豆腐块，
    直接投屏终端输出会满屏「□」；
  - 终端原始输出信息密度太高，放在 15 秒的短视频里根本看不清。

所以这里把四个模块**真实跑出来的数据**（数字全部来自线上实测）重新设计成
卡片、表格、对比条，再用 PIL 逐帧渲染、ffmpeg 编码。

用法::

    python promo/make_promo.py --aspect 16:9 --out promo/mcquartet-16x9.mp4
    python promo/make_promo.py --aspect 9:16 --out promo/mcquartet-9x16.mp4
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ------------------------------------------------------------------ 调色板

RED = (218, 41, 28)
RED_DARK = (170, 26, 17)
YELLOW = (255, 199, 44)
CREAM = (255, 248, 238)
CREAM_DEEP = (252, 238, 219)
INK = (43, 33, 24)
INK_SOFT = (122, 104, 84)
GREEN = (26, 127, 55)
WHITE = (255, 255, 255)
CARD = (255, 255, 255)

FONT_DIR = Path("C:/Windows/Fonts")
HEAD_FONT = FONT_DIR / "msyhbd.ttc"   # 微软雅黑 Bold
BODY_FONT = FONT_DIR / "msyh.ttc"     # 微软雅黑
EMOJI_FONT = FONT_DIR / "seguiemj.ttf"  # Segoe UI Emoji（彩色）

FPS = 30

_font_cache: dict[tuple, ImageFont.FreeTypeFont] = {}


def font(path: Path, size: int, index: int = 0) -> ImageFont.FreeTypeFont:
    key = (str(path), size, index)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(str(path), size, index=index)
    return _font_cache[key]


# ------------------------------------------------------------------ 中英混排 + 彩色 emoji


def _is_emoji(ch: str) -> bool:
    cp = ord(ch)
    return (
        0x1F300 <= cp <= 0x1FAFF
        or 0x1F000 <= cp <= 0x1F2FF
        or 0x2600 <= cp <= 0x27BF
        or 0x2B00 <= cp <= 0x2BFF
        or 0x1F1E6 <= cp <= 0x1F1FF
        or cp in (0xFE0F, 0x200D, 0x20E3)
    )


def tokenize(text: str) -> list[tuple[str, str]]:
    """把字符串切成 [(kind, chunk)]，kind 为 'e'(emoji) 或 't'(普通文字)。"""
    runs: list[tuple[str, str]] = []
    buf = ""
    kind = "t"
    for ch in text:
        k = "e" if _is_emoji(ch) else "t"
        if not buf:
            kind = k
        elif k != kind:
            runs.append((kind, buf))
            buf = ""
            kind = k
        buf += ch
    if buf:
        runs.append((kind, buf))
    return runs


def mixed_size(text: str, size: int) -> tuple[int, int]:
    """混排文本的像素宽高。"""
    w = 0
    asc = desc = 0
    for kind, chunk in tokenize(text):
        f = font(EMOJI_FONT if kind == "e" else BODY_FONT, size)
        bbox = f.getbbox(chunk)
        w += bbox[2] - bbox[0]
        a, d = f.getmetrics()
        asc = max(asc, a)
        desc = max(desc, d)
    return w, asc + desc


def draw_mixed(
    img: Image.Image,
    xy: tuple[int, int],
    text: str,
    size: int,
    fill=INK,
    head: bool = False,
) -> int:
    """画中英混排 + 彩色 emoji，返回结束的 x 坐标。"""
    d = ImageDraw.Draw(img)
    x, y = xy
    body_path = HEAD_FONT if head else BODY_FONT
    for kind, chunk in tokenize(text):
        if kind == "e":
            f = font(EMOJI_FONT, size)
            d.text((x, y), chunk, font=f, embedded_color=True, anchor="ls")
        else:
            f = font(body_path, size)
            d.text((x, y), chunk, font=f, fill=fill, anchor="ls")
        bbox = f.getbbox(chunk)
        x += bbox[2] - bbox[0]
    return x


def draw_mixed_center(
    img: Image.Image,
    cx: int,
    baseline: int,
    text: str,
    size: int,
    fill=INK,
    head: bool = False,
) -> None:
    w, _ = mixed_size(text, size)
    draw_mixed(img, (cx - w // 2, baseline), text, size, fill=fill, head=head)


# ------------------------------------------------------------------ 基础图形


def rounded(d: ImageDraw.ImageDraw, box, radius, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def card(img, box, radius=28, fill=CARD, shadow=True):
    """带柔和投影的圆角卡片。"""
    if shadow:
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        x0, y0, x1, y1 = box
        sd.rounded_rectangle(
            (x0 + 5, y0 + 9, x1 + 5, y1 + 9), radius=radius, fill=(180, 150, 120, 60)
        )
        img.alpha_composite(sh)
    d = ImageDraw.Draw(img)
    rounded(d, box, radius, fill=fill)


def arch(img, cx, cy, size, color, width):
    """金拱门「M」：两个并排的半圆拱，底边对齐 cy，总宽 size。"""
    d = ImageDraw.Draw(img)
    h = size / 2
    for sign in (-1, 1):
        cxh = cx + sign * h / 2
        d.arc([cxh - h / 2, cy - h / 2, cxh + h / 2, cy + h / 2], 180, 360, fill=color, width=width)


def split_two(text: str) -> tuple[str, str]:
    """把一句话尽量在标点处折成两行，避免从词中间劈开。"""
    for sep in ("，", "、", "；", "·"):
        if sep in text:
            i = text.index(sep) + 1
            if 0 < i < len(text):
                return text[:i], text[i:]
    mid = len(text) // 2
    return text[:mid], text[mid:]


def ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_io(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def seg(t: float, start: float, dur: float) -> float:
    """把全局进度映射成某一段的 0→1 进度。"""
    if dur <= 0:
        return 1.0 if t >= start else 0.0
    return max(0.0, min(1.0, (t - start) / dur))


def background(w: int, h: int, tint=CREAM) -> Image.Image:
    img = Image.new("RGBA", (w, h), tint + (255,))
    d = ImageDraw.Draw(img)
    # 淡淡的斜纹，避免纯色发闷
    for i in range(-h, w, 90):
        d.line([(i, h), (i + h, 0)], fill=(238, 224, 204, 90), width=26)
    return img


# ------------------------------------------------------------------ 真实数据
# 以下数字全部来自线上真实调用（2026-10-10，深圳湾一店 / 用户账号实测）

PRACTICE = {
    "level": "麦门学徒",
    "orders": "8 单",
    "days": "8 天",
    "spend": "¥138.00",
    "coupons": "3 张",
    "progress": (3, 10),
    "next": "麦门弟子",
    "badges": 5,
    "levels": 6,
}

GROUP = [
    ("小王", "巨无霸", "¥24.50", "想吃「牛肉」 · 预算 ¥25"),
    ("小李", "麦香鸡", "¥15.50", "想吃「鸡肉」 · 预算 ¥20 · 忌口 辣"),
    ("小张", "麦香鱼", "¥17.50", "想吃「鱼」 · 预算 ¥15"),
    ("小赵", "高达吉士双牛堡", "¥26.00", "想吃「汉堡」 · 预算 ¥30 · 忌口 油炸"),
    ("小陈", "大薯条", "¥13.50", "想吃「素食」 · 预算 ¥22"),
    ("小周", "大杯鲜萃咖啡", "¥12.50", "想吃「咖啡」 · 预算 ¥18"),
]
GROUP_TOTAL = ("¥109.50", "¥18.25")

HIDDEN = {
    "name": "全明星双人分享餐八件套 · 减脂版",
    "energy": (2150, 1212),
    "fat": (90, 55),
    "protein": 61,
}

FORTUNE = {
    "sign": "中吉",
    "verse": "咖啡入喉，万事不愁",
    "picks": [("🥇", "高达吉士双牛堡", "448 kcal"), ("🥈", "猪柳蛋麦满分", "387 kcal")],
    "hour": "09:00 - 10:00",
    "lucky": "51",
}

MODULES = [
    ("🧘", "修行录", "点餐即打卡，解锁成就与麦门段位"),
    ("🍱", "团餐指挥官", "一群人的点单，自动合成最优团餐"),
    ("🧪", "隐藏菜单实验室", "重组套餐配方，实时对比营养"),
    ("🔮", "每日运势签", "今天宜吃啥，还有活动与抽奖吉时"),
]

REPO = "github.com/janetom645-coder/mcd-buddy"


# ------------------------------------------------------------------ 场景
# 每个场景签名: fn(img, t) -> None，t 为 0→1 的场景内进度


def scene_intro(img, t):
    w, h = img.size
    cx = w // 2

    a = ease_out(seg(t, 0.0, 0.22))
    size = int(w * 0.20 * (0.6 + 0.4 * a))
    arch(img, cx, int(h * 0.36), size, YELLOW, max(6, int(size * 0.14)))

    if t > 0.10:
        k = ease_out(seg(t, 0.10, 0.25))
        size = int(w * 0.021)
        draw_mixed_center(
            img, cx, int(h * 0.52) + int(30 * (1 - k)), "麦当劳中国官方 MCP 已上线",
            size, INK_SOFT,
        )

    if t > 0.22:
        k = ease_out(seg(t, 0.22, 0.30))
        size = int(w * 0.062)
        draw_mixed_center(
            img, cx, int(h * 0.63) + int(40 * (1 - k)),
            "我给它写了个「四重奏」", size, RED, head=True,
        )

    if t > 0.45:
        k = ease_out(seg(t, 0.45, 0.30))
        size = int(w * 0.030)
        draw_mixed_center(
            img, cx, int(h * 0.74) + int(30 * (1 - k)),
            "🍔 🍟 🥤 🍦", size, INK,
        )


def scene_modules(img, t):
    w, h = img.size
    cx = w // 2
    tall = h > w

    draw_mixed_center(img, cx, int(h * (0.16 if not tall else 0.14)),
                      "一个 Skill · 四个玩法", int(w * 0.040), RED, head=True)

    if tall:
        cw, ch = int(w * 0.80), int(h * 0.135)
        x0 = (w - cw) // 2
        top = int(h * 0.21)
        gap = int(h * 0.022)
        for i, (emoji, name, desc) in enumerate(MODULES):
            k = ease_out(seg(t, 0.10 + i * 0.12, 0.28))
            y = top + i * (ch + gap)
            box = (x0 + int(70 * (1 - k)), y, x0 + cw, y + ch)
            card(img, box)
            draw_mixed(img, (box[0] + int(w * 0.05), y + int(ch * 0.40)),
                       emoji, int(w * 0.062))
            draw_mixed(img, (box[0] + int(w * 0.155), y + int(ch * 0.36)),
                       name, int(w * 0.043), RED, head=True)
            draw_mixed(img, (box[0] + int(w * 0.155), y + int(ch * 0.72)),
                       desc, int(w * 0.027), INK_SOFT)
    else:
        cw = int(w * 0.205)
        gap = int(w * 0.022)
        total = cw * 4 + gap * 3
        x0 = (w - total) // 2
        top = int(h * 0.30)
        ch = int(h * 0.46)
        for i, (emoji, name, desc) in enumerate(MODULES):
            k = ease_out(seg(t, 0.10 + i * 0.12, 0.28))
            x = x0 + i * (cw + gap)
            y = top + int(60 * (1 - k))
            box = (x, y, x + cw, y + ch)
            card(img, box)
            draw_mixed_center(img, x + cw // 2, y + int(ch * 0.30), emoji, int(w * 0.052))
            draw_mixed_center(img, x + cw // 2, y + int(ch * 0.50), name, int(w * 0.024), RED, head=True)
            # 描述按两行折（优先在标点处断，避免从词中间劈开）
            desc_size = int(w * 0.0145)
            for j, part in enumerate(split_two(desc)):
                draw_mixed_center(img, x + cw // 2, y + int(ch * 0.66) + j * int(desc_size * 1.7),
                                  part, desc_size, INK_SOFT)


def scene_practice(img, t):
    w, h = img.size
    cx = w // 2
    tall = h > w

    draw_mixed_center(img, cx, int(h * (0.15 if not tall else 0.10)),
                      "🧘 修行录", int(w * 0.044), RED, head=True)
    draw_mixed_center(img, cx, int(h * (0.15 if not tall else 0.10)) + int(w * 0.032),
                      "把「吃麦当劳」变成一场修行", int(w * 0.020), INK_SOFT)

    m = int(w * 0.08)
    if tall:
        box = (m, int(h * 0.22), w - m, int(h * 0.42))
    else:
        box = (m, int(h * 0.32), m + int(w * 0.42), int(h * 0.72))
    card(img, box)
    bx0, by0, bx1, by1 = box
    inner = bx0 + int(w * 0.03)
    draw_mixed(img, (inner, by0 + int(h * 0.075)), "🎖️ 当前段位", int(w * 0.018), INK_SOFT)
    draw_mixed(img, (inner, by0 + int(h * 0.145)), PRACTICE["level"], int(w * 0.042), RED, head=True)

    # 薯条进度条
    bar_y = by0 + int(h * 0.20)
    bar_w = bx1 - bx0 - int(w * 0.06)
    done, total = PRACTICE["progress"]
    frac = ease_out(seg(t, 0.20, 0.45)) * (done / total)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((inner, bar_y, inner + bar_w, bar_y + int(h * 0.028)),
                        radius=int(h * 0.014), fill=CREAM_DEEP)
    d.rounded_rectangle((inner, bar_y, inner + max(6, int(bar_w * frac)), bar_y + int(h * 0.028)),
                        radius=int(h * 0.014), fill=YELLOW)
    draw_mixed(img, (inner, bar_y + int(h * 0.065)),
               f"{done}/{total}　距「{PRACTICE['next']}」还差 {total - done} 单",
               int(w * 0.018), INK)

    # 数据格
    if tall:
        gbox = (m, int(h * 0.45), w - m, int(h * 0.68))
    else:
        gbox = (m + int(w * 0.46), int(h * 0.32), w - m, int(h * 0.72))
    card(img, gbox)
    gx0, gy0, gx1, gy1 = gbox
    stats = [
        ("🍔 累计点餐", PRACTICE["orders"]),
        ("📆 修行天数", PRACTICE["days"]),
        ("💸 累计消费", PRACTICE["spend"]),
        ("🎟️ 卡包券数", PRACTICE["coupons"]),
    ]
    col_w = (gx1 - gx0) // 2
    row_h = (gy1 - gy0) // 2
    for i, (label, value) in enumerate(stats):
        k = ease_out(seg(t, 0.30 + i * 0.08, 0.25))
        x = gx0 + (i % 2) * col_w + int(w * 0.02)
        y = gy0 + (i // 2) * row_h + int(h * 0.055)
        draw_mixed(img, (x, y - int(h * 0.012) + int(14 * (1 - k))), label, int(w * 0.0155), INK_SOFT)
        draw_mixed(img, (x, y + int(h * 0.030) + int(14 * (1 - k))), value, int(w * 0.027), INK, head=True)

    k = ease_out(seg(t, 0.62, 0.28))
    draw_mixed_center(img, cx, int(h * (0.80 if not tall else 0.75)) + int(20 * (1 - k)),
                      f"🏅 {PRACTICE['badges']} 枚成就徽章　·　{PRACTICE['levels']} 级段位",
                      int(w * 0.024), RED_DARK, head=True)


def _group_command_card(img, cx, t):
    """竖版专用：底部一张深色终端卡，展示真实可复现的命令。"""
    w, h = img.size
    d = ImageDraw.Draw(img)

    k = ease_out(seg(t, 0.78, 0.22))
    if k <= 0:
        return
    dy = int(28 * (1 - k))

    cap_y = int(h * 0.665) + dy
    draw_mixed_center(img, cx, cap_y, "一条命令，不用 Token 就能复现", int(w * 0.022), INK, head=True)

    m = int(w * 0.075)
    top = int(h * 0.715) + dy
    bot = int(h * 0.875) + dy
    d.rounded_rectangle((m, top, w - m, bot), radius=int(h * 0.020), fill=INK)

    dot = int(w * 0.013)
    for i, color in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        dx = m + int(w * 0.032) + i * int(w * 0.030)
        d.ellipse((dx, top + int(h * 0.017), dx + dot, top + int(h * 0.017) + dot), fill=color)

    lh = int(h * 0.034)
    l1 = top + int(h * 0.050)
    tx = m + int(w * 0.032)
    draw_mixed(img, (tx, l1), "$ mcd-buddy group-meal --demo",
               int(w * 0.0175), (255, 199, 44), head=True)
    draw_mixed(img, (tx, l1 + lh), "→ 6 人团餐 ¥109.50　·　人均 ¥18.25",
               int(w * 0.0165), (235, 230, 222))
    draw_mixed(img, (tx, l1 + lh * 2), "→ 忌口 > 口味 > 预算，不会推 2 块钱的饼干",
               int(w * 0.0155), (158, 226, 172))


def scene_group(img, t):
    w, h = img.size
    cx = w // 2
    tall = h > w

    draw_mixed_center(img, cx, int(h * (0.13 if not tall else 0.09)),
                      "🍱 团餐指挥官", int(w * 0.044), RED, head=True)
    draw_mixed_center(img, cx, int(h * (0.13 if not tall else 0.09)) + int(w * 0.032),
                      "一群人的点单，不用吵", int(w * 0.020), INK_SOFT)

    # 竖版画面更窄更长，文字随宽度缩得比横版小，所以整体上移、卡片按行数取高，
    # 再在下方补一张真实命令卡，避免底部留出一大条空白。
    m = int(w * 0.06)
    top = int(h * (0.27 if not tall else 0.185))
    card_h = int(h * (0.47 if not tall else 0.30))
    bot = top + card_h
    card(img, (m, top, w - m, bot))
    x0, y0, x1, y1 = m, top, w - m, bot
    inner = x0 + int(w * 0.025)

    # 表头 + N 行数据 = N+1 个等分槽，行高自适应，不留空
    slot = (y1 - y0) // (len(GROUP) + 1)

    def row_base(i: int) -> int:
        return y0 + slot * i + slot // 2

    d = ImageDraw.Draw(img)
    heads = ["伙伴", "推荐单品", "单价", "依据"]
    colx = [inner, inner + int(w * 0.11), inner + int(w * 0.40), inner + int(w * 0.50)]
    hy = row_base(0)
    for label, x in zip(heads, colx, strict=False):
        draw_mixed(img, (x, hy), label, int(w * 0.0165), INK_SOFT, head=True)
    d.line((inner, hy + int(h * 0.012), x1 - int(w * 0.025), hy + int(h * 0.012)),
           fill=CREAM_DEEP, width=3)

    for i, (who, dish, price, why) in enumerate(GROUP):
        k = ease_out(seg(t, 0.16 + i * 0.09, 0.26))
        y = row_base(i + 1) + int(18 * (1 - k))
        draw_mixed(img, (colx[0], y), who, int(w * 0.0175), INK, head=True)
        draw_mixed(img, (colx[1], y), dish, int(w * 0.0175), INK)
        draw_mixed(img, (colx[2], y), price, int(w * 0.0175), RED, head=True)
        draw_mixed(img, (colx[3], y), why, int(w * (0.0145 if not tall else 0.0130)), INK_SOFT)

    k = ease_out(seg(t, 0.72, 0.22))
    y = y1 + int(h * (0.075 if not tall else 0.070)) + int(20 * (1 - k))
    draw_mixed_center(img, cx, y, f"应付 {GROUP_TOTAL[0]}　·　人均 {GROUP_TOTAL[1]}",
                      int(w * 0.028), RED_DARK, head=True)
    k2 = ease_out(seg(t, 0.80, 0.20))
    draw_mixed_center(img, cx, y + int(h * 0.048) + int(20 * (1 - k2)),
                      "忌口 > 口味 > 预算，预算内取最接近预算的那份",
                      int(w * 0.0185), INK_SOFT)

    if tall:
        _group_command_card(img, cx, t)


def scene_hidden(img, t):
    w, h = img.size
    cx = w // 2
    tall = h > w

    draw_mixed_center(img, cx, int(h * (0.13 if not tall else 0.09)),
                      "🧪 隐藏菜单实验室", int(w * 0.044), RED, head=True)
    draw_mixed_center(img, cx, int(h * (0.13 if not tall else 0.09)) + int(w * 0.032),
                      "人人都能发明自己的麦当劳", int(w * 0.020), INK_SOFT)

    m = int(w * 0.09)
    y = int(h * (0.27 if not tall else 0.19))
    k = ease_out(seg(t, 0.06, 0.22))
    draw_mixed_center(img, cx, y + int(24 * (1 - k)), HIDDEN["name"], int(w * 0.026), INK, head=True)

    d = ImageDraw.Draw(img)
    rows = [
        ("🔥 能量", HIDDEN["energy"][0], HIDDEN["energy"][1], "kcal"),
        ("🧈 脂肪", HIDDEN["fat"][0], HIDDEN["fat"][1], "g"),
    ]
    top = int(h * (0.36 if not tall else 0.28))
    row_h = int(h * 0.135)
    full = int(w * 0.46)
    bh = int(h * 0.024)
    radius = int(bh / 2)
    for i, (label, before, after, unit) in enumerate(rows):
        k = ease_out(seg(t, 0.20 + i * 0.14, 0.30))
        yy = top + i * row_h
        draw_mixed(img, (m, yy), label, int(w * 0.019), INK_SOFT)

        bar_y = yy + int(h * 0.030)
        # 原配方（浅色）在下，改配后（黄色）覆盖其上 —— 露出的浅色就是「省下来的」
        d.rounded_rectangle((m, bar_y, m + int(full * k), bar_y + bh), radius=radius,
                            fill=(232, 212, 184))
        d.rounded_rectangle((m, bar_y, m + max(radius, int(full * (after / before) * k)), bar_y + bh),
                            radius=radius, fill=YELLOW)

        ty = bar_y + int(bh * 0.85)
        size = int(w * 0.019)
        tx = m + full + int(w * 0.025)
        s1 = f"{before} → {after} {unit}"
        draw_mixed(img, (tx, ty), s1, size, INK, head=True)
        w1, _ = mixed_size(s1, size)
        draw_mixed(img, (tx + w1 + int(w * 0.022), ty), f"{after - before:+d}", size, GREEN, head=True)

    k = ease_out(seg(t, 0.60, 0.26))
    draw_mixed_center(img, cx, int(h * (0.70 if not tall else 0.68)) + int(20 * (1 - k)),
                      f"蛋白质保留 {HIDDEN['protein']}g", int(w * 0.024), RED_DARK, head=True)
    k2 = ease_out(seg(t, 0.72, 0.25))
    draw_mixed_center(img, cx, int(h * (0.70 if not tall else 0.68)) + int(h * 0.055) + int(20 * (1 - k2)),
                      "改配价格回传门店实时核价，不是估算", int(w * 0.0185), INK_SOFT)


def scene_fortune(img, t):
    w, h = img.size
    cx = w // 2
    tall = h > w

    draw_mixed_center(img, cx, int(h * (0.13 if not tall else 0.09)),
                      "🔮 每日运势签", int(w * 0.044), RED, head=True)
    draw_mixed_center(img, cx, int(h * (0.13 if not tall else 0.09)) + int(w * 0.032),
                      "今天宜吃啥，交给麦门灵签", int(w * 0.020), INK_SOFT)

    m = int(w * 0.14)
    top = int(h * (0.28 if not tall else 0.20))
    box = (m, top, w - m, top + int(h * (0.28 if not tall else 0.30)))
    card(img, box)
    x0, y0, x1, y1 = box
    k = ease_out(seg(t, 0.08, 0.24))
    draw_mixed_center(img, cx, y0 + int(h * 0.075) + int(20 * (1 - k)),
                      f"🎋 签　等：{FORTUNE['sign']}", int(w * 0.030), RED, head=True)
    k2 = ease_out(seg(t, 0.22, 0.26))
    draw_mixed_center(img, cx, y0 + int(h * 0.175) + int(20 * (1 - k2)),
                      f"📜 签　文：{FORTUNE['verse']}", int(w * 0.023), INK)

    k3 = ease_out(seg(t, 0.42, 0.26))
    y = y1 + int(h * 0.075) + int(24 * (1 - k3))
    draw_mixed_center(img, cx, y, "今日宜吃", int(w * 0.021), INK_SOFT, head=True)
    for i, (medal, dish, kcal) in enumerate(FORTUNE["picks"]):
        kk = ease_out(seg(t, 0.48 + i * 0.10, 0.24))
        draw_mixed_center(img, cx, y + int(h * 0.055) * (i + 1) + int(20 * (1 - kk)),
                          f"{medal} {dish}　{kcal}", int(w * 0.026), INK, head=True)

    k4 = ease_out(seg(t, 0.70, 0.24))
    draw_mixed_center(img, cx, int(h * (0.88 if not tall else 0.86)) + int(20 * (1 - k4)),
                      f"⏰ 吉时 {FORTUNE['hour']}　·　🔢 幸运数字 {FORTUNE['lucky']}",
                      int(w * 0.019), RED_DARK)


def scene_tech(img, t):
    w, h = img.size
    cx = w // 2
    tall = h > w

    draw_mixed_center(img, cx, int(h * (0.18 if not tall else 0.14)),
                      "不是壳子，是真的接进去了", int(w * 0.038), RED, head=True)

    stats = [("35", "个真实 MCP 工具"), ("187", "个测试全绿"), ("0", "处假数据")]
    if tall:
        top = int(h * 0.28)
        row_h = int(h * 0.15)
        for i, (num, label) in enumerate(stats):
            k = ease_out(seg(t, 0.10 + i * 0.13, 0.28))
            y = top + i * row_h + int(30 * (1 - k))
            draw_mixed_center(img, cx, y, num, int(w * 0.10), RED, head=True)
            draw_mixed_center(img, cx, y + int(h * 0.038), label, int(w * 0.024), INK_SOFT)
    else:
        top = int(h * 0.42)
        col_w = w // 3
        for i, (num, label) in enumerate(stats):
            k = ease_out(seg(t, 0.10 + i * 0.13, 0.28))
            x = col_w * i + col_w // 2
            draw_mixed_center(img, x, top + int(30 * (1 - k)), num, int(w * 0.062), RED, head=True)
            draw_mixed_center(img, x, top + int(h * 0.075) + int(30 * (1 - k)),
                              label, int(w * 0.019), INK_SOFT)

    k = ease_out(seg(t, 0.50, 0.28))
    draw_mixed_center(img, cx, int(h * (0.80 if not tall else 0.76)) + int(24 * (1 - k)),
                      "所有 API 行为都来自实测，不是文档推测", int(w * 0.021), INK)
    k2 = ease_out(seg(t, 0.64, 0.28))
    draw_mixed_center(img, cx, int(h * (0.80 if not tall else 0.76)) + int(h * 0.05) + int(24 * (1 - k2)),
                      "离线演示与线上行为同构，由测试锁死保真度", int(w * 0.0185), INK_SOFT)


def scene_cta(img, t):
    w, h = img.size
    cx = w // 2
    d = ImageDraw.Draw(img)

    a = ease_out(seg(t, 0.0, 0.22))
    size = int(w * 0.14 * (0.7 + 0.3 * a))
    arch(img, cx, int(h * 0.30), size, YELLOW, max(5, int(size * 0.14)))

    k = ease_out(seg(t, 0.10, 0.26))
    draw_mixed_center(img, cx, int(h * 0.47) + int(30 * (1 - k)),
                      "麦门四重奏 McQuartet", int(w * 0.045), RED, head=True)

    k2 = ease_out(seg(t, 0.26, 0.26))
    draw_mixed_center(img, cx, int(h * 0.57) + int(24 * (1 - k2)), REPO, int(w * 0.024), INK)

    k3 = ease_out(seg(t, 0.44, 0.26))
    size = int(w * 0.034)
    tw, _ = mixed_size("⭐ 求个 Star 支持一下", size)
    box = (cx - tw // 2 - int(w * 0.03), int(h * 0.64) - int(size * 1.2),
           cx + tw // 2 + int(w * 0.03), int(h * 0.64) + int(size * 0.55))
    d.rounded_rectangle(box, radius=int(h * 0.035), fill=RED)
    draw_mixed_center(img, cx, int(h * 0.64) + int(24 * (1 - k3)), "⭐ 求个 Star 支持一下",
                      size, WHITE, head=True)

    k4 = ease_out(seg(t, 0.60, 0.26))
    draw_mixed_center(img, cx, int(h * 0.78) + int(20 * (1 - k4)),
                      "麦当劳程序员创意开发大赛 · 参赛作品", int(w * 0.019), INK_SOFT)


# ------------------------------------------------------------------ 时间轴

SCENES = [
    (scene_intro, 6.0, 4.5),
    (scene_modules, 8.5, 7.0),
    (scene_practice, 13.0, 10.5),
    (scene_group, 15.0, 11.5),
    (scene_hidden, 13.0, 10.5),
    (scene_fortune, 12.0, 9.5),
    (scene_tech, 9.5, 7.0),
    (scene_cta, 9.0, 7.0),
]

FADE = 0.35


def render_frames(w: int, h: int, tall: bool, total: float):
    """逐帧生成 RGB 数据，yield bytes。"""
    durations = [d if not tall else td for _, d, td in SCENES]
    starts: list[float] = []
    acc = 0.0
    for d in durations:
        starts.append(acc)
        acc += d
    total = acc

    n_frames = int(total * FPS)
    for i in range(n_frames):
        now = i / FPS
        idx = 0
        for j, st in enumerate(starts):
            if now >= st:
                idx = j
        dur = durations[idx]
        local = (now - starts[idx]) / dur

        img = background(w, h)
        scene = SCENES[idx][0]

        # 与上一场景交叉淡化
        prev_alpha = 1.0
        if now - starts[idx] < FADE and idx > 0:
            prev_alpha = (now - starts[idx]) / FADE
            prev_img = background(w, h)
            SCENES[idx - 1][0](prev_img, 1.0)
            img = prev_img

        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        scene(layer, local)

        if prev_alpha < 1.0:
            # 用默认参数把循环变量绑进闭包，避免 B023（延迟求值会取到最后一次的值）
            a = layer.getchannel("A").point(lambda v, _a=prev_alpha: int(v * _a))
            layer.putalpha(a)

        img.alpha_composite(layer)
        yield img.convert("RGB").tobytes()


def encode(aspect: str, out_path: Path) -> None:
    if aspect == "16:9":
        w, h, tall = 1920, 1080, False
    else:
        w, h, tall = 1080, 1920, True

    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    durations = [d if not tall else td for _, d, td in SCENES]
    total = sum(durations)
    print(f"[{aspect}] {w}x{h} · {total:.1f}s · {int(total * FPS)} 帧")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for n, frame in enumerate(render_frames(w, h, tall, total), 1):
            proc.stdin.write(frame)
            if n % 150 == 0:
                print(f"  {n} 帧 …", flush=True)
    finally:
        proc.stdin.close()
        proc.wait()
    if proc.returncode != 0:
        raise SystemExit(f"ffmpeg 失败，退出码 {proc.returncode}")
    print(f"✅ 已生成 {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aspect", choices=["16:9", "9:16", "both"], default="both")
    ap.add_argument("--out", default="promo")
    args = ap.parse_args()

    base = Path(args.out)
    if args.aspect in ("16:9", "both"):
        encode("16:9", base / "mcquartet-16x9.mp4")
    if args.aspect in ("9:16", "both"):
        encode("9:16", base / "mcquartet-9x16.mp4")


if __name__ == "__main__":
    main()
