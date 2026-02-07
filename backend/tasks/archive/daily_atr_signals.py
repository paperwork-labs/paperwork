#!/usr/bin/env python3
"""
AxiomFolio V1 - Daily ATR Signals Cron Task
============================================

Scheduled task that runs ATR signal generation:
- Runs multiple times per day (pre-market, open, midday, close)  
- Uses the SINGLE ATR signal generator
- Saves signals to database
- Sends Discord notifications
- Logs performance metrics

SCHEDULE:
- 6:00 AM ET: Pre-market analysis
- 9:30 AM ET: Market open signals
- 12:00 PM ET: Midday check
- 4:00 PM ET: Market close analysis

USAGE:
    python backend/tasks/daily_atr_signals.py
    
Or via cron:
    0 6,9,12,16 * * 1-5 /path/to/python backend/tasks/daily_atr_signals.py
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List
import json

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.services.signals.atr_signal_generator import (
    run_daily_atr_signals,
)
from backend.models.user import User
from backend.database import SessionLocal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/app/logs/atr_signals.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class ATRSignalScheduler:
    """Handles scheduled execution of ATR signal generation."""

    def __init__(self):
        self.market_hours = {
            "pre_market": {"hour": 6, "minute": 0},  # 6:00 AM ET
            "market_open": {"hour": 9, "minute": 30},  # 9:30 AM ET
            "midday": {"hour": 12, "minute": 0},  # 12:00 PM ET
            "market_close": {"hour": 16, "minute": 0},  # 4:00 PM ET
        }

    async def run_scheduled_signals(self, session_type: str = None) -> Dict:
        """
        Run scheduled ATR signal generation.

        Args:
            session_type: pre_market, market_open, midday, market_close
        """
        logger.info(f"🚀 Starting scheduled ATR signals: {session_type or 'manual'}")

        start_time = datetime.now()

        try:
            # Get all active users
            active_users = await self._get_active_users()

            if not active_users:
                logger.warning("No active users found for signal generation")
                return {"error": "No active users"}

            # Run signals for all users
            overall_results = {
                "session_type": session_type,
                "start_time": start_time.isoformat(),
                "users_processed": 0,
                "total_signals_generated": 0,
                "total_notifications_sent": 0,
                "user_results": [],
                "errors": [],
            }

            for user in active_users:
                try:
                    logger.info(
                        f"🔍 Processing signals for user: {user.username} (ID: {user.id})"
                    )

                    # Generate signals for this user
                    user_result = await run_daily_atr_signals(user.id)

                    if "error" in user_result:
                        overall_results["errors"].append(
                            {
                                "user_id": user.id,
                                "username": user.username,
                                "error": user_result["error"],
                            }
                        )
                        continue

                    # Collect metrics
                    overall_results["users_processed"] += 1
                    overall_results["total_signals_generated"] += user_result.get(
                        "signals_generated", 0
                    )
                    overall_results["total_notifications_sent"] += user_result.get(
                        "notifications_sent", 0
                    )

                    # Store user result
                    overall_results["user_results"].append(
                        {
                            "user_id": user.id,
                            "username": user.username,
                            "signals_generated": user_result.get(
                                "signals_generated", 0
                            ),
                            "entry_signals": user_result.get("entry_signals", 0),
                            "scale_out_signals": user_result.get(
                                "scale_out_signals", 0
                            ),
                            "exit_signals": user_result.get("exit_signals", 0),
                            "risk_warnings": user_result.get("risk_warnings", 0),
                            "notifications_sent": user_result.get(
                                "notifications_sent", 0
                            ),
                        }
                    )

                    logger.info(
                        f"✅ User {user.username}: {user_result.get('signals_generated', 0)} signals generated"
                    )

                except Exception as e:
                    logger.error(f"Error processing user {user.username}: {e}")
                    overall_results["errors"].append(
                        {"user_id": user.id, "username": user.username, "error": str(e)}
                    )

            # Calculate execution time
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            overall_results["end_time"] = end_time.isoformat()
            overall_results["execution_time_seconds"] = execution_time

            # Log summary
            logger.info("🎯 Scheduled signals complete:")
            logger.info(f"   👥 Users processed: {overall_results['users_processed']}")
            logger.info(
                f"   📊 Total signals: {overall_results['total_signals_generated']}"
            )
            logger.info(
                f"   📢 Notifications sent: {overall_results['total_notifications_sent']}"
            )
            logger.info(f"   ⏱️ Execution time: {execution_time:.1f}s")

            if overall_results["errors"]:
                logger.warning(f"   ⚠️ Errors: {len(overall_results['errors'])}")

            # Send summary to Discord (optional)
            if session_type and overall_results["total_signals_generated"] > 0:
                await self._send_session_summary(session_type, overall_results)

            return overall_results

        except Exception as e:
            logger.error(f"Error in scheduled signal generation: {e}")
            return {"error": str(e), "start_time": start_time.isoformat()}

    async def _get_active_users(self) -> List[User]:
        """Get all active users for signal generation."""
        db = SessionLocal()

        try:
            # Get users who are active and have signal generation enabled
            users = (
                db.query(User)
                .filter(
                    User.is_active == True,
                    # Add any additional filters for signal preferences
                )
                .all()
            )

            return users

        except Exception as e:
            logger.error(f"Error getting active users: {e}")
            return []
        finally:
            db.close()

    async def _send_session_summary(self, session_type: str, results: Dict):
        """Send session summary to Discord."""
        try:
            from backend.services.notifications.discord_notifier import discord_notifier

            # Format summary message
            summary = f"""📊 **ATR Signals Summary - {session_type.replace('_', ' ').title()}**
            
