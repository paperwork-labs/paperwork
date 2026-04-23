"""Unified options-chain service (broker-agnostic).

Picks the first available source for an option chain in this order:

1. IBKR gateway (if the user has an IBKR account AND the local gateway
   process is connected — dev-only for now).
2. Yahoo Finance (``yfinance``) — free, broker-agnostic, always
   available when the library is installed. Primary production source
   for Schwab / Tastytrade / "no-broker" users.

Designed to be thin: delegates all network/IO to existing client modules
(``ibkr_client.get_option_chain``, ``fetch_yfinance_options_chain``). If
other clients (Schwab, Tastytrade, Polygon, Tradier, Alpha Vantage) grow
chain methods in the future, plug them in here as additional branches
with matching priority — no caller changes required.

Observability: logs which source was tried and what succeeded. Returns
``source: "none"`` rather than an empty silent payload so callers can
surface an explicit empty state (see ``no-silent-fallback.mdc``).

Medallion layer: silver (enrichment over raw broker ingestion).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models.broker_account import AccountStatus, BrokerAccount, BrokerType

logger = logging.getLogger(__name__)


@dataclass
class _SourceResult:
    """Outcome of a single chain-source attempt."""

    name: str
    available: bool
    tried: bool
    succeeded: bool
    error: Optional[str] = None


def _empty_chain_payload() -> Dict[str, Any]:
    """Shape expected by the frontend chain renderer."""
    return {"expirations": [], "chains": {}}


# ---------------------------------------------------------------------------
# Source availability probe
# ---------------------------------------------------------------------------


def probe_sources(*, db: Session, user_id: int) -> List[Dict[str, Any]]:
    """Return a list of chain sources + whether each is currently usable.

    Shape is intentionally UI-friendly: the frontend iterates the list and
    renders an ``[Available] Name — description`` row for each, so we do
    not have to hardcode broker names in the frontend.
    """

    sources: List[Dict[str, Any]] = []

    # 1. IBKR gateway — available iff user has an IBKR broker account AND
    # the local gateway reports connected. Dev-only in practice.
    ibkr_available, ibkr_reason = _ibkr_gateway_status(db=db, user_id=user_id)
    sources.append(
        {
            "name": "ibkr_gateway",
            "label": "IB Gateway",
            "available": ibkr_available,
            "reason": ibkr_reason,
            "kind": "broker",
        }
    )

    # 2. Yahoo Finance via yfinance — free, always on when installed.
    yf_available, yf_reason = _yfinance_availability()
    sources.append(
        {
            "name": "yfinance",
            "label": "Yahoo Finance",
            "available": yf_available,
            "reason": yf_reason,
            "kind": "provider",
        }
    )

    # Future: Schwab chain API, Tastytrade SDK, Polygon, Tradier, Alpha
    # Vantage. For now these clients do not expose a chain method; see
    # PR body "Follow-ups" for scope. Listed intentionally in probe order
    # so the UI can surface them as "connect to enable" hints without code
    # changes when they land.
    return sources


def _ibkr_gateway_status(*, db: Session, user_id: int) -> tuple[bool, str]:
    """Is the IBKR gateway both connectable AND owned by this user?"""

    try:
        has_ibkr_account = (
            db.query(BrokerAccount)
            .filter(
                BrokerAccount.user_id == user_id,
                BrokerAccount.broker == BrokerType.IBKR,
                BrokerAccount.status == AccountStatus.ACTIVE,
            )
            .first()
            is not None
        )
    except Exception as e:
        logger.warning(
            "options_chain_service: IBKR account lookup failed user=%s: %s",
            user_id,
            e,
        )
        has_ibkr_account = False

    if not has_ibkr_account:
        return False, "no_ibkr_account"

    try:
        from backend.services.clients.ibkr_client import (
            IBKR_AVAILABLE,
            ibkr_client,
        )

        if not IBKR_AVAILABLE:
            return False, "ib_insync_not_installed"
        if not ibkr_client.is_connected():
            return False, "gateway_not_connected"
        return True, "connected"
    except Exception as e:
        logger.warning("options_chain_service: IBKR availability probe failed: %s", e)
        return False, "probe_error"


def _yfinance_availability() -> tuple[bool, str]:
    """yfinance is always available when importable (no API key required)."""
    try:
        import yfinance  # noqa: F401

        return True, "ready"
    except ImportError:
        return False, "yfinance_not_installed"


# ---------------------------------------------------------------------------
# Chain fetch
# ---------------------------------------------------------------------------


async def get_chain(
    symbol: str, *, user_id: int, db: Session
) -> Dict[str, Any]:
    """Fetch an options chain from the first available source.

    Returns a dict with:
        source: str          # e.g. "ibkr_gateway", "yfinance", or "none"
        expirations: list[str]
        chains: dict[str, { calls: [...], puts: [...] }]
        attempts: list[dict] # per-source trace for observability

    Never raises for "data not available" — callers render an empty state.
    Only raises on genuinely unexpected programmer errors (caught by route).
    """

    sym = (symbol or "").upper().strip()
    if not sym:
        return {
            "source": "none",
            "symbol": "",
            **_empty_chain_payload(),
            "attempts": [],
        }

    attempts: List[_SourceResult] = []

    # 1. IBKR gateway (broker-specific)
    ibkr_available, ibkr_reason = _ibkr_gateway_status(db=db, user_id=user_id)
    if ibkr_available:
        try:
            from backend.services.clients.ibkr_client import ibkr_client

            chain = await ibkr_client.get_option_chain(sym)
            if chain and chain.get("expirations"):
                logger.info(
                    "options_chain_service: source=ibkr_gateway symbol=%s "
                    "expirations=%d",
                    sym,
                    len(chain.get("expirations") or []),
                )
                attempts.append(
                    _SourceResult("ibkr_gateway", True, True, True)
                )
                return {
                    "source": "ibkr_gateway",
                    "symbol": sym,
                    "expirations": chain.get("expirations") or [],
                    "chains": chain.get("chains") or {},
                    "attempts": [a.__dict__ for a in attempts],
                }
            logger.info(
                "options_chain_service: ibkr_gateway returned empty chain "
                "for %s; trying next source",
                sym,
            )
            attempts.append(_SourceResult("ibkr_gateway", True, True, False, "empty"))
        except Exception as e:
            logger.warning(
                "options_chain_service: ibkr_gateway failed for %s: %s", sym, e
            )
            attempts.append(
                _SourceResult("ibkr_gateway", True, True, False, str(e))
            )
    else:
        attempts.append(
            _SourceResult("ibkr_gateway", False, False, False, ibkr_reason)
        )

    # 2. Yahoo Finance (provider; broker-agnostic, no key)
    yf_available, yf_reason = _yfinance_availability()
    if yf_available:
        try:
            from backend.services.market.yfinance_options_chain import (
                fetch_yfinance_options_chain,
            )

            rows = fetch_yfinance_options_chain(sym)
            if rows:
                shaped = _shape_yfinance_rows(rows)
                logger.info(
                    "options_chain_service: source=yfinance symbol=%s "
                    "rows=%d expirations=%d",
                    sym,
                    len(rows),
                    len(shaped["expirations"]),
                )
                attempts.append(_SourceResult("yfinance", True, True, True))
                return {
                    "source": "yfinance",
                    "symbol": sym,
                    **shaped,
                    "attempts": [a.__dict__ for a in attempts],
                }
            attempts.append(
                _SourceResult("yfinance", True, True, False, "empty")
            )
        except Exception as e:
            logger.warning(
                "options_chain_service: yfinance failed for %s: %s", sym, e
            )
            attempts.append(
                _SourceResult("yfinance", True, True, False, str(e))
            )
    else:
        attempts.append(
            _SourceResult("yfinance", False, False, False, yf_reason)
        )

    logger.info(
        "options_chain_service: source=none symbol=%s attempts=%s",
        sym,
        [a.__dict__ for a in attempts],
    )
    return {
        "source": "none",
        "symbol": sym,
        **_empty_chain_payload(),
        "attempts": [a.__dict__ for a in attempts],
    }


def _shape_yfinance_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Reshape flat yfinance rows into { expirations, chains } for the UI."""

    chains: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for row in rows:
        exp = row.get("expiry")
        if exp is None:
            continue
        try:
            exp_key = exp.isoformat()
        except Exception:
            exp_key = str(exp)
        bucket = chains.setdefault(exp_key, {"calls": [], "puts": []})
        entry = {
            "strike": float(row["strike"]) if row.get("strike") is not None else None,
            "last": None,
            "bid": float(row["bid"]) if row.get("bid") is not None else None,
            "ask": float(row["ask"]) if row.get("ask") is not None else None,
            "iv": float(row["implied_vol"]) if row.get("implied_vol") is not None else None,
            "delta": float(row["delta"]) if row.get("delta") is not None else None,
            "gamma": float(row["gamma"]) if row.get("gamma") is not None else None,
            "theta": float(row["theta"]) if row.get("theta") is not None else None,
            "vega": float(row["vega"]) if row.get("vega") is not None else None,
            "volume": int(row["volume"]) if row.get("volume") is not None else None,
            "open_interest": (
                int(row["open_interest"]) if row.get("open_interest") is not None else None
            ),
        }
        if entry["strike"] is None:
            continue
        if (row.get("option_type") or "").upper() == "CALL":
            bucket["calls"].append(entry)
        else:
            bucket["puts"].append(entry)

    expirations = sorted(chains.keys())
    return {"expirations": expirations, "chains": chains}
