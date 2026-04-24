"""User-facing portfolio chat (PortfolioChat).

This is the **Pro+** in-app conversational interface. It is intentionally
distinct from :class:`app.services.agent.brain.AgentBrain`, which is
the auto-ops brain. They share the LLM substrate but answer different
questions:

* ``AgentBrain`` (ops): "the dashboard is red — what should I do?"
* ``PortfolioChat`` (user): "what stocks in my Stage 2 watchlist have
  insider buying this week?"

Design constraints
------------------

1. **Read-only.** Every tool the chat can call must be safe in the
   absence of human review. Order routing, exit cascades, position
   resizing — all forbidden. The tool registry on this class enumerates
   the *only* operations the chat can perform. Adding a new one is an
   intentional act, not an emergent property of "having LLM access".
2. **User-scoped.** Every tool call carries the caller's ``user_id``.
   No tool may read another user's data. Multi-tenancy is enforced at
   the tool layer, not the LLM layer.
3. **Deterministic surface.** The LLM is non-deterministic; the *API*
   the LLM exposes to the user must not be. We return strict
   ``ChatResponse`` rows with explicit ``sources`` so the frontend can
   render verifiable citations.
4. **Bounded cost.** Each request has hard caps on token spend, tool
   call count, and wall time, so a runaway model cannot eat the
   monthly budget on one user.
5. **Pluggable LLM provider.** Tests use the in-memory
   :class:`StubLLMProvider`; production binds the OpenAI provider once
   the route lands. This PR ships v0 with the protocol + stub and
   leaves the OpenAI binding for the route PR (it depends on PR A's
   ``require_feature("brain.native_chat")`` dependency).

PR F scope
----------
This PR ships only the service layer + tests. The HTTP route lands in a
follow-up PR once PR #326 (entitlements) merges so we can gate it with
``Depends(require_feature("brain.native_chat"))``.

medallion: ops
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import (
    Any,
    Protocol,
    runtime_checkable,
)

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str
    tool_call_id: str | None = None
    tool_name: str | None = None


@dataclass(frozen=True)
class ChatRequest:
    user_id: int
    message: str
    history: tuple[ChatMessage, ...] = ()
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


@dataclass(frozen=True)
class ToolTrace:
    """One tool call recorded for transparency in the response."""

    name: str
    arguments: dict[str, Any]
    result_summary: str
    elapsed_ms: int
    error: str | None = None


@dataclass(frozen=True)
class ChatResponse:
    request_id: str
    answer: str
    tool_trace: tuple[ToolTrace, ...] = ()
    sources: tuple[dict[str, Any], ...] = ()
    tokens_in: int = 0
    tokens_out: int = 0
    elapsed_ms: int = 0
    truncated: bool = False
    error: str | None = None


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------


ToolFn = Callable[[Session, int, dict[str, Any]], dict[str, Any]]
"""Tool signature: ``(db, user_id, arguments) -> result``.

The result dict is JSON-serialisable. Tools must:

* Accept and respect ``user_id`` for multi-tenant scoping.
* Never write. Reading allowed; mutating forbidden.
* Raise on bad input; the dispatcher catches and logs.
* Return a dict with at minimum ``{"summary": str, "sources": [...]}``
  so the response body has citations to render.
"""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    fn: ToolFn

    def openai_function_schema(self) -> dict[str, Any]:
        """OpenAI ``function`` tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }


# ---------------------------------------------------------------------------
# LLM provider protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMProvider(Protocol):
    """Minimum surface a chat-capable LLM must implement.

    The protocol is deliberately small: ``chat()`` returns a structured
    response in a provider-neutral shape so swapping providers does not
    leak into call sites.
    """

    def chat(
        self,
        *,
        system: str,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
        max_tokens: int,
    ) -> LLMChatResult: ...


@dataclass(frozen=True)
class LLMChatResult:
    """Provider-neutral chat result.

    ``tool_calls`` is a list of ``{"name": str, "arguments": dict,
    "id": str}`` items; ``content`` is the assistant's free-text reply
    (may be empty when the model decides to call tools instead).
    """

    content: str
    tool_calls: tuple[dict[str, Any], ...] = ()
    tokens_in: int = 0
    tokens_out: int = 0
    finish_reason: str = "stop"


