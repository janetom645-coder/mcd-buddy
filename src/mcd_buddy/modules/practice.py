"""🧘 修行录 —— 把每一次点餐都变成修行进度。

数据来源（麦当劳 MCP）：
  - ``order-list``        历史订单（``data.list[].orderProductList[].comboItemList[]``）
  - ``query-my-account``  积分账户（``availablePoint`` 等均为字符串）
  - ``query-my-coupons``  卡包券数量
  - ``query-my-prizes``   抽奖所得奖品
  - ``now-time-info``     当前日期（用于计算连续打卡天数）

输出：修行报告（统计 + 成就徽章 + 段位进度）。
"""

from __future__ import annotations

import datetime as dt

from .. import theme
from ..mcd_api import (
    fetch_account,
    fetch_my_coupons,
    fetch_my_prizes,
    fetch_now,
    fetch_orders,
    to_float,
)
from ..mcp_client import MCDClientProtocol
from ..utils import md_table, money, parse_date, pick

# 段位：累计点餐单数 -> 称号
LEVELS: list[tuple[int, str]] = [
    (0, "见习麦徒"),
    (5, "麦门学徒"),
    (15, "麦门弟子"),
    (30, "麦门执事"),
    (60, "麦门长老"),
    (100, "麦门宗主"),
]

# 成就定义：(ID, 徽章, 名称, 达成条件)
ACHIEVEMENTS: list[tuple[str, str, str, str]] = [
    ("first", "🍔", "初入麦门", "完成人生第一单"),
    ("streak3", "🔥", "三连修行", "连续 3 天点餐"),
    ("streak7", "⚡", "七日不辍", "连续 7 天点餐"),
    ("big10", "💪", "巨无霸十人斩", "累计点过 10 个巨无霸"),
    ("breakfast", "🌅", "晨钟暮鼓", "累计 5 次早餐订单"),
    ("coffee", "☕", "咖啡因续命", "累计 5 杯咖啡"),
    ("night", "🌙", "深夜食堂", "在 21:00 之后点过餐"),
    ("spender", "💸", "麦门金主", "累计消费超过 ¥500"),
    ("collector", "🏅", "单品收集家", "点过 8 种以上不同单品"),
    ("coupon", "🎟️", "券包大户", "卡包里有 3 张以上券"),
    ("lucky", "🎰", "麦金喜锦鲤", "抽奖中过奖品"),
    ("loyal", "🧿", "麦门信徒", "累计点餐 30 单"),
]

_BREAKFAST_HOUR = 10
_NIGHT_HOUR = 21


class PracticeModule:
    """修行录模块。"""

    name = "修行录"
    emoji = "🧘"

    async def run(self, client: MCDClientProtocol) -> str:
        now = await fetch_now(client)
        orders = _parse_orders(await fetch_orders(client))
        account = await fetch_account(client)
        coupons = await fetch_my_coupons(client)
        prizes = await fetch_my_prizes(client)

        today = parse_date(pick(now, "date", "formatted", "datetime")) or dt.date.today().isoformat()
        return _render(orders, account, today, len(coupons), len(prizes))


# ------------------------------------------------------------------ 解析


def _parse_orders(raw: list[dict]) -> list[dict]:
    """把真实订单结构拍平成便于统计的扁平结构。"""
    orders: list[dict] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        date = parse_date(pick(entry, "createTime", "orderTime", "time"))
        if not date:
            continue

        names: list[str] = []
        for product in entry.get("orderProductList", []) or []:
            if not isinstance(product, dict):
                continue
            combo_items = product.get("comboItemList") or []
            if combo_items:
                # 套餐：记录套餐名 + 拆出子项（子项用于「本命单品」统计）
                combo_name = pick(product, "productName", "name")
                if combo_name:
                    names.append(str(combo_name))
                for child in combo_items:
                    if not isinstance(child, dict):
                        continue
                    child_name = pick(child, "name", "productName")
                    qty = int(pick(child, "quantity", default=1) or 1)
                    if child_name:
                        names.extend([str(child_name)] * qty)
            else:
                name = pick(product, "productName", "name")
                qty = int(pick(product, "quantity", default=1) or 1)
                if name:
                    names.extend([str(name)] * qty)

        orders.append(
            {
                "date": date,
                "time": str(pick(entry, "createTime", "orderTime", default="")),
                "amount": to_float(pick(entry, "realTotalAmount", "totalAmount", "amount")),
                "be_type": str(pick(entry, "beType", default="1")),
                "store": str(pick(entry, "storeName", default="")),
                "names": names,
            }
        )
    orders.sort(key=lambda o: o["time"], reverse=True)
    return orders


def _streak(dates: set[str], today: str) -> int:
    if not dates:
        return 0
    try:
        cursor = dt.date.fromisoformat(today)
    except ValueError:
        cursor = dt.date.fromisoformat(max(dates))
    if today not in dates:
        cursor -= dt.timedelta(days=1)
    streak = 0
    while cursor.isoformat() in dates:
        streak += 1
        cursor -= dt.timedelta(days=1)
    return streak


