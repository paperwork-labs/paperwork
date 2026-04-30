from pydantic import BaseModel, Field


class ProcessRequest(BaseModel):
    organization_id: str = Field(description="Which Brain to use")
    message: str = Field(description="User message to process")
    user_id: str | None = Field(default=None, description="Who sent the message")
    channel: str | None = Field(default=None, description="Channel name (api, web, conversations)")
    channel_id: str | None = Field(default=None, description="Channel ID for persona routing")
    request_id: str | None = Field(default=None, description="Idempotency key")
    thread_context: list[dict[str, str]] | None = Field(
        default=None, description="Prior messages in thread"
    )
    thread_id: str | None = Field(
        default=None,
        description=(
            "Stable identifier for a conversation thread. When set, Brain looks up the "
            "persona that last replied in this thread and sticks with it so "
            "follow-up questions don't bounce between employees mid-thread."
        ),
    )
    persona_pin: str | None = Field(
        default=None,
        description=(
            "Caller-pinned persona slug (e.g. 'cpa', 'qa'). When set we "
            "bypass the keyword router and go straight to the PersonaSpec route."
        ),
    )
    strategy: str | None = Field(
        default=None,
        description=(
            "Chain strategy override. 'auto' / null picks "
            "PersonaPinnedRoute when persona_pin is set, else ClassifyAndRoute. "
            "'classify_route' forces the Gemini Flash classifier even when a "
            "persona is pinned. 'extract_reason' runs "
            "the P3 two-hop pattern. Unknown values "
            "fall back to 'auto' with a warning."
        ),
    )


class ProcessResponse(BaseModel):
    response: str
    persona: str
    persona_spec: str | None = Field(
        default=None,
        description=(
            "Name of the PersonaSpec used, or None if the persona has no typed "
            "contract (legacy classify-and-route path)."
        ),
    )
    persona_pinned: bool = Field(
        default=False,
        description=(
            "True when the caller passed persona_pin and the router bypassed the keyword heuristic."
        ),
    )
    chain_strategy: str | None = Field(
        default=None,
        description="Which ChainStrategy ran.",
    )
    model: str
    tokens_in: int
    tokens_out: int
    episode_id: int | None = Field(
        default=None,
        description="Primary key of the episode that captured this exchange.",
    )
    episode_uri: str | None = Field(
        default=None,
        description=(
            "Canonical provenance URI (brain://episode/{id}) for this "
            "response. Append to downstream artifacts so operators can "
            "trace back to the source exchange."
        ),
    )
    needs_human_review: bool = Field(
        default=False,
        description=(
            "True when the persona is compliance_flagged and has a "
            "confidence_floor — downstream UIs should surface a review badge."
        ),
    )
    error: str | None = Field(
        default=None,
        description=(
            "Structured error code when the pipeline short-circuited "
            "(e.g. 'cost_ceiling_exceeded', 'llm_unavailable'). Null on "
            "a normal response."
        ),
    )
