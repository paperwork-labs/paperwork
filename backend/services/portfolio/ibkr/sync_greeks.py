"""IB Gateway Greeks enrichment for open option positions."""

import logging
from typing import Dict

from sqlalchemy.orm import Session

from backend.models.options import Option

logger = logging.getLogger(__name__)


async def sync_option_greeks_from_gateway(db: Session, broker_account) -> Dict[str, int]:
    """Enrich open option positions with live Greeks from IB Gateway.

    Gracefully skips if Gateway is unreachable.
    """
    try:
        from backend.services.clients.ibkr_client import ibkr_client, IBKR_AVAILABLE
        if not IBKR_AVAILABLE or not ibkr_client.is_connected():
            logger.info("IB Gateway not connected — skipping Greeks enrichment")
            return {"greeks_enriched": 0, "status": "gateway_offline"}
    except ImportError:
        return {"greeks_enriched": 0, "status": "import_error"}

    try:
        from ib_insync import Option as IBOption

        options = (
            db.query(Option)
            .filter(
                Option.account_id == broker_account.id,
                Option.open_quantity != 0,
            )
            .all()
        )

        if not options:
            return {"greeks_enriched": 0}

        contracts = []
        option_map = {}
        for opt in options:
            exp_str = opt.expiry_date.strftime("%Y%m%d") if opt.expiry_date else ""
            right = "C" if (opt.option_type or "").upper() in ("CALL", "C") else "P"
            sym = opt.underlying_symbol or opt.symbol
            contract = IBOption(sym, exp_str, float(opt.strike_price), right, "SMART")
            contracts.append(contract)
            option_map[f"{sym}_{exp_str}_{opt.strike_price}_{right}"] = opt

        greeks_data = await ibkr_client.get_option_greeks(contracts)

        enriched = 0
        for gd in greeks_data:
            key = f"{gd['symbol']}_{gd['expiry']}_{gd['strike']}_{gd['right']}"
            opt = option_map.get(key)
            if not opt:
                continue
            if gd.get("delta") is not None:
                opt.delta = gd["delta"]
            if gd.get("gamma") is not None:
                opt.gamma = gd["gamma"]
            if gd.get("theta") is not None:
                opt.theta = gd["theta"]
            if gd.get("vega") is not None:
                opt.vega = gd["vega"]
            if gd.get("implied_volatility") is not None:
                opt.implied_volatility = gd["implied_volatility"]
            if gd.get("last_price") is not None:
                opt.current_price = gd["last_price"]
            enriched += 1

        db.flush()
        logger.info("Enriched %d/%d options with live Greeks", enriched, len(options))
        return {"greeks_enriched": enriched, "total_options": len(options)}
    except Exception as exc:
        logger.warning("Greeks enrichment failed: %s", exc)
        return {"greeks_enriched": 0, "error": str(exc)}