def _level(total: int) -> tuple[str, int, int, str]:
    current, nxt = LEVELS[0], None
    for threshold, title in LEVELS:
        if total >= threshold:
            current = (threshold, title)
        elif nxt is None:
            nxt = (threshold, title)
    title = current[1]
    low = current[0]
    if nxt is None:
        return title, 100, 100, "已达顶阶 · 麦门圆满"
    span = nxt[0] - low
    done = total - low
    return title, done, span, f"距「{nxt[1]}」还差 {nxt[0] - total} 单"


def _hour(text: str) -> int | None:
    try:
        return int(str(text).split(" ")[1].split(":")[0])
    except (IndexError, ValueError):
        return None


# ------------------------------------------------------------------ 渲染


def _render(
    orders: list[dict],
    account: dict,
    today: str,
    coupon_count: int,
    prize_count: int,
) -> str:
    total_orders = len(orders)
    dates = {o["date"] for o in orders}
    streak = _streak(dates, today)
    spend = sum(o["amount"] for o in orders)

    item_count: dict[str, int] = {}
    for order in orders:
        for name in order["names"]:
            item_count[name] = item_count.get(name, 0) + 1

    # 排除套餐名本身，避免「本命单品」被套餐名占据
    singles = {k: v for k, v in item_count.items() if "套餐" not in k and "随心配" not in k}
    top_items = sorted(singles.items(), key=lambda kv: kv[1], reverse=True)[:5]

    breakfast = sum(
        1 for o in orders if (_hour(o["time"]) or 99) < _BREAKFAST_HOUR
    )
    coffee = sum(v for k, v in item_count.items() if "咖啡" in k)
    bigmac = sum(v for k, v in item_count.items() if "巨无霸" in k)
    late_night = any((_hour(o["time"]) or 0) >= _NIGHT_HOUR for o in orders)

    flags = {
        "first": total_orders >= 1,
        "streak3": streak >= 3,
        "streak7": streak >= 7,
        "big10": bigmac >= 10,
        "breakfast": breakfast >= 5,
        "coffee": coffee >= 5,
        "night": late_night,
        "spender": spend >= 500,
        "collector": len(singles) >= 8,
        "coupon": coupon_count >= 3,
        "lucky": prize_count >= 1,
        "loyal": total_orders >= 30,
    }

    title, done, span, hint = _level(total_orders)
    unlocked_count = sum(1 for v in flags.values() if v)

    lines: list[str] = []
    lines.append(theme.banner("麦门修行录", "McQuartet · 点餐即修行"))
    lines.append("")

    head = "\n".join(
        [
            f"📅 修行日期：{today}",
            f"🎖️ 当前段位：{theme.bold(title)}",
            theme.fries_bar(done, span, 12) + f"　{hint}",
        ]
    )
    lines.append(theme.card("🧘 我的修行进度", head, 58))
    lines.append("")

    lines.append(theme.section("📊 修行数据"))
    lines.append("")
    lines.append(
        md_table(
            ["指标", "数值"],
            [
                ["🍔 累计点餐", f"{total_orders} 单"],
                ["📆 修行天数", f"{len(dates)} 天"],
                ["🔥 当前连击", f"{streak} 天"],
                ["💸 累计消费", money(spend)],
                ["🌅 早餐修行", f"{breakfast} 次"],
                ["☕ 咖啡因摄入", f"{coffee} 杯"],
                ["🏅 可用积分", f"{to_float(pick(account, 'availablePoint')):g} 分"],
                ["📈 累计积分", f"{to_float(pick(account, 'accumulativePoint')):g} 分"],
                ["🎟️ 卡包券数", f"{coupon_count} 张"],
                ["🎰 抽奖奖品", f"{prize_count} 个"],
            ],
        )
    )
    lines.append("")

    lines.append(theme.section(f"🏅 成就徽章　{unlocked_count}/{len(ACHIEVEMENTS)}"))
    lines.append("")
    rows = []
    for key, badge, name, desc in ACHIEVEMENTS:
        unlocked = flags.get(key, False)
        rows.append(
            [
                badge if unlocked else "🔒",
                theme.sticker(name, unlocked),
                desc,
                "✅" if unlocked else "—",
            ]
        )
    lines.append(md_table(["", "成就", "达成条件", "状态"], rows))
    lines.append("")

    if top_items:
        lines.append(theme.section("🍟 你的本命单品"))
        lines.append("")
        lines.append(
            md_table(
                ["排名", "单品", "次数"],
                [[f"{i + 1}", n, f"{c} 次"] for i, (n, c) in enumerate(top_items)],
            )
        )
        lines.append("")

    if orders:
        lines.append(theme.section("🧾 最近修行"))
        lines.append("")
        lines.append(
            md_table(
                ["时间", "门店", "内容", "金额"],
                [
                    [
                        o["time"],
                        o["store"] or "—",
                        "、".join(_dedupe(o["names"]))[:28] or "—",
                        money(o["amount"]),
                    ]
                    for o in orders[:5]
                ],
            )
        )
        lines.append("")

    lines.append(theme.rule(38))
    lines.append(theme.dim("修行不止，麦门长明。数据来自你的麦当劳历史订单。"))
    return "\n".join(lines)


def _dedupe(names: list[str]) -> list[str]:
    """把同名商品折叠成「名字×数量」。"""
    counter: dict[str, int] = {}
    for name in names:
        counter[name] = counter.get(name, 0) + 1
    return [f"{k}×{v}" if v > 1 else k for k, v in counter.items()]
