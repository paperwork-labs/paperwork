"""Typed errors for the agent pipeline.

Prefer these over catching broad Exception so agent.process can turn
each into an honest, user-facing message with the right HTTP status
at the API layer.
"""
from __future__ import annotations


class LLMUnavailableError(Exception):
    """Raised when every provider in the router failed.

    Use this instead of returning mock text — the agent layer can then
    surface a real error (HTTP 503 / Slack message like
    'Brain providers are degraded, try again shortly') rather than
    handing the user fake content labelled like a genuine answer.
    """

    def __init__(self, *, provider: str, model: str, reason: str):
        self.provider = provider
        self.model = model
        self.reason = reason
        super().__init__(f"{provider}/{model} failed: {reason}")
