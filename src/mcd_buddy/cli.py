"""麦门四重奏 McQuartet 命令行入口。

用法示例::

    # 离线演示（无需 Token）
    python -m mcd_buddy.cli practice --demo
    python -m mcd_buddy.cli group-meal --demo
    python -m mcd_buddy.cli hidden-menu --meal 双人分享餐 --preset 减脂 --demo
    python -m mcd_buddy.cli fortune --demo

    # 真实调用（需先申请 MCP Token）
    export MCD_MCP_TOKEN=your_token
    python -m mcd_buddy.cli hidden-menu --city 深圳市 --keyword 麦当劳 --meal 双人分享餐 --preset 增肌
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from .demo import DemoMCDClient
from .mcd_api import (
    BE_DINE_IN,
    BE_TYPE_LABELS,
    ORDER_PICKUP,
    MCDApiError,
    resolve_store,
)
from .mcp_client import MCDClient, MCDError
from .modules import FortuneModule, GroupMealModule, HiddenMenuModule, PracticeModule
from .modules.group_meal import Person
from .modules.hidden_menu import menu_table

DEFAULT_CITY = os.environ.get("MCD_CITY", "深圳市")
DEFAULT_KEYWORD = os.environ.get("MCD_KEYWORD", "麦当劳")


class RecordingClient:
    """代理客户端，记录每次工具调用的原始返回，供 ``--json`` 输出。"""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.records: dict[str, Any] = {}

    async def call(self, tool: str, arguments: dict | None = None) -> Any:
        data = await self._inner.call(tool, arguments)
        self.records.setdefault(tool, data)
        return data

    async def list_tools(self) -> list[str]:
        return await self._inner.list_tools()

    async def aclose(self) -> None:
        return await self._inner.aclose()


DEMO_PEOPLE = [
    {"name": "小王", "budget": 25, "want": "牛肉", "avoid": []},
    {"name": "小李", "budget": 20, "want": "鸡肉", "avoid": ["辣"]},
    {"name": "小张", "budget": 15, "want": "鱼", "avoid": []},
    {"name": "小赵", "budget": 30, "want": "汉堡", "avoid": ["油炸"]},
    {"name": "小陈", "budget": 22, "want": "素食", "avoid": []},
    {"name": "小周", "budget": 18, "want": "咖啡", "avoid": []},
]


def _add_common(parser: argparse.ArgumentParser) -> None:
    """给子命令挂上通用参数（用 SUPPRESS 保证不覆盖主命令的同名值）。"""
    parser.add_argument("--token", default=argparse.SUPPRESS, help="麦当劳 MCP Token")
    parser.add_argument("--demo", action="store_true", default=argparse.SUPPRESS, help="离线演示模式")
    parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="输出 JSON")


def _add_store(parser: argparse.ArgumentParser) -> None:
    """给需要门店的子命令挂上门店定位参数。"""
    parser.add_argument("--city", default=argparse.SUPPRESS, help=f"城市名（默认 {DEFAULT_CITY}）")
    parser.add_argument(
        "--keyword", default=argparse.SUPPRESS, help=f"门店关键词（默认 {DEFAULT_KEYWORD}）"
    )
    parser.add_argument("--store", default=argparse.SUPPRESS, help="直接指定门店编码，跳过搜索")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcd-buddy",
        description="🍟 麦门四重奏 McQuartet —— 基于麦当劳中国 MCP 的多玩法助手",
    )
    parser.add_argument("--token", help="麦当劳 MCP Token（也可用环境变量 MCD_MCP_TOKEN）")
    parser.add_argument("--demo", action="store_true", help="离线演示模式，无需 Token")
    parser.add_argument("--json", action="store_true", help="输出 JSON（含原始工具返回 + markdown）")
    parser.add_argument("--city", default=DEFAULT_CITY, help=f"城市名（默认 {DEFAULT_CITY}）")
    parser.add_argument("--keyword", default=DEFAULT_KEYWORD, help=f"门店关键词（默认 {DEFAULT_KEYWORD}）")
    parser.add_argument("--store", help="直接指定门店编码，跳过搜索")

    common = argparse.ArgumentParser(add_help=False)
    _add_common(common)
    _add_store(common)

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("practice", parents=[common], help="🧘 修行录：点餐成就与段位")

    gm = sub.add_parser("group-meal", parents=[common], help="🍱 团餐指挥官：多人点单凑单")
    gm.add_argument(
        "--people",
        help='伙伴需求。简写："阿May:25:不要辣;老王:40:要咖啡"；也支持内联 JSON 或 @文件路径',
    )

    hm = sub.add_parser("hidden-menu", parents=[common], help="🧪 隐藏菜单实验室：重组套餐配方")
    hm.add_argument("--meal", default="双人分享餐", help="套餐编码或名称关键词")
    hm.add_argument("--preset", choices=["减脂", "增肌", "解馋", "清醒"], help="一键配方")
    hm.add_argument("--swap", action="append", default=[], help="自定义替换，格式 轮次=商品，可多次")
    hm.add_argument("--list", action="store_true", help="只列出当前门店菜单")

    sub.add_parser("fortune", parents=[common], help="🔮 每日运势签")
    sub.add_parser("tools", parents=[common], help="列出 MCP Server 提供的工具")
    return parser


async def dispatch(client, args: argparse.Namespace) -> str:
    if args.command == "practice":
        return await PracticeModule().run(client)

    if args.command == "fortune":
        return await FortuneModule().run(client)

    if args.command == "tools":
        tools = await client.list_tools()
        return "可用工具：\n" + "\n".join(f"- `{t}`" for t in tools)

    if args.command == "group-meal":
        # 先解析伙伴需求：参数写错就地报错，不必先跑一趟网络
        people = _load_people(args.people)
        store = await _store(client, args)
        return await GroupMealModule().run(
            client, people, store, ORDER_PICKUP, BE_DINE_IN, ""
        )

    if args.command == "hidden-menu":
        store = await _store(client, args)
        if getattr(args, "list", False):
            from .mcd_api import fetch_menu

            menu = await fetch_menu(client, store.store_code, ORDER_PICKUP, BE_DINE_IN, "")
            header = f"🍟 {store.name}　{store.status_text}　{store.hours_text}\n"
            return header + menu_table(menu)
        swaps = {}
        for pair in args.swap:
            if "=" in pair:
                key, value = pair.split("=", 1)
                swaps[key.strip()] = value.strip()
        return await HiddenMenuModule().run(
            client,
            store.store_code,
            args.meal,
            args.preset,
            swaps,
            ORDER_PICKUP,
            BE_DINE_IN,
            "",
        )

    raise MCDError(f"未知命令：{args.command}")


async def _store(client, args: argparse.Namespace):
    """解析门店；失败时给出可操作的提示。"""
    store = await resolve_store(
        client,
        city=getattr(args, "city", DEFAULT_CITY),
        keyword=getattr(args, "keyword", DEFAULT_KEYWORD),
        be_type=BE_DINE_IN,
        search_type=2,
        store_code=getattr(args, "store", "") or "",
    )
    if store is None:
        raise MCDApiError(
            f"在「{getattr(args, 'city', DEFAULT_CITY)}」没有搜到「"
            f"{getattr(args, 'keyword', DEFAULT_KEYWORD)}」相关门店。\n"
            "试试用 --city 换城市，或用 --keyword 换关键词。"
        )
    return store


_PEOPLE_USAGE = (
    "用法：--people \"阿May:25:不要辣; 老王:40:要咖啡; 小林:30\"\n"
    "  每个人用 ; 分隔，字段用 : 分隔；字段可以是\n"
    "    名字（任意中文/英文）\n"
    "    预算（纯数字，或写 预算25 / ¥25）\n"
    "    忌口（以 不要/忌/别/免/无 开头，多个用 、 连接）\n"
    "    偏好（以 要/想吃/来/喜欢 开头）\n"
    "  也支持 JSON 或 @文件名。"
)

_BUDGET_RE = re.compile(r"^\d+(?:\.\d+)?$")
_AVOID_PREFIX = r"^(?:不要|不吃|忌口|忌|别要|别|免|无|少)"
_WANT_PREFIX = r"^(?:要|想吃|想|来|喜欢|多加)"
_FIELD_KEYS = {
    "name": "name",
    "名字": "name",
    "budget": "budget",
    "预算": "budget",
    "want": "want",
    "要": "want",
    "avoid": "avoid",
    "忌口": "avoid",
    "不要": "avoid",
}


def _split_person_fields(segment: str) -> list[str]:
    """把一个「人」拆成字段：按冒号，退化为按分号，再退化为按空白。"""
    parts = [p.strip() for p in re.split(r"[:：]", segment) if p.strip()]
    if len(parts) > 1:
        return parts
    # name=小B;budget=35 这种键值写法用分号分隔字段
    parts = [p.strip() for p in re.split(r"[;；]", segment) if p.strip()]
    if len(parts) > 1:
        return parts
    return [p for p in re.split(r"\s+", segment.strip()) if p]


def _split_multi(value: str) -> list[str]:
    """把一个字段里的多个标签拆开（不要辣、不要香菜）。"""
    return [v.strip() for v in re.split(r"[、,，/+＋]|\s+", value) if v.strip()]


def _strip_money(text: str) -> str:
    """去掉预算字段里的修饰，只留数字。"""
    return (
        text.replace("预算", "")
        .replace("¥", "")
        .replace("￥", "")
        .replace("元", "")
        .strip()
    )


def _looks_like_person(segment: str) -> bool:
    """首字段是名字（而不是预算/忌口/偏好）才认为这是一位伙伴。

    用来决定逗号到底是在「分隔两个人」还是在「列举一个人的多个要求」。
    """
    fields = _split_person_fields(segment)
    if not fields:
        return False
    first = fields[0]
    if _BUDGET_RE.match(_strip_money(first)):
        return False
    return not (re.match(_AVOID_PREFIX, first) or re.match(_WANT_PREFIX, first))


def _parse_person(segment: str) -> Person:
    """把 ``阿May:25:不要辣`` 这类片段解析成 Person。

    规则：认得出的一律归类；认不出的第一个当名字，其余的并入忌口 ——
    这样「名字 + 一串要求」这种最自然的写法永远能跑通。
    """
    fields = _split_person_fields(segment)
    if not fields:
        raise MCDApiError(f"有一个人是空的，没写任何内容。\n{_PEOPLE_USAGE}")

    name = ""
    budget: float | None = None
    want = ""
    avoid: list[str] = []

    for field in fields:
        key = None
        value = field
        if "=" in field:
            head, tail = field.split("=", 1)
            head = head.strip()
            key = _FIELD_KEYS.get(head.lower()) or _FIELD_KEYS.get(head)
            if key:
                value = tail.strip()

        if key is None:
            money = _strip_money(field)
            if _BUDGET_RE.match(money):
                budget = float(money)
            elif re.match(_AVOID_PREFIX, field):
                rest = re.sub(_AVOID_PREFIX, "", field).strip() or field
                avoid.extend(_clean_avoid(rest))
            elif re.match(_WANT_PREFIX, field):
                want = re.sub(_WANT_PREFIX, "", field).strip() or field
            elif not name:
                name = field
            else:
                avoid.extend(_split_multi(field))
            continue

        if key == "name":
            name = value
        elif key == "budget":
            money = _strip_money(value)
            if not _BUDGET_RE.match(money):
                raise MCDApiError(
                    f"预算「{value}」不是数字。\n{_PEOPLE_USAGE}"
                )
            budget = float(money)
        elif key == "want":
            want = value
        else:  # avoid
            avoid.extend(_clean_avoid(value))

    if not name:
        raise MCDApiError(
            f"「{segment}」里没解析出名字，第一位应该是名字。\n{_PEOPLE_USAGE}"
        )
    return Person(name=name, budget=budget, want=want, avoid=avoid)


def _clean_avoid(value: str) -> list[str]:
    """拆开忌口标签，并把每个标签上残留的「不要」前缀去掉。"""
    tokens = _split_multi(value) or [value]
    cleaned = [re.sub(_AVOID_PREFIX, "", token).strip() or token for token in tokens]
    return [token for token in cleaned if token]


def _load_people(raw: str | None) -> list[Person]:
    """解析伙伴需求：支持友好简写、JSON、@文件三种写法。"""
    if not raw:
        return [Person.from_dict(item) for item in DEMO_PEOPLE]

    try:
        text = Path(raw[1:]).read_text(encoding="utf-8") if raw.startswith("@") else raw
    except OSError as exc:
        raise MCDApiError(f"读不到文件 {raw[1:]}：{exc}") from exc

    stripped = text.strip()
    if not stripped:
        raise MCDApiError(f"伙伴需求是空的。\n{_PEOPLE_USAGE}")

    # JSON 分支
    if stripped[0] in "[{":
        try:
            data = json.loads(stripped)
        except ValueError as exc:
            raise MCDApiError(
                f"这看起来是 JSON，但解析失败：{exc}\n{_PEOPLE_USAGE}"
            ) from exc
        if isinstance(data, dict):
            data = data.get("people", [])
        if not isinstance(data, list) or not data:
            raise MCDApiError(f"JSON 里没有解析出伙伴列表。\n{_PEOPLE_USAGE}")
        return [Person.from_dict(item) for item in data]

    # 键值写法（name=小B;budget=35）：整串是「一个人」，不能按分隔符切人
    if re.search(r"(?:^|[;；,，:\s])(?:name|名字)\s*=", stripped):
        return [_parse_person(stripped)]

    # 友好简写分支：; ； 换行 优先，其次 , ，
    segments = [s for s in re.split(r"[;；\n]+", stripped) if s.strip()]
    if len(segments) == 1 and re.search(r"[,，]", stripped):
        # 逗号既可能是「分隔人」，也可能是「列举一个人的多个要求」，
        # 只有当每一段都像一个人（首字段是名字）时才按逗号拆。
        comma_parts = [s for s in re.split(r"[,，]+", stripped) if s.strip()]
        if all(_looks_like_person(part) for part in comma_parts):
            segments = comma_parts
    if not segments:
        raise MCDApiError(f"没解析出任何伙伴。\n{_PEOPLE_USAGE}")
    return [_parse_person(segment) for segment in segments]


async def run(args: argparse.Namespace) -> str:
    """执行命令；``--json`` 时输出含原始工具返回的 JSON。"""
    if args.demo:
        client: Any = DemoMCDClient()
        recorder = RecordingClient(client)
        try:
            output = await dispatch(recorder, args)
        finally:
            await client.aclose()
    else:
        async with MCDClient(token=args.token) as client:
            recorder = RecordingClient(client)
            output = await dispatch(recorder, args)

    if getattr(args, "json", False):
        return json.dumps(
            {
                "command": args.command,
                "demo": bool(args.demo),
                "beType": BE_DINE_IN,
                "beTypeLabel": BE_TYPE_LABELS[BE_DINE_IN],
                "tools": recorder.records,
                "markdown": output,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    return output


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        output = asyncio.run(run(args))
    except (MCDError, MCDApiError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n已取消", file=sys.stderr)
        return 130
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
