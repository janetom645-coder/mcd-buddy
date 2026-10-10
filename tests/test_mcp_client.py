"""传输层（mcp_client）单元测试。

这里只覆盖一件事：**什么该重试、什么不该重试**。

背景：线上真实出现过一次 ``Server returned an error response``，
当时客户端只对 429 重试，于是整个模块直接失败。这类瞬时故障如果不重试，
用户看到的就是「莫名其妙报错」，属于体验硬伤。
"""

import asyncio

import pytest

from mcd_buddy import mcp_client
from mcd_buddy.mcp_client import MAX_RETRY, MCDClient, MCDError


def run(coro):
    return asyncio.run(coro)


class _FakeResult:
    """模拟 CallToolResult。"""

    def __init__(self, payload=None, is_error=False):
        self.structured_content = payload or {}
        self.is_error = is_error
        self.content = []


class _FakeSession:
    """按预设顺序逐个吐出结果/异常，用来观察重试次数。"""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    async def call_tool(self, tool, arguments):
        self.calls += 1
        if not self.outcomes:
            raise AssertionError("调用次数超出预期，说明重试没有收敛")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def no_sleep(monkeypatch):
    """把退避等待记录下来，避免测试真的睡 0.8 + 1.6 秒。"""
    slept: list[float] = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(mcp_client.asyncio, "sleep", fake_sleep)
    return slept


def make_client(outcomes) -> tuple[MCDClient, _FakeSession]:
    client = MCDClient(token="fake-token-for-test")
    session = _FakeSession(outcomes)
    client._session = session
    return client, session


class TestRetryableFailures:
    def test_transient_server_error_then_success(self, no_sleep):
        """线上真实场景：第一次网关抖动，第二次成功。"""
        client, session = make_client(
            [
                RuntimeError("Server returned an error response"),
                _FakeResult({"success": True, "data": {"ok": 1}}),
            ]
        )
        assert run(client.call("query-meals", {"storeCode": "x"})) == {
            "success": True,
            "data": {"ok": 1},
        }
        assert session.calls == 2
        assert no_sleep == [0.8]

    def test_backoff_is_exponential(self, no_sleep):
        """连续抖动时，等待时间应为 0.8 → 1.6 指数退避。"""
        client, session = make_client(
            [
                RuntimeError("429 Too Many Requests"),
                RuntimeError("503 Service Unavailable"),
                _FakeResult({"success": True, "data": {}}),
            ]
        )
        run(client.call("query-meals", {}))
        assert session.calls == 3
        assert no_sleep == [0.8, 1.6]

    def test_gives_up_after_max_retry(self, no_sleep):
        """重试耗尽后必须抛出可读异常，而不是把底层异常直接漏给用户。"""
        client, session = make_client([RuntimeError("502 Bad Gateway")] * MAX_RETRY)
        with pytest.raises(MCDError) as exc:
            run(client.call("query-meals", {}))
        assert session.calls == MAX_RETRY
        assert f"已重试 {MAX_RETRY} 次" in str(exc.value)
        assert len(no_sleep) == MAX_RETRY - 1

    def test_timeout_is_retried(self, no_sleep):
        client, _ = make_client(
            [asyncio.TimeoutError("timed out"), _FakeResult({"success": True, "data": {}})]
        )
        run(client.call("now-time-info", {}))
        assert no_sleep == [0.8]


class TestNonRetryableFailures:
    def test_401_is_not_retried(self, no_sleep):
        """Token 失效重试多少次都没用，必须立刻告诉用户去换 Token。"""
        client, session = make_client([RuntimeError("401 Unauthorized")])
        with pytest.raises(MCDError) as exc:
            run(client.call("query-meals", {}))
        assert session.calls == 1
        assert no_sleep == []
        assert "Token 无效或已过期" in str(exc.value)
        assert "open.mcd.cn/mcp" in str(exc.value)

    def test_unauthorized_word_also_detected(self, no_sleep):
        client, session = make_client([RuntimeError("Unauthorized")])
        with pytest.raises(MCDError):
            run(client.call("query-meals", {}))
        assert session.calls == 1

    def test_unknown_error_is_not_retried(self, no_sleep):
        """无法归类的错误不该盲目重试，直接暴露原因更利于排查。"""
        client, session = make_client([ValueError("unexpected payload shape")])
        with pytest.raises(MCDError) as exc:
            run(client.call("query-meals", {}))
        assert session.calls == 1
        assert no_sleep == []
        assert "unexpected payload shape" in str(exc.value)

    def test_business_error_is_not_retried(self, no_sleep):
        """工具自己返回的 is_error 属于业务错误（如门店打烊），重试无意义。"""
        client, session = make_client([_FakeResult(is_error=True)])
        with pytest.raises(MCDError):
            run(client.call("query-meals", {}))
        assert session.calls == 1
        assert no_sleep == []


class TestUninitialised:
    def test_call_before_enter_raises(self):
        client = MCDClient(token="fake-token-for-test")
        with pytest.raises(MCDError) as exc:
            run(client.call("query-meals", {}))
        assert "未初始化" in str(exc.value)

    def test_missing_token_raises(self, monkeypatch):
        monkeypatch.delenv("MCD_MCP_TOKEN", raising=False)
        with pytest.raises(MCDError) as exc:
            MCDClient()
        assert "MCD_MCP_TOKEN" in str(exc.value)
