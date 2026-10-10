"""🧪 隐藏菜单实验室 —— 人人都能发明自己的麦当劳。

数据来源（麦当劳 MCP）：
  - ``query-meal-detail``      套餐轮次与可替换选项（``rounds[].choices[]``）
  - ``list-nutrition-foods``   餐品营养（紧凑表格字符串）
  - ``calculate-price``        改配后**真实**价格（传完整 roundList）

玩法：用套餐的「可替换轮次」重组配方，实时对比营养与价格，生成可分享的配方卡。
内置 减脂 / 增肌 / 解馋 / 清醒 四套一键配方。

关键实现细节（踩坑记录）：
  * ``calculate-price`` 的 ``items[].roundList`` 必须传**全部**轮次，
    且 ``round`` 字段是轮次的**数字 id 字符串**（不是名称）；漏轮次会报 60006。
  * 只能选该轮次 ``choices`` 里真实存在的 code，否则同样报 60006。
  * 价格增量公式：``新价 = 套餐价 + Σ(diffPrice × 该轮次数量)``。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .. import theme
from ..mcd_api import (
    BE_TYPE_LABELS,
    Choice,
    MenuItem,
    Round,
    calculate_price,
    cents_to_yuan,
    default_composition,
    extract_rounds,
    fetch_meal_detail,
    fetch_menu,
    fetch_nutrition,
    lookup_nutrition,
)
from ..mcp_client import MCDClientProtocol
from ..utils import md_table, money

# 咖啡因关键词（用于「清醒」配方）
# 用单字「咖」而不是「咖啡」，因为菜单里叫「鲜萃冰咖」——不含「咖啡」二字。
_CAFFEINE_HINTS = ("咖", "浓缩", "美式", "拿铁", "卡布", "黑巧")

# 预设配方：给每个轮次的可选项打分，取最高分。
#
# 打分函数返回 ``None`` 表示「这一项我不评价」，该选项会被排除在比较之外。
# 需要营养数据的配方在拿不到数据时也返回 ``None`` ——
# 这样「查不到数据」的选项就不会以 0 分伪装成「零热量」而被误选。
# 若某个轮次里能被评价的选项不足两个，就保留默认选项。
PRESETS: dict[str, dict[str, Any]] = {
    "减脂": {
        "desc": "逐轮挑低热量选项，把油炸和含糖换下去",
        "score": lambda info, choice: -float(info["energyKcal"]) if info else None,
    },
    "增肌": {
        "desc": "优先拉高蛋白质，主食尽量保留",
        "score": lambda info, choice: (
            float(info.get("protein", 0)) * 10 - float(info.get("energyKcal", 0)) * 0.02
            if info
            else None
        ),
    },
    "解馋": {
        "desc": "热量拉满，快乐优先",
        "score": lambda info, choice: float(info["energyKcal"]) if info else None,
    },
    "清醒": {
        "desc": "只把饮料换成含咖啡因的，其余保持原样",
        # 只看名字，不需要营养数据
        "score": lambda info, choice: (
            1000.0 if any(h in choice.name for h in _CAFFEINE_HINTS) else None
        ),
    },
}


class HiddenMenuModule:
    """隐藏菜单实验室模块。"""

    name = "隐藏菜单实验室"
    emoji = "🧪"

    async def run(
        self,
        client: MCDClientProtocol,
        store_code: str,
        meal_query: str,
        preset: str | None = None,
        custom_swaps: dict[str, str] | None = None,
        order_type: int = 1,
        be_type: int = 1,
        be_code: str = "",
    ) -> str:
        menu = await fetch_menu(client, store_code, order_type, be_type, be_code)
        target = find_meal(menu, meal_query)
        if target is None:
            return _not_found(meal_query, menu)

        detail = await fetch_meal_detail(
            client, store_code, target.code, order_type, be_type, be_code
        )
        rounds = extract_rounds(detail)
        if not rounds:
            return _no_rounds(target)

        nutrition = await fetch_nutrition(client)
        base_composition = default_composition(detail)
        base_price = target.price

        chosen, notes = _apply(
            rounds, preset, custom_swaps or {}, nutrition, base_composition
        )

        new_price, price_note = await _price_combo(
            client, store_code, target, rounds, chosen, base_price, order_type, be_type, be_code
        )

        return _render(
            detail=detail,
            target=target,
            preset=preset,
            rounds=rounds,
            chosen=chosen,
            notes=notes,
            nutrition=nutrition,
            base_price=base_price,
            new_price=new_price,
            price_note=price_note,
            base_composition=base_composition,
        )


# ------------------------------------------------------------------ 选品


def find_meal(menu: list[MenuItem], query: str) -> MenuItem | None:
    """按 code / 名称模糊查找餐品。"""
    query = (query or "").strip()
    if not query:
        return None
    for item in menu:
        if item.code == query:
            return item
    upper = query.upper()
    for item in menu:
        if item.code.upper() == upper:
            return item
    for item in menu:
        if item.name and query in item.name:
            return item
    for item in menu:
        if item.name and any(part and part in item.name for part in _tokens(query)):
            return item
    for item in menu:
        if query in item.code:
            return item
    return None


def _tokens(text: str) -> list[str]:
    """把查询串切成候选片段（兼容用户只记得关键词的情况）。"""
    for sep in ("/", "、", ",", "，", " "):
        text = text.replace(sep, "|")
    return [t for t in text.split("|") if t]


def _apply(
    rounds: list[Round],
    preset: str | None,
    custom_swaps: dict[str, str],
    nutrition: dict[str, dict],
    base_composition: list[dict],
) -> tuple[list[dict], list[str]]:
    """计算每一轮的最终选项，返回 [(round, choice)] 与改配说明。"""
    preset_cfg = PRESETS.get(preset or "")
    scorer: Callable[[dict, Choice], float | None] | None = (
        preset_cfg["score"] if preset_cfg else None
    )

    default_by_round = {
        str(i + 1): comp.get("code", "") for i, comp in enumerate(base_composition)
    }

    chosen: list[dict] = []
    notes: list[str] = []

    for index, round_ in enumerate(rounds, start=1):
        round_id = str(index)
        pick = _pick_for_round(
            round_, round_id, scorer, custom_swaps, nutrition, default_by_round
        )
        chosen.append({"round_id": round_id, "round": round_, "choice": pick})

        default_code = default_by_round.get(round_id)
        if pick is not None and default_code and pick.code != default_code:
            default_choice = next(
                (c for c in round_.choices if c.code == default_code), None
            )
            before = default_choice.name if default_choice else default_code
            delta = pick.diff_price
            suffix = f"（{pick.diff_text}）" if abs(delta) > 0.001 else ""
            notes.append(f"{round_.name}：{before} ➜ {pick.name}{suffix}")

    return chosen, notes


def _pick_for_round(
    round_: Round,
    round_id: str,
    scorer: Callable[[dict, Choice], float | None] | None,
    custom_swaps: dict[str, str],
    nutrition: dict[str, dict],
    default_by_round: dict[str, str],
) -> Choice | None:
    # 1) 用户显式指定优先（支持「轮次id」或「轮次名」两种 key）
    override = _lookup_swap(custom_swaps, round_id, round_.name)
    if override is not None:
        matched = _match_choice(round_, override)
        if matched is not None:
            return matched

    # 2) 只有唯一选项 → 没得选
    if len(round_.choices) <= 1:
        return round_.default_choice

    # 3) 没有预设 → 保持默认
    if scorer is None:
        return round_.default_choice

    # 4) 按预设打分，只保留「能被打分」的选项
    #
    # 关键点：新品常常不在官方营养表里。如果让查不到数据的选项以 0 分参与比较，
    # 它会伪装成「零热量」，让减脂配方越减越离谱 —— 所以拿不到数据就不评价。
    default_code = default_by_round.get(round_id)
    scored: list[tuple[float, Choice]] = []
    for choice in round_.choices:
        info = lookup_nutrition(nutrition, choice.name)
        score = scorer(info, choice)
        if score is None:
            continue
        if info:
            score += 1e-9  # 有真实数据的选项在平分时略占优
        if choice.code == default_code:
            score += 1e-6  # 再优先保留默认项
        scored.append((score, choice))

    if not scored:
        return round_.default_choice

    # 只有一个候选时：若它本来就是默认项，就没必要「换」；否则值得换过去。
    # （「清醒」配方常常整轮只有一个含咖啡因的选项，不能被这条挡掉。）
    if len(scored) < 2 and any(choice.code == default_code for _, choice in scored):
        return round_.default_choice

    return max(scored, key=lambda pair: pair[0])[1]


def _lookup_swap(swaps: dict[str, str], round_id: str, round_name: str) -> str | None:
    if round_id in swaps:
        return swaps[round_id]
    if round_name in swaps:
        return swaps[round_name]
    for key, value in swaps.items():
        if key and key in round_name:
            return value
    return None


def _match_choice(round_: Round, token: str) -> Choice | None:
    token = token.strip()
    if not token:
        return None
    for choice in round_.choices:
        if choice.code == token:
            return choice
    for choice in round_.choices:
        if token == choice.name:
            return choice
    for choice in round_.choices:
        if token and token in choice.name:
            return choice
    return None


# ------------------------------------------------------------------ 真实定价


async def _price_combo(
    client: MCDClientProtocol,
    store_code: str,
    target: MenuItem,
    rounds: list[Round],
    chosen: list[dict],
    base_price: float,
    order_type: int,
    be_type: int,
    be_code: str,
) -> tuple[float, str]:
    """用 ``calculate-price`` 计算改配后的真实价格。

    roundList 必须完整，``round`` 传轮次数字 id 字符串。
    """
    round_list = [
        {
            "round": entry["round_id"],
            "comboItemList": [
                {"code": entry["choice"].code, "quantity": entry["round"].quantity or 1}
            ],
        }
        for entry in chosen
        if entry["choice"] is not None
    ]

    if len(round_list) == len(rounds):
        try:
            data = await calculate_price(
                client,
                store_code,
                [
                    {
                        "productCode": target.code,
                        "quantity": 1,
                        "roundList": round_list,
                    }
                ],
                order_type,
                be_type,
                be_code,
            )
            price = cents_to_yuan(data.get("price"))
            if price > 0:
                return price, "已通过 calculate-price 实时核算"
        except Exception:  # noqa: BLE001 - 任何失败都降级为公式估算
            pass

    # 降级：套餐价 + Σ(差价 × 轮次数量)
    delta = 0.0
    for entry in chosen:
        choice = entry["choice"]
        if choice is None:
            continue
        delta += choice.diff_price * (entry["round"].quantity or 1)
    return round(base_price + delta, 2), "按套餐差价公式估算（实时核算不可用）"


# ------------------------------------------------------------------ 渲染


def _nutrition_of(name: str, nutrition: dict[str, dict]) -> dict:
    return lookup_nutrition(nutrition, name)


def _sum_nutrition(entries: list[dict], nutrition: dict[str, dict]) -> dict[str, float]:
    total = {"energyKcal": 0.0, "protein": 0.0, "fat": 0.0, "carbohydrate": 0.0, "sodium": 0.0}
    for entry in entries:
        info = _nutrition_of(entry["name"], nutrition)
        qty = entry.get("quantity", 1) or 1
        for key in total:
            total[key] += float(info.get(key, 0) or 0) * qty
    return total


def _render(
    detail: dict,
    target: MenuItem,
    preset: str | None,
    rounds: list[Round],
    chosen: list[dict],
    notes: list[str],
    nutrition: dict[str, dict],
    base_price: float,
    new_price: float,
    price_note: str,
    base_composition: list[dict],
) -> str:
    base_name = str(detail.get("name") or target.name or target.code)
    tag = f"{preset}版" if preset else "自定义版"
    recipe_name = f"{base_name}·{tag}"

    before_entries = [
        {"name": comp["name"], "quantity": comp.get("quantity", 1)}
        for comp in base_composition
    ]
    after_entries = [
        {
            "name": entry["choice"].name,
            "quantity": entry["round"].quantity or 1,
        }
        for entry in chosen
        if entry["choice"] is not None
    ]

    n_before = _sum_nutrition(before_entries, nutrition)
    n_after = _sum_nutrition(after_entries, nutrition)

    lines: list[str] = []
    lines.append(theme.banner("隐藏菜单实验室", "MCD Buddy · 人人都能发明自己的麦当劳"))
    lines.append("")

    head = "\n".join(
        [
            f"🍔 配方名称：{theme.bold(recipe_name)}",
            f"🔖 配方编号：HM-{abs(hash(recipe_name)) % 10000:04d}",
            f"🧾 基础套餐：{base_name}（{target.code}）",
        ]
    )
    lines.append(theme.card("🧪 我的隐藏配方", head, 58))
    lines.append("")

    lines.append(theme.section("🔧 改配说明"))
    lines.append("")
    if notes:
        for note in notes:
            lines.append(f"- {note}")
    else:
        lines.append("（未做替换，展示原配方）")
    lines.append("")

    lines.append(theme.section("🍔 配方组成"))
    lines.append("")
    rows = []
    for entry in chosen:
        round_ = entry["round"]
        choice = entry["choice"]
        if choice is None:
            rows.append([round_.name, "—", "—", "—"])
            continue
        rows.append(
            [
                round_.name,
                choice.name,
                f"×{round_.quantity or 1}",
                choice.diff_text,
            ]
        )
    lines.append(md_table(["轮次", "已选", "数量", "差价"], rows))
    lines.append("")

    if len(rounds) > 1 and any(len(r.choices) > 1 for r in rounds):
        lines.append(theme.dim("可替换选项（每轮任选其一）："))
        for index, round_ in enumerate(rounds, start=1):
            if len(round_.choices) <= 1:
                continue
            options = " / ".join(
                f"{c.name}{c.diff_text}" if abs(c.diff_price) > 0.001 else c.name
                for c in round_.choices
            )
            lines.append(theme.dim(f"  {index}. {round_.name}：{options}"))
        lines.append("")

    lines.append(theme.section("📈 营养对比"))
    lines.append("")

    def delta_row(label: str, key: str, unit: str) -> list[str]:
        before, after = n_before[key], n_after[key]
        diff = after - before
        sign = f"{diff:+.0f}" if abs(diff) >= 0.5 else "±0"
        return [label, f"{before:.0f}{unit}", "➜", f"{after:.0f}{unit}", sign + unit]

    lines.append(
        md_table(
            ["指标", "原配方", "", "新配方", "变化"],
            [
                delta_row("🔥 能量", "energyKcal", " kcal"),
                delta_row("💪 蛋白质", "protein", " g"),
                delta_row("🧈 脂肪", "fat", " g"),
                delta_row("🍚 碳水", "carbohydrate", " g"),
                delta_row("🧂 钠", "sodium", " mg"),
            ],
        )
    )
    lines.append("")
    missing = [e["name"] for e in after_entries if not _nutrition_of(e["name"], nutrition)]
    if missing:
        lines.append(
            theme.dim(
                "⚠️ 以下餐品暂无官方营养数据，未计入上表："
                + "、".join(dict.fromkeys(missing))
            )
        )
        lines.append("")

    lines.append(theme.section("💰 价格"))
    lines.append("")
    lines.append(
        md_table(
            ["版本", "价格"],
            [
                ["原套餐", money(base_price)],
                [f"**{tag}**", f"**{money(new_price)}**"],
            ],
        )
    )
    lines.append("")
    lines.append(theme.dim(f"定价来源：{price_note}"))
    lines.append("")

    lines.append(theme.section("📤 分享配方卡"))
    lines.append("")
    lines.append("```text")
    lines.append(f"🧪 {recipe_name}")
    lines.append(f"🍔 {' + '.join(e['name'] for e in after_entries)}")
    lines.append(
        f"🔥 {n_after['energyKcal']:.0f} kcal | 蛋白 {n_after['protein']:.0f}g | "
        f"脂肪 {n_after['fat']:.0f}g"
    )
    lines.append(f"💰 {money(new_price)}")
    lines.append("—— 来自麦门助手 · 隐藏菜单实验室")
    lines.append("```")
    lines.append("")
    lines.append(theme.rule(38))
    lines.append(
        theme.dim("营养数据来源于麦当劳官方餐品营养信息；实际供应与价格以门店为准。")
    )
    return "\n".join(lines)


def _not_found(query: str, menu: list[MenuItem]) -> str:
    lines = [theme.banner("隐藏菜单实验室", "MCD Buddy"), ""]
    lines.append(theme.card("🧪 没找到这个餐品", f"查询：{query}", 58))
    lines.append("")
    lines.append(theme.section("📋 当前门店菜单（部分）"))
    lines.append("")
    rows = [[item.name or "（未命名）", item.code, money(item.price)] for item in menu[:20]]
    lines.append(md_table(["餐品", "编码", "价格"], rows))
    lines.append("")
    lines.append(theme.dim("提示：用 --meal 传餐品编码或名称关键词，例如 --meal 双人分享餐"))
    return "\n".join(lines)


def _no_rounds(target: MenuItem) -> str:
    lines = [theme.banner("隐藏菜单实验室", "MCD Buddy"), ""]
    lines.append(
        theme.card(
            "🧪 这是单品，没有可替换轮次",
            f"{target.name}（{target.code}）\n单品无法改配，请换一个套餐试试。",
            58,
        )
    )
    return "\n".join(lines)


def menu_table(menu: list[MenuItem]) -> str:
    """把菜单渲染成表格（供 CLI --list 使用）。"""
    if not menu:
        return "（菜单为空）"
    categories: dict[str, list[MenuItem]] = {}
    for item in menu:
        categories.setdefault(item.category or "其他", []).append(item)
    lines: list[str] = []
    for name, items in categories.items():
        lines.append(theme.section(f"🍟 {name}"))
        lines.append("")
        lines.append(
            md_table(
                ["餐品", "编码", "价格"],
                [[i.name or "（未命名）", i.code, money(i.price)] for i in items],
            )
        )
        lines.append("")
    return "\n".join(lines).rstrip()


def be_label(be_type: int) -> str:
    return BE_TYPE_LABELS.get(be_type, str(be_type))
