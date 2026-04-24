"""Tests for PortfolioChat (v0 internal interface).

The chat is the Pro+ in-app conversational surface. We test the
control flow without spending real LLM tokens by injecting a
deterministic StubLLMProvider.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from app.services.agent.portfolio_chat import (
    BUILT_IN_TOOLS,
    ChatLimits,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    LLMChatResult,
    LLMProvider,
    PortfolioChat,
    StubLLMProvider,
    ToolSpec,
    default_tools,
)


# ---------------------------------------------------------------------------
# Tool helpers used by tests
# ---------------------------------------------------------------------------


def _user_only_tool(call_log: List[Dict[str, Any]]) -> ToolSpec:
    """A test tool that records the (user_id, args) it was called with."""

    def fn(db, user_id, args):
        call_log.append({"user_id": user_id, "args": args})
        return {
            "summary": f"called with user_id={user_id} keys={sorted(args)}",
            "sources": [{"kind": "test", "user_id": user_id}],
        }

    return ToolSpec(
        name="user_echo",
        description="Echo back the calling user_id and arguments.",
        parameters_schema={"type": "object", "properties": {}, "required": []},
        fn=fn,
    )


def _raising_tool() -> ToolSpec:
    def fn(db, user_id, args):
        raise RuntimeError("intentional tool failure")

    return ToolSpec(
        name="boom",
        description="Always raises.",
        parameters_schema={"type": "object", "properties": {}, "required": []},
        fn=fn,
    )


# ---------------------------------------------------------------------------
# Basic dispatch
# ---------------------------------------------------------------------------


class TestDispatch:
    def test_no_tool_calls_returns_immediate_answer(self, db_session):
        provider = StubLLMProvider(
            [LLMChatResult(content="Stage 2A in 6 of your holdings.", tokens_in=12, tokens_out=8)]
        )
        chat = PortfolioChat(provider=provider, tools=BUILT_IN_TOOLS)
        resp = chat.ask(
            db_session,
            ChatRequest(user_id=1, message="What's up with my portfolio?"),
        )
        assert isinstance(resp, ChatResponse)
        assert resp.answer.startswith("Stage 2A")
        assert resp.tool_trace == ()
        assert resp.tokens_in == 12
        assert resp.tokens_out == 8
        assert resp.error is None
        assert resp.truncated is False

    def test_tool_call_then_final_answer(self, db_session):
        log: List[Dict[str, Any]] = []
        echo = _user_only_tool(log)
        provider = StubLLMProvider(
            [
                LLMChatResult(
                    content="thinking",
                    tool_calls=(
                        {"id": "call_1", "name": "user_echo", "arguments": {"foo": "bar"}},
                    ),
                    tokens_in=20,
                    tokens_out=4,
                ),
                LLMChatResult(
                    content="Done. You hold 5 names.",
                    tokens_in=18,
                    tokens_out=10,
                ),
            ]
        )
        chat = PortfolioChat(provider=provider, tools=[echo])
        resp = chat.ask(db_session, ChatRequest(user_id=42, message="hi"))

        assert resp.answer == "Done. You hold 5 names."
        assert len(resp.tool_trace) == 1
        trace = resp.tool_trace[0]
        assert trace.name == "user_echo"
        assert trace.arguments == {"foo": "bar"}
        assert trace.error is None
        assert "user_id=42" in trace.result_summary

        assert log == [{"user_id": 42, "args": {"foo": "bar"}}]
        assert resp.sources and resp.sources[0]["user_id"] == 42
        assert resp.tokens_in == 38
        assert resp.tokens_out == 14

    def test_unknown_tool_returns_error_trace_not_exception(self, db_session):
        provider = StubLLMProvider(
            [
                LLMChatResult(
                    content="",
                    tool_calls=(
                        {"id": "x", "name": "does_not_exist", "arguments": {}},
                    ),
                ),
                LLMChatResult(content="Sorry, I could not find that data."),
            ]
        )
        chat = PortfolioChat(provider=provider, tools=BUILT_IN_TOOLS)
        resp = chat.ask(db_session, ChatRequest(user_id=1, message="x"))

        assert len(resp.tool_trace) == 1
        assert resp.tool_trace[0].error is not None
        assert "unknown tool" in resp.tool_trace[0].error
        assert resp.answer.startswith("Sorry")

    def test_tool_exception_isolated(self, db_session):
        provider = StubLLMProvider(
            [
                LLMChatResult(
                    content="",
                    tool_calls=(
                        {"id": "boom_1", "name": "boom", "arguments": {}},
                    ),
                ),
                LLMChatResult(content="Recovered."),
            ]
        )
        chat = PortfolioChat(provider=provider, tools=[_raising_tool()])
        resp = chat.ask(db_session, ChatRequest(user_id=1, message="x"))
        assert resp.tool_trace[0].error == "intentional tool failure"
        assert resp.answer == "Recovered."


# ---------------------------------------------------------------------------
# Limits and safety
# ---------------------------------------------------------------------------


class TestLimits:
    def test_too_many_tool_calls_truncates(self, db_session):
        log: List[Dict[str, Any]] = []
        echo = _user_only_tool(log)
        # Provider always asks for another tool call.
        provider = StubLLMProvider(
            [
                LLMChatResult(
                    content="",
                    tool_calls=(
                        {"id": f"call_{i}", "name": "user_echo", "arguments": {}},
                    ),
                )
                for i in range(10)
            ]
        )
        chat = PortfolioChat(
            provider=provider,
            tools=[echo],
            limits=ChatLimits(max_tool_calls=2, max_tokens_per_request=1000),
        )
        resp = chat.ask(db_session, ChatRequest(user_id=1, message="loop"))
        assert resp.truncated is True
        assert resp.error == "tool_call_limit_or_timeout"
        assert len(resp.tool_trace) == 2  # Hit the cap

    def test_invalid_provider_raises_at_construction(self):
        class NotAProvider:
            pass

        with pytest.raises(TypeError, match="LLMProvider"):
            PortfolioChat(provider=NotAProvider(), tools=BUILT_IN_TOOLS)


# ---------------------------------------------------------------------------
# Conversation history is preserved
# ---------------------------------------------------------------------------


class TestHistory:
    def test_history_is_replayed_to_provider(self, db_session):
        provider = StubLLMProvider([LLMChatResult(content="ok")])
        chat = PortfolioChat(provider=provider, tools=BUILT_IN_TOOLS)
        request = ChatRequest(
            user_id=1,
            message="latest",
            history=(
                ChatMessage(role="user", content="hello"),
                ChatMessage(role="assistant", content="hi back"),
            ),
        )
        chat.ask(db_session, request)
        sent = provider.call_log[0]["messages"]
        roles_contents = [(m["role"], m["content"]) for m in sent]
        assert ("user", "hello") in roles_contents
        assert ("assistant", "hi back") in roles_contents
        assert ("user", "latest") in roles_contents


# ---------------------------------------------------------------------------
# Tool registry sanity
# ---------------------------------------------------------------------------


class TestToolRegistry:
    def test_default_tools_are_well_formed(self):
        for spec in default_tools():
            schema = spec.openai_function_schema()
            assert schema["type"] == "function"
            fn_block = schema["function"]
            assert fn_block["name"] == spec.name
            assert "description" in fn_block
            assert fn_block["parameters"]["type"] == "object"

    def test_tool_names_are_unique(self):
        names = [t.name for t in default_tools()]
        assert len(names) == len(set(names))

    def test_now_utc_returns_iso_string(self, db_session):
        spec = next(t for t in default_tools() if t.name == "now_utc")
        out = spec.fn(db_session, user_id=1, arguments={})
        assert isinstance(out["summary"], str)
        # Loose ISO check: should parse with datetime
        from datetime import datetime as _dt

        _dt.fromisoformat(out["summary"])

    def test_summarize_portfolio_carries_user_id_in_sources(self, db_session):
        spec = next(t for t in default_tools() if t.name == "summarize_portfolio")
        out = spec.fn(db_session, user_id=99, arguments={})
        assert out["sources"][0]["user_id"] == 99


# ---------------------------------------------------------------------------
# Multi-tenant safety
# ---------------------------------------------------------------------------


class TestMultiTenancy:
    def test_user_id_is_threaded_through_to_each_tool_call(self, db_session):
        log: List[Dict[str, Any]] = []
        echo = _user_only_tool(log)
        provider = StubLLMProvider(
            [
                LLMChatResult(
                    content="",
                    tool_calls=(
                        {"id": "a", "name": "user_echo", "arguments": {}},
                        {"id": "b", "name": "user_echo", "arguments": {"k": 1}},
                    ),
                ),
                LLMChatResult(content="done"),
            ]
        )
        chat = PortfolioChat(provider=provider, tools=[echo])
        chat.ask(db_session, ChatRequest(user_id=7, message="x"))
        assert [c["user_id"] for c in log] == [7, 7]

    def test_isolation_between_two_users_with_separate_chats(self, db_session):
        log: List[Dict[str, Any]] = []
        echo = _user_only_tool(log)
        provider1 = StubLLMProvider(
            [
                LLMChatResult(
                    content="",
                    tool_calls=({"id": "a", "name": "user_echo", "arguments": {}},),
                ),
                LLMChatResult(content="user1"),
            ]
        )
        provider2 = StubLLMProvider(
            [
                LLMChatResult(
                    content="",
                    tool_calls=({"id": "b", "name": "user_echo", "arguments": {}},),
                ),
                LLMChatResult(content="user2"),
            ]
        )
        c1 = PortfolioChat(provider=provider1, tools=[echo])
        c2 = PortfolioChat(provider=provider2, tools=[echo])
        c1.ask(db_session, ChatRequest(user_id=1, message="x"))
        c2.ask(db_session, ChatRequest(user_id=2, message="y"))
        assert sorted(c["user_id"] for c in log) == [1, 2]


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocol:
    def test_stub_satisfies_runtime_protocol(self):
        provider = StubLLMProvider([LLMChatResult(content="ok")])
        assert isinstance(provider, LLMProvider)
