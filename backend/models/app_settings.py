from __future__ import annotations

from sqlalchemy import Column, Integer, Boolean, TIMESTAMP
from sqlalchemy.sql import func
import sqlalchemy as sa

from . import Base


class AppSettings(Base):
    """Singleton app-wide feature flags and release controls."""

    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    market_only_mode = Column(
        Boolean,
        default=True,
        server_default=sa.text("true"),
        nullable=False,
    )
    portfolio_enabled = Column(
        Boolean,
        default=False,
        server_default=sa.text("false"),
        nullable=False,
    )
    strategy_enabled = Column(
        Boolean,
        default=False,
        server_default=sa.text("false"),
        nullable=False,
    )
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )
