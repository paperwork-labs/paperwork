"""Manual span decorators for hot paths.

Auto-instrumentation covers HTTP routes, SQL queries, Celery task
bookkeeping, httpx, and Redis. Decorate any function whose internal
behavior the auto-instrumented edges cannot describe (the indicator
engine, scan overlays, picks parser, etc.) with :func:`traced` to add an
explicit span.

The decorator is safe to apply before :func:`init_tracing` runs: until a
real provider is installed, OTel returns proxy objects whose
``start_as_current_span`` is a cheap no-op.

Span naming convention: snake_case, no emojis, no slashes. Use the
``attrs`` argument for component / module hints rather than encoding them
into the name.
"""

from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable, Dict, Optional, TypeVar

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def traced(
    span_name: str,
    *,
    attrs: Optional[Dict[str, Any]] = None,
    record_exceptions: bool = True,
) -> Callable[[F], F]:
    """Wrap a function in an OTel span.

    Parameters
    ----------
    span_name:
        snake_case identifier (no emojis). Becomes the OTel span name.
    attrs:
        Static attributes attached to every invocation. Use this for
        component / subsystem tags. Per-call attributes should be added
        from inside the wrapped function via ``trace.get_current_span``.
    record_exceptions:
        When True (default) any exception raised inside the wrapped
        function is recorded on the span and the span status is set to
        ERROR before the exception is re-raised.

    Notes
    -----
    * Async and sync callables are supported.
    * The wrapped function's signature, name, and docstring are preserved
      via :func:`functools.wraps`.
    * Decorating a function does NOT change its return value, raise
      semantics, or side effects — this is pure observability.
    """
    static_attrs = dict(attrs) if attrs else {}

    def decorator(func: F) -> F:
        is_coro = inspect.iscoroutinefunction(func)

        if is_coro:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                # Resolve tracer per call so spans attach to whatever
                # TracerProvider tests (or init_tracing) installed most recently.
                tracer = trace.get_tracer(func.__module__)
                with tracer.start_as_current_span(span_name) as span:
                    for k, v in static_attrs.items():
                        try:
                            span.set_attribute(k, v)
                        except Exception:
                            pass
                    try:
                        return await func(*args, **kwargs)
                    except Exception as exc:
                        if record_exceptions:
                            try:
                                span.record_exception(exc)
                                span.set_status(
                                    Status(StatusCode.ERROR, str(exc)[:200])
                                )
                            except Exception:
                                pass
                        raise

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            tracer = trace.get_tracer(func.__module__)
            with tracer.start_as_current_span(span_name) as span:
                for k, v in static_attrs.items():
                    try:
                        span.set_attribute(k, v)
                    except Exception:
                        pass
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    if record_exceptions:
                        try:
                            span.record_exception(exc)
                            span.set_status(
                                Status(StatusCode.ERROR, str(exc)[:200])
                            )
                        except Exception:
                            pass
                    raise

        return sync_wrapper  # type: ignore[return-value]

    return decorator


__all__ = ["traced"]
