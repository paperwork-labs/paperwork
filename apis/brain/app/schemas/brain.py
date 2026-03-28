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


class ProcessResponse(BaseModel):
    response: str
    persona: str
    model: str
    tokens_in: int
    tokens_out: int