class StubLLMProvider:
    """Deterministic in-memory LLM provider used by tests.

    Configure with a queue of canned responses; each ``chat()`` pops the
    next one. Lets tests assert tool-dispatch behaviour without spending
    real tokens.
    """

    def __init__(self, responses: Sequence[LLMChatResult]) -> None:
        self._responses: list[LLMChatResult] = list(responses)
        self.call_log: list[dict[str, Any]] = []

    def chat(
        self,
        *,
        system: str,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
        max_tokens: int,
    ) -> LLMChatResult:
        self.call_log.append(
            {
                "system": system,
                "messages": list(messages),
                "tools": list(tools),
                "max_tokens": max_tokens,
            }
        )
        if not self._responses:
            return LLMChatResult(content="(stub: no more responses)")
        return self._responses.pop(0)


# ---------------------------------------------------------------------------
# PortfolioChat
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = """\
You are AxiomFolio's portfolio assistant. You help the user understand
their portfolio and the market through analysis grounded in their
actual data.

Hard rules:
1. You may ONLY call the tools provided. Do not invent tool names.
2. You operate read-only. You cannot place trades, change settings,
   or modify any data. Direct the user to the appropriate UI for those.
3. Cite your sources. Every claim about a number must trace back to a
   tool call result.
4. Stage Analysis is the framework — refer to stages as 1A/1B/2A/2B/2C
   /3A/3B/4A/4B/4C and respect the SMA150 anchor.
5. If you do not have data, say so. Do not speculate.
6. Be concise. Subscribers pay for signal, not prose.

Risk language:
- Never tell the user "buy" or "sell". You can describe setup
  characteristics ("Stage 2A breakout, RS 78, 2 ATR from pivot") and
  let them decide.
"""


@dataclass
class ChatLimits:
    max_tool_calls: int = 6
    max_tokens_per_request: int = 4000
    max_wall_seconds: float = 30.0


_DEFAULT_LIMITS = ChatLimits()


