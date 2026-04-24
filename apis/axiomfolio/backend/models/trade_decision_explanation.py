"""Trade Decision Explanation model.

Persisted output of
:class:`backend.services.agent.trade_decision_explainer.TradeDecisionExplainer`
so the trade drawer can poll a stable endpoint instead of re-running the
LLM on every render, and so we have an auditable history of what the
explainer told the user about each executed order.

Storage choices:

* ``payload_json`` holds the structured LLM output (trigger, headline,
  rationale_bullets, risk_context, outcome_so_far). Schema evolution
  lives entirely inside the prompt schema; no Alembic columns to chase
  when a new structured field appears.
* The flat columns (``trigger_type``, ``model_used``, ``is_fallback``,
  token counts, ``cost_usd``) are denormalized copies so the trades
  list view and cost-analytics queries don't have to parse JSON in
  Postgres on every read.
* ``cost_usd`` uses :class:`Numeric` (10, 6) because OpenAI prices in
  fractions of a cent; the iron law is monetary values use Decimal.
* ``UniqueConstraint("order_id", "version")`` makes the regenerate
  endpoint's "next-version" contract enforceable at the DB layer.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)

from . import Base


class TradeDecisionExplanation(Base):
    """Structured "why was this trade taken" record for one executed order."""

    __tablename__ = "trade_decision_explanations"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id = Column(
        Integer,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trade_id = Column(
        Integer,
        ForeignKey("trades.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    schema_version = Column(String(64), nullable=False)
    version = Column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    trigger_type = Column(String(32), nullable=False)
    model_used = Column(String(64), nullable=False)

    prompt_token_count = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    completion_token_count = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    cost_usd = Column(
        Numeric(10, 6), nullable=False, default=0, server_default="0"
    )

    is_fallback = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    payload_json = Column(JSON, nullable=False)
    narrative = Column(Text, nullable=False)

    generated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "order_id",
            "version",
            name="uq_trade_decision_explanations_order_version",
        ),
        CheckConstraint(
            "cost_usd >= 0",
            name="ck_trade_decision_explanations_cost_nonneg",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_trade_decision_explanations_version_positive",
        ),
        CheckConstraint(
            "trigger_type IN ('pick','scan','rebalance','manual','strategy','unknown')",
            name="ck_trade_decision_explanations_trigger_type",
        ),
        Index(
            "ix_trade_decision_explanations_user_generated",
            "user_id",
            "generated_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<TradeDecisionExplanation id={self.id} order_id={self.order_id} "
            f"version={self.version} trigger={self.trigger_type} "
            f"model={self.model_used} fallback={self.is_fallback}>"
        )
