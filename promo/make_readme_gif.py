"""生成 README 首屏用的演示 GIF。

为什么不用录屏：Windows 终端默认字体（MS Gothic / SimSun）会把 emoji 渲染成豆腐块，
录出来是一片方框。所以这里用 Pillow 按终端的样式**逐帧绘制**真实 `--demo` 输出的内容，
字体走 msyh + seguiemj，emoji 正常显示。

所有数字都取自真实 `--demo` 运行结果，改数据请同步 `make_promo.py` 里的常量。

用法：
    python promo/make_readme_gif.py --out promo/demo.gif
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from make_promo import draw_mixed, draw_mixed_center, ease_out, seg

# ------------------------------------------------------------------ 视觉常量

W, H = 1000, 560
FPS = 12
BG = (27, 27, 31)
BAR = (42, 42, 48)
EDGE = (58, 58, 66)
TXT = (222, 222, 226)
DIM = (140, 140, 150)
GREEN = (80, 220, 120)
YELLOW = (255, 199, 44)
RED = (255, 110, 100)
TRACK = (70, 70, 78)

PAD_X = 46
PAD_Y = 74
LINE_H = 33

TITLE = "mcd-buddy — zsh"

CMD1 = "mcd-buddy practice --demo"
CMD2 = "mcd-buddy group-meal --demo"

# 修行录：真实 --demo 输出（markdown 表格按对齐列呈现）
OUT1_HEAD = [
    ("  🍟 麦门修行录 🍔", YELLOW),
    ("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", EDGE),
    ("", None),
    ("  🎖️ 当前段位：麦门学徒", TXT),
    ("__PROGRESS__", None),          # 占位：进度条单独绘制，避免 ▰▱ 落到 emoji 字体
    ("", None),
]
OUT1_ROWS = [
    ("🍔 累计点餐", "8 单"),
    ("📆 修行天数", "8 天"),
    ("💸 累计消费", "¥138.00"),
    ("🎟️ 卡包券数", "3 张"),
    ("🏅 成就徽章", "5/12"),
]

# 团餐指挥官：真实 --demo 输出
OUT2_HEAD = [
    ("  🍟 团餐指挥官 🍔", YELLOW),
    ("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", EDGE),
    ("", None),
    ("  👥 6 人　·　到店自取", TXT),
    ("  💰 应付 ¥109.50　·　人均 ¥18.25", TXT),
    ("", None),
]
OUT2_ROWS = [
    ("小王", "巨无霸", "¥24.50"),
    ("小李", "麦香鸡", "¥15.50"),
    ("小张", "麦香鱼", "¥17.50"),
    ("小赵", "高达吉士双牛堡", "¥26.00"),
    ("小陈", "大薯条", "¥13.50"),
    ("小周", "大杯鲜萃咖啡", "¥12.50"),
]
OUT2_TAIL = [("  ⚠️ 小张：超预算 ¥2.50", DIM)]

# 列位置（固定 x，保证不同字宽也严格对齐）
COL_NAME = PAD_X + 14
COL_DISH = PAD_X + 96
COL_PRICE = PAD_X + 330
COL_VALUE = PAD_X + 260


def terminal_base() -> Image.Image:
    """画一个静态的终端窗口底板。"""
    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)

    # 标题栏
    d.rectangle((0, 0, W, 44), fill=BAR)
    d.line((0, 44, W, 44), fill=EDGE, width=2)
    for i, color in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        cx = 28 + i * 22
        d.ellipse((cx - 7, 15, cx + 7, 29), fill=color)
    draw_mixed_center(img, W // 2, 31, TITLE, 17, DIM)
    return img


def draw_prompt(img: Image.Image, y: int, cmd: str, typed: int) -> None:
    """画 `$ ` 提示符与「正在输入」的命令。"""
    draw_mixed(img, (PAD_X, y), "$", 21, GREEN, head=True)
    draw_mixed(img, (PAD_X + 20, y), cmd[:typed], 21, TXT)
    if typed < len(cmd):
        # 光标
        x = PAD_X + 20 + (len(cmd[:typed]) * 12)
        d = ImageDraw.Draw(img)
        d.rectangle((x, y - 18, x + 11, y + 4), fill=(200, 200, 210))


def draw_rows(img: Image.Image, y0: int, rows, reveal: int) -> None:
    """逐行揭示「标签 —— 数值」两列。"""
    for i, (label, value) in enumerate(rows):
        if i >= reveal:
            break
        y = y0 + i * LINE_H
        k = ease_out(seg(reveal - i, 0, 1))
        dy = int(9 * (1 - k))
        draw_mixed(img, (PAD_X + 14, y + dy), label, 20, DIM)
        draw_mixed(img, (COL_VALUE, y + dy), value, 20, TXT, head=True)


def draw_table(img: Image.Image, y0: int, rows, reveal: int) -> None:
    """逐行揭示「伙伴 / 单品 / 单价」三列表格。"""
    for i, (who, dish, price) in enumerate(rows):
        if i >= reveal:
            break
        y = y0 + i * LINE_H
        k = ease_out(seg(reveal - i, 0, 1))
        dy = int(9 * (1 - k))
        draw_mixed(img, (COL_NAME, y + dy), who, 20, TXT, head=True)
        draw_mixed(img, (COL_DISH, y + dy), dish, 20, TXT)
        draw_mixed(img, (COL_PRICE, y + dy), price, 20, YELLOW, head=True)


def draw_progress(img: Image.Image, y: int, done: int, total: int, fill: float) -> None:
    """手绘薯条进度条：▰▱ 在部分字体下会落到 emoji 字体，所以自己画。"""
    d = ImageDraw.Draw(img)
    x = PAD_X + 14
    draw_mixed(img, (x, y), "🍟", 20, TXT)
    x += 34

    seg_w, gap, bar_h = 15, 4, 15
    for i in range(total):
        bx = x + i * (seg_w + gap)
        by = y - bar_h + 2
        on = i < done
        if on:
            k = ease_out(max(0.0, min(1.0, fill * total - i)))
            h = max(3, int(bar_h * k))
            d.rounded_rectangle((bx, by + bar_h - h, bx + seg_w, by + bar_h),
                                radius=2, fill=YELLOW)
        else:
            d.rounded_rectangle((bx, by, bx + seg_w, by + bar_h), radius=2, fill=TRACK)

    x += total * (seg_w + gap) + 14
    draw_mixed(img, (x, y), f"{done}/{total}　距「麦门弟子」还差 {total - done} 单", 20, TXT)


def draw_block(img: Image.Image, y0: int, block, reveal: int, prog: float = 1.0) -> None:
    for i, (text, color) in enumerate(block):
        if i >= reveal:
            break
        if not text:
            continue
        k = ease_out(seg(reveal - i, 0, 1))
        y = y0 + i * LINE_H + int(9 * (1 - k))
        if text == "__PROGRESS__":
            draw_progress(img, y, 3, 10, prog)
        else:
            draw_mixed(img, (PAD_X, y), text, 20, color or TXT)


# ------------------------------------------------------------------ 时间轴
# 单位：秒
T_TYPE1 = (0.35, 0.75)          # 开始输入 / 时长
T_OUT1 = 1.25                   # 输出开始
N1 = len(OUT1_HEAD) + len(OUT1_ROWS)
T_HOLD1 = 0.9
T_TYPE2 = T_OUT1 + N1 * 0.26 + T_HOLD1
T_OUT2 = T_TYPE2 + 0.75 + 0.25
N2 = len(OUT2_HEAD) + len(OUT2_ROWS) + len(OUT2_TAIL)
T_END = T_OUT2 + N2 * 0.24 + 1.1
STEP1 = (T_TYPE2 - T_HOLD1 - T_OUT1) / max(1, N1)
STEP2 = (T_END - 1.1 - T_OUT2) / max(1, N2)


def frame(now: float) -> Image.Image:
    img = terminal_base()
    y0 = PAD_Y

    if now < T_TYPE2:
        typed = int(len(CMD1) * ease_out(seg(now, T_TYPE1[0], T_TYPE1[1])) * 1.02)
        draw_prompt(img, y0, CMD1, min(typed, len(CMD1)))
        if now >= T_OUT1:
            reveal = int((now - T_OUT1) / STEP1) + 1
            prog = ease_out(seg(now, T_OUT1 + 4 * STEP1, 6 * STEP1))
            draw_block(img, y0 + LINE_H, OUT1_HEAD, reveal, prog)
            draw_rows(img, y0 + LINE_H * (len(OUT1_HEAD) + 1), OUT1_ROWS,
                      max(0, reveal - len(OUT1_HEAD)))
    else:
        typed = int(len(CMD2) * ease_out(seg(now, T_TYPE2, 0.75)) * 1.02)
        draw_prompt(img, y0, CMD2, min(typed, len(CMD2)))
        if now >= T_OUT2:
            reveal = int((now - T_OUT2) / STEP2) + 1
            draw_block(img, y0 + LINE_H, OUT2_HEAD, reveal)
            draw_table(img, y0 + LINE_H * (len(OUT2_HEAD) + 1), OUT2_ROWS,
                       max(0, reveal - len(OUT2_HEAD)))
            draw_block(img, y0 + LINE_H * (len(OUT2_HEAD) + len(OUT2_ROWS) + 1), OUT2_TAIL,
                       max(0, reveal - len(OUT2_HEAD) - len(OUT2_ROWS)))
    return img


def build(out_path: Path) -> None:
    n = int(T_END * FPS)
    frames: list[Image.Image] = []
    for i in range(n):
        img = frame(i / FPS).convert("RGB")
        frames.append(img.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
        if (i + 1) % 24 == 0:
            print(f"  {i + 1}/{n} 帧 …", flush=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=int(1000 / FPS),
        loop=0,
        optimize=True,
        disposal=2,
    )
    size = out_path.stat().st_size / 1024
    print(f"✅ {out_path} · {n} 帧 · {T_END:.1f}s · {size:.0f} KB")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="promo/demo.gif")
    args = ap.parse_args()
    build(Path(args.out))


if __name__ == "__main__":
    main()