👥 **Users**: {results['users_processed']}
📈 **Total Signals**: {results['total_signals_generated']}
🔔 **Notifications**: {results['total_notifications_sent']}
⏱️ **Runtime**: {results['execution_time_seconds']:.1f}s

**Signal Breakdown**:
"""

            # Add user breakdown if multiple users
            if len(results["user_results"]) > 1:
                for user_result in results["user_results"][:5]:  # Show top 5
                    summary += f"• {user_result['username']}: {user_result['signals_generated']} signals\n"

            if results["errors"]:
                summary += f"\n⚠️ **Errors**: {len(results['errors'])}"

            # Send to system status channel
            await discord_notifier.send_system_message(
                message=summary, channel="SYSTEM_STATUS"
            )

        except Exception as e:
            logger.error(f"Error sending session summary: {e}")

    def get_next_run_time(self) -> datetime:
        """Calculate the next scheduled run time."""
        now = datetime.now()

        # Check each scheduled time for today
        for session_name, time_config in self.market_hours.items():
            scheduled_time = now.replace(
                hour=time_config["hour"],
                minute=time_config["minute"],
                second=0,
                microsecond=0,
            )

            if scheduled_time > now:
                return scheduled_time

        # If all times for today have passed, return first time tomorrow
        first_session = list(self.market_hours.values())[0]
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(
            hour=first_session["hour"],
            minute=first_session["minute"],
            second=0,
            microsecond=0,
        )

    def determine_session_type(self) -> str:
        """Determine current session type based on time."""
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute

        # Convert current time to minutes since midnight
        current_minutes = current_hour * 60 + current_minute

        # Convert schedule to minutes and find closest
        session_times = []
        for name, time_config in self.market_hours.items():
            session_minutes = time_config["hour"] * 60 + time_config["minute"]
            session_times.append((session_minutes, name))

        session_times.sort()

        # Find the closest session (within 30 minutes)
        for session_minutes, session_name in session_times:
            if abs(current_minutes - session_minutes) <= 30:
                return session_name

        return "manual"


# Global scheduler instance
atr_scheduler = ATRSignalScheduler()


async def main():
    """Main entry point for scheduled execution."""
    logger.info("🚀 ATR Signal Scheduler Starting...")

    # Determine session type
    session_type = atr_scheduler.determine_session_type()

    # Run signal generation
    results = await atr_scheduler.run_scheduled_signals(session_type)

    if "error" in results:
        logger.error(f"❌ Scheduler failed: {results['error']}")
        sys.exit(1)
    else:
        logger.info("✅ ATR Signal Scheduler completed successfully")

        # Print JSON results for cron logging
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    # Run the scheduler
    asyncio.run(main())
