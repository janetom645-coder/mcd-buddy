"""麦当劳中国 MCP 客户端封装。

基于官方 ``mcp`` SDK 的 Streamable HTTP 传输，接入 ``https://mcp.mcd.cn`` 。
鉴权方式：请求头 ``Authorization: Bearer <MCP_TOKEN>`` 。

错误码约定（来自官方文档）：
  - 401  Token 无效、已过期或未提供
  - 429  触发限流（每个 Token 每分钟最多 600 次请求）
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import AsyncExitStack
from typing import Any, Protocol, runtime_checkable

from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

DEFAULT_MCP_URL = os.environ.get("MCD_MCP_URL", "https://mcp.mcd.cn")
MAX_RETRY = 3

# 可重试的瞬时故障特征：限流、网关抖动、超时、连接中断
_RETRYABLE_HINTS = (
    "429",
    "rate limit",
    "too many requests",
    "server returned an error response",
    "502",
    "503",
    "504",
    "bad gateway",
    "service unavailable",
    "gateway timeout",
    "timeout",
    "timed out",
    "connection reset",
    "connection aborted",
    "temporarily",
)


class MCDError(RuntimeError):
    """麦当劳 MCP 调用异常。"""


@runtime_checkable
class MCDClientProtocol(Protocol):
    """客户端接口，真实客户端与演示客户端都实现它。"""

    async def call(self, tool: str, arguments: dict | None = None) -> Any: ...

    async def list_tools(self) -> list[str]: ...

    async def aclose(self) -> None: ...


def _error_text(result: Any) -> str:
    parts = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts) or "工具返回错误"


def _field(obj: Any, *names: str, default: Any = None) -> Any:
    """按候选属性名取值（兼容 pydantic 的 snake_case / camelCase 两种写法）。"""
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return default


def extract_result(result: Any) -> Any:
    """把 CallToolResult 规整成 Python 对象。"""
    structured = _field(result, "structured_content", "structuredContent")
    if structured:
        return structured
    texts = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            texts.append(text)
    if not texts:
        return {}
    joined = "\n".join(texts)
    try:
        return json.loads(joined)
    except (ValueError, TypeError):
        return {"text": joined}


class MCDClient:
    """真实的麦当劳 MCP 客户端（Streamable HTTP）。

    用法::

        async with MCDClient() as client:
            data = await client.call("query-meals", {"storeCode": "..."})
    """

    def __init__(self, token: str | None = None, url: str | None = None):
        self.token = token or os.environ.get("MCD_MCP_TOKEN", "")
        self.url = url or DEFAULT_MCP_URL
        if not self.token:
            raise MCDError(
                "未找到 MCP Token。请设置环境变量 MCD_MCP_TOKEN，"
                "或前往 https://open.mcd.cn/mcp 申请后传入。"
            )
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> MCDClient:
        self._stack = AsyncExitStack()
        http_client = create_mcp_http_client(
            headers={"Authorization": f"Bearer {self.token}"}
        )
        await self._stack.enter_async_context(http_client)
        streams = await self._stack.enter_async_context(
            streamable_http_client(self.url, http_client=http_client)
        )
        # mcp 2.x 返回 (read, write)；旧版返回 (read, write, get_session_id)
        read, write = streams[0], streams[1]
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
            self._session = None

    async def list_tools(self) -> list[str]:
        if self._session is None:
            raise MCDError("客户端未初始化，请使用 `async with MCDClient() as c:`")
        result = await self._session.list_tools()
        return [tool.name for tool in result.tools]

    async def call(self, tool: str, arguments: dict | None = None) -> Any:
        if self._session is None:
            raise MCDError("客户端未初始化，请使用 `async with MCDClient() as c:`")
        arguments = arguments or {}
        last_error: Exception | None = None
        for attempt in range(MAX_RETRY):
            try:
                result = await self._session.call_tool(tool, arguments)
                if _field(result, "is_error", "isError", default=False):
                    raise MCDError(f"{tool}: {_error_text(result)}")
                return extract_result(result)
            except MCDError:
                raise
            except Exception as exc:  # noqa: BLE001 - SDK 抛出的异常类型不稳定
                message = str(exc)
                lowered = message.lower()
                if "401" in message or "unauthorized" in lowered:
                    raise MCDError(
                        "MCP Token 无效或已过期（401）。"
                        "请前往 https://open.mcd.cn/mcp 重新申请。"
                    ) from exc
                # 限流 / 网关抖动 / 超时等瞬时故障：退避重试
                if any(hint in lowered for hint in _RETRYABLE_HINTS):
                    last_error = exc
                    if attempt < MAX_RETRY - 1:
                        await asyncio.sleep(0.8 * (2**attempt))
                        continue
                    break
                raise MCDError(f"调用工具 {tool} 失败：{exc}") from exc
        raise MCDError(
            f"调用工具 {tool} 失败（已重试 {MAX_RETRY} 次）：{last_error}"
        )


async def call_with_fallback(
    client: MCDClientProtocol,
    tool: str,
    candidates: list[dict] | None = None,
) -> Any:
    """按候选参数依次尝试调用，兼容不同版本工具的参数命名差异。"""
    candidates = candidates or [{}]
    last_error: Exception | None = None
    for args in candidates:
        try:
            return await client.call(tool, args)
        except MCDError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return {}
