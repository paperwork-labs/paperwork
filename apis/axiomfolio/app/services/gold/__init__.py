"""Medallion layer: gold.

medallion: gold

Contract:
    gold/ consumes silver artifacts (clean + enriched data) and produces
    business-ready decision products: conviction picks, trade cards, peak
    signals, backtests, strategy outputs, winner-exit advice.

    gold/ reads from: bronze/, silver/, clients/
    gold/ does NOT import from: execution/  (execution is downstream)

Import rules enforced by ``scripts/medallion/check_imports.py``.

NOTE (Wave 0.C): this __init__.py is intentionally empty. Earlier versions
re-exported every gold subclass at the package root, which created an
import-order cycle — loading any transitive consumer of ``gold.strategy``
(including ``execution.risk_gate``, which imports ``account_strategy``)
would pull in ``trade_card_composer`` via this __init__, which in turn
imports back into ``execution.risk_gate`` before it finished initializing.
Import the concrete module you need directly (e.g.
``from app.services.gold.trade_card_composer import TradeCard``).
"""
