"""Per-account risk profile — additive layer on top of firm-level risk caps.

This model stores **user-chosen** per-account limits. It does NOT replace
the firm-level caps defined in ``backend/config.py`` and enforced by
``backend/services/execution/risk_gate.py``. Effective limits are always
the tighter of ``(firm_cap, per_account_cap)`` — see
``backend/services/risk/account_risk_profile.py``.

All percent fields use ``Numeric(5, 4)`` for four decimal places of
precision (e.g. ``0.0500`` for 5%). **Business rule:** each value is a
fractional percent in ``[0, 1]``; enforcement is in the API (Pydantic),
``apply_override`` / merge services, and the table CHECK constraints —
not from the column type alone (``Numeric(5, 4)`` can represent larger
magnitudes at the SQL layer if written around those layers). Storing
percents as ``Decimal`` avoids the float drift documented in the Iron
Laws (monetary and percent math never uses ``float``).

Why per-account, not per-user: different broker accounts (a tax-deferred
IRA vs a taxable joint account) may have legitimately different risk
appetites. The per-account layer lets users dial their own style within
the firm-level discipline boundaries.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from . import Base


class BrokerAccountRiskProfile(Base):
    """User-configurable per-account risk caps.

    Effective limit for any field is ``min(firm_cap, per_account_cap)``.
    Firm caps are defined in ``backend/config.py`` and a small number of
    additional constants in ``backend/services/risk/firm_caps.py``. The
    firm layer can only tighten, never loosen.
    """

    __tablename__ = "broker_account_risk_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(
        Integer,
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    max_position_pct = Column(Numeric(5, 4), nullable=True)
    max_stage_2c_pct = Column(Numeric(5, 4), nullable=True)
    max_options_pct = Column(Numeric(5, 4), nullable=True)
    max_daily_loss_pct = Column(Numeric(5, 4), nullable=True)
    hard_stop_pct = Column(Numeric(5, 4), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    account = relationship("BrokerAccount")
