"""🔮 每日运势签 —— 今天宜吃巨无霸。

数据来源（麦当劳 MCP）：
  - ``now-time-info``         当前日期（决定当天的签，保证同一天结果一致）
  - ``list-nutrition-foods``  官方餐品清单（160+ 项，用于「今日宜吃」）
  - ``campaign-calendar``     当月活动日历（真实 dailyList[].events[]）
  - ``query-lottery-info``    积分抽奖活动与奖品池
  - ``query-my-prizes``       我已抽中的奖品

玩法：以日期为种子做确定性抽签，同一天抽到的签永远一致 —— 仪式感 + 可验证。

设计取舍：不调用 ``query-meals``，因为那需要先解析门店（还要额外请求补全名称）。
营养清单本身就带全部餐品名，且与门店无关，更适合做「每日运势」这种全局玩法。
"""

from __future__ import annotations

import random

from .. import theme
from ..mcd_api import (
    fetch_calendar,
    fetch_lottery,
    fetch_my_prizes,
    fetch_now,
    fetch_nutrition,
    to_float,
)
from ..mcp_client import MCDClientProtocol
from ..utils import md_table, parse_date, pick

SIGNS: list[tuple[str, str]] = [
    ("大吉", "金拱门开，福气自来。今日一口巨无霸，胜过人间无数餐。"),
    ("大吉", "麦香穿堂，好事成双。宜结伴同吃，宜加个大薯。"),
    ("中吉", "薯条在手，烦恼没有。今日宜慢食，忌狼吞。"),
    ("中吉", "咖啡入喉，万事不愁。今日宜早起，忌拖延。"),
    ("小吉", "麦旋风转，时来运转。今日宜尝鲜，忌守旧。"),
    ("小吉", "鸡块六枚，喜事成堆。今日宜分享，忌独食。"),
    ("平", "甜筒虽小，回味悠长。今日宜低调，忌张扬。"),
    ("平", "一杯可乐，半日清闲。今日宜按部就班，忌急躁。"),
]

LUCKY_COLORS = ["金拱黄", "可乐红", "生菜绿", "薯条金", "奶油白", "咖啡棕"]
AVOID_HINTS = ["油炸", "含糖", "冰淇淋", "辣", "咖啡因"]
WEEKDAY_CN = {
    "MONDAY": "星期一", "TUESDAY": "星期二", "WEDNESDAY": "星期三",
    "THURSDAY": "星期四", "FRIDAY": "星期五", "SATURDAY": "星期六", "SUNDAY": "星期日",
}


class FortuneModule:
    """每日运势签模块。"""

    name = "每日运势签"
    emoji = "🔮"

    async def run(self, client: MCDClientProtocol) -> str:
        now = await fetch_now(client)
        nutrition = await fetch_nutrition(client)
        calendar = await fetch_calendar(client)
        lottery = await fetch_lottery(client)
        prizes = await fetch_my_prizes(client)
        return _render(now, nutrition, calendar, lottery, prizes)


