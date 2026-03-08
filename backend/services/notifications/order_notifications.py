"""Order-related Discord notifications."""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from discord_webhook import DiscordWebhook, DiscordEmbed

from backend.config import settings

logger = logging.getLogger(__name__)


def _get_trade_webhook() -> Optional[str]:
    return getattr(settings, "DISCORD_WEBHOOK_PORTFOLIO_DIGEST", None) or getattr(
        settings, "DISCORD_WEBHOOK_SIGNALS", None
    )


def _get_alerts_webhook() -> Optional[str]:
    return getattr(settings, "DISCORD_WEBHOOK_SYSTEM_STATUS", None) or getattr(
        settings, "DISCORD_WEBHOOK_SIGNALS", None
    )


async def send_trade_execution(order_data: Dict[str, Any]) -> None:
    """Send a Discord embed when an order is filled."""
    webhook_url = _get_trade_webhook()
    if not webhook_url:
        logger.debug("No Discord webhook configured for trade notifications")
        return

    side = order_data.get("side", "unknown").upper()
    symbol = order_data.get("symbol", "???")
    qty = order_data.get("filled_quantity", order_data.get("quantity", 0))
    price = order_data.get("filled_avg_price", "N/A")
    status = order_data.get("status", "unknown")
    source = order_data.get("source", "manual")

    color = 0x22C55E if side == "BUY" else 0xEF4444

    side_emoji = "🟢" if side == "BUY" else "🔴"
    embed = DiscordEmbed(
        title=f"{side_emoji} {side} {symbol}",
        description=f"Order **{status.upper()}** for {symbol}",
        color=color,
    )
    embed.add_embed_field(name="Quantity", value=str(qty), inline=True)
    embed.add_embed_field(
        name="Avg Price",
        value=f"${price}" if isinstance(price, (int, float)) else str(price),
        inline=True,
    )
    embed.add_embed_field(name="Status", value=status.upper(), inline=True)
    embed.add_embed_field(name="Source", value=source.title(), inline=True)
    embed.set_footer(text="AxiomFolio • Trade Execution")
    embed.set_timestamp()

    try:
        webhook = DiscordWebhook(url=webhook_url)
        webhook.add_embed(embed)
        webhook.execute()
    except Exception as e:
        logger.warning("Failed to send trade notification to Discord: %s", e)


async def send_risk_alert(
    violation_msg: str, order_data: Dict[str, Any]
) -> None:
    """Send a Discord alert when a risk gate blocks an order."""
    webhook_url = _get_alerts_webhook()
    if not webhook_url:
        return

    embed = DiscordEmbed(
        title="⚠️ Risk Gate Triggered",
        description=violation_msg,
        color=0xF59E0B,
    )
    embed.add_embed_field(
        name="Symbol", value=order_data.get("symbol", "???"), inline=True
    )
    embed.add_embed_field(
        name="Side", value=order_data.get("side", "?").upper(), inline=True
    )
    embed.add_embed_field(
        name="Quantity", value=str(order_data.get("quantity", 0)), inline=True
    )
    embed.set_footer(text="AxiomFolio • Risk Management")
    embed.set_timestamp()

    try:
        webhook = DiscordWebhook(url=webhook_url)
        webhook.add_embed(embed)
        webhook.execute()
    except Exception as e:
        logger.warning("Failed to send risk alert to Discord: %s", e)


async def send_order_summary(
    orders: List[Dict[str, Any]], period: str = "daily"
) -> None:
    """Send a periodic order summary digest to Discord."""
    webhook_url = _get_trade_webhook()
    if not webhook_url or not orders:
        return

    filled = [o for o in orders if o.get("status") == "filled"]
    cancelled = [o for o in orders if o.get("status") == "cancelled"]
    errored = [o for o in orders if o.get("status") in ("error", "rejected")]

    summary_lines = [
        f"**Filled:** {len(filled)}",
        f"**Cancelled:** {len(cancelled)}",
        f"**Errors:** {len(errored)}",
        f"**Total:** {len(orders)}",
    ]

    embed = DiscordEmbed(
        title=f"📊 {period.title()} Order Summary",
        description="\n".join(summary_lines),
        color=0x3B82F6,
    )
    embed.set_footer(text="AxiomFolio • Order Summary")
    embed.set_timestamp()

    try:
        webhook = DiscordWebhook(url=webhook_url)
        webhook.add_embed(embed)
        webhook.execute()
    except Exception as e:
        logger.warning("Failed to send order summary to Discord: %s", e)
