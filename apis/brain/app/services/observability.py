"""Langfuse observability integration (D41)."""

import logging

from app.config import settings

logger = logging.getLogger(__name__)

_langfuse = None


def init_langfuse():
    """Initialize Langfuse client. Call during app startup."""
    global _langfuse
    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        logger.info("Langfuse keys not set, observability disabled")
        return
    try:
        from langfuse import Langfuse

        _langfuse = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        logger.info("Langfuse initialized (host=%s)", settings.LANGFUSE_HOST)
    except Exception:
        logger.warning("Failed to initialize Langfuse", exc_info=True)


def create_trace(
    name: str,
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    metadata: dict | None = None,
):
    """Create a new Langfuse trace for a Brain request."""
    if not _langfuse:
        return _NoOpTrace()
    try:
        return _langfuse.trace(
            name=name,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata or {},
        )
    except Exception:
        logger.warning("Failed to create Langfuse trace", exc_info=True)
        return _NoOpTrace()


class _NoOpTrace:
    """No-op trace when Langfuse is disabled."""

    def span(self, **kwargs):
        return _NoOpSpan()

    def generation(self, **kwargs):
        return _NoOpSpan()

    def score(self, **kwargs):
        pass

    def update(self, **kwargs):
        pass

    def end(self, **kwargs):
        pass


class _NoOpSpan:
    """No-op span when Langfuse is disabled."""

    def end(self, **kwargs):
        pass

    def update(self, **kwargs):
        pass

    def generation(self, **kwargs):
        return self

    def span(self, **kwargs):
        return self

    def score(self, **kwargs):
        pass


def flush():
    """Flush pending Langfuse events."""
    if _langfuse:
        try:
            _langfuse.flush()
        except Exception:
            logger.warning("Langfuse flush failed", exc_info=True)
