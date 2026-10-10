"""utils 与 theme 的单元测试。"""

from mcd_buddy import theme
from mcd_buddy.utils import (
    deep_find_list,
    display_width,
    md_table,
    money,
    pad,
    parse_date,
    pick,
    strip_ansi,
    wrap_text,
)


class TestDisplayWidth:
    def test_ascii(self):
        assert display_width("abc") == 3

    def test_cjk_counts_two(self):
        assert display_width("中文") == 4

    def test_emoji_counts_two(self):
        assert display_width("🍔") == 2

    def test_variation_selector_is_zero_width(self):
        # 🎖 本身 2 格，后面的变体选择符 U+FE0F 不应再占宽度
        assert display_width("🎖️") == 2

    def test_fullwidth_punctuation(self):
        assert display_width("：") == 2

    def test_ansi_escape_ignored(self):
        assert display_width("\033[38;5;160m红\033[0m") == 2


class TestStripAnsi:
    def test_removes_color_codes(self):
        assert strip_ansi("\033[1m粗\033[0m") == "粗"


class TestPad:
    def test_pads_by_display_width(self):
        assert pad("中文", 6) == "中文  "

    def test_never_truncates(self):
        assert pad("abcdef", 3) == "abcdef"


class TestWrapText:
    def test_wraps_cjk_at_width(self):
        assert wrap_text("一二三四五", 4) == ["一二", "三四", "五"]

    def test_empty_string_yields_one_line(self):
        assert wrap_text("", 5) == [""]

    def test_zero_width_returns_input(self):
        assert wrap_text("abc", 0) == ["abc"]


class TestMdTable:
    def test_builds_header_and_rows(self):
        table = md_table(["A", "B"], [[1, 2], [3, 4]])
        assert table.splitlines()[0] == "| A | B |"
        assert "| 1 | 2 |" in table

    def test_empty_rows(self):
        assert md_table(["A"], []) == "（暂无数据）"


class TestMoney:
    def test_formats_yuan(self):
        assert money(21.5) == "¥21.50"

    def test_does_not_guess_units(self):
        # 约定：money() 只负责格式化「元」，不做任何单位猜测。
        # 真实 MCP 金额是「分」，必须先经 cents_to_yuan 转换。
        assert money(2150) == "¥2150.00"

    def test_invalid_value(self):
        assert money("abc") == "—"


class TestDeepFindList:
    def test_finds_nested_list(self):
        payload = {"data": {"meals": [1, 2]}}
        assert deep_find_list(payload, ["meals"]) == [1, 2]

    def test_returns_bare_list(self):
        assert deep_find_list([1, 2], ["meals"]) == [1, 2]

    def test_missing_returns_empty(self):
        assert deep_find_list({"a": 1}, ["meals"]) == []


class TestPick:
    def test_first_matching_key(self):
        assert pick({"b": 2, "a": 1}, "a", "b") == 1

    def test_skips_blank_values(self):
        assert pick({"a": "", "b": 2}, "a", "b") == 2

    def test_default(self):
        assert pick({}, "a", default="x") == "x"


class TestParseDate:
    def test_extracts_iso_date(self):
        assert parse_date("2026-10-10 08:12:00") == "2026-10-10"

    def test_normalises_single_digit(self):
        assert parse_date("2026/1/5") == "2026-01-05"

    def test_invalid_returns_empty(self):
        assert parse_date("没有日期") == ""


class TestThemeCard:
    def test_all_lines_share_same_display_width(self):
        body = "\n".join(["📅 修行日期：2026-10-10", "🎖️ 当前段位：麦门学徒", "🍟 ▰▰▰▱▱ 3/5"])
        rendered = theme.card("🧘 我的修行进度", body, 56)
        widths = {display_width(line) for line in rendered.split("\n")}
        assert len(widths) == 1, f"卡片边框未对齐：{widths}"

    def test_long_line_wraps_inside_card(self):
        rendered = theme.card("🔮 麦门灵签", "签文：" + "金拱门" * 30, 40)
        widths = {display_width(line) for line in rendered.split("\n")}
        assert len(widths) == 1, f"长文本撑破卡片：{widths}"

    def test_no_ansi_when_color_disabled(self):
        rendered = theme.card("标题", "内容", 30)
        assert "\033" not in rendered


class TestThemeFriesBar:
    def test_full_progress(self):
        assert "5/5" in theme.fries_bar(5, 5, 5)

    def test_zero_total_does_not_crash(self):
        assert "0/0" in theme.fries_bar(0, 0, 5)


class TestThemeSticker:
    def test_unlocked_has_no_ansi_when_disabled(self):
        assert "\033" not in theme.sticker("七日不辍", True)
