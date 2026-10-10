"""🎨 麦门助手卡通主题 —— 麦当劳配色 + ASCII 卡片 + 薯条进度条。

设计基调：圆润、可爱、有亲和力，尽量用金拱门、汉堡、薯条、可乐等元素，
让命令行输出也带着「麦门」的快乐感。

颜色遵循麦当劳品牌色：
  - 麦当劳红 `#DA291C`
  - 金拱黄 `#FFC72C`

设置环境变量 ``NO_COLOR=1`` 或输出到非终端时，自动降级为纯文本（不输出转义码）。
"""

from __future__ import annotations

import os
import sys

from .utils import display_width, pad, wrap_text

# ---------------------------------------------------------------- 颜色

def _supports_color() -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    try:
        return bool(sys.stdout.isatty())
    except (AttributeError, ValueError):
        return False


_COLOR = _supports_color()

_RESET = "\033[0m" if _COLOR else ""
_BOLD = "\033[1m" if _COLOR else ""
_DIM = "\033[2m" if _COLOR else ""
_RED = "\033[38;5;160m" if _COLOR else ""    # 麦当劳红 #DA291C
_YELLOW = "\033[38;5;220m" if _COLOR else ""  # 金拱黄 #FFC72C


def red(text: str) -> str:
    return f"{_RED}{text}{_RESET}"


def yellow(text: str) -> str:
    return f"{_YELLOW}{text}{_RESET}"


def bold(text: str) -> str:
    return f"{_BOLD}{text}{_RESET}"


def dim(text: str) -> str:
    return f"{_DIM}{text}{_RESET}"


def brand(text: str) -> str:
    """红黄交替的品牌强调色，用于标题。"""
    return f"{_RED}{_BOLD}{text}{_RESET}"


# ---------------------------------------------------------------- 元素

ARCHES = r"""   ▄▄███▄▄   ▄▄███▄▄
  ███   ███ ███   ███
  ██     ██ ██     ██
  ██     ██ ██     ██"""

BURGER = "🍔"
FRIES = "🍟"
DRINK = "🥤"
SUNDAE = "🍦"
COFFEE = "☕"
BURGER_KEY = "🍔"


def banner(title: str = "麦门助手 MCD BUDDY", subtitle: str = "") -> str:
    """金拱门抬头的卡通 banner。"""
    lines = [red(ARCHES)]
    lines.append("")
    lines.append(f"  {yellow('🍟')} {brand(title)} {yellow('🍔')}")
    if subtitle:
        lines.append(f"  {dim(subtitle)}")
    lines.append(f"  {red('━' * 34)}")
    return "\n".join(lines)


def card(title: str, body: str, width: int = 60) -> str:
    """圆角卡片：顶部带标题，内容自动折行与对齐（兼容中文与 emoji 宽度）。"""
    inner = max(width - 2, 20)
    head = "─ " + title + " "
    fill = max(inner - display_width(head) - 1, 0)
    top = red("╭") + red(head + "─" * fill + "─") + red("╮")
    bottom = red("╰" + "─" * inner + "╯")
    rows = [top]
    for line in body.split("\n"):
        if not line.strip():
            rows.append(red("│") + " " * inner + red("│"))
            continue
        for segment in wrap_text(line, inner - 2):
            rows.append(red("│") + pad(" " + segment, inner) + red("│"))
    rows.append(bottom)
    return "\n".join(rows)


def fries_bar(done: int, total: int, slots: int = 12) -> str:
    """薯条进度条：已点亮的是金黄薯条，未点亮的是空框。"""
    if total <= 0:
        filled = slots
    else:
        filled = max(0, min(slots, round(done / total * slots)))
    bar = yellow("▰" * filled) + dim("▱" * (slots - filled))
    return f"{FRIES} {bar} {bold(f'{done}/{total}')}"


def sticker(label: str, unlocked: bool = True) -> str:
    """贴纸式徽章：已解锁高亮，未解锁灰暗。"""
    if unlocked:
        return yellow(f"「{label}」")
    return dim(f"「{label}」")


def rule(width: int = 40) -> str:
    """卡通分隔线。"""
    return dim("🍟 " + "─" * width + " 🍔")


def section(title: str) -> str:
    """小节标题，带红色竖条。"""
    return f"{red('▍')} {bold(title)}"


def tag(text: str) -> str:
    """小标签。"""
    return red(f"[{text}]")