def _render(
    now: dict,
    nutrition: dict[str, dict],
    calendar: dict,
    lottery: dict,
    prizes: list[dict],
) -> str:
    date = parse_date(pick(now, "date", "formatted", "datetime")) or "1970-01-01"
    weekday = WEEKDAY_CN.get(str(pick(now, "dayOfWeek", default="")), "")
    rng = random.Random(f"mcd-fortune-{date}")

    meals = list(nutrition.keys())
    lucky_meal = rng.choice(meals) if meals else "巨无霸"
    others = [m for m in meals if m != lucky_meal] or ["中薯条"]
    lucky_meal2 = rng.choice(others)

    sign_level, sign_text = rng.choice(SIGNS)
    lucky_hour = rng.randint(6, 21)
    lucky_number = rng.randint(1, 99)
    lucky_color = rng.choice(LUCKY_COLORS)
    avoid_tag = rng.choice(AVOID_HINTS)
    lucky_kcal = rng.randrange(400, 1001, 50)

    lines: list[str] = []
    lines.append(theme.banner("每日运势签", "McQuartet · 今天宜吃巨无霸"))
    lines.append("")

    sign_body = "\n".join(
        [
            f"🎋 签　等：{theme.bold(sign_level)}",
            f"📅 日　期：{date} {weekday}",
            "",
            f"📜 签　文：{sign_text}",
        ]
    )
    lines.append(theme.card("🔮 麦门灵签", sign_body, 58))
    lines.append("")

    lines.append(theme.section("🍟 今日宜吃"))
    lines.append("")
    rows = [
        [f"🥇 {lucky_meal}", _meal_hint(lucky_meal, nutrition, "今日头牌，主推")],
        [f"🥈 {lucky_meal2}", _meal_hint(lucky_meal2, nutrition, "搭配之选，可加购")],
    ]
    lines.append(md_table(["推荐", "说明"], rows))
    lines.append("")

    lines.append(theme.section("🚫 今日小忌"))
    lines.append("")
    lines.append(f"- 今日对「{theme.bold(avoid_tag)}」类餐品稍显不利，浅尝即止。")
    lines.append(f"- 🎨 幸运色：{theme.bold(lucky_color)}（挑带这个颜色的包装，运气 +1）")
    lines.append(f"- 🔥 建议热量预算：约 {lucky_kcal} kcal（超了就当破财消灾）")
    lines.append("")

    lines.append(theme.section("🎰 抽奖吉时"))
    lines.append("")
    lines.append(
        md_table(
            ["项目", "今日指引"],
            [
                ["⏰ 吉时", f"{lucky_hour:02d}:00 - {lucky_hour + 1:02d}:00"],
                ["🔢 幸运数字", str(lucky_number)],
                ["🎁 抽奖活动", _lottery_name(lottery)],
                ["💳 单次消耗", _lottery_cost(lottery)],
                ["🏅 我的奖品", f"{len(prizes)} 个" if prizes else "暂无，今日宜开抽"],
            ],
        )
    )
    lines.append("")

    prize_names = _prize_names(lottery)
    if prize_names:
        lines.append(theme.section("🎁 本期奖品池"))
        lines.append("")
        lines.append("　".join(f"· {n}" for n in prize_names[:8]))
        lines.append("")

    activity = _today_activity(calendar, date)
    if activity:
        lines.append(theme.section("📅 今日活动"))
        lines.append("")
        title = pick(activity, "activityTitle") or pick(
            activity.get("articleDto") or {}, "title", default="活动"
        )
        lines.append(f"- **{title}**")
        content = pick(activity.get("articleDto") or {}, "content", default="")
        if content:
            for chunk in str(content).split("\n"):
                lines.append(f"  {chunk}")
        highlights = pick(activity.get("articleDto") or {}, "highlights", default="")
        if highlights:
            lines.append(f"  ✨ {highlights}")
        lines.append("")

    if prizes:
        lines.append(theme.section("🏆 我已抽中的奖品"))
        lines.append("")
        lines.append(
            md_table(
                ["奖品", "类型", "中奖时间", "状态"],
                [
                    [
                        str(pick(p, "name", default="奖品")),
                        str(pick(p, "prizeTypeText", default="—")),
                        str(pick(p, "recordTime", default="—")),
                        str(pick(p, "statusText", default="—")),
                    ]
                    for p in prizes[:5]
                ],
            )
        )
        lines.append("")

    lines.append(theme.rule(38))
    lines.append(theme.dim("签由日期确定生成，同一天结果唯一 —— 仅供娱乐，不构成任何建议。"))
    return "\n".join(lines)


def _meal_hint(name: str, nutrition: dict[str, dict], fallback: str) -> str:
    info = nutrition.get(name) or {}
    kcal = to_float(info.get("energyKcal"))
    protein = to_float(info.get("protein"))
    if kcal <= 0 and protein <= 0:
        return fallback
    return f"{fallback}　{kcal:.0f} kcal · 蛋白 {protein:.0f}g"


def _lottery_name(lottery: dict) -> str:
    name = str(pick(lottery, "activityName", default=""))
    status = str(pick(lottery, "activityStatusText", default=""))
    if not name:
        return "暂无抽奖活动"
    return f"{name}（{status}）" if status else name


def _lottery_cost(lottery: dict) -> str:
    decision = lottery.get("drawDecision") or {}
    text = pick((decision.get("nextConsumption") or {}), "text", default="")
    if text:
        return str(text)
    points = pick(lottery, "drawPoint", default="")
    return f"{points} 积分" if points else "—"


def _prize_names(lottery: dict) -> list[str]:
    return [
        str(pick(row, "name", default=""))
        for row in (lottery.get("prizes") or [])
        if isinstance(row, dict) and pick(row, "name")
    ]


def _today_activity(calendar: dict, date: str) -> dict | None:
    """优先取今天的活动，其次取标记 today 的，最后取任意一场。"""
    days = calendar.get("dailyList") or []
    for day in days:
        if isinstance(day, dict) and str(day.get("date", "")).startswith(date):
            events = day.get("events") or []
            if events and isinstance(events[0], dict):
                return events[0]
    for day in days:
        if isinstance(day, dict) and day.get("today"):
            events = day.get("events") or []
            if events and isinstance(events[0], dict):
                return events[0]
    for day in days:
        if not isinstance(day, dict):
            continue
        events = day.get("events") or []
        if events and isinstance(events[0], dict):
            return events[0]
    return None
