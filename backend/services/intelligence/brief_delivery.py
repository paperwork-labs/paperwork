"""Brief delivery via Discord embeds."""

from __future__ import annotations

import logging
from typing import Any

from backend.config import settings

logger = logging.getLogger(__name__)

REGIME_EMOJI = {
    "R1": "\U0001f7e2",  # green circle
    "R2": "\U0001f7e1",  # yellow circle
    "R3": "\U0001f7e0",  # orange circle
    "R4": "\U0001f534",  # red circle
    "R5": "\u26d4",      # no entry
}


async def deliver_daily_digest_discord(brief: dict[str, Any]) -> bool:
    """Send the daily digest as a Discord embed."""
    try:
        from discord_webhook import DiscordWebhook, DiscordEmbed
    except ImportError:
        logger.warning("discord-webhook not installed, skipping delivery")
        return False

    webhook_url = settings.DISCORD_WEBHOOK_MORNING_BREW
    if not webhook_url:
        logger.info("No DISCORD_WEBHOOK_MORNING_BREW configured, skipping")
        return False

    regime = brief.get("regime", {})
    state = regime.get("state", "UNKNOWN")
    score = regime.get("score", 0)
    emoji = REGIME_EMOJI.get(state, "")

    embed = DiscordEmbed(
        title=f"{emoji} Daily Intelligence Brief — {brief.get('as_of', 'today')}",
        color=0x22C55E if state in ("R1", "R2") else 0xEAB308 if state == "R3" else 0xDC2626,
    )

    regime_text = f"**{state}** (Score: {score:.2f})"
    if regime.get("changed"):
        regime_text += f"\n\u26a0\ufe0f Changed from {regime.get('previous_state')}"
    if regime.get("vix_spot"):
        regime_text += f"\nVIX: {regime['vix_spot']:.1f}"
    if regime.get("pct_above_200d"):
        regime_text += f" | %Above 200D: {regime['pct_above_200d']:.0f}%"
    embed.add_embed_field(name="Market Regime", value=regime_text, inline=False)

    breadth = brief.get("breadth", {})
    if breadth.get("total"):
        embed.add_embed_field(
            name="Breadth",
            value=f"Above 50D: {breadth.get('above_50d_pct', 0):.0f}% | Above 200D: {breadth.get('above_200d_pct', 0):.0f}%",
            inline=False,
        )

    transitions = brief.get("stage_transitions", [])
    if transitions:
        lines = [f"`{t['symbol']}` {t['from_stage']} \u2192 {t['to_stage']}" for t in transitions[:8]]
        if len(transitions) > 8:
            lines.append(f"...and {len(transitions) - 8} more")
        embed.add_embed_field(name="Stage Transitions", value="\n".join(lines), inline=False)

    exit_alerts = brief.get("exit_alerts", [])
    if exit_alerts:
        lines = [f"\u26a0\ufe0f `{a['symbol']}` Stage {a['stage']}" for a in exit_alerts[:5]]
        embed.add_embed_field(name="Exit Alerts", value="\n".join(lines), inline=False)

    dist = brief.get("stage_distribution", {})
    if dist:
        parts = [f"{k}: {v}" for k, v in sorted(dist.items())]
        embed.add_embed_field(name="Stage Distribution", value=" | ".join(parts), inline=False)

    embed.set_footer(text=f"AxiomFolio Intelligence | {brief.get('snapshot_count', 0)} symbols")
    embed.set_timestamp()

    try:
        webhook = DiscordWebhook(url=webhook_url)
        webhook.add_embed(embed)
        webhook.execute()
        logger.info("Daily digest delivered to Discord")
        return True
    except Exception as e:
        logger.error("Discord delivery failed: %s", e)
        return False


async def deliver_weekly_brief_discord(brief: dict[str, Any]) -> bool:
    """Send the weekly brief as a Discord embed."""
    try:
        from discord_webhook import DiscordWebhook, DiscordEmbed
    except ImportError:
        logger.warning("discord-webhook not installed, skipping delivery")
        return False

    webhook_url = settings.DISCORD_WEBHOOK_MORNING_BREW
    if not webhook_url:
        logger.info("No DISCORD_WEBHOOK_MORNING_BREW configured, skipping")
        return False

    regime_trend = brief.get("regime_trend", [])
    latest_state = regime_trend[-1]["state"] if regime_trend else "UNKNOWN"
    emoji = REGIME_EMOJI.get(latest_state, "")

    embed = DiscordEmbed(
        title=f"{emoji} Weekly Strategy Brief — {brief.get('as_of', 'today')}",
        color=0x3B82F6,
    )

    if regime_trend:
        states = [r["state"] for r in regime_trend]
        embed.add_embed_field(
            name="Regime Trend",
            value=" \u2192 ".join(dict.fromkeys(states)),
            inline=False,
        )

    top_picks = brief.get("top_picks", {})
    buy_list = top_picks.get("buy", [])
    if buy_list:
        embed.add_embed_field(
            name=f"Buy List ({len(buy_list)})",
            value=", ".join(f"`{p['symbol']}`" for p in buy_list[:10]),
            inline=True,
        )

    short_list = top_picks.get("short", [])
    if short_list:
        embed.add_embed_field(
            name=f"Short List ({len(short_list)})",
            value=", ".join(f"`{p['symbol']}`" for p in short_list[:10]),
            inline=True,
        )

    sector_analysis = brief.get("sector_analysis", [])
    if sector_analysis:
        top3 = sector_analysis[:3]
        bottom3 = sector_analysis[-3:] if len(sector_analysis) > 3 else []
        lines = [f"\U0001f4c8 {s['sector']}: RS {s['avg_rs']:+.1f}" for s in top3]
        if bottom3:
            lines.extend([f"\U0001f4c9 {s['sector']}: RS {s['avg_rs']:+.1f}" for s in bottom3])
        embed.add_embed_field(name="Sector Rotation", value="\n".join(lines), inline=False)

    embed.set_footer(text=f"AxiomFolio Intelligence | {brief.get('snapshot_count', 0)} symbols")
    embed.set_timestamp()

    try:
        webhook = DiscordWebhook(url=webhook_url)
        webhook.add_embed(embed)
        webhook.execute()
        logger.info("Weekly brief delivered to Discord")
        return True
    except Exception as e:
        logger.error("Discord delivery failed: %s", e)
        return False
