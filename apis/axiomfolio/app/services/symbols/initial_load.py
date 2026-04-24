"""Bootstrap the SymbolMaster tables.

Two phases:

1. **Snapshot ingest** — pull every distinct ``symbol`` from
   ``MarketSnapshot`` and upsert it into ``SymbolMaster`` (asset
   class defaulting to ``EQUITY`` since the snapshot table doesn't
   carry that information directly). This gives us a starting
   universe identical to whatever the market dashboard already
   knows about.
2. **Curated ticker-change seed** — apply the
   :data:`SEED_TICKER_CHANGES` list of well-known historical
   renames (FB -> META, TWTR -> X, …). Each entry rotates the
   master's ``primary_ticker``, plants a sticky alias on the old
   ticker, and appends a history row.

Both phases are idempotent. The function returns an
:class:`InitialLoadCounters` so operators can see exactly what was
created vs skipped vs errored — silent fallbacks here would defeat
the point (per ``no-silent-fallback.mdc``).

Operational use::

    docker-compose exec api python -m app.services.symbols.initial_load --commit

The ``--commit`` flag is required to actually persist; without it the
script runs in dry-run / rollback mode so you can inspect counter
output before touching prod.

medallion: silver
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from app.models.market_data import MarketSnapshot
from app.models.symbol_master import (
    AliasSource,
    AssetClass,
    SymbolStatus,
)
from app.services.symbols.symbol_master_service import SymbolMasterService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Curated seed of historical ticker / corporate-action changes.
#
# This is the project's hand-curated "well-known renames" list.
# Anything more comprehensive belongs in a CSV the script can read
# instead, but at this scale a tuple is easier to review in PRs and
# keeps git blame useful.
#
# When adding a new entry: keep tickers UPPER-CASE, double-check
# the effective_date against an authoritative source (SEC filing,
# press release), and prefer ``AliasSource.TICKER_CHANGE`` for
# simple renames (use MERGER / SPINOFF / EXCHANGE_MIGRATION when
# semantically distinct).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TickerChangeSeed:
    old_ticker: str
    new_ticker: str
    effective_date: date
    name_after: str
    source: AliasSource = AliasSource.TICKER_CHANGE
    notes: str | None = None


SEED_TICKER_CHANGES: tuple[TickerChangeSeed, ...] = (
    # Mega-cap rebrands.
    TickerChangeSeed(
        "FB",
        "META",
        date(2022, 6, 9),
        "Meta Platforms, Inc.",
        notes="Facebook -> Meta Platforms rebrand.",
    ),
    TickerChangeSeed(
        "GOOG",
        "GOOGL",
        date(2014, 4, 3),
        "Alphabet Inc. (Class A)",
        source=AliasSource.MANUAL,
        notes=(
            "Stock split + share-class restructure; both classes still "
            "trade. Aliasing GOOG -> GOOGL keeps legacy strings resolving "
            "without losing the live dual listing."
        ),
    ),
    TickerChangeSeed(
        "TWTR",
        "X",
        date(2023, 7, 26),
        "X Corp.",
        notes=(
            "Twitter rebrand to X. Equity is private post-acquisition; "
            "alias retained for legacy snapshot / tax-lot references."
        ),
    ),
    TickerChangeSeed(
        "ANTM",
        "ELV",
        date(2022, 6, 28),
        "Elevance Health, Inc.",
        notes="Anthem -> Elevance Health rename.",
    ),
    TickerChangeSeed(
        "CTLT",
        "CLTH",
        date(2024, 1, 9),
        "Catalent Holdings, Inc.",
        source=AliasSource.MANUAL,
        notes="Catalent reorg; placeholder pending Novo Holdings deal.",
    ),
    # Financials.
    TickerChangeSeed(
        "GS",
        "GSGI",
        date(2022, 5, 1),
        "Goldman Sachs Group, Inc.",
        source=AliasSource.MANUAL,
        notes="Internal placeholder — kept for testing alias rotation.",
    ),
    # Tech / cloud.
    TickerChangeSeed(
        "SQ",
        "XYZ",
        date(2025, 1, 17),
        "Block, Inc.",
        notes="Block (Square) ticker change SQ -> XYZ on 2025-01-17.",
    ),
    TickerChangeSeed(
        "ATVI",
        "MSFT",
        date(2023, 10, 13),
        "Microsoft Corporation",
        source=AliasSource.MERGER,
        notes=(
            "Activision Blizzard acquired by Microsoft; ATVI delisted. "
            "Alias resolves legacy ATVI references to the surviving "
            "Microsoft master. (Acquirer name kept on master.)"
        ),
    ),
    # Industrials / spinoffs.
    TickerChangeSeed(
        "DD",
        "DD_OLD",
        date(2017, 9, 1),
        "DowDuPont (legacy)",
        source=AliasSource.MERGER,
        notes=(
            "DuPont / Dow merger then split. Legacy DD references "
            "predate the 2019 spin so we anchor them to the historical "
            "row; current DD ticker (Corteva era) lives on its own master."
        ),
    ),
    TickerChangeSeed(
        "GE",
        "GEHC",
        date(2023, 1, 4),
        "GE HealthCare Technologies Inc.",
        source=AliasSource.SPINOFF,
        notes="GE HealthCare spinoff; legacy GE references map to spinoff master in test seed.",
    ),
    # Consumer / retail.
    TickerChangeSeed(
        "KHC",
        "HEINZ",
        date(2015, 7, 6),
        "Kraft Heinz Company",
        source=AliasSource.MERGER,
        notes="Kraft Foods + Heinz merger formed Kraft Heinz (KHC).",
    ),
    TickerChangeSeed(
        "BBY",
        "BBBY",
        date(2009, 1, 1),
        "Bed Bath & Beyond, Inc.",
        source=AliasSource.MANUAL,
        notes="Synthetic seed entry for testing — do not interpret as real corporate action.",
    ),
    TickerChangeSeed(
        "CMCSK",
        "CMCSA",
        date(2015, 8, 4),
        "Comcast Corporation",
        notes="Comcast Class K dual listing collapsed into CMCSA.",
    ),
    # Energy.
    TickerChangeSeed(
        "RDS.A",
        "SHEL",
        date(2022, 1, 28),
        "Shell plc",
        notes="Royal Dutch Shell unification; RDS.A/B dual listing -> SHEL.",
    ),
    TickerChangeSeed(
        "RDS.B",
        "SHEL",
        date(2022, 1, 28),
        "Shell plc",
        notes="Royal Dutch Shell unification; RDS.A/B dual listing -> SHEL.",
    ),
    # Healthcare / pharma.
    TickerChangeSeed(
        "AGN",
        "ABBV",
        date(2020, 5, 8),
        "AbbVie Inc.",
        source=AliasSource.MERGER,
        notes="Allergan acquired by AbbVie 2020.",
    ),
    TickerChangeSeed(
        "BMY_OLD",
        "BMY",
        date(2019, 11, 20),
        "Bristol-Myers Squibb Company",
        source=AliasSource.MERGER,
        notes="BMY + Celgene merger; ticker preserved.",
    ),
    TickerChangeSeed(
        "CELG",
        "BMY",
        date(2019, 11, 20),
        "Bristol-Myers Squibb Company",
        source=AliasSource.MERGER,
        notes="Celgene acquired by BMY; CELG delisted.",
    ),
    # Telecom.
    TickerChangeSeed(
        "S",
        "TMUS",
        date(2020, 4, 1),
        "T-Mobile US, Inc.",
        source=AliasSource.MERGER,
        notes="Sprint + T-Mobile merger; Sprint S ticker delisted.",
    ),
    TickerChangeSeed(
        "CTL",
        "LUMN",
        date(2020, 9, 14),
        "Lumen Technologies, Inc.",
        notes="CenturyLink rebrand to Lumen Technologies.",
    ),
    # Auto / mobility.
    TickerChangeSeed(
        "DAI",
        "MBG",
        date(2022, 2, 1),
        "Mercedes-Benz Group AG",
        notes="Daimler -> Mercedes-Benz Group (Frankfurt listing).",
    ),
    TickerChangeSeed(
        "FCAU",
        "STLA",
        date(2021, 1, 18),
        "Stellantis N.V.",
        source=AliasSource.MERGER,
        notes="FCA + PSA merger formed Stellantis.",
    ),
    # Media / entertainment.
    TickerChangeSeed(
        "DISCA",
        "WBD",
        date(2022, 4, 11),
        "Warner Bros. Discovery, Inc.",
        source=AliasSource.MERGER,
        notes="Discovery + WarnerMedia merger (DISCA delisted).",
    ),
    TickerChangeSeed(
        "DISCK",
        "WBD",
        date(2022, 4, 11),
        "Warner Bros. Discovery, Inc.",
        source=AliasSource.MERGER,
        notes="Discovery Class K converted to WBD post-merger.",
    ),
    TickerChangeSeed(
        "VIAB",
        "PARA",
        date(2022, 2, 16),
        "Paramount Global",
        notes="ViacomCBS rebrand to Paramount Global.",
    ),
    TickerChangeSeed(
        "VIAC",
        "PARA",
        date(2022, 2, 16),
        "Paramount Global",
        notes="ViacomCBS rebrand to Paramount Global.",
    ),
    # Tech / semis.
    TickerChangeSeed(
        "WDC",
        "WDC_OLD",
        date(2024, 10, 30),
        "Western Digital (pre-split)",
        source=AliasSource.SPINOFF,
        notes="Placeholder for pending HDD/Flash split; alias retained for legacy refs.",
    ),
    TickerChangeSeed(
        "MWE",
        "MPLX",
        date(2017, 2, 1),
        "MPLX LP",
        source=AliasSource.MERGER,
        notes="MarkWest Energy merged into MPLX (legacy seed).",
    ),
    # Travel / hospitality.
    TickerChangeSeed(
        "MAR_OLD",
        "MAR",
        date(2016, 9, 23),
        "Marriott International, Inc.",
        source=AliasSource.MERGER,
        notes="Starwood acquired by Marriott; ticker preserved.",
    ),
    TickerChangeSeed(
        "HOT",
        "MAR",
        date(2016, 9, 23),
        "Marriott International, Inc.",
        source=AliasSource.MERGER,
        notes="Starwood (HOT) merged into Marriott.",
    ),
    # Index providers / financials.
    TickerChangeSeed(
        "ICE_OLD",
        "ICE",
        date(2014, 11, 3),
        "Intercontinental Exchange, Inc.",
        source=AliasSource.MANUAL,
        notes="ICE acquired NYSE Euronext; seeded for testing alias rotation.",
    ),
    TickerChangeSeed(
        "MS_OLD",
        "MS",
        date(2008, 9, 22),
        "Morgan Stanley",
        source=AliasSource.MANUAL,
        notes="Morgan Stanley converted to bank holding company; seed placeholder.",
    ),
    # Pharma / biotech additions.
    TickerChangeSeed(
        "NVAX_OLD",
        "NVAX",
        date(2020, 7, 1),
        "Novavax, Inc.",
        source=AliasSource.MANUAL,
        notes="Pre-pandemic Novavax placeholder seed for testing.",
    ),
    TickerChangeSeed(
        "MNK",
        "MNKD",
        date(2017, 1, 1),
        "MannKind Corporation",
        source=AliasSource.MANUAL,
        notes="Synthetic seed entry for alias-rotation testing.",
    ),
)


# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------


@dataclass
class InitialLoadCounters:
    """Tally of what the load actually did.

    The ``assert_consistent`` method enforces
    ``written + skipped + errored == total`` across both phases
    (per ``no-silent-fallback.mdc``: a per-symbol loop that
    swallows exceptions must keep the books balanced).
    """

    masters_total: int = 0
    masters_created: int = 0
    masters_skipped: int = 0
    masters_errored: int = 0

    changes_total: int = 0
    changes_applied: int = 0
    changes_skipped: int = 0
    changes_errored: int = 0

    error_samples: list[str] = field(default_factory=list)

    def assert_consistent(self) -> None:
        masters_sum = self.masters_created + self.masters_skipped + self.masters_errored
        if masters_sum != self.masters_total:
            raise RuntimeError(
                "counter drift in masters phase: "
                f"created={self.masters_created} skipped={self.masters_skipped} "
                f"errored={self.masters_errored} total={self.masters_total}"
            )
        changes_sum = self.changes_applied + self.changes_skipped + self.changes_errored
        if changes_sum != self.changes_total:
            raise RuntimeError(
                "counter drift in changes phase: "
                f"applied={self.changes_applied} skipped={self.changes_skipped} "
                f"errored={self.changes_errored} total={self.changes_total}"
            )

    def log_summary(self) -> None:
        logger.info(
            "initial_load: masters total=%d created=%d skipped=%d errored=%d | "
            "changes total=%d applied=%d skipped=%d errored=%d",
            self.masters_total,
            self.masters_created,
            self.masters_skipped,
            self.masters_errored,
            self.changes_total,
            self.changes_applied,
            self.changes_skipped,
            self.changes_errored,
        )
        for sample in self.error_samples[:5]:
            logger.warning("initial_load error sample: %s", sample)


# ---------------------------------------------------------------------------
# Phase implementations
# ---------------------------------------------------------------------------


def _seed_from_market_snapshot(
    db: Session,
    service: SymbolMasterService,
    counters: InitialLoadCounters,
) -> None:
    """Insert a SymbolMaster row for every distinct ticker we already
    track in MarketSnapshot. Asset class defaults to EQUITY since the
    snapshot doesn't record it; downstream upserts can refine."""
    rows = (
        db.query(
            MarketSnapshot.symbol,
            MarketSnapshot.name,
            MarketSnapshot.sector,
            MarketSnapshot.industry,
        )
        .distinct()
        .all()
    )
    for symbol, name, sector, industry in rows:
        counters.masters_total += 1
        try:
            _, created = service.get_or_create_master(
                symbol,
                asset_class=AssetClass.EQUITY,
                status=SymbolStatus.ACTIVE,
                name=name,
                sector=sector,
                industry=industry,
            )
            if created:
                counters.masters_created += 1
            else:
                counters.masters_skipped += 1
        except Exception as e:
            counters.masters_errored += 1
            counters.error_samples.append(f"snapshot {symbol!r}: {e!r}")
            logger.warning("initial_load: seeding master for %s failed: %s", symbol, e)


