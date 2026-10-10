"""麦当劳 MCP 业务层封装。

真实接口与直觉差异很大，本模块把这些坑统一收口，模块层只面对干净的 Python 对象：

1. **响应信封**：所有工具返回 ``{success, code, message, datetime, traceId, data}``，
   业务数据在 ``data`` 里；``success=false`` 时 ``message`` 是中文错误原因。
2. **门店前置**：菜单、价格、优惠券类工具都必传 ``storeCode`` / ``orderType`` / ``beType``，
   所以必须先解析门店。
3. **价格单位是「分」**：``7950`` 表示 ¥79.50。订单金额 ``realTotalAmount`` 却是「元」字符串。
4. **query-meals 只有编码和标签**（``data.categories[].meals[].code``），
   没有名称和价格，需要 ``calculate-price`` 批量补全。
5. **套餐组成是 rounds**：``data.rounds[].choices[]``，可选项带 ``diffPrice`` 差价字符串。
6. **营养数据是紧凑表格字符串**，不是 JSON 数组。
7. **外送 / 团餐场景需要 ``beCode``**，来自 ``delivery-query-stores``（需先有地址 ID）。
   到店自取（beType=1）不传 beCode，传了会报错。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .mcp_client import MCDClientProtocol
from .utils import pick

# beType：1-到店取餐，2-麦乐送到家，5-得来速，6-企业团餐
BE_DINE_IN = 1
BE_DELIVERY = 2
BE_DRIVE_THRU = 5
BE_GROUP = 6

# orderType：1-到店（自取+得来速），2-外送（麦乐送+团餐）
ORDER_PICKUP = 1
ORDER_DELIVERY = 2

BE_TYPE_LABELS = {1: "到店自取", 2: "麦乐送", 5: "得来速", 6: "企业团餐"}

# 这些 beType 属于「外送」大类，必须带 beCode
NEEDS_BE_CODE = {BE_DELIVERY, BE_DRIVE_THRU, BE_GROUP}


class MCDApiError(RuntimeError):
    """业务层错误（接口返回 success=false）。"""


# ------------------------------------------------------------------ 数据模型


@dataclass
class Store:
    """门店。"""

    store_code: str
    name: str
    address: str = ""
    distance: int = 0
    open: bool = False
    open_time: str = ""
    close_time: str = ""
    reservation: bool = False

    @property
    def status_text(self) -> str:
        return "营业中" if self.open else "已打烊"

    @property
    def hours_text(self) -> str:
        if self.open_time and self.close_time:
            return f"{self.open_time}-{self.close_time}"
        return "—"

    @property
    def distance_text(self) -> str:
        if self.distance <= 0:
            return "—"
        return f"{self.distance} 米" if self.distance < 1000 else f"{self.distance / 1000:.1f} 公里"


@dataclass
class MenuItem:
    """菜单商品（名称与价格由 calculate-price 补全）。"""

    code: str
    name: str = ""
    price: float = 0.0          # 单位：元
    category: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def haystack(self) -> str:
        return f"{self.name} {self.category} {' '.join(self.tags)}"


@dataclass
class Choice:
    """套餐某个轮次里的一个可选项。"""

    code: str
    name: str
    selected: bool = False
    quantity: int = 0
    diff_price: float = 0.0     # 单位：元
    support_modify: bool = False

    @property
    def diff_text(self) -> str:
        if abs(self.diff_price) < 0.001:
            return "±¥0"
        return f"{'+' if self.diff_price > 0 else '-'}¥{abs(self.diff_price):.2f}".replace(".00", "")


@dataclass
class Round:
    """套餐的一个可选轮次，例如「选择小食」。"""

    name: str
    quantity: int = 1
    min_quantity: int = 1
    max_quantity: int = 1
    choices: list[Choice] = field(default_factory=list)

    @property
    def default_choice(self) -> Choice | None:
        for choice in self.choices:
            if choice.selected:
                return choice
        return self.choices[0] if self.choices else None


@dataclass
class Coupon:
    """用户卡包中的一张优惠券。"""

    title: str
    value_text: str = ""
    desc: str = ""
    scope: str = ""
    valid_text: str = ""
    status_text: str = ""
    code: str = ""

    @property
    def display(self) -> str:
        parts = [self.title]
        if self.value_text:
            parts.append(f"({self.value_text})")
        return " ".join(parts)


# ------------------------------------------------------------------ 信封


def unwrap(payload: Any, tool: str = "") -> Any:
    """拆开响应信封，返回 ``data``；失败时抛出 :class:`MCDApiError`。"""
    if not isinstance(payload, dict):
        return payload
    if payload.get("success") is False:
        code = payload.get("code", "")
        message = payload.get("message", "未知错误")
        raise MCDApiError(f"[{tool}] {message}" + (f"（code={code}）" if code else ""))
    if "data" in payload:
        return payload["data"]
    return payload


async def safe_call(
    client: MCDClientProtocol,
    tool: str,
    arguments: dict | None = None,
    default: Any = None,
) -> Any:
    """调用工具并拆信封；任何业务错误都降级为 ``default``，不中断整体流程。"""
    try:
        return unwrap(await client.call(tool, arguments or {}), tool)
    except MCDApiError:
        return default


# ------------------------------------------------------------------ 门店


def _store_from_row(row: dict) -> Store:
    return Store(
        store_code=str(pick(row, "storeCode", "code", default="")),
        name=str(pick(row, "storeName", "name", default="门店")),
        address=str(pick(row, "address", default="")),
        distance=int(pick(row, "distance", default=0) or 0),
        open=bool(pick(row, "businessStatus", "open", default=False)),
        open_time=str(pick(row, "businessStartTime", default="")),
        close_time=str(pick(row, "businessEndTime", default="")),
        reservation=bool(pick(row, "reservation", default=False)),
    )


async def search_stores(
    client: MCDClientProtocol,
    city: str,
    keyword: str,
    be_type: int = BE_DINE_IN,
    search_type: int = 2,
) -> list[Store]:
    """按「城市 + 关键词」搜索门店。

    注意：``query-nearby-stores`` 要求 ``city`` 与 ``keyword`` **同时非空**，
    只传一个会返回 600058「城市名或者关键词不能为空」。
    ``searchType=2`` 按位置搜索，``searchType=1`` 搜收藏门店。
    """
    payload = await client.call(
        "query-nearby-stores",
        {"beType": be_type, "searchType": search_type, "city": city, "keyword": keyword},
    )
    rows = unwrap(payload, "query-nearby-stores")
    if not isinstance(rows, list):
        rows = []
    stores = [_store_from_row(row) for row in rows if isinstance(row, dict)]
    return [s for s in stores if s.store_code]


async def resolve_store(
    client: MCDClientProtocol,
    city: str = "",
    keyword: str = "麦当劳",
    be_type: int = BE_DINE_IN,
    search_type: int = 2,
    store_code: str = "",
) -> Store | None:
    """解析出一家可用门店：优先营业中，其次距离最近。"""
    if store_code:
        return Store(store_code=store_code, name=f"门店 {store_code}", open=True)

    if not city:
        raise MCDApiError("需要提供城市名才能搜索门店（用 --city 指定）。")

    stores = await search_stores(client, city, keyword, be_type, search_type)
    if not stores:
        return None
    stores.sort(key=lambda s: (not s.open, s.distance))
    return stores[0]


# ------------------------------------------------------------------ 菜单


def parse_menu_codes(data: Any) -> list[MenuItem]:
    """解析 ``query-meals`` 的 ``data.categories[].meals[]``。"""
    items: list[MenuItem] = []
    seen: set[str] = set()
    if not isinstance(data, dict):
        return items
    for category in data.get("categories", []) or []:
        if not isinstance(category, dict):
            continue
        category_name = str(pick(category, "name", default="")).replace("\n", " ").strip()
        for meal in category.get("meals", []) or []:
            if not isinstance(meal, dict):
                continue
            code = str(pick(meal, "code", "productCode", default=""))
            if not code or code in seen:
                continue
            seen.add(code)
            items.append(
                MenuItem(
                    code=code,
                    category=category_name,
                    tags=[str(t) for t in (meal.get("tags") or [])],
                )
            )
    return items


async def fetch_menu_codes(
    client: MCDClientProtocol,
    store_code: str,
    order_type: int = ORDER_PICKUP,
    be_type: int = BE_DINE_IN,
    be_code: str = "",
) -> list[MenuItem]:
    """拉取门店菜单编码列表。"""
    args = _store_args(store_code, order_type, be_type, be_code)
    data = unwrap(await client.call("query-meals", args), "query-meals")
    return parse_menu_codes(data)


async def enrich_menu(
    client: MCDClientProtocol,
    store_code: str,
    items: list[MenuItem],
    order_type: int = ORDER_PICKUP,
    be_type: int = BE_DINE_IN,
    be_code: str = "",
    chunk_size: int = 50,
) -> list[MenuItem]:
    """用 ``calculate-price`` 批量补全菜单的名称与价格。

    一次请求可算多个商品，失败时二分重试，保证个别不可售商品不影响整体。
    """
    price_map: dict[str, tuple[str, float]] = {}

    async def price_batch(batch: list[MenuItem]) -> None:
        if not batch:
            return
        args = _store_args(store_code, order_type, be_type, be_code)
        args["items"] = [{"productCode": item.code, "quantity": 1} for item in batch]
        try:
            data = unwrap(await client.call("calculate-price", args), "calculate-price")
        except MCDApiError:
            if len(batch) == 1:
                return
            mid = len(batch) // 2
            await price_batch(batch[:mid])
            await price_batch(batch[mid:])
            return
        for row in (data or {}).get("productList", []) or []:
            if not isinstance(row, dict):
                continue
            code = str(pick(row, "productCode", default=""))
            price_map[code] = (
                str(pick(row, "productName", default="")),
                cents_to_yuan(pick(row, "subtotal", "originalSubtotal", default=0)),
            )

    for start in range(0, len(items), chunk_size):
        await price_batch(items[start : start + chunk_size])

    for item in items:
        name, price = price_map.get(item.code, ("", 0.0))
        item.name = name or item.name
        item.price = price
    return items


async def fetch_menu(
    client: MCDClientProtocol,
    store_code: str,
    order_type: int = ORDER_PICKUP,
    be_type: int = BE_DINE_IN,
    be_code: str = "",
) -> list[MenuItem]:
    """拉取并补全门店菜单（编码 + 标签 + 名称 + 价格）。"""
    items = await fetch_menu_codes(client, store_code, order_type, be_type, be_code)
    return await enrich_menu(client, store_code, items, order_type, be_type, be_code)


def _store_args(
    store_code: str,
    order_type: int,
    be_type: int,
    be_code: str = "",
) -> dict[str, Any]:
    args: dict[str, Any] = {"storeCode": store_code, "orderType": order_type, "beType": be_type}
    if be_type in NEEDS_BE_CODE and be_code:
        args["beCode"] = be_code
    return args


# ------------------------------------------------------------------ 餐品详情


async def fetch_meal_detail(
    client: MCDClientProtocol,
    store_code: str,
    code: str,
    order_type: int = ORDER_PICKUP,
    be_type: int = BE_DINE_IN,
    be_code: str = "",
) -> dict:
    """查询餐品详情（套餐组成、可替换项、特制选项）。"""
    args = _store_args(store_code, order_type, be_type, be_code)
    args["code"] = code
    data = unwrap(await client.call("query-meal-detail", args), "query-meal-detail")
    return data if isinstance(data, dict) else {}


async def calculate_price(
    client: MCDClientProtocol,
    store_code: str,
    items: list[dict],
    order_type: int = ORDER_PICKUP,
    be_type: int = BE_DINE_IN,
    be_code: str = "",
) -> dict:
    """计算价格。``items`` 元素形如 ``{"productCode": "1440", "quantity": 1}``。"""
    args = _store_args(store_code, order_type, be_type, be_code)
    args["items"] = items
    data = unwrap(await client.call("calculate-price", args), "calculate-price")
    return data if isinstance(data, dict) else {}


# ------------------------------------------------------------------ 优惠券 / 奖品


async def fetch_my_coupons(
    client: MCDClientProtocol,
    page: str = "1",
    page_size: str = "200",
) -> list[Coupon]:
    """查询用户卡包里的优惠券（不校验门店/渠道，只是「我有什么券」）。"""
    data = await safe_call(
        client, "query-my-coupons", {"page": page, "pageSize": page_size}, {}
    )
    rows = (data or {}).get("coupons", []) if isinstance(data, dict) else []
    coupons: list[Coupon] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        info = row.get("discountInfo") or {}
        value = str(pick(info, "discountTypeText", default="")) + str(
            pick(info, "discountValue", default="")
        )
        labels = ((row.get("instructions") or {}).get("labels")) or []
        status = next(
            (str(item.get("text")) for item in labels if isinstance(item, dict) and item.get("text")),
            "",
        )
        tags = [str(t.get("label")) for t in (row.get("tags") or []) if isinstance(t, dict)]
        coupons.append(
            Coupon(
                title=str(pick(row, "title", "couponName", default="优惠券")),
                value_text=value.strip(),
                desc=str(pick(info, "discountDesc", default="")),
                scope=" / ".join(t for t in tags if t),
                valid_text=str(pick(row, "tradeStartDate", default=""))
                + " ~ "
                + str(pick(row, "tradeEndDate", default="")),
                status_text=status,
                code=str(pick(row, "code", default="")),
            )
        )
    return coupons


async def fetch_available_coupons(client: MCDClientProtocol) -> list[dict]:
    """查询可领取 / 已领取的营销券列表。"""
    data = await safe_call(client, "available-coupons", {}, [])
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


async def fetch_my_prizes(client: MCDClientProtocol, page_size: str = "50") -> list[dict]:
    """查询积分抽奖获得的本期及历史奖品。"""
    data = await safe_call(client, "query-my-prizes", {"pageNum": "1", "pageSize": page_size}, {})
    rows = (data or {}).get("prizes", []) if isinstance(data, dict) else []
    return [row for row in rows if isinstance(row, dict)]


async def fetch_store_coupons(
    client: MCDClientProtocol,
    store_code: str,
    order_type: int = ORDER_PICKUP,
    be_type: int = BE_DINE_IN,
    be_code: str = "",
) -> list[dict]:
    """查询指定门店 + 订单类型下**可用**的优惠券。"""
    args = _store_args(store_code, order_type, be_type, be_code)
    data = await safe_call(client, "query-store-coupons", args, [])
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


# ------------------------------------------------------------------ 无参工具


async def fetch_now(client: MCDClientProtocol) -> dict:
    """当前时间信息。"""
    data = await safe_call(client, "now-time-info", {}, {})
    return data if isinstance(data, dict) else {}


async def fetch_account(client: MCDClientProtocol) -> dict:
    """积分账户信息。"""
    data = await safe_call(client, "query-my-account", {}, {})
    return data if isinstance(data, dict) else {}


async def fetch_orders(client: MCDClientProtocol) -> list[dict]:
    """历史订单（``data.list[]``）。"""
    data = await safe_call(client, "order-list", {}, {})
    if isinstance(data, dict) and isinstance(data.get("list"), list):
        return [row for row in data["list"] if isinstance(row, dict)]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


async def fetch_calendar(client: MCDClientProtocol, specified_date: str = "") -> dict:
    """当月营销活动日历。"""
    args = {"specifiedDate": specified_date} if specified_date else {}
    data = await safe_call(client, "campaign-calendar", args, {})
    return data if isinstance(data, dict) else {}


async def fetch_lottery(client: MCDClientProtocol) -> dict:
    """积分抽奖活动信息（不执行抽奖）。"""
    data = await safe_call(client, "query-lottery-info", {}, {})
    return data if isinstance(data, dict) else {}


async def fetch_nutrition(client: MCDClientProtocol) -> dict[str, dict]:
    """餐品营养数据（解析紧凑表格字符串）。"""
    data = await safe_call(client, "list-nutrition-foods", {}, "")
    return parse_nutrition_table(data)


# ------------------------------------------------------------------ 解析工具


def cents_to_yuan(value: Any) -> float:
    """麦当劳 MCP 的金额单位是「分」，转换为「元」。"""
    try:
        return round(float(value) / 100, 2)
    except (TypeError, ValueError):
        return 0.0


def to_float(value: Any, default: float = 0.0) -> float:
    """把字符串 / 数字安全转成 float（真实接口里金额常是字符串）。"""
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


_DIFF_RE = re.compile(r"([+-])\s*¥?\s*([\d.]+)")


def parse_diff_price(text: Any) -> float:
    """解析 ``"+ ¥1.5"`` / ``"- ¥1.5"`` / ``"+ ¥0"`` 形式的差价，返回元。"""
    if isinstance(text, (int, float)):
        return float(text)
    if not text:
        return 0.0
    match = _DIFF_RE.search(str(text))
    if not match:
        return 0.0
    sign, number = match.groups()
    try:
        value = float(number)
    except ValueError:
        return 0.0
    return -value if sign == "-" else value


def parse_nutrition_table(payload: Any) -> dict[str, dict]:
    """解析 ``list-nutrition-foods`` 返回的紧凑表格字符串。

    真实格式形如::

        [160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:
          猪柳麦满分,null,1288,308,16,16,24,781,213
    """
    if isinstance(payload, dict):
        payload = payload.get("data", payload)
    if not isinstance(payload, str):
        return {}

    header_match = re.search(r"\{(.*?)\}", payload)
    if not header_match:
        return {}
    columns = [c.strip() for c in header_match.group(1).split(",")]

    table: dict[str, dict] = {}
    body = payload[header_match.end() :]
    for line in body.split("\n"):
        line = line.strip()
        if not line:
            continue
        cells = [c.strip() for c in line.split(",")]
        if len(cells) < len(columns):
            continue
        row = dict(zip(columns, cells, strict=False))
        name = row.get("productName", "").strip()
        if not name:
            continue
        record: dict[str, Any] = {"name": name}
        for key in (
            "energyKj",
            "energyKcal",
            "protein",
            "fat",
            "carbohydrate",
            "sodium",
            "calcium",
        ):
            record[key] = to_float(row.get(key))
        table[name] = record
    return table


_NAME_NOISE_RE = re.compile(r"[\s\-—–－_·・,，.。()（）\[\]【】\"'“”‘’+＋/\\]+")


def _norm_name(name: str) -> str:
    """归一化餐品名，抹掉分隔符差异。

    菜单里叫「麦辣鸡翅2块」，营养表里叫「麦辣鸡翅-2块」——
    不归一化就会双双查不到数据，让「减脂」配方把未知项当成零热量。
    """
    return _NAME_NOISE_RE.sub("", str(name or "")).lower()


def lookup_nutrition(table: dict[str, dict], name: str) -> dict:
    """按名称查营养数据，支持归一化后的精确 / 包含匹配。"""
    if not name:
        return {}
    if name in table:
        return table[name]

    target = _norm_name(name)
    if not target:
        return {}

    normalized = {_norm_name(key): value for key, value in table.items()}
    if target in normalized:
        return normalized[target]

    # 包含式匹配：优先取名字更短的（更精确）的那个
    hits = [
        (len(key), value)
        for key, value in normalized.items()
        if key and (key in target or target in key)
    ]
    if hits:
        hits.sort(key=lambda pair: pair[0])
        return hits[0][1]

    # 原始名称的包含式兜底
    for key, value in table.items():
        if key in name or name in key:
            return value
    return {}


def extract_rounds(detail: dict) -> list[Round]:
    """从餐品详情中取出「套餐轮次 / 可替换组」。"""
    rounds: list[Round] = []
    for raw in detail.get("rounds", []) or []:
        if not isinstance(raw, dict):
            continue
        choices: list[Choice] = []
        for choice in raw.get("choices", []) or []:
            if not isinstance(choice, dict):
                continue
            choices.append(
                Choice(
                    code=str(pick(choice, "code", default="")),
                    name=str(pick(choice, "name", default="")),
                    selected=bool(pick(choice, "isDefault", default=0)),
                    quantity=int(pick(choice, "quantity", default=0) or 0),
                    diff_price=parse_diff_price(pick(choice, "diffPrice", default="")),
                    support_modify=bool(pick(choice, "supportModify", default=False)),
                )
            )
        if choices:
            rounds.append(
                Round(
                    name=str(pick(raw, "name", default="")),
                    quantity=int(pick(raw, "quantity", default=1) or 1),
                    min_quantity=int(pick(raw, "minQuantity", default=1) or 1),
                    max_quantity=int(pick(raw, "maxQuantity", default=1) or 1),
                    choices=choices,
                )
            )
    return rounds


def default_composition(detail: dict) -> list[dict]:
    """取套餐当前默认组成（每个 round 中 isDefault 的项）。"""
    composition: list[dict] = []
    for round_ in extract_rounds(detail):
        choice = round_.default_choice
        if choice is None:
            continue
        composition.append(
            {
                "name": choice.name,
                "code": choice.code,
                "group": round_.name,
                "quantity": choice.quantity or round_.quantity,
                "diff_price": choice.diff_price,
            }
        )
    if not composition and detail.get("name"):
        composition.append(
            {
                "name": str(detail["name"]),
                "code": str(detail.get("code", "")),
                "group": "单品",
                "quantity": 1,
                "diff_price": 0.0,
            }
        )
    return composition
