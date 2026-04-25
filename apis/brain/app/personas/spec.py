"""PersonaSpec — typed contract for a Brain persona.

Every persona under .cursor/rules/<name>.mdc can have a paired spec at
apis/brain/app/personas/specs/<name>.yaml. The .mdc holds the natural-
language system instructions; the YAML holds the operational contract:
which model to default to, when to escalate, what tools are allowed,
daily cost ceiling, and expected input/output shape.

The registry layer (registry.py) loads specs on demand and caches them.
Missing specs are not errors — the agent falls back to legacy classify-
and-route behavior. This lets us migrate personas one at a time without
breaking the world.

A PersonaSpec is intentionally narrow. Deeper policy (PII rules,
escalation to humans, rate limits) belongs in platform middleware, not
per-persona config.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


ModelSlug = str


class PersonaSpec(BaseModel):
    """Operational contract for one persona."""

    name: str = Field(description="Persona slug. Matches .cursor/rules/<name>.mdc.")
    description: str = Field(
        description="One-line summary of what this persona does.",
    )
    default_model: ModelSlug = Field(
        description=(
            "Model to use for standard requests. Cheap by default; we escalate "
            "per the rules below."
        ),
    )
    escalation_model: ModelSlug | None = Field(
        default=None,
        description=(
            "Higher-capability model used when escalate_if conditions hit. If "
            "None, this persona never escalates and stays on default_model."
        ),
    )
    escalate_if: list[str] = Field(
        default_factory=list,
        description=(
            "Ordered list of tags that force escalation. Supported tags: "
            "'compliance' — persona is compliance-flagged; "
            "'tokens>N' — input tokens exceed N (counted with tiktoken); "
            "'mention:<slug>' — message mentions a slug (case-insensitive)."
        ),
    )
    requires_tools: bool = Field(
        default=False,
        description=(
            "If True, route every call through the provider's MCP path (so the "
            "LLM can invoke tools). If False, use the plain text-completion "
            "path. Set True for personas that must read the repo, list PRs, "
            "or query infra (engineering, trading, agent-ops)."
        ),
    )
    daily_cost_ceiling_usd: float | None = Field(
        default=None,
        description=(
            "Per-org daily cost cap for this persona in USD. Enforced by "
            "platform middleware. None means no cap (inherits global)."
        ),
    )
    max_output_tokens: int | None = Field(
        default=None,
        description=(
            "Track I: hard cap on output tokens for this persona. Prevents "
            "runaway completions (e.g. a chatty persona streaming 8k tokens "
            "of hedging). None = provider default (~4096 for text paths)."
        ),
    )
    requests_per_minute: int | None = Field(
        default=None,
        description=(
            "Track I: optional per-org rate limit for this persona. Enforced "
            "on /brain/process when persona_pin matches. None = falls back to "
            "global SlowAPI default."
        ),
    )
    confidence_floor: float | None = Field(
        default=None,
        description=(
            "If the model's self-reported confidence is below this, append a "
            "'needs-human-review' marker. Used by compliance-flagged personas."
        ),
    )
    compliance_flagged: bool = Field(
        default=False,
        description=(
            "If True, persona handles compliance-sensitive content (tax, legal, "
            "security, PII). Enables stricter guardrails + mandatory review."
        ),
    )
    owner_channel: str | None = Field(
        default=None,
        description=(
            "Default Slack channel where this persona posts. Used by scheduled "
            "workflows migrated out of n8n."
        ),
    )
    tone_prefix: str | None = Field(
        default=None,
        description=(
            "Track C: short string prepended to the system prompt so each persona "
            "has a distinct voice even though the underlying LLM is the same. "
            "Example: 'Speak like a senior CPA — concise, conservative, always "
            "flags tax-law caveats.' Falls back to an empty prefix."
        ),
    )
    proactive_cadence: Literal["never", "daily", "weekly", "monthly"] = Field(
        default="never",
        description=(
            "Track C: how often this persona posts proactively in its "
            "owner_channel. 'never' = reactive only; 'daily' = posts a standup "
            "every morning UTC; 'weekly' = posts a digest every Monday; "
            "'monthly' = posts on the 1st. Scheduler reads this to build the "
            "cron plan without us hand-coding per-persona jobs."
        ),
    )
    input_schema: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional JSON Schema for structured invocations. For chat-style "
            "calls this is ignored; for /admin/agents/run it validates input."
        ),
    )
    output_schema: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional JSON Schema for structured responses. If present, the "
            "response is validated and a violation is flagged on failure."
        ),
    )
    mode: Literal["chat", "task"] = Field(
        default="chat",
        description=(
            "'chat' for open-ended conversations; 'task' for schema-bound one-"
            "shot invocations with input_schema + output_schema."
        ),
    )

    @field_validator("escalate_if")
    @classmethod
    def _validate_escalate_if(cls, v: list[str]) -> list[str]:
        for tag in v:
            if tag == "compliance":
                continue
            if tag.startswith(("tokens>", "mention:")):
                continue
            raise ValueError(f"unknown escalate_if tag: {tag!r}")
        return v