class PortfolioChat:
    """User-facing chat session.

    Construct one per request. Each ``ask()`` is independent — sessions
    are reconstructed from the ``history`` field of the next
    ``ChatRequest``, persisted by the route layer.
    """

    def __init__(
        self,
        *,
        provider: LLMProvider,
        tools: Sequence[ToolSpec],
        limits: ChatLimits | None = None,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        if not isinstance(provider, LLMProvider):  # runtime_checkable
            raise TypeError(f"provider must implement LLMProvider, got {type(provider).__name__}")
        self._provider = provider
        self._tools_by_name: dict[str, ToolSpec] = {t.name: t for t in tools}
        self._limits = limits or _DEFAULT_LIMITS
        self._system_prompt = system_prompt

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def ask(self, db: Session, request: ChatRequest) -> ChatResponse:
        started = time.monotonic()
        deadline = started + self._limits.max_wall_seconds

        messages: list[dict[str, Any]] = self._compose_messages(request)
        tool_trace: list[ToolTrace] = []
        sources: list[dict[str, Any]] = []
        total_in = 0
        total_out = 0
        truncated = False

        for iteration in range(self._limits.max_tool_calls + 1):
            if time.monotonic() > deadline:
                truncated = True
                break

            result = self._provider.chat(
                system=self._system_prompt,
                messages=messages,
                tools=[t.openai_function_schema() for t in self._tools_by_name.values()],
                max_tokens=self._limits.max_tokens_per_request,
            )
            total_in += result.tokens_in
            total_out += result.tokens_out

            if not result.tool_calls:
                # Model produced a final answer.
                elapsed_ms = int((time.monotonic() - started) * 1000)
                return ChatResponse(
                    request_id=request.request_id,
                    answer=result.content or "",
                    tool_trace=tuple(tool_trace),
                    sources=tuple(sources),
                    tokens_in=total_in,
                    tokens_out=total_out,
                    elapsed_ms=elapsed_ms,
                    truncated=truncated,
                )

            if iteration >= self._limits.max_tool_calls:
                truncated = True
                break

            # Append the assistant's tool-call message and dispatch each call.
            messages.append(
                {
                    "role": "assistant",
                    "content": result.content,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc.get("arguments", {})),
                            },
                        }
                        for tc in result.tool_calls
                    ],
                }
            )
            for tc in result.tool_calls:
                trace, tool_sources = self._dispatch_tool(db, request.user_id, tc)
                tool_trace.append(trace)
                sources.extend(tool_sources)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tc["name"],
                        "content": trace.result_summary,
                    }
                )

        elapsed_ms = int((time.monotonic() - started) * 1000)
        return ChatResponse(
            request_id=request.request_id,
            answer="",
            tool_trace=tuple(tool_trace),
            sources=tuple(sources),
            tokens_in=total_in,
            tokens_out=total_out,
            elapsed_ms=elapsed_ms,
            truncated=truncated,
            error="tool_call_limit_or_timeout" if truncated else None,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _compose_messages(self, request: ChatRequest) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in request.history:
            entry: dict[str, Any] = {"role": m.role, "content": m.content}
            if m.tool_call_id:
                entry["tool_call_id"] = m.tool_call_id
            if m.tool_name:
                entry["name"] = m.tool_name
            out.append(entry)
        out.append({"role": "user", "content": request.message})
        return out

    def _dispatch_tool(
        self,
        db: Session,
        user_id: int,
        tool_call: dict[str, Any],
    ) -> tuple[ToolTrace, list[dict[str, Any]]]:
        name = tool_call["name"]
        arguments = tool_call.get("arguments", {})
        if not isinstance(arguments, dict):
            arguments = {}

        spec = self._tools_by_name.get(name)
        started = time.monotonic()
        if spec is None:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            err = f"unknown tool: {name}"
            logger.warning("portfolio_chat: %s (user=%s)", err, user_id)
            return (
                ToolTrace(
                    name=name,
                    arguments=arguments,
                    result_summary=err,
                    elapsed_ms=elapsed_ms,
                    error=err,
                ),
                [],
            )
        try:
            result = spec.fn(db, user_id, arguments) or {}
        except Exception as e:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            logger.exception("portfolio_chat tool %s failed (user=%s): %s", name, user_id, e)
            return (
                ToolTrace(
                    name=name,
                    arguments=arguments,
                    result_summary=f"error: {e}",
                    elapsed_ms=elapsed_ms,
                    error=str(e),
                ),
                [],
            )

        summary = str(result.get("summary", json.dumps(result)[:500]))
        sources = list(result.get("sources", []))
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return (
            ToolTrace(
                name=name,
                arguments=arguments,
                result_summary=summary,
                elapsed_ms=elapsed_ms,
            ),
            sources,
        )


# ---------------------------------------------------------------------------
# Built-in tools (read-only stubs)
# ---------------------------------------------------------------------------


def _summarize_portfolio(db: Session, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    """Return a compact textual summary of the user's portfolio.

    v0 implementation is intentionally a thin wrapper that the route PR
    will swap for the real query — the goal of PR F is to lock the
    surface area, not duplicate existing portfolio queries.
    """
    return {
        "summary": (
            f"portfolio summary for user_id={user_id} not yet wired; "
            "the route PR will bind this tool to PortfolioService."
        ),
        "sources": [{"kind": "stub", "user_id": user_id}],
    }


def _now_utc(db: Session, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    """Return the current UTC time. Useful smoke tool."""
    return {
        "summary": datetime.now(UTC).isoformat(),
        "sources": [],
    }


BUILT_IN_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="summarize_portfolio",
        description="Return a one-paragraph summary of the user's portfolio.",
        parameters_schema={"type": "object", "properties": {}, "required": []},
        fn=_summarize_portfolio,
    ),
    ToolSpec(
        name="now_utc",
        description="Return the current UTC time. Useful when computing windows.",
        parameters_schema={"type": "object", "properties": {}, "required": []},
        fn=_now_utc,
    ),
)


def default_tools() -> tuple[ToolSpec, ...]:
    """Return the default tool registry for production wiring.

    Kept as a function so future PRs can extend it without mutating a
    module-level tuple.
    """
    return BUILT_IN_TOOLS
