"""medallion: silver

Silver layer — enriched, cross-broker, analytical.

Contract:
    silver/ reads bronze outputs (clean, broker-native data) and produces
    analytical artifacts: indicators, stage classification, regime signals,
    cross-broker reconciliation, tax lots, corporate-action-adjusted history.

    silver/ does NOT write to real brokers, does NOT generate trade signals,
    does NOT talk to external user-bound services (Stripe, Discord, etc.).

Import rules (enforced by scripts/medallion/check_imports.py):
    silver/ → may import from: bronze/, stdlib, services/clients/, services/ops/*
    silver/ → MUST NOT import from: gold/, execution/, strategy/, picks/

As of Wave 0 Phase 0.A (2026-04-23) this folder is a scaffold; grandfathered
silver-layer code lives in services/market/, services/portfolio/ (partial),
services/tax/, services/corporate_actions/, services/data_quality/,
services/intelligence/, services/symbols/. Phase 0.C Pass 1-2 migrates those
files into this tree. See docs/plans/MEDALLION_AUDIT_2026Q2.md.
"""
