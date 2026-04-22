"""Candidate generator framework.

Each ``CandidateGenerator`` reads the latest authoritative state
(``MarketSnapshot``) and emits ``Candidate`` rows that the validator
queue will surface for human review. A candidate becomes a
``ValidatedPick`` only after a validator promotes it.

Design notes
------------

* **One generator = one thesis.** Generators are intentionally narrow
  ("Stage 2A + RS Mansfield > 70 + within 5 ATR of pivot"). Mixing
  theses inside one generator destroys the funnel metric per thesis.
* **Stateless.** Generators do not write or hold state; they receive
  a ``Session`` and return ``GeneratedCandidate`` dataclasses. The
  orchestrator persists.
* **Idempotency.** The orchestrator de-duplicates against any
  ``Candidate`` with the same ``(symbol, generator_name,
  generator_version)`` from the same UTC trading day, so re-running a
  generator within the same day does not produce noise.
* **Pure DB inputs.** Generators may not call providers. They run after
  the nightly pipeline lands fresh ``MarketSnapshot`` rows; they read
  the snapshot, never bypass it. This keeps point-in-time correctness
  intact (per ``point-in-time-data.mdc``).

Per ``engineering.mdc``:

* Sessions are passed in by the caller; nothing here opens connections.
* ``Decimal`` is used for any score that flows into rationale; no
  ``float`` in scoring.

Medallion layer: gold. See docs/ARCHITECTURE.md and D127.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Type

from sqlalchemy.orm import Session

from backend.models.picks import Candidate, CandidateQueueState, PickAction


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Generator output type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GeneratedCandidate:
    """The pure-data output of a generator.

    ``score`` is on whatever scale the generator chooses; the validator
    queue ranks within a generator, never across generators (different
    generators can have wildly different score distributions).
    """

    symbol: str
    action_suggestion: PickAction
    score: Optional[Decimal] = None
    rationale_summary: Optional[str] = None
    signals: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Base class + registry
# ---------------------------------------------------------------------------


class CandidateGenerator(ABC):
    """Abstract base. Subclasses must set ``name`` and ``version`` and
    implement :meth:`generate`."""

    name: str = ""
    version: str = ""
    enabled_by_default: bool = True

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Concrete subclasses must declare name/version. Skip abstract
        # intermediates that explicitly opt out by leaving name empty.
        if not cls.name or not cls.version:
            return
        _register(cls)

    @abstractmethod
    def generate(self, db: Session) -> Sequence[GeneratedCandidate]:
        """Produce candidates from the current market state.

        MUST be deterministic given the same DB snapshot.
        """


_REGISTRY: Dict[str, Type[CandidateGenerator]] = {}


def _register(cls: Type[CandidateGenerator]) -> None:
    key = cls.name
    if key in _REGISTRY and _REGISTRY[key] is not cls:
        raise RuntimeError(
            f"Duplicate CandidateGenerator name: {key!r} "
            f"(existing={_REGISTRY[key].__module__}, new={cls.__module__})"
        )
    _REGISTRY[key] = cls


def registered_generators() -> Tuple[Type[CandidateGenerator], ...]:
    """Return all registered generator classes (deterministic order)."""
    return tuple(sorted(_REGISTRY.values(), key=lambda c: c.name))


def get_generator(name: str) -> Type[CandidateGenerator]:
    try:
        return _REGISTRY[name]
    except KeyError as e:
        known = ", ".join(sorted(_REGISTRY)) or "<none>"
        raise KeyError(
            f"Unknown CandidateGenerator {name!r}. Known: {known}"
        ) from e


def _clear_registry_for_tests() -> None:
    """Test-only reset hook. Do not call from production code."""
    _REGISTRY.clear()


# ---------------------------------------------------------------------------
# Persistence helper (idempotent)
# ---------------------------------------------------------------------------


def _today_utc_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _existing_candidate_today(
    db: Session, *, symbol: str, generator_name: str, generator_version: str
) -> Optional[Candidate]:
    """Return today's candidate row if one already exists for this
    (symbol, generator, version) — drives idempotency."""
    return (
        db.query(Candidate)
        .filter(
            Candidate.symbol == symbol,
            Candidate.generator_name == generator_name,
            Candidate.generator_version == generator_version,
            Candidate.generated_at >= _today_utc_start(),
        )
        .order_by(Candidate.generated_at.desc())
        .first()
    )


def persist_candidates(
    db: Session,
    generator: CandidateGenerator,
    items: Iterable[GeneratedCandidate],
) -> Dict[str, int]:
    """Persist candidates idempotently for the calling generator.

    Returns counts per outcome; the caller commits the transaction.

    The function never commits — it lets the orchestrator (or test
    harness) decide the transaction boundary, matching the project
    convention of caller-owned sessions.
    """
    if not generator.name or not generator.version:
        raise RuntimeError(
            "CandidateGenerator subclasses must set name and version "
            f"(got {generator.__class__.__name__})"
        )

    counts = {"created": 0, "skipped_duplicate": 0, "invalid": 0}

    for item in items:
        symbol = (item.symbol or "").upper().strip()
        if not symbol:
            counts["invalid"] += 1
            continue
        existing = _existing_candidate_today(
            db,
            symbol=symbol,
            generator_name=generator.name,
            generator_version=generator.version,
        )
        if existing is not None:
            counts["skipped_duplicate"] += 1
            continue

        row = Candidate(
            symbol=symbol,
            generator_name=generator.name,
            generator_version=generator.version,
            action_suggestion=item.action_suggestion,
            score=item.score,
            rationale_summary=item.rationale_summary,
            signals=item.signals or None,
            status=CandidateQueueState.DRAFT,
        )
        db.add(row)
        counts["created"] += 1

    if counts["created"]:
        db.flush()

    return counts


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


@dataclass
class GeneratorRunReport:
    """Per-generator outcome from one orchestrator pass."""

    generator: str
    version: str
    produced: int
    created: int
    skipped_duplicate: int
    invalid: int
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generator": self.generator,
            "version": self.version,
            "produced": self.produced,
            "created": self.created,
            "skipped_duplicate": self.skipped_duplicate,
            "invalid": self.invalid,
            "error": self.error,
        }


def run_all_generators(
    db: Session,
    *,
    only: Optional[Sequence[str]] = None,
) -> List[GeneratorRunReport]:
    """Run every registered generator (or only the named subset).

    Each generator runs in its own SAVEPOINT (``begin_nested``) so a
    failure rolls back only that generator's writes; successful
    generators in the same batch remain in the outer transaction. The
    caller commits once at the end.
    """
    reports: List[GeneratorRunReport] = []
    selected = registered_generators()
    if only:
        only_set = set(only)
        selected = tuple(c for c in selected if c.name in only_set)

    for cls in selected:
        gen = cls()
        items: Optional[List[GeneratedCandidate]] = None
        try:
            with db.begin_nested():
                items = list(gen.generate(db))
                counts = persist_candidates(db, gen, items)
        except Exception as e:  # noqa: BLE001 - per-generator isolation
            logger.exception(
                "candidate generator %s/%s failed: %s",
                cls.name,
                cls.version,
                e,
            )
            produced = len(items) if items is not None else 0
            reports.append(
                GeneratorRunReport(
                    generator=cls.name,
                    version=cls.version,
                    produced=produced,
                    created=0,
                    skipped_duplicate=0,
                    invalid=0,
                    error=str(e),
                )
            )
            continue

        reports.append(
            GeneratorRunReport(
                generator=cls.name,
                version=cls.version,
                produced=len(items),
                created=counts["created"],
                skipped_duplicate=counts["skipped_duplicate"],
                invalid=counts["invalid"],
            )
        )

    return reports
