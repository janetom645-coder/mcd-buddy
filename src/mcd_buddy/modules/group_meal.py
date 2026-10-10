"""🍱 团餐指挥官 —— 一群人的点单，终于不用吵了。

数据来源（麦当劳 MCP）：
  - ``query-nearby-stores``    解析可用门店（``city`` + ``keyword`` 必须同时非空）
  - ``query-meals``            门店实时菜单（只给 code + tags）
  - ``calculate-price``        补全名称/价格，并计算整单金额
  - ``query-my-coupons``       我的卡包（真实券数据）
  - ``query-store-coupons``    该门店 + 渠道下**可用**的券

输入：一群人的点单需求（姓名 / 预算 / 想吃什么 / 忌口）。
输出：每人推荐 + 合并订单 + 价格明细 + 人均分摊 + 凑券建议。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .. import theme
from ..mcd_api import (
    BE_TYPE_LABELS,
    Coupon,
    MenuItem,
    Store,
    calculate_price,
    cents_to_yuan,
    fetch_menu,
    fetch_my_coupons,
    fetch_store_coupons,
)
from ..mcp_client import MCDClientProtocol
from ..utils import md_table, money

# 预算档位建议（来自官方 query-meals 说明：团餐搭配规则）
BUDGET_HINTS = [
    (20, "小食"),
    (30, "汉堡 + 小食 或 汉堡 + 饮料"),
    (40, "汉堡 + 薯条/小食 + 饮料"),
]

# 没有填预算时，按「一顿正餐」的目标价来挑，而不是无脑挑最贵/最便宜
DEFAULT_TARGET = 30.0

# 真实菜单里混着蘸酱和周边（按摩捶、痒痒挠…），这些不算「一份吃的」
_NON_MEAL_HINTS = (
    "按摩捶",
    "痒痒挠",
    "玩具",
    "周边",
    "礼品卡",
    "兑换券",
    "徽章",
    "贴纸",
    "杯套",
    "购物袋",
    "包装袋",
    "手提袋",
)

# 用来判断「这是不是一份正经主食」
# 注意：必须同时看类目和名称 —— 「巨无霸」名字里没有「堡」字，
# 只看名称会把它误判成小食，从而输给名字里带「堡」的普通单品。
_MAIN_CATEGORY_HINTS = ("堡", "餐", "卷", "饭", "随心配", "乐园", "大卡", "人气热卖")
_MAIN_NAME_HINTS = ("堡", "卷", "餐", "随心配", "饭")
_DRINK_HINTS = ("饮", "咖啡", "可乐", "雪碧", "牛奶", "果汁", "红茶")

# 标签里的否定词：出现在关键词之前就说明这个词是「没有」的意思
_NEGATION_HINTS = ("无", "非", "不含", "零", "去")


@dataclass
class Person:
    """一位点单的伙伴。"""

    name: str
    budget: float | None = None
    want: str = ""
    avoid: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> Person:
        return cls(
            name=str(data.get("name", "匿名")),
            budget=float(data["budget"]) if data.get("budget") else None,
            want=str(data.get("want", "") or ""),
            avoid=[str(x) for x in (data.get("avoid") or [])],
        )


class GroupMealModule:
    """团餐指挥官模块。"""

    name = "团餐指挥官"
    emoji = "🍱"

    async def run(
        self,
        client: MCDClientProtocol,
        people: list[Person],
        store: Store,
        order_type: int = 1,
        be_type: int = 1,
        be_code: str = "",
    ) -> str:
        menu = await fetch_menu(client, store.store_code, order_type, be_type, be_code)
        sellable = [item for item in menu if item.price > 0]
        if not sellable:
            return _empty_menu(store)

        picks = [_match(sellable, person) for person in people]

        merged: dict[str, dict] = {}
        for item in picks:
            if item is None:
                continue
            slot = merged.setdefault(
                item.code, {"item": item, "qty": 0, "people": []}
            )
            slot["qty"] += 1
            slot["people"].append(item)

        order_lines = [
            {"item": slot["item"], "qty": slot["qty"]} for slot in merged.values()
        ]
        price = await _price_order(
            client, store, order_lines, order_type, be_type, be_code
        )

        coupons = await fetch_my_coupons(client)
        store_coupons = await fetch_store_coupons(
            client, store.store_code, order_type, be_type, be_code
        )

        return _render(
            people=people,
            picks=picks,
            order_lines=order_lines,
            price=price,
            coupons=coupons,
            store_coupons=store_coupons,
            store=store,
            be_type=be_type,
            menu=sellable,
        )


# ------------------------------------------------------------------ 匹配


def _hit(item: MenuItem, keyword: str) -> bool:
    """关键词命中判定：名称包含 / 类目包含 / 标签包含（排除否定式标签）。

    标签这块要小心两件事：
      - 真实标签是长串营销词，「牛肉」必须能命中「100%纯牛肉」；
      - 但不能让「咖啡」命中「无咖啡因」—— 那是完全相反的意思。
    所以先看关键词前面有没有否定词（无 / 非 / 不含…），有就判定为不命中。
    """
    if not keyword:
        return False
    keyword = keyword.strip()
    if not keyword:
        return False
    if keyword in item.name:
        return True
    if keyword in item.category:
        return True
    for tag in item.tags:
        if keyword == tag:
            return True
        if keyword in tag and not _is_negated(tag, keyword):
            return True
    return False


def _is_negated(tag: str, keyword: str) -> bool:
    """关键词在标签里是否被否定（「无咖啡因」对「咖啡」是否定）。"""
    index = tag.find(keyword)
    if index <= 0:
        return False
    prefix = tag[:index]
    return any(hint in prefix for hint in _NEGATION_HINTS)


def _is_meal(item: MenuItem) -> bool:
    """蘸酱、周边、玩具这类东西不算「一份吃的」。

    真实菜单的「小食甜品 /其他」类目里混着 ¥14.90 的按摩捶，
    「蘸酱炸鸡」类目里混着 ¥3 的蘸酱 —— 不排掉就会出现荒谬推荐。
    """
    if item.name.endswith("酱"):
        return False
    return not any(hint in item.name for hint in _NON_MEAL_HINTS)


def _meal_tier(item: MenuItem) -> int:
    """2 = 主食/套餐，1 = 小食/炸鸡，0 = 饮品。

    先看类目再看名称：真实菜单里「巨无霸」的类目是「巨无霸 牛鱼肉堡」，
    光看名称（没有「堡」字）会把它错判成小食。
    """
    if any(hint in item.category for hint in _DRINK_HINTS):
        return 0
    if any(hint in item.name for hint in _DRINK_HINTS):
        return 0
    if any(hint in item.category for hint in _MAIN_CATEGORY_HINTS):
        return 2
    if any(hint in item.name for hint in _MAIN_NAME_HINTS):
        return 2
    return 1


def _best_value(candidates: list[MenuItem], target: float) -> MenuItem:
    """挑「最像一顿饭、且最接近目标价」的那份。

    先比餐品等级（主食 > 小食 > 饮品），再比价格与目标的接近程度。
    取「最接近」而不是「最便宜」，是因为 25 元预算推 2 元饼干这种事
    在真实菜单上真的会发生。
    """
    return max(
        candidates,
        key=lambda m: (_meal_tier(m), -abs(m.price - target), m.price),
    )


def _match(menu: list[MenuItem], person: Person) -> MenuItem | None:
    """分层匹配：排除忌口 → 排除非餐品 → 满足口味 → 卡预算 → 取最优。

    取舍原则：
      - 「想吃什么」优先于「预算」，避免想吃鱼却推了蛋堡；
      - 预算内取**最接近预算**的一份，而不是最便宜的；
      - 没有预算时按一顿正餐的目标价挑，而不是无脑挑最贵。
    """
    if not menu:
        return None

    candidates = [m for m in menu if not any(_hit(m, bad) for bad in person.avoid)]
    if not candidates:
        candidates = list(menu)

    meals = [m for m in candidates if _is_meal(m)]
    if meals:
        candidates = meals

    if person.want:
        wanted = [m for m in candidates if _hit(m, person.want)]
        if wanted:
            candidates = wanted

    target = person.budget or DEFAULT_TARGET
    if person.budget:
        within = [m for m in candidates if m.price <= person.budget]
        if within:
            return _best_value(within, target)
    return _best_value(candidates, target)


def _caveats(menu: list[MenuItem], person: Person, item: MenuItem | None) -> list[str]:
    """列出这次推荐里「没能完全满足」的地方，避免静默失败。

    真实菜单的 tags 是营销标签（爆款 / 新品 / 冷饮），
    并不包含「油炸」「辣」这类烹饪属性，所以忌口未必生效 —— 必须如实说明。
    「想吃什么」同理：门店当天可能根本没有这个品类。
    """
    notes: list[str] = []
    if item is None:
        return notes

    if person.want and not any(_hit(m, person.want) for m in menu):
        notes.append(f"菜单里没有「{person.want}」，已按预算与忌口另选")

    for bad in person.avoid:
        if not any(_hit(m, bad) for m in menu):
            notes.append(f"菜单标签无「{bad}」信息，忌口未生效")

    if person.budget and item.price > person.budget:
        notes.append(f"超预算 ¥{item.price - person.budget:.2f}")

    return notes


async def _price_order(
    client: MCDClientProtocol,
    store: Store,
    order_lines: list[dict],
    order_type: int,
    be_type: int,
    be_code: str,
) -> dict:
    """整单实时定价；失败时降级为菜单单价求和。"""
    if not order_lines:
        return {}
    items = [
        {"productCode": line["item"].code, "quantity": line["qty"]}
        for line in order_lines
    ]
    try:
        data = await calculate_price(
            client, store.store_code, items, order_type, be_type, be_code
        )
    except Exception:  # noqa: BLE001 - 降级为本地求和
        data = {}
    if data:
        return data
    subtotal = sum(line["item"].price * line["qty"] for line in order_lines)
    return {"price": int(round(subtotal * 100)), "productList": []}


# ------------------------------------------------------------------ 渲染


def _render(
    people: list[Person],
    picks: list[MenuItem | None],
    order_lines: list[dict],
    price: dict,
    coupons: list[Coupon],
    store_coupons: list[dict],
    store: Store,
    be_type: int,
    menu: list[MenuItem],
) -> str:
    subtotal = cents_to_yuan(price.get("productOriginalPrice"))
    payable = cents_to_yuan(price.get("price"))
    discount = cents_to_yuan(price.get("discount"))
    if not subtotal:
        subtotal = sum(line["item"].price * line["qty"] for line in order_lines)
    if not payable:
        payable = subtotal - discount
    count = max(len(people), 1)
    per_head = payable / count

    lines: list[str] = []
    lines.append(theme.banner("团餐指挥官", "McQuartet · 一群人的点单，不用吵"))
    lines.append("")

    summary = "\n".join(
        [
            f"👥 团餐人数：{count} 人",
            f"🏪 取餐门店：{store.name}",
            f"🛵 取餐方式：{BE_TYPE_LABELS.get(be_type, be_type)}",
            f"💰 预计应付：{theme.bold(money(payable))}",
            f"🍔 人均分摊：{theme.bold(money(per_head))}",
        ]
    )
    lines.append(theme.card("🍱 本次团餐", summary, 58))
    lines.append("")

    lines.append(theme.section("🙋 每人推荐"))
    lines.append("")
    rows = []
    all_caveats: list[str] = []
    for person, item in zip(people, picks, strict=True):
        if item is None:
            rows.append([person.name, "—", "—", "菜单为空"])
            continue
        reason = []
        if person.want:
            reason.append(f"想吃「{person.want}」")
        if person.budget:
            reason.append(f"预算 ¥{person.budget:.0f}")
        if person.avoid:
            reason.append(f"忌口 {'/'.join(person.avoid)}")
        caveats = _caveats(menu, person, item)
        for note in caveats:
            all_caveats.append(f"**{person.name}**：{note}")
        rows.append([person.name, item.name, money(item.price), " · ".join(reason) or "随机搭配"])
    lines.append(md_table(["伙伴", "推荐单品", "单价", "依据"], rows))
    lines.append("")
    if all_caveats:
        lines.append(theme.dim("⚠️ 匹配说明："))
        for note in all_caveats:
            lines.append(theme.dim(f"  · {note}"))
        lines.append("")

    lines.append(theme.section("🧾 合并订单"))
    lines.append("")
    lines.append(
        md_table(
            ["单品", "编码", "数量", "小计"],
            [
                [
                    line["item"].name,
                    line["item"].code,
                    f"×{line['qty']}",
                    money(line["item"].price * line["qty"]),
                ]
                for line in order_lines
            ],
        )
    )
    lines.append("")

    lines.append(theme.section("💰 价格明细"))
    lines.append("")
    lines.append(
        md_table(
            ["项目", "金额"],
            [
                ["🍔 商品小计", money(subtotal)],
                ["🎟️ 优惠减免", f"-{money(discount)}" if discount > 0 else "—"],
                ["💳 **应付合计**", f"**{money(payable)}**"],
                ["👛 **人均分摊**", f"**{money(per_head)}**"],
            ],
        )
    )
    lines.append("")

    _coupon_block(lines, coupons, store_coupons, subtotal, store)
    _budget_block(lines, count)

    lines.append(theme.rule(38))
    lines.append(theme.dim("下单前请确认忌口与过敏原；餐品供应以门店实时菜单为准。"))
    return "\n".join(lines)


def _coupon_block(
    lines: list[str],
    coupons: list[Coupon],
    store_coupons: list[dict],
    subtotal: float,
    store: Store,
) -> None:
    usable = [c for c in coupons if c.status_text in ("", "可用")]
    if usable:
        lines.append(theme.section(f"🎟️ 我的卡包（{len(usable)} 张可用）"))
        lines.append("")
        rows = [
            [
                coupon.title,
                coupon.value_text or "—",
                coupon.scope or "通用",
                coupon.status_text or "可用",
            ]
            for coupon in usable[:8]
        ]
        lines.append(md_table(["优惠券", "力度", "渠道", "状态"], rows))
        lines.append("")
        lines.append(
            theme.dim(
                "提示：卡包里的券不校验门店与渠道，能否用以下单时系统判定为准。"
            )
        )
        lines.append("")
    elif coupons:
        lines.append(theme.section("🎟️ 我的卡包"))
        lines.append("")
        lines.append(f"卡包共 {len(coupons)} 张券，但当前均不在可用状态。")
        lines.append("")

    if store_coupons:
        lines.append(theme.section("✅ 本门店可用券"))
        lines.append("")
        rows = []
        for row in store_coupons[:8]:
            title = str(row.get("title") or row.get("couponName") or "优惠券")
            info = row.get("discountInfo") or {}
            value = f"{info.get('discountTypeText', '')}{info.get('discountValue', '')}"
            rows.append([title, value or "—", row.get("tradeEndDate", "")])
        lines.append(md_table(["优惠券", "力度", "有效期至"], rows))
        lines.append("")


def _budget_block(lines: list[str], count: int) -> None:
    lines.append(theme.section("💡 凑单建议"))
    lines.append("")
    lines.append("官方团餐搭配规则：")
    for limit, combo in BUDGET_HINTS:
        lines.append(f"- **{limit} 元以下**：{combo}")
    lines.append("")
    if count >= 10:
        lines.append("🎉 已满 10 人，可解锁**企业团餐助餐服务**（分批取餐 / 统一配送）。")
    else:
        lines.append(f"💡 还差 {10 - count} 人即可解锁企业团餐助餐服务。")
    lines.append("")


def _empty_menu(store: Store) -> str:
    lines = [theme.banner("团餐指挥官", "McQuartet"), ""]
    lines.append(
        theme.card(
            "🍱 该门店当前不可点餐",
            f"{store.name}（{store.store_code}）\n"
            f"营业时间：{store.hours_text}　状态：{store.status_text}\n\n"
            "可能原因：门店已打烊，或不在营业时间。\n请换一家门店或稍后再试。",
            58,
        )
    )
    return "\n".join(lines)
