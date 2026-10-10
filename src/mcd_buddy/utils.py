"""通用工具函数：结果解析、Markdown 表格、文本处理。"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from typing import Any


def as_dict(value: Any) -> dict:
    """把 MCP 返回结果尽量规整成 dict。"""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {"data": parsed}
        except (ValueError, TypeError):
            return {"text": value}
    return {"data": value}


def deep_find_list(payload: Any, keys: Sequence[str]) -> list:
    """在嵌套结构中按候选 key 名找到第一个 list。

    麦当劳 MCP 各工具返回结构不完全统一，用这个兜底能提高鲁棒性。
    """
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
        for value in payload.values():
            found = deep_find_list(value, keys)
            if found:
                return found
    elif isinstance(payload, list):
        return payload
    return []


def pick(mapping: Any, *keys: str, default: Any = None) -> Any:
    """从 dict 中按多个候选 key 取值（兼容不同字段命名）。"""
    if not isinstance(mapping, dict):
        return default
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return default


def money(value: Any) -> str:
    """把「元」数值格式化为 ¥x.xx。

    注意：麦当劳 MCP 返回的金额单位是**分**，调用方需先用
    :func:`mcd_buddy.mcd_api.cents_to_yuan` 转换。本函数不做任何单位猜测。
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"¥{number:.2f}"


def md_table(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    """生成 Markdown 表格。"""
    rows = list(rows)
    if not rows:
        return "（暂无数据）"
    lines = ["| " + " | ".join(str(h) for h in headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# 零宽字符：变体选择符、零宽连接符、零宽空格 —— 不占显示宽度
_ZERO_WIDTH = {0xFE0E, 0xFE0F, 0x200B, 0x200C, 0x200D, 0x2060}


def strip_ansi(text: str) -> str:
    """去掉 ANSI 颜色转义码，便于计算真实显示宽度。"""
    return _ANSI_RE.sub("", text)


def display_width(text: str) -> int:
    """估算终端显示宽度：中日韩字符与 emoji 按 2 格计，其余按 1 格。"""
    width = 0
    for char in strip_ansi(text):
        code = ord(char)
        if code in _ZERO_WIDTH:
            continue
        if code > 0x1100 and (
            0x2E80 <= code <= 0xA4CF      # CJK 部首、假名、汉字
            or 0xAC00 <= code <= 0xD7A3   # 谚文
            or 0xF900 <= code <= 0xFAFF   # CJK 兼容汉字
            or 0xFE30 <= code <= 0xFE6F   # CJK 兼容形式
            or 0xFF00 <= code <= 0xFF60   # 全角字符
            or 0xFFE0 <= code <= 0xFFE6
            or 0x1F300 <= code <= 0x1FAFF  # emoji 与符号
            or 0x2600 <= code <= 0x27BF    # 杂项符号、装饰符
        ):
            width += 2
        else:
            width += 1
    return width


def pad(text: str, width: int) -> str:
    """按显示宽度右补空格，用于 ASCII 卡片对齐。"""
    return text + " " * max(width - display_width(text), 0)


def wrap_text(text: str, width: int) -> list[str]:
    """按显示宽度折行（中文与 emoji 友好），用于卡片内长文本。"""
    if width <= 0:
        return [text]
    lines: list[str] = []
    current = ""
    current_width = 0
    for char in text:
        char_width = display_width(char)
        if current and current_width + char_width > width:
            lines.append(current)
            current, current_width = char, char_width
        else:
            current += char
            current_width += char_width
    lines.append(current)
    return lines


def parse_date(text: Any) -> str:
    """从时间字符串中截取出 YYYY-MM-DD。"""
    if not text:
        return ""
    match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", str(text))
    if not match:
        return ""
    year, month, day = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"
