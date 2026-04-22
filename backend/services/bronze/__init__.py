"""Bronze layer — raw broker and market-data ingestion.

This is the landing zone for the medallion architecture committed in the
``broker_parity_medallion_v1`` plan:

* **Bronze** (this package) — raw per-broker ingestion (positions, trades,
  transactions, dividends, balances, options). One subpackage per broker;
  each exposes a ``SyncService`` with a ``sync_account_comprehensive``
  entry point (synchronous for E*TRADE; async coroutine for TastyTrade
  and IBKR) matching the contract enforced by
  ``backend.services.portfolio.broker_sync_service.BrokerSyncService``
  (the dispatcher awaits awaitables and passes through sync returns).
* **Silver** (``backend/services/silver/*``, coming in Phase 2) — enrichment
  on top of bronze output: indicator engine, stage classification, closing-
  lot matcher, regime engine, analytics.
* **Gold** (``backend/services/gold/*``, coming in Phase 3) — decision
  services: PickQualityScorer (G7), OptionsChainSurface (G9),
  TradeCardComposer (G10), RiskGate, OrderManager.

Existing modules under ``backend/services/portfolio/ibkr``,
``backend/services/portfolio/schwab_sync_service.py`` and
``backend/services/portfolio/tastytrade_sync_service.py`` are bronze-layer
services too — they predate the rename and are annotated in place rather
than moved (no big-bang rename; see docs/KNOWLEDGE.md D127).

PR D2 (Phase 1) seeds this package with the E*TRADE sandbox ingestion.
"""
