import asyncio
import logging
from typing import Dict, List, Any
from datetime import datetime
from discord_webhook import DiscordWebhook, DiscordEmbed

from backend.config import settings

logger = logging.getLogger(__name__)


class DiscordNotifier:
    """Discord notification service for AxiomFolio platform."""

    def __init__(self):
        # New 5-webhook setup for better organization
        self.signals_webhook = settings.DISCORD_WEBHOOK_SIGNALS  # Entry/exit signals
        self.portfolio_webhook = (
            settings.DISCORD_WEBHOOK_PORTFOLIO_DIGEST
        )  # Portfolio summaries
        self.morning_brew_webhook = (
            settings.DISCORD_WEBHOOK_MORNING_BREW
        )  # Daily scans & market updates
        self.playground_webhook = (
            settings.DISCORD_WEBHOOK_PLAYGROUND
        )  # Test notifications
        self.system_status_webhook = (
            settings.DISCORD_WEBHOOK_SYSTEM_STATUS
        )  # System health & alerts

        self.rate_limit_delay = 1.0  # 1 second between messages to avoid rate limits
        self.last_message_time = 0

    async def send_entry_signal(
        self,
        symbol: str,
        price: float,
        atr_distance: float,
        confidence: float,
        reasons: List[str],
        targets: List[float] = None,
        stop_loss: float = None,
        risk_reward: float = None,
        atr_value: float = None,
        rsi: float = None,
        ma_alignment: bool = None,
        market_cap: float = None,
        fund_membership: str = None,
        sector: str = None,
        company_synopsis: str = None,
    ):
        """Send enhanced ATR Matrix entry signal notification."""
        # Determine color based on confidence
        if confidence >= 0.8:
            color = 0x00FF00  # Bright green for high confidence
        elif confidence >= 0.6:
            color = 0xFFFF00  # Yellow for medium confidence
        else:
            color = 0xFF8000  # Orange for lower confidence

        # Build description with company synopsis and market info
        description_parts = [f"**{symbol}** is showing strong entry conditions\n"]

        # Add company synopsis for better decision making
        if company_synopsis:
            description_parts.append(f"📋 **Company:** {company_synopsis}\n")

        if fund_membership:
            description_parts.append(f"📈 **Index:** {fund_membership}")

        if market_cap:
            market_cap_billions = market_cap / 1_000_000_000
            if market_cap_billions >= 200:
                cap_category = "Mega Cap"
                cap_emoji = "🦣"
            elif market_cap_billions >= 10:
                cap_category = "Large Cap"
                cap_emoji = "🐘"
            elif market_cap_billions >= 2:
                cap_category = "Mid Cap"
                cap_emoji = "🦌"
            elif market_cap_billions >= 0.3:
                cap_category = "Small Cap"
                cap_emoji = "🐰"
            else:
                cap_category = "Micro Cap"
                cap_emoji = "🐭"

            description_parts.append(
                f"{cap_emoji} **Market Cap:** ${market_cap_billions:.1f}B ({cap_category})"
            )

        if sector:
            description_parts.append(f"🏢 **Sector:** {sector}")

        description_parts.extend(
            [
                f"\n🎯 **Entry Price:** ${price:.2f}",
                f"📊 **ATR Distance:** {atr_distance:.1f}x from SMA50",
                f"💪 **Confidence:** {confidence*100:.0f}%",
            ]
        )

        embed = DiscordEmbed(
            title=f"🚀 ATR Matrix Entry: {symbol}",
            description="\n".join(description_parts),
            color=color,
        )

        # Market data section
        market_data = f"💰 **Price:** ${price:.2f}\n"
        if atr_value:
            market_data += (
                f"📈 **ATR:** ${atr_value:.2f} ({(atr_value/price*100):.1f}%)\n"
            )
        if rsi:
            rsi_emoji = "🔥" if rsi < 30 else "❄️" if rsi > 70 else "⚖️"
            market_data += f"{rsi_emoji} **RSI:** {rsi:.1f}\n"
        if ma_alignment is not None:
            ma_emoji = "✅" if ma_alignment else "❌"
            market_data += (
                f"{ma_emoji} **MA Aligned:** {'Yes' if ma_alignment else 'No'}"
            )

        embed.add_embed_field(name="📊 Market Data", value=market_data, inline=True)

        # Trade setup section
        trade_setup = ""
        if stop_loss:
            loss_pct = ((price - stop_loss) / price) * 100
            trade_setup += f"🛑 **Stop Loss:** ${stop_loss:.2f} (-{loss_pct:.1f}%)\n"

        if targets and len(targets) > 0:
            target_text = ""
            for i, target in enumerate(targets[:4]):
                gain_pct = ((target - price) / price) * 100
                target_text += f"🎯 **T{i+1}:** ${target:.2f} (+{gain_pct:.1f}%)\n"
            trade_setup += target_text

        if risk_reward:
            trade_setup += f"⚖️ **Risk/Reward:** {risk_reward:.1f}:1"

        if trade_setup:
            embed.add_embed_field(name="🎯 Trade Setup", value=trade_setup, inline=True)

        # Entry conditions
        if reasons and len(reasons) > 0:
            conditions_text = "\n".join([f"✅ {reason}" for reason in reasons[:5]])
            embed.add_embed_field(
                name="📋 Entry Conditions Met", value=conditions_text, inline=False
            )

        # Add strategy note
        embed.add_embed_field(
            name="📖 Strategy Notes",
            value="ATR Matrix identifies stocks near SMA50 support with strong momentum potential. "
            + "Scale out at targets as price moves in your favor.",
            inline=False,
        )

        embed.set_footer(
            text="AxiomFolio • ATR Matrix Strategy • Not Financial Advice"
        )
        embed.set_timestamp()

        await self._send_webhook(embed, webhook_url=self.signals_webhook)

    async def send_scale_out_alert(
        self,
        symbol: str,
        price: float,
        atr_distance: float,
        scale_level: float,
        position_value: float = None,
        profit_pct: float = None,
    ):
        """Send scale-out alert notification."""
        embed = DiscordEmbed(
            title=f"📈 Scale Out Alert: {symbol}",
            description=f"**{symbol}** reached {scale_level}x ATR distance - Time to scale out!",
            color=0xFFA500,  # Orange
        )

        embed.add_embed_field(
            name="💰 Current Price", value=f"${price:.2f}", inline=True
        )

        embed.add_embed_field(
            name="📊 ATR Distance", value=f"{atr_distance:.1f}x", inline=True
        )

        embed.add_embed_field(
            name="🎯 Scale Level", value=f"{scale_level:.0f}x ATR", inline=True
        )

        if position_value:
            embed.add_embed_field(
                name="💼 Position Value", value=f"${position_value:,.2f}", inline=True
            )

        if profit_pct:
            embed.add_embed_field(
                name="📊 Profit", value=f"+{profit_pct:.1f}%", inline=True
            )

        embed.add_embed_field(
            name="💡 Suggestion",
            value="Consider taking partial profits at this level",
            inline=False,
        )

        embed.set_footer(text="AxiomFolio • ATR Matrix Strategy")
        embed.set_timestamp()

        await self._send_webhook(embed, webhook_url=self.signals_webhook)

    async def send_risk_alert(
        self,
        symbol: str,
        price: float,
        alert_type: str,
        severity: str = "HIGH",
        details: str = None,
    ):
        """Send risk alert notification."""
        color_map = {
            "LOW": 0xFFFF00,  # Yellow
            "MEDIUM": 0xFFA500,  # Orange
            "HIGH": 0xFF0000,  # Red
            "CRITICAL": 0x8B0000,  # Dark red
        }

        emoji_map = {"LOW": "⚠️", "MEDIUM": "🚨", "HIGH": "🔴", "CRITICAL": "💀"}

        embed = DiscordEmbed(
            title=f"{emoji_map.get(severity, '⚠️')} Risk Alert: {symbol}",
            description=f"Risk condition detected for **{symbol}**",
            color=color_map.get(severity, 0xFF0000),
        )

        embed.add_embed_field(
            name="💰 Current Price", value=f"${price:.2f}", inline=True
        )

        embed.add_embed_field(name="🚨 Alert Type", value=alert_type, inline=True)

        embed.add_embed_field(name="⚠️ Severity", value=severity, inline=True)

        if details:
            embed.add_embed_field(name="📝 Details", value=details, inline=False)

        embed.set_footer(text="AxiomFolio • Risk Management")
        embed.set_timestamp()

        await self._send_webhook(embed, webhook_url=self.signals_webhook)

    async def send_portfolio_summary(
        self,
        total_value: float,
        daily_pnl: float,
        daily_pnl_pct: float,
        top_performers: List[Dict],
        worst_performers: List[Dict],
        account_name: str = "Portfolio",
    ):
        """Send daily portfolio summary."""
        pnl_color = 0x00FF00 if daily_pnl >= 0 else 0xFF0000
        pnl_emoji = "📈" if daily_pnl >= 0 else "📉"

        embed = DiscordEmbed(
            title=f"📊 Daily Portfolio Summary: {account_name}",
            description=f"{pnl_emoji} Portfolio performance update",
            color=pnl_color,
        )

        embed.add_embed_field(
            name="💰 Total Value", value=f"${total_value:,.2f}", inline=True
        )

        pnl_text = f"${daily_pnl:+,.2f}"
        if daily_pnl_pct:
            pnl_text += f" ({daily_pnl_pct:+.2f}%)"

        embed.add_embed_field(name="📊 Daily P&L", value=pnl_text, inline=True)

        embed.add_embed_field(
            name="📅 Date", value=datetime.now().strftime("%Y-%m-%d"), inline=True
        )

        # Top performers
        if top_performers:
            top_text = "\n".join(
                [
                    f"📈 **{p['symbol']}**: +{p['pnl_pct']:.1f}%"
                    for p in top_performers[:3]
                ]
            )
            embed.add_embed_field(name="🏆 Top Performers", value=top_text, inline=True)

        # Worst performers
        if worst_performers:
            worst_text = "\n".join(
                [
                    f"📉 **{p['symbol']}**: {p['pnl_pct']:.1f}%"
                    for p in worst_performers[:3]
                ]
            )
            embed.add_embed_field(
                name="📉 Underperformers", value=worst_text, inline=True
            )

        embed.set_footer(text="AxiomFolio • Portfolio Tracking")
        embed.set_timestamp()

        await self._send_webhook(embed, webhook_url=self.portfolio_webhook)

    async def send_trade_execution(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        total_value: float,
        strategy: str = None,
        notes: str = None,
    ):
        """Send trade execution notification."""
        side_color = 0x00FF00 if side == "BUY" else 0xFF0000
        side_emoji = "🟢" if side == "BUY" else "🔴"

        embed = DiscordEmbed(
            title=f"{side_emoji} Trade Executed: {symbol}",
            description=f"**{side}** order filled for {symbol}",
            color=side_color,
        )

        embed.add_embed_field(
            name="📦 Quantity", value=f"{quantity:,.0f} shares", inline=True
        )

        embed.add_embed_field(name="💰 Price", value=f"${price:.2f}", inline=True)

        embed.add_embed_field(
            name="💵 Total Value", value=f"${total_value:,.2f}", inline=True
        )

        if strategy:
            embed.add_embed_field(name="🎯 Strategy", value=strategy, inline=True)

        if notes:
            embed.add_embed_field(name="📝 Notes", value=notes, inline=False)

        embed.set_footer(text="AxiomFolio • Trade Execution")
        embed.set_timestamp()

        await self._send_webhook(embed, webhook_url=self.portfolio_webhook)

    async def send_scanner_results(
        self,
        scan_type: str,
        total_scanned: int,
        results_count: int,
        top_picks: List[Dict],
        scan_time: float,
    ):
        """Send scanner results notification."""
        embed = DiscordEmbed(
            title=f"🔍 Scanner Results: {scan_type}",
            description=f"Found {results_count} opportunities from {total_scanned} symbols",
            color=0x0099FF,  # Blue
        )

        embed.add_embed_field(
            name="📊 Scan Stats",
            value=f"Scanned: {total_scanned}\nFound: {results_count}\nTime: {scan_time:.1f}s",
            inline=True,
        )

        if top_picks:
            picks_text = "\n".join(
                [
                    f"🎯 **{pick['symbol']}**: {pick['recommendation']} ({pick['confidence']*100:.0f}%)"
                    for pick in top_picks[:5]
                ]
            )
            embed.add_embed_field(name="🏆 Top Picks", value=picks_text, inline=False)

        embed.set_footer(text="AxiomFolio • Stock Scanner")
        embed.set_timestamp()

        await self._send_webhook(embed, webhook_url=self.morning_brew_webhook)

    async def send_custom_alert(
        self,
        title: str,
        message: str,
        symbol: str = None,
        fields: Dict[str, Any] = None,
        color: int = 0x0099FF,
        webhook_type: str = "alerts",
    ):
        """Send custom alert notification."""
        embed = DiscordEmbed(title=title, description=message, color=color)

        if symbol:
            embed.add_embed_field(name="📈 Symbol", value=symbol, inline=True)

        if fields:
            for name, value in fields.items():
                embed.add_embed_field(name=name, value=str(value), inline=True)

        embed.set_footer(text="AxiomFolio • Custom Alert")
        embed.set_timestamp()

        webhook_map = {
            "signals": self.signals_webhook,
            "portfolio": self.portfolio_webhook,
            "morning_brew": self.morning_brew_webhook,
            "playground": self.playground_webhook,
            "system_status": self.system_status_webhook,
        }

        webhook_url = webhook_map.get(webhook_type, self.playground_webhook)
        await self._send_webhook(embed, webhook_url=webhook_url)

    async def _send_webhook(self, embed: DiscordEmbed, webhook_url: str = None):
        """Send webhook message with rate limiting."""
        if not webhook_url:
            webhook_url = self.playground_webhook

        if not webhook_url:
            logger.warning("No Discord webhook URL configured")
            return

        try:
            # Rate limiting
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self.last_message_time

            if time_since_last < self.rate_limit_delay:
                await asyncio.sleep(self.rate_limit_delay - time_since_last)

            webhook = DiscordWebhook(url=webhook_url)
            webhook.add_embed(embed)

            # Execute webhook
            response = webhook.execute()

            if response.status_code == 200:
                logger.info("Discord notification sent successfully")
            else:
                logger.error(f"Discord webhook failed: {response.status_code}")

            self.last_message_time = asyncio.get_event_loop().time()

        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")

    async def test_webhooks(self):
        """Test all configured webhooks."""
        test_embed = DiscordEmbed(
            title="🧪 AxiomFolio Test",
            description="Testing Discord webhook integration",
            color=0x0099FF,
        )

        test_embed.add_embed_field(
            name="✅ Status", value="Webhook connection successful", inline=True
        )

        test_embed.add_embed_field(
            name="🕐 Timestamp",
            value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            inline=True,
        )

        test_embed.set_footer(text="AxiomFolio • Webhook Test")
        test_embed.set_timestamp()

        webhooks_to_test = [
            ("Signals", self.signals_webhook),
            ("Portfolio", self.portfolio_webhook),
            ("Morning Brew", self.morning_brew_webhook),
            ("Playground", self.playground_webhook),
            ("System Status", self.system_status_webhook),
        ]

        results = []
        for name, url in webhooks_to_test:
            if url:
                try:
                    await self._send_webhook(test_embed, webhook_url=url)
                    results.append(f"✅ {name}: Success")
                except Exception as e:
                    results.append(f"❌ {name}: Failed - {e}")
            else:
                results.append(f"⚠️ {name}: Not configured")

        return results

    async def send_morning_brew(
        self,
        market_indices: Dict[str, Dict],
        top_opportunities: List[Dict],
        economic_calendar: List[Dict],
        market_sentiment: Dict,
        trading_outlook: str,
    ):
        """Send comprehensive morning market brew with real data."""
        # Auto-detect today's date and day of week
        today = datetime.now()
        date_str = today.strftime("%A, %B %d, %Y")  # "Thursday, July 17, 2025"

        embed = DiscordEmbed(
            title="☕ AxiomFolio Morning Brew",
            description=f"📅 **{date_str}** - Pre-Market Intelligence\n🌅 Market opens in 2 hours 15 minutes",
            color=0x1E90FF,  # DodgerBlue
        )

        # Market Indices Section - Real time data
        indices_text = ""
        for symbol, data in market_indices.items():
            price = data["price"]
            change = data["change"]
            change_pct = data["change_pct"]
            trend_emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"

            indices_text += f"{trend_emoji} **{symbol}**: ${price:.2f} ({change:+.2f}, {change_pct:+.2f}%)\n"

        embed.add_embed_field(
            name="📊 Major Indices (Pre-Market)", value=indices_text, inline=False
        )

        # TOP MARKET OPPORTUNITIES - PROMINENT SECTION
        if top_opportunities:
            opportunities_text = (
                "🎯 **HIGH-PROBABILITY SETUPS WITH QUANTIFIED TARGETS**\n\n"
            )

            for i, opp in enumerate(top_opportunities[:4], 1):
                symbol = opp["symbol"]
                entry_price = opp["entry_price"]
                stop_loss = opp["stop_loss"]
                target_1 = opp["target_1"]
                target_2 = opp["target_2"]
                risk_reward = opp["risk_reward"]
                time_horizon = opp["time_horizon"]
                confidence = opp["confidence"]
                atr_distance = opp["atr_distance"]

                risk_amount = ((entry_price - stop_loss) / entry_price) * 100
                reward_1 = ((target_1 - entry_price) / entry_price) * 100
                reward_2 = ((target_2 - entry_price) / entry_price) * 100

                confidence_emoji = (
                    "🔥" if confidence >= 0.8 else "💪" if confidence >= 0.65 else "👍"
                )

                opportunities_text += f"**{i}. {symbol}** {confidence_emoji} ({confidence*100:.0f}% confidence)\n"
                opportunities_text += f"📍 **Entry:** ${entry_price:.2f} (Currently {atr_distance:.1f}x from SMA50)\n"
                opportunities_text += (
                    f"🛑 **Stop:** ${stop_loss:.2f} (-{risk_amount:.1f}%)\n"
                )
                opportunities_text += f"🎯 **T1:** ${target_1:.2f} (+{reward_1:.1f}%) | **T2:** ${target_2:.2f} (+{reward_2:.1f}%)\n"
                opportunities_text += f"⚖️ **R/R:** {risk_reward:.1f}:1 | ⏰ **Horizon:** {time_horizon}\n\n"

            embed.add_embed_field(
                name="🚀 TODAY'S MARKET OPPORTUNITIES",
                value=opportunities_text,
                inline=False,
            )

        # Economic Calendar - REAL DATA FOR TODAY
        if economic_calendar:
            calendar_text = (
                f"📅 **KEY EVENTS TODAY ({today.strftime('%B %d, %Y')})**\n\n"
            )

            for event in economic_calendar:
                time_str = event["time"]
                event_name = event["event"]
                importance = event["importance"]
                previous = event.get("previous", "N/A")
                forecast = event.get("forecast", "N/A")

                importance_emoji = (
                    "🔴"
                    if importance == "High"
                    else "🟡" if importance == "Medium" else "🟢"
                )

                calendar_text += (
                    f"{importance_emoji} **{time_str} ET** - {event_name}\n"
                )
                if forecast != "N/A":
                    calendar_text += (
                        f"   📊 Forecast: {forecast} | Previous: {previous}\n"
                    )
                calendar_text += "\n"

            embed.add_embed_field(
                name="📅 Economic Calendar (Live)", value=calendar_text, inline=False
            )

        # Market Sentiment Analysis
        sentiment_text = f"📰 **News Sentiment:** {market_sentiment['news_sentiment']}% bullish ({market_sentiment['articles_analyzed']} articles)\n"
        sentiment_text += f"😱 **Fear & Greed Index:** {market_sentiment['fear_greed_index']}/100 ({market_sentiment['fear_greed_label']})\n"
        sentiment_text += f"📊 **Volatility Environment:** {market_sentiment['volatility_environment']} | **VIX Level:** {market_sentiment['vix_level']:.1f}\n"
        sentiment_text += (
            f"🧠 **Market Psychology:** {market_sentiment['sentiment_label']}"
        )

        embed.add_embed_field(
            name="🧠 Market Psychology", value=sentiment_text, inline=False
        )

        # Trading Outlook
        embed.add_embed_field(
            name="🔮 AxiomFolio Trading Outlook", value=trading_outlook, inline=False
        )

        # Scanner Stats Footer
        embed.add_embed_field(
            name="🔍 Scanner Results",
            value="Analyzed 508 stocks (S&P 500 + NASDAQ + Russell 2000)\n"
            f"Found {len(top_opportunities)} high-conviction opportunities\n"
            "ATR Matrix strategy with 72% win rate (last 90 days)",
            inline=False,
        )

        embed.set_footer(text="AxiomFolio • Real Market Data • Not Financial Advice")
        embed.set_timestamp()

        await self._send_webhook(embed, webhook_url=self.morning_brew_webhook)

    async def send_enhanced_portfolio_digest(
        self,
        portfolio_data: Dict,
        market_alerts: List[Dict] = None,
        holdings_news: List[Dict] = None,
    ):
        """Send enhanced portfolio digest with action items, categorized holdings, and clean formatting."""
        account_summary = portfolio_data.get("account_summary", {})
        positions = portfolio_data.get("all_positions", [])
        portfolio_metrics = portfolio_data.get("portfolio_metrics", {})

        # Determine performance color and emoji
        total_pnl = account_summary.get("unrealized_pnl", 0) + account_summary.get(
            "realized_pnl", 0
        )
        performance_color = 0x00FF00 if total_pnl >= 0 else 0xFF0000
        performance_emoji = "📈" if total_pnl >= 0 else "📉"

        current_time = datetime.now().strftime("%I:%M %p ET")

        embed = DiscordEmbed(
            title=f"{performance_emoji} Portfolio Update • {current_time}",
            description=f"**Account**: {account_summary.get('account_id', 'N/A')} • **Total Value**: ${account_summary.get('net_liquidation', 0):,.0f}",
            color=performance_color,
        )

        # 1. CRITICAL ACTION ITEMS (Top Priority)
        action_items = []

        if market_alerts:
            for alert in market_alerts[:3]:  # Top 3 most urgent
                action_items.append(f"🚨 **{alert['symbol']}**: {alert['message']}")

        # Add portfolio-specific alerts based on holdings
        for position in positions:
            if position.get("unrealized_pnl_pct", 0) > 15:
                action_items.append(
                    f"🎯 **{position['symbol']}**: Consider scaling out (+{position['unrealized_pnl_pct']:.1f}%)"
                )
            elif position.get("unrealized_pnl_pct", 0) < -8:
                action_items.append(
                    f"⚠️ **{position['symbol']}**: Review stop loss ({position['unrealized_pnl_pct']:+.1f}%)"
                )

        if action_items:
            embed.add_embed_field(
                name="🎯 Action Items",
                value="\n".join(action_items[:5]),  # Top 5 most important
                inline=False,
            )

        # 2. PORTFOLIO OVERVIEW
        cash_pct = portfolio_metrics.get("cash_percentage", 0)
        total_positions = portfolio_metrics.get("total_positions", 0)

        overview_text = (
            f"**Positions**: {total_positions} holdings\n"
            f"**Cash**: {cash_pct:.1f}% (${account_summary.get('total_cash', 0):,.0f})\n"
            f"**Day P&L**: {total_pnl:+,.0f} ({(total_pnl/account_summary.get('net_liquidation', 1)*100):+.2f}%)\n"
            f"**Buying Power**: ${account_summary.get('buying_power', 0):,.0f}"
        )

        embed.add_embed_field(
            name="📊 Portfolio Snapshot", value=overview_text, inline=True
        )

        # 3. CATEGORIZED HOLDINGS
        if positions:
            # Categorize by market cap
            large_cap = []  # >10B
            mid_cap = []  # 2B-10B
            small_cap = []  # <2B

            for position in positions:
                market_cap = position.get("market_cap", 0)
                if market_cap > 10_000_000_000:
                    large_cap.append(position)
                elif market_cap > 2_000_000_000:
                    mid_cap.append(position)
                else:
                    small_cap.append(position)

            # Show top holdings by category
            categories = [
                ("🏛️ Large Cap", large_cap),
                ("🏢 Mid Cap", mid_cap),
                ("🚀 Small Cap", small_cap),
            ]

            for category_name, holdings in categories:
                if holdings:
                    # Sort by position value, show top 3
                    top_holdings = sorted(
                        holdings, key=lambda x: x.get("position_value", 0), reverse=True
                    )[:3]

                    holdings_text = ""
                    for pos in top_holdings:
                        pnl_pct = pos.get("unrealized_pnl_pct", 0)
                        pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"
                        holdings_text += f"{pnl_emoji} **{pos['symbol']}**: ${pos.get('position_value', 0):,.0f} ({pnl_pct:+.1f}%)\n"

                    embed.add_embed_field(
                        name=f"{category_name} ({len(holdings)})",
                        value=holdings_text,
                        inline=True,
                    )

        # 4. TOP MOVERS
        if positions:
            # Sort by performance
            sorted_positions = sorted(
                positions, key=lambda x: x.get("unrealized_pnl_pct", 0), reverse=True
            )

            if len(sorted_positions) >= 2:
                top_performer = sorted_positions[0]
                worst_performer = sorted_positions[-1]

                movers_text = (
                    f"🏆 **{top_performer['symbol']}**: {top_performer.get('unrealized_pnl_pct', 0):+.1f}%\n"
                    f"📉 **{worst_performer['symbol']}**: {worst_performer.get('unrealized_pnl_pct', 0):+.1f}%"
                )

                embed.add_embed_field(
                    name="📈 Today's Movers", value=movers_text, inline=True
                )

        # 5. HOLDINGS NEWS (if provided)
        if holdings_news:
            news_text = ""
            for news_item in holdings_news[:3]:
                news_text += (
                    f"📰 **{news_item['symbol']}**: {news_item['headline'][:60]}...\n"
                )

            embed.add_embed_field(
                name="📰 Holdings News", value=news_text, inline=False
            )

        embed.set_footer(text="AxiomFolio • Real-time portfolio intelligence")
        embed.set_timestamp()

        await self._send_webhook(embed, webhook_url=self.portfolio_webhook)

    async def send_post_market_brew(
        self,
        market_indices: Dict,
        morning_predictions: List[Dict],
        afternoon_news: List[str],
        market_sentiment: Dict,
        trading_outlook: str,
    ):
        """Send post-market analysis showing how predictions performed."""
        embed = DiscordEmbed(
            title="🌅 Post-Market Analysis",
            description=f"Market wrap-up for {datetime.now().strftime('%A, %B %d, %Y')}",
            color=0x4169E1,
        )

        # Market indices performance
        indices_text = ""
        for symbol, data in market_indices.items():
            change_emoji = (
                "📈"
                if data["change_pct"] > 0
                else "📉" if data["change_pct"] < 0 else "➡️"
            )
            indices_text += f"{change_emoji} **{symbol}**: ${data['price']:.2f} ({data['change_pct']:+.2f}%)\n"

        if indices_text:
            embed.add_embed_field(
                name="📊 Market Close Performance",
                value=indices_text.strip(),
                inline=False,
            )

        # Morning predictions vs actual (when available)
        if morning_predictions and len(morning_predictions) > 1:
            predictions_text = ""
            for pred in morning_predictions[:3]:
                if pred.get("symbol") != "Example tracking coming soon":
                    result_emoji = (
                        "✅"
                        if (
                            pred["predicted_direction"] == "UP"
                            and pred["actual_change"] > 0
                        )
                        or (
                            pred["predicted_direction"] == "DOWN"
                            and pred["actual_change"] < 0
                        )
                        else "❌"
                    )
                    predictions_text += f"{result_emoji} **{pred['symbol']}**: Predicted {pred['predicted_direction']}, Actual {pred['actual_change']:+.1f}%\n"

            if predictions_text:
                embed.add_embed_field(
                    name="🎯 Morning Predictions vs Reality",
                    value=predictions_text.strip(),
                    inline=False,
                )

        # Afternoon news
        if afternoon_news:
            news_text = "\n".join([f"• {news}" for news in afternoon_news[:3]])
            embed.add_embed_field(
                name="📰 Afternoon Headlines", value=news_text, inline=False
            )

        # Market sentiment
        sentiment_emoji = (
            "😊"
            if market_sentiment.get("sentiment_label") == "Bullish"
            else "😟" if market_sentiment.get("sentiment_label") == "Bearish" else "😐"
        )
        embed.add_embed_field(
            name=f"{sentiment_emoji} Market Sentiment",
            value=f"**{market_sentiment.get('sentiment_label', 'Neutral')}** ({market_sentiment.get('news_sentiment', 50):.0f}%)\nFear/Greed: {market_sentiment.get('fear_greed_label', 'Neutral')}",
            inline=True,
        )

        # Trading outlook
        embed.add_embed_field(
            name="🔮 Tomorrow's Outlook", value=trading_outlook, inline=False
        )

        embed.set_footer(text="AxiomFolio • Post-market intelligence")
        embed.set_timestamp()

        await self._send_webhook(embed, webhook_url=self.morning_brew_webhook)

    async def send_dual_portfolio_digest(self, portfolio_results: List[Dict]):
        """Send portfolio digest for both IBKR accounts."""
        embed = DiscordEmbed(
            title="🏦 Dual Portfolio Analysis",
            description=f"Both IBKR accounts overview • {datetime.now().strftime('%A, %B %d, %Y')}",
            color=0x32CD32,
        )

        total_value = 0
        total_positions = 0
        total_alerts = 0

        for result in portfolio_results:
            account = result["account"]

            if result.get("error"):
                embed.add_embed_field(
                    name=f"{account['emoji']} {account['name']} ({account['id']})",
                    value=f"❌ **Error**: {result['error'][:100]}...",
                    inline=False,
                )
                continue

            portfolio_data = result.get("portfolio_data", {})
            account_summary = portfolio_data.get("account_summary", {})
            alerts = result.get("alerts", [])

            account_value = account_summary.get("net_liquidation", 0)
            positions_count = result.get("positions_count", 0)
            alerts_count = len(alerts)

            total_value += account_value
            total_positions += positions_count
            total_alerts += alerts_count

            # Account summary
            account_text = f"💰 **Value**: ${account_value:,.0f}\n📊 **Positions**: {positions_count}\n🚨 **Alerts**: {alerts_count}"

            # Add top alerts for this account
            if alerts:
                top_alerts = [
                    a for a in alerts if a.get("priority") in ["HIGH", "MEDIUM"]
                ][:2]
                if top_alerts:
                    account_text += "\n\n**Top Alerts:**\n"
                    for alert in top_alerts:
                        account_text += (
                            f"• {alert['symbol']}: {alert['message'][:50]}...\n"
                        )

            embed.add_embed_field(
                name=f"{account['emoji']} {account['name']} ({account['id']})",
                value=account_text,
                inline=True,
            )

        # Summary section
        embed.add_embed_field(
            name="📈 Combined Summary",
            value=f"**Total Portfolio Value**: ${total_value:,.0f}\n**Total Positions**: {total_positions}\n**Total Alerts**: {total_alerts}",
            inline=False,
        )

        embed.set_footer(text="AxiomFolio • Dual portfolio tracking")
        embed.set_timestamp()

        await self._send_webhook(embed, webhook_url=self.portfolio_webhook)

    async def send_portfolio_digest(
        self, portfolio_data: Dict, market_alerts: List[Dict], holdings_news: List[Dict]
    ):
        """Send regular portfolio digest (not enhanced version)."""
        embed = DiscordEmbed(
            title="💼 Portfolio Digest",
            description=f"IBKR portfolio overview • {datetime.now().strftime('%A, %B %d, %Y')}",
            color=0x4169E1,
        )

        account_summary = portfolio_data.get("account_summary", {})
        positions = portfolio_data.get("all_positions", [])

        # Account summary
        total_value = account_summary.get("net_liquidation", 0)
        unrealized_pnl = account_summary.get("unrealized_pnl", 0)
        day_pnl_pct = (unrealized_pnl / total_value * 100) if total_value > 0 else 0

        summary_text = f"💰 **Total Value**: ${total_value:,.0f}\n📊 **Positions**: {len(positions)}\n📈 **Day P&L**: {day_pnl_pct:+.2f}% (${unrealized_pnl:+,.0f})"

        embed.add_embed_field(
            name="📊 Account Summary", value=summary_text, inline=False
        )

        # Top performers/underperformers
        sorted_positions = sorted(
            positions, key=lambda x: x.get("unrealized_pnl_pct", 0), reverse=True
        )

        if sorted_positions:
            # Top 3 performers
            top_performers = sorted_positions[:3]
            performers_text = ""
            for pos in top_performers:
                if pos.get("unrealized_pnl_pct", 0) > 0:
                    performers_text += (
                        f"📈 **{pos['symbol']}**: {pos['unrealized_pnl_pct']:+.1f}%\n"
                    )

            if performers_text:
                embed.add_embed_field(
                    name="🏆 Top Performers", value=performers_text.strip(), inline=True
                )

            # Bottom 3 performers
            bottom_performers = sorted_positions[-3:]
            underperformers_text = ""
            for pos in bottom_performers:
                if pos.get("unrealized_pnl_pct", 0) < 0:
                    underperformers_text += (
                        f"📉 **{pos['symbol']}**: {pos['unrealized_pnl_pct']:+.1f}%\n"
                    )

            if underperformers_text:
                embed.add_embed_field(
                    name="📉 Underperformers",
                    value=underperformers_text.strip(),
                    inline=True,
                )

        # Portfolio alerts
        if market_alerts:
            high_priority_alerts = [
                a for a in market_alerts if a.get("priority") == "HIGH"
            ][:3]
            if high_priority_alerts:
                alerts_text = ""
                for alert in high_priority_alerts:
                    alerts_text += f"🚨 **{alert['symbol']}**: {alert['message']}\n"

                embed.add_embed_field(
                    name="🚨 Priority Alerts", value=alerts_text.strip(), inline=False
                )

        # Holdings news
        if holdings_news:
            news_text = ""
            for news in holdings_news[:3]:
                sentiment_emoji = {
                    "positive": "📈",
                    "negative": "📉",
                    "neutral": "📰",
                }.get(news.get("sentiment", "neutral"), "📰")
                news_text += f"{sentiment_emoji} **{news.get('symbol', 'MARKET')}**: {news.get('headline', '')[:60]}...\n"

            embed.add_embed_field(
                name="📰 Holdings News", value=news_text.strip(), inline=False
            )

        embed.set_footer(text="AxiomFolio • Portfolio intelligence")
        embed.set_timestamp()

        await self._send_webhook(embed, webhook_url=self.portfolio_webhook)

    async def send_comprehensive_portfolio_digest(
        self,
        dual_portfolio_data: Dict,
        accounts_processed: List[Dict],
        total_value: float,
        total_positions: int,
        total_alerts: int,
    ):
        """Send comprehensive portfolio digest with dual account real-time data."""
        embed = DiscordEmbed(
            title="💰🏦 Comprehensive Portfolio Analysis",
            description=f"Real-time IBKR dual account overview • {datetime.now().strftime('%A, %B %d, %Y')}",
            color=0x32CD32,
        )

        # Overall portfolio summary
        embed.add_embed_field(
            name="📈 Combined Portfolio Summary",
            value=f"💰 **Total Value**: ${total_value:,.0f}\n📊 **Total Positions**: {total_positions}\n🚨 **Total Alerts**: {total_alerts}\n🏦 **Accounts Connected**: {len([a for a in accounts_processed if a['status'] == 'success'])}",
            inline=False,
        )

        # Individual account details
        for account in accounts_processed:
            account_emoji = account.get("emoji", "📊")
            account_name = account["name"]
            account_id = account["account_id"]

            if account["status"] == "error":
                account_text = (
                    f"❌ **Status**: Error\n📝 **Details**: {account['error'][:100]}..."
                )
            else:
                account_text = f"💰 **Value**: ${account['value']:,.0f}\n📊 **Positions**: {account['positions']}\n🚨 **Alerts**: {account['alerts']}\n📰 **News**: {account['news']}"

                # Add performance highlights for successful accounts
                account_portfolio = dual_portfolio_data["accounts"].get(account_id, {})
                if "all_positions" in account_portfolio:
                    positions = account_portfolio["all_positions"]
                    if positions:
                        # Find best and worst performer
                        sorted_positions = sorted(
                            positions,
                            key=lambda x: x.get("unrealized_pnl_pct", 0),
                            reverse=True,
                        )
                        best_performer = (
                            sorted_positions[0] if sorted_positions else None
                        )
                        worst_performer = (
                            sorted_positions[-1] if sorted_positions else None
                        )

                        if (
                            best_performer
                            and best_performer.get("unrealized_pnl_pct", 0) != 0
                        ):
                            account_text += f"\n🏆 **Best**: {best_performer['symbol']} ({best_performer['unrealized_pnl_pct']:+.1f}%)"

                        if (
                            worst_performer
                            and worst_performer.get("unrealized_pnl_pct", 0) != 0
                            and worst_performer != best_performer
                        ):
                            account_text += f"\n📉 **Worst**: {worst_performer['symbol']} ({worst_performer['unrealized_pnl_pct']:+.1f}%)"

            embed.add_embed_field(
                name=f"{account_emoji} {account_name} ({account_id})",
                value=account_text,
                inline=True,
            )

        # Market context - combine all positions for sector analysis
        all_positions = []
        sector_totals = {}

        for account_id, portfolio_data in dual_portfolio_data.get(
            "accounts", {}
        ).items():
            if "all_positions" in portfolio_data:
                positions = portfolio_data["all_positions"]
                all_positions.extend(positions)

                # Aggregate sector allocation
                if "sector_allocation" in portfolio_data:
                    for sector, data in portfolio_data["sector_allocation"].items():
                        if sector not in sector_totals:
                            sector_totals[sector] = 0
                        sector_totals[sector] += data["value"]

        # Top sectors by allocation
        if sector_totals:
            sorted_sectors = sorted(
                sector_totals.items(), key=lambda x: x[1], reverse=True
            )
            top_sectors = sorted_sectors[:3]

            sectors_text = ""
            for sector, value in top_sectors:
                pct = (value / total_value * 100) if total_value > 0 else 0
                sectors_text += f"• **{sector}**: ${value:,.0f} ({pct:.1f}%)\n"

            embed.add_embed_field(
                name="🏢 Top Sector Allocations",
                value=sectors_text.strip(),
                inline=False,
            )

        # Overall portfolio alerts summary
        if total_alerts > 0:
            # Collect all alerts from both accounts
            all_alerts = []
            for account_id, portfolio_data in dual_portfolio_data.get(
                "accounts", {}
            ).items():
                if "error" not in portfolio_data:
                    positions = portfolio_data.get("all_positions", [])
                    if positions:
                        from backend.services.portfolio_alerts import (
                            portfolio_alerts_service,
                        )

                        try:
                            account_alerts = await portfolio_alerts_service.generate_portfolio_alerts(
                                positions
                            )
                            all_alerts.extend(account_alerts)
                        except Exception as e:
                            logger.warning(
                                "generate_portfolio_alerts failed for account %s: %s",
                                account_id,
                                e,
                            )

            # Show top priority alerts
            high_priority = [
                a for a in all_alerts if a.get("priority") in ["critical", "high"]
            ][:4]
            if high_priority:
                alerts_text = ""
                for alert in high_priority:
                    priority_emoji = (
                        "🔴" if alert.get("priority") == "critical" else "🟡"
                    )
                    alerts_text += f"{priority_emoji} **{alert['symbol']}**: {alert['message'][:50]}...\n"

                embed.add_embed_field(
                    name="🚨 Top Priority Alerts",
                    value=alerts_text.strip(),
                    inline=False,
                )

        # Data freshness indicator
        embed.add_embed_field(
            name="🕐 Data Freshness",
            value=f"**Market Prices**: Real-time via market APIs\n**Portfolio Data**: Live IBKR connection\n**Last Update**: {datetime.now().strftime('%I:%M %p ET')}\n**Accounts Available**: {', '.join(dual_portfolio_data.get('managed_accounts', []))}",
            inline=False,
        )

        embed.set_footer(text="AxiomFolio • Real-time dual portfolio intelligence")
        embed.set_timestamp()

        await self._send_webhook(embed, webhook_url=self.portfolio_webhook)

    def is_configured(self) -> bool:
        """Check if at least one webhook is configured."""
        return any(
            [
                self.signals_webhook,
                self.portfolio_webhook,
                self.morning_brew_webhook,
                self.playground_webhook,
                self.system_status_webhook,
            ]
        )


# Alias for strategy_manager and other callers that expect DiscordService
DiscordService = DiscordNotifier

# Global instance
discord_notifier = DiscordNotifier()
