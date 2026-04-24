#!/usr/bin/env python3
"""
Phase 0.C prep — generate medallion_move_map.yaml.

For every tagged .py file under app/services/, emit a YAML entry mapping
the current path to its Phase 0.C target path. The output is consumed by
scripts/medallion_migrate.py (Phase 0.C) which performs the git mv + import
rewrites in one atomic pass.

Target-path rules are per-directory; see TARGETS below. Pass order matches
the handoff section 4.2 dependency-safe move sequence.

Usage:
    python scripts/medallion/generate_move_map.py > medallion_move_map.yaml
    python scripts/medallion/generate_move_map.py --stats   # dry-run summary
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SERVICES = REPO_ROOT / "app" / "services"


def classify(rel: str) -> tuple[str | None, str]:
    """Return (target_path_relative_to_backend_services, pass_name). None if stays put."""

    # Pass 5 — execution stays in place.
    if rel.startswith("execution/") or rel == "execution":
        return None, "pass5_execution_stays"

    # Already native:
    if rel.startswith("bronze/"):
        return None, "already_native_bronze"
    if rel.startswith("silver/"):
        return None, "already_native_silver"
    if rel.startswith("gold/"):
        return None, "already_native_gold"

    # Pass 1 — leaf utilities (pure math, no dependencies).
    pass1_leaves = {
        "market/dataframe_utils.py": "silver/math/dataframe_utils.py",
        "market/atr_series.py":       "silver/math/atr_series.py",
        "market/coverage_utils.py":   "silver/math/coverage_utils.py",
        "market/stage_utils.py":      "silver/math/stage_utils.py",
        "market/backfill_params.py":  "silver/math/backfill_params.py",
        "market/constants.py":        "silver/math/constants.py",
        "market/rate_limiter.py":     "silver/math/rate_limiter.py",
    }
    if rel in pass1_leaves:
        return pass1_leaves[rel], "pass1_leaf_utilities"

    # Pass 2 — silver core.
    if rel.startswith("market/providers/"):
        # market data providers are bronze (external I/O), not silver
        return f"bronze/market/providers/{rel.removeprefix('market/providers/')}", "pass3_bronze_market_providers"
    if rel.startswith("market/"):
        # Everything else in market/ is silver (indicators, regime, stage).
        fname = rel.removeprefix("market/")
        # Subdivide known families
        if fname in ("indicator_engine.py", "stage_classifier.py", "stage_quality_service.py",
                     "multi_timeframe.py", "regime_engine.py", "regime_inputs.py", "regime_monitor.py",
                     "quad_engine.py"):
            subdir = "indicators" if "indicator" in fname or "multi_timeframe" in fname else "regime"
            return f"silver/{subdir}/{fname}", "pass2_silver_core"
        return f"silver/market/{fname}", "pass2_silver_core"
    if rel == "tax" or rel.startswith("tax/"):
        return f"silver/tax/{rel.removeprefix('tax/')}" if "/" in rel else "silver/tax/__init__.py", "pass2_silver_core"
    if rel.startswith("corporate_actions/"):
        return f"silver/corporate_actions/{rel.removeprefix('corporate_actions/')}", "pass2_silver_core"
    if rel.startswith("data_quality/"):
        return f"silver/data_quality/{rel.removeprefix('data_quality/')}", "pass2_silver_core"
    if rel.startswith("intelligence/"):
        return f"silver/intelligence/{rel.removeprefix('intelligence/')}", "pass2_silver_core"
    if rel.startswith("symbols/"):
        return f"silver/symbols/{rel.removeprefix('symbols/')}", "pass2_silver_core"

    # Pass 3 — bronze core (broker-facing portfolio code).
    if rel.startswith("portfolio/ibkr/"):
        return f"bronze/ibkr/{rel.removeprefix('portfolio/ibkr/')}", "pass3_bronze_core"
    if rel == "portfolio/schwab_sync_service.py":
        return "bronze/schwab/sync_service.py", "pass3_bronze_core"
    if rel == "portfolio/tastytrade_sync_service.py":
        return "bronze/tastytrade/sync_service.py", "pass3_bronze_core"
    if rel == "portfolio/broker_sync_service.py":
        return "bronze/broker_sync_service.py", "pass3_bronze_core"
    if rel == "portfolio/ibkr_sync_service.py":
        return "bronze/ibkr/sync_service.py", "pass3_bronze_core"
    if rel.startswith("portfolio/plaid/"):
        return f"bronze/plaid/{rel.removeprefix('portfolio/plaid/')}", "pass3_bronze_core"
    if rel.startswith("portfolio/adapters/"):
        return f"bronze/adapters/{rel.removeprefix('portfolio/adapters/')}", "pass3_bronze_core"

    # Remaining portfolio/* — analytics (silver).
    portfolio_silver_families = {
        "portfolio_analytics_service.py":  "silver/portfolio/analytics.py",
        "closing_lot_matcher.py":          "silver/portfolio/closing_lot_matcher.py",
        "activity_aggregator.py":          "silver/portfolio/activity_aggregator.py",
        "tax_lot_service.py":              "silver/portfolio/tax_lot_service.py",
        "tax_loss_harvester.py":           "silver/portfolio/tax_loss_harvester.py",
        "day_pnl_service.py":              "silver/portfolio/day_pnl_service.py",
        "discipline_trajectory_service.py": "silver/portfolio/discipline_trajectory_service.py",
        "drawdown.py":                     "silver/portfolio/drawdown.py",
        "reconciliation.py":               "silver/portfolio/reconciliation.py",
        "broker_catalog.py":               "silver/portfolio/broker_catalog.py",
        "monitoring.py":                   "silver/portfolio/monitoring.py",
    }
    if rel.startswith("portfolio/"):
        fname = rel.removeprefix("portfolio/")
        if fname in portfolio_silver_families:
            return portfolio_silver_families[fname], "pass2_silver_portfolio"
        if fname in ("account_config_service.py", "account_credentials_service.py", "account_type_resolver.py"):
            # account/credentials helpers — ops (cross-cutting infra).
            return None, "ops_stays_portfolio_helpers"
        # Everything else in portfolio/ stays as silver/portfolio/ default.
        return f"silver/portfolio/{fname}", "pass2_silver_portfolio"

    # Pass 4 — gold stragglers.
    if rel.startswith("strategy/"):
        return f"gold/strategy/{rel.removeprefix('strategy/')}", "pass4_gold_stragglers"
    if rel.startswith("picks/"):
        return f"gold/picks/{rel.removeprefix('picks/')}", "pass4_gold_stragglers"
    if rel.startswith("backtest/"):
        return f"gold/backtest/{rel.removeprefix('backtest/')}", "pass4_gold_stragglers"
    if rel.startswith("narrative/"):
        return f"gold/narrative/{rel.removeprefix('narrative/')}", "pass4_gold_stragglers"
    if rel.startswith("ml/"):
        return f"gold/ml/{rel.removeprefix('ml/')}", "pass4_gold_stragglers"
    if rel.startswith("signals/"):
        return f"gold/signals/{rel.removeprefix('signals/')}", "pass4_gold_stragglers"

    # risk/ — per-file decision (B4 blocker).
    risk_split = {
        "risk/pre_trade_validator.py":     "execution/risk/pre_trade_validator.py",   # pre-trade = execution
        "risk/circuit_breaker.py":         "gold/risk/circuit_breaker.py",            # portfolio-level signal = gold
        "risk/firm_caps.py":               "gold/risk/firm_caps.py",                  # policy = gold
        "risk/account_risk_profile.py":    "gold/risk/account_risk_profile.py",       # portfolio-level = gold
    }
    if rel.startswith("risk/"):
        if rel in risk_split:
            return risk_split[rel], "pass4_risk_split"
        return f"gold/risk/{rel.removeprefix('risk/')}", "pass4_risk_default_gold"

    # aggregator/ — bronze (broker aggregation).
    if rel.startswith("aggregator/"):
        return f"bronze/aggregator/{rel.removeprefix('aggregator/')}", "pass3_bronze_aggregator"

    # Ops dirs — stay put (escape hatch).
    ops_dirs = {
        "agent", "billing", "brain", "clients", "connections", "core", "deploys",
        "engine", "gdpr", "multitenant", "notifications", "oauth", "observability",
        "ops", "pipeline", "security", "share"
    }
    top = rel.split("/", 1)[0]
    if top in ops_dirs:
        return None, "ops_stays"

    # services-level files.
    if "/" not in rel:
        return None, "services_root_stays"

    return None, "unclassified"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()

    entries: list[tuple[str, str | None, str]] = []
    for py in sorted(SERVICES.rglob("*.py")):
        rel = py.relative_to(SERVICES).as_posix()
        target, reason = classify(rel)
        entries.append((rel, target, reason))

    if args.stats:
        by_pass: dict[str, int] = {}
        moves = 0
        stays = 0
        for _rel, target, reason in entries:
            by_pass[reason] = by_pass.get(reason, 0) + 1
            if target is None:
                stays += 1
            else:
                moves += 1
        print(f"Total files: {len(entries)}")
        print(f"  Moves: {moves}")
        print(f"  Stays: {stays}")
        print()
        print("By pass / reason:")
        for k, v in sorted(by_pass.items()):
            print(f"  {k:30s} {v}")
        return 0

    print("# medallion_move_map.yaml — Phase 0.C migration input")
    print("# Generated by scripts/medallion/generate_move_map.py")
    print("# Format: per-file mapping from current path (relative to app/services/)")
    print("# to target path. Files with target: null stay in place.")
    print("#")
    print("# Consumed by scripts/medallion_migrate.py (not yet written).")
    print()
    print("moves:")
    for rel, target, reason in entries:
        if target is None:
            continue
        print(f"  - source: {rel}")
        print(f"    target: {target}")
        print(f"    pass:   {reason}")
    print()
    print("stays:")
    stays_by_reason: dict[str, list[str]] = {}
    for rel, target, reason in entries:
        if target is None:
            stays_by_reason.setdefault(reason, []).append(rel)
    for reason in sorted(stays_by_reason):
        print(f"  # {reason}: {len(stays_by_reason[reason])} files")

    return 0


if __name__ == "__main__":
    sys.exit(main())
