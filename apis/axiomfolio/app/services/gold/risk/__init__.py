"""Gold-layer risk services.

medallion: gold

``PreTradeValidator`` moved to :mod:`app.services.execution.risk.pre_trade_validator`
as part of Medallion Wave 0.C (pre-trade validation is an execution-layer
concern, not a gold analytic). Import from the canonical module.
"""
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig, circuit_breaker

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "circuit_breaker",
]
