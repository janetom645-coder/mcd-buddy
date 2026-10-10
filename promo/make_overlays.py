"""生成剪映用的产品截图叠加层（透明背景 PNG）。

视频的画面主体是真实食物实拍，产品界面只作为「证据」短暂叠加上去。
这里把四个模块的 `--demo` 真实输出渲染成深色卡片，背景透明，可直接丢进剪映当画中画。

数据与 `make_promo.py` / `make_readme_gif.py` 保持同一份，改一处要一起改。

用法：
    python promo/make_overlays.py --out promo/overlay
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from make_promo import draw_mixed, mixed_size

# ------------------------------------------------------------------ 视觉常量

W = 1080
MARGIN = 58                       # 卡片左右留白
PAD = 52                          # 卡片内边距
LINE_H = 62
CARD = (20, 20, 25, 244)          # 深色卡片（略微透明，叠在食物上不突兀）
EDGE = (62, 62, 72, 255)
TXT = (238, 238, 242)
DIM = (150, 150, 162)
YELLOW = (255, 199, 44)
RED = (255, 96, 84)
GREEN = (110, 226, 150)
TRACK = (72, 72, 82)

TITLE_SIZE = 46
BODY_SIZE = 38
SMALL_SIZE = 32
HEAD_SIZE = 42


# ------------------------------------------------------------------ 内容定义
# 每项：("kind", ...)
#   title  — 模块名（带 emoji）
#   rule   — 分隔线
#   gap    — 空行
#   text   — 普通文本
#   kv     — 左标签右数值（右对齐）
#   row3   — 三列（伙伴 / 单品 / 单价）
#   bar    — 前后对比条（标签, 前值, 后值, 单位）
#   prog   — 薯条进度条（已完成, 总数）
#   note   — 小字注释

OVERLAYS: dict[str, list[tuple]] = {
    "shot-practice": [
        ("title", "🧘 修行录"),
        ("rule",),
        ("text", "🎖️ 当前段位：麦门学徒"),
        ("prog", 3, 10),
        ("gap",),
        ("kv", "🍔 累计点餐", "8 单"),
        ("kv", "💸 累计消费", "¥138.00"),
        ("kv", "🏅 成就徽章", "5/12"),
        ("kv", "🎟️ 卡包券数", "3 张"),
    ],
    "shot-group": [
        ("title", "🍱 团餐指挥官"),
        ("rule",),
        ("text", "👥 6 人　·　到店自取"),
        ("text", "💰 应付 ¥109.50　·　人均 ¥18.25"),
        ("gap",),
        ("row3", "小王", "巨无霸", "¥24.50"),
        ("row3", "小李", "麦香鸡", "¥15.50"),
        ("row3", "小张", "麦香鱼", "¥17.50"),
        ("row3", "小赵", "高达吉士双牛堡", "¥26.00"),
        ("row3", "小陈", "大薯条", "¥13.50"),
        ("row3", "小周", "大杯鲜萃咖啡", "¥12.50"),
        ("note", "⚠️ 小张：超预算 ¥2.50"),
    ],
    "shot-hidden": [
        ("title", "🧪 隐藏菜单实验室"),
        ("rule",),
        ("text", "全明星双人分享餐八件套 · 减脂版"),
        ("gap",),
        ("bar", "🔥 能量", 2150, 1212, "kcal"),
        ("bar", "💪 蛋白质", 78, 61, "g"),
        ("bar", "🧈 脂肪", 90, 55, "g"),
        ("gap",),
        ("kv", "原套餐", "¥114.50"),
        ("kv", "减脂版", "¥115.50"),
        ("note", "定价来源：calculate-price 实时核算"),
    ],
    "shot-fortune": [
        ("title", "🔮 每日运势签"),
        ("rule",),
        ("text", "🎋 签等：中吉"),
        ("text", "📜 咖啡入喉，万事不愁。"),
        ("gap",),
        ("kv", "🥇 高达吉士双牛堡", "448 kcal"),
        ("kv", "🥈 猪柳蛋麦满分", "387 kcal"),
        ("gap",),
        ("kv", "⏰ 抽奖吉时", "09:00 - 10:00"),
        ("kv", "🔢 幸运数字", "51"),
    ],
}


# ------------------------------------------------------------------ 绘制


def layout_height(items: list[tuple]) -> int:
    h = PAD
    for item in items:
        kind = item[0]
        if kind == "gap":
            h += LINE_H // 2
        elif kind == "rule":
            h += 26
        elif kind == "bar":
            h += int(LINE_H * 1.75)
        elif kind == "note":
            h += int(LINE_H * 0.95)
        elif kind == "prog":
            h += int(LINE_H * 1.15)
        else:
            h += LINE_H
    return h + PAD


def draw_progress(d: ImageDraw.ImageDraw, img: Image.Image, x: int, y: int, done: int, total: int) -> None:
    """手绘薯条进度条（▰▱ 在雅黑里缺字，会落到 emoji 字体）。"""
    draw_mixed(img, (x, y), "🍟", BODY_SIZE, TXT)
    x += 62
    seg_w, gap, bar_h = 30, 8, 26
    for i in range(total):
        bx = x + i * (seg_w + gap)
        by = y - bar_h
        if i < done:
            d.rounded_rectangle((bx, by, bx + seg_w, by + bar_h), radius=4, fill=YELLOW)
        else:
            d.rounded_rectangle((bx, by, bx + seg_w, by + bar_h), radius=4, fill=TRACK)
    x += total * (seg_w + gap) + 22
    draw_mixed(img, (x, y), f"{done}/{total}", BODY_SIZE, TXT, head=True)


def render(name: str, items: list[tuple], out_dir: Path) -> Path:
    card_h = layout_height(items)
    img = Image.new("RGBA", (W, card_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    d.rounded_rectangle((MARGIN, 0, W - MARGIN, card_h), radius=44, fill=CARD, outline=EDGE, width=2)

    x0 = MARGIN + PAD
    x1 = W - MARGIN - PAD
    y = PAD

    for item in items:
        kind = item[0]
        if kind == "gap":
            y += LINE_H // 2
        elif kind == "rule":
            d.line((x0, y + 12, x1, y + 12), fill=EDGE, width=3)
            y += 26
        elif kind == "title":
            draw_mixed(img, (x0, y + HEAD_SIZE), item[1], TITLE_SIZE, YELLOW, head=True)
            y += LINE_H
        elif kind == "text":
            draw_mixed(img, (x0, y + BODY_SIZE), item[1], BODY_SIZE, TXT)
            y += LINE_H
        elif kind == "prog":
            draw_progress(d, img, x0, y + BODY_SIZE, item[1], item[2])
            y += int(LINE_H * 1.15)
        elif kind == "kv":
            draw_mixed(img, (x0, y + BODY_SIZE), item[1], BODY_SIZE, DIM)
            tw, _ = mixed_size(item[2], BODY_SIZE)
            draw_mixed(img, (x1 - tw, y + BODY_SIZE), item[2], BODY_SIZE, TXT, head=True)
            y += LINE_H
        elif kind == "row3":
            draw_mixed(img, (x0, y + BODY_SIZE), item[1], BODY_SIZE, TXT, head=True)
            draw_mixed(img, (x0 + 190, y + BODY_SIZE), item[2], BODY_SIZE, TXT)
            tw, _ = mixed_size(item[3], BODY_SIZE)
            draw_mixed(img, (x1 - tw, y + BODY_SIZE), item[3], BODY_SIZE, YELLOW, head=True)
            y += LINE_H
        elif kind == "bar":
            _, label, before, after, unit = item
            draw_mixed(img, (x0, y + SMALL_SIZE), label, SMALL_SIZE, DIM)
            bar_y = y + int(LINE_H * 0.62)
            full = int((x1 - x0) * 0.52)
            bh = 26
            d.rounded_rectangle((x0, bar_y, x0 + full, bar_y + bh), radius=13, fill=(96, 88, 78))
            d.rounded_rectangle(
                (x0, bar_y, x0 + max(13, int(full * after / before)), bar_y + bh), radius=13, fill=YELLOW
            )
            tx = x0 + full + 34
            draw_mixed(img, (tx, bar_y + bh - 2), f"{before} → {after} {unit}", BODY_SIZE, TXT, head=True)
            tw, _ = mixed_size(f"{before} → {after} {unit}", BODY_SIZE)
            draw_mixed(img, (tx + tw + 22, bar_y + bh - 2), f"{after - before:+d}", BODY_SIZE, GREEN, head=True)
            y += int(LINE_H * 1.75)
        elif kind == "note":
            draw_mixed(img, (x0, y + SMALL_SIZE), item[1], SMALL_SIZE, DIM)
            y += int(LINE_H * 0.95)

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.png"
    img.save(path)
    print(f"✅ {path}  ({W}×{card_h}, {path.stat().st_size / 1024:.0f} KB)")
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="promo/overlay")
    args = ap.parse_args()
    out_dir = Path(args.out)
    for name, items in OVERLAYS.items():
        render(name, items, out_dir)


if __name__ == "__main__":
    main()