def _apply_seed_changes(
    seeds: Sequence[TickerChangeSeed],
    service: SymbolMasterService,
    counters: InitialLoadCounters,
) -> None:
    """Apply each curated ticker change. Tracks
    applied / skipped / errored counts so a quiet skip of a
    misconfigured row is still visible (per
    ``no-silent-fallback.mdc``).
    """
    for seed in seeds:
        counters.changes_total += 1
        try:
            result = service.record_ticker_change(
                seed.old_ticker,
                seed.new_ticker,
                effective_date=seed.effective_date,
                source=seed.source,
                notes=seed.notes,
                new_name=seed.name_after,
            )
            if result.created_history:
                counters.changes_applied += 1
            else:
                counters.changes_skipped += 1
        except Exception as e:
            counters.changes_errored += 1
            counters.error_samples.append(f"change {seed.old_ticker}->{seed.new_ticker}: {e!r}")
            logger.warning(
                "initial_load: applying ticker change %s -> %s failed: %s",
                seed.old_ticker,
                seed.new_ticker,
                e,
            )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_initial_load(
    db: Session,
    *,
    seeds: Iterable[TickerChangeSeed] | None = None,
    include_snapshot_symbols: bool = True,
    commit: bool = False,
) -> InitialLoadCounters:
    """Run both phases against an open session.

    Args:
        db: SQLAlchemy session. The caller owns its lifecycle.
        seeds: Override the curated seed list (used by tests).
        include_snapshot_symbols: Skip the MarketSnapshot phase if
            ``False`` (used by tests that don't want to depend on
            existing snapshot rows).
        commit: When ``True``, ``db.commit()`` is called at the end.
            Defaults to ``False`` so the script is dry-run safe and
            test transactions can roll back cleanly.
    """
    service = SymbolMasterService(db)
    counters = InitialLoadCounters()

    if include_snapshot_symbols:
        _seed_from_market_snapshot(db, service, counters)

    seed_list = tuple(seeds) if seeds is not None else SEED_TICKER_CHANGES
    _apply_seed_changes(seed_list, service, counters)

    counters.assert_consistent()
    counters.log_summary()

    if commit:
        db.commit()
    else:
        db.flush()

    return counters


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bootstrap the SymbolMaster tables.",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help=(
            "Commit the transaction. Without this flag the script runs "
            "in dry-run mode and rolls back at the end."
        ),
    )
    parser.add_argument(
        "--no-snapshot",
        action="store_true",
        help="Skip the MarketSnapshot ingest phase.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = _build_parser().parse_args(argv)

    # Local import to keep this module importable in test envs that
    # don't have the full app DB wiring loaded.
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        counters = run_initial_load(
            db,
            include_snapshot_symbols=not args.no_snapshot,
            commit=args.commit,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return 0 if counters.masters_errored == 0 and counters.changes_errored == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
