from pydantic import BaseModel, Field


class ProcessRequest(BaseModel):
    organization_id: str = Field(description="Which Brain to use")
    message: str = Field(description="User message to process")
    user_id: str | None = Field(default=None, description="Who sent the message")
    channel: str | None = Field(default=None, description="Channel name (slack, api, web)")
    channel_id: str | None = Field(default=None, description="Slack channel ID for persona routing")
    request_id: str | None = Field(default=None, description="D10: idempotency key (e.g. Slack ts)")
    thread_context: list[dict[str, str]] | None = Field(
        default=None, description="Prior messages in thread"
    )
    thread_id: str | None = Field(
        default=None,
        description=(
            "Track C: stable identifier for a conversation thread, e.g. "
            "'slack:<channel_id>:<thread_ts>'. When set, Brain looks up the "
            "persona that last replied in this thread and sticks with it so "
            "follow-up questions don't bounce between employees mid-thread."
        ),
    )
    persona_pin: str | None = Field(
        default=None,
        description=(
            "Track F: caller-pinned persona slug (e.g. 'cpa', 'qa'). When set we "
            "bypass the keyword router and go straight to the PersonaSpec route. "
            "Used by n8n workflows that already know which employee to invoke "
            "and by /persona slash commands."
        ),
    )
    strategy: str | None = Field(
        default=None,
        description=(
            "Buffer Week 4: chain strategy override. 'auto' / null picks "
            "PersonaPinnedRoute when persona_pin is set, else ClassifyAndRoute. "
            "'classify_route' forces the Gemini Flash classifier even when a "
            "persona is pinned (useful for research queries where model choice "
            "should follow the query, not the persona). 'extract_reason' runs "
            "the P3 two-hop pattern — cheap Flash extracts structured facts, "
            "then Sonnet reasons over them — for high-signal persona calls "
            "like CPA tax analysis or QA incident root-cause. Unknown values "
            "fall back to 'auto' with a warning so callers aren't broken by "
            "typos."
        ),
    )
    slack_channel_id: str | None = Field(
        default=None,
        description=(
            "Track H: when set, Brain posts the persona's response to this "
            "Slack channel after generation (using slack_outbound). Lets n8n "
            "workflows collapse to 2 nodes — Webhook → Brain — instead of "
            "Webhook → LLM → format → Slack."
        ),
    )
    slack_username: str | None = Field(
        default=None,
        description=(
            "Optional display name for the Slack post (defaults to the "
            "PersonaSpec name when slack_channel_id is set)."
        ),
    )
    slack_icon_emoji: str | None = Field(
        default=None,
        description="Optional emoji avatar for the Slack post (e.g. ':nerd_face:').",
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
            "Track F: True when the caller passed persona_pin and the router "
            "bypassed the keyword heuristic. Useful for observability when "
            "n8n workflows force a specific persona."
        ),
    )
    chain_strategy: str | None = Field(
        default=None,
        description=(
            "Which ChainStrategy ran: 'persona_pinned_route' when a "
            "PersonaSpec was resolved, 'classify_and_route' for the Gemini "
            "Flash classifier fallback. Surfaces to n8n so flows can detect "
            "drift (e.g. a persona that should pin but didn't)."
        ),
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
            "confidence_floor — downstream UIs should surface a review "
            "badge. Enforcement of blocking on low confidence is D7."
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
