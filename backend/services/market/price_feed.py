"""
Real-time price feed service using Alpaca WebSocket.

Queue-based architecture with reconnection logic and Redis Stream publishing.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Set

import redis.asyncio as aioredis

from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class BarData:
    """OHLCV bar data from WebSocket."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "vwap": self.vwap,
        }


class PriceFeedService:
    """
    Real-time price feed using Alpaca WebSocket.

    Features:
    - Queue-based processing (non-blocking)
    - Exponential backoff reconnection
    - Heartbeat monitoring
    - Publishes to Redis Stream `stream:bar_close`
    """

    REDIS_STREAM = "stream:bar_close"
    HEARTBEAT_INTERVAL = 30  # seconds
    MAX_RECONNECT_DELAY = 60  # seconds
    INITIAL_RECONNECT_DELAY = 1  # seconds

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        redis_client: Optional[aioredis.Redis] = None,
        paper: bool = True,
    ):
        self.api_key = api_key or settings.ALPACA_API_KEY
        self.api_secret = api_secret or settings.ALPACA_API_SECRET
        self.paper = paper

        self._redis = redis_client
        self._ws = None
        self._running = False
        self._subscribed_symbols: Set[str] = set()
        self._queue: asyncio.Queue[BarData] = asyncio.Queue()
        self._reconnect_delay = self.INITIAL_RECONNECT_DELAY
        self._last_heartbeat: Optional[datetime] = None
        self._callbacks: List[Callable[[BarData], None]] = []
        self._background_tasks: Set[asyncio.Task] = set()

    def _spawn_background(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _get_redis(self) -> aioredis.Redis:
        """Get async Redis connection (lazy initialization)."""
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL)
        return self._redis

    @property
    def ws_url(self) -> str:
        """WebSocket URL based on paper/live mode."""
        if self.paper:
            return "wss://stream.data.sandbox.alpaca.markets/v2/iex"
        return "wss://stream.data.alpaca.markets/v2/iex"

    async def start(self, symbols: List[str]) -> None:
        """Start the price feed service."""
        if self._running:
            logger.warning("PriceFeedService already running")
            return

        self._running = True
        self._subscribed_symbols = set(s.upper() for s in symbols)

        # Start background tasks (retain refs so tasks are not GC'd mid-flight)
        self._spawn_background(self._connection_loop())
        self._spawn_background(self._processing_loop())
        self._spawn_background(self._heartbeat_loop())

        logger.info(
            "PriceFeedService started for %d symbols",
            len(self._subscribed_symbols),
        )

    async def stop(self) -> None:
        """Stop the price feed service."""
        self._running = False
        if self._ws:
            await self._ws.close()
        logger.info("PriceFeedService stopped")

    def subscribe(self, symbols: List[str]) -> None:
        """Add symbols to subscription."""
        new_symbols = set(s.upper() for s in symbols)
        self._subscribed_symbols.update(new_symbols)
        logger.info("Added %d symbols to subscription", len(new_symbols))

    def unsubscribe(self, symbols: List[str]) -> None:
        """Remove symbols from subscription."""
        remove_symbols = set(s.upper() for s in symbols)
        self._subscribed_symbols -= remove_symbols
        logger.info("Removed %d symbols from subscription", len(remove_symbols))

    def add_callback(self, callback: Callable[[BarData], None]) -> None:
        """Add a callback to be called on each bar."""
        self._callbacks.append(callback)

    async def _connection_loop(self) -> None:
        """Main connection loop with reconnection logic."""
        while self._running:
            try:
                await self._connect_and_stream()
            except Exception as e:
                if not self._running:
                    break
                logger.error(
                    "WebSocket connection error: %s. Reconnecting in %ds...",
                    e,
                    self._reconnect_delay,
                )
                await asyncio.sleep(self._reconnect_delay)
                # Exponential backoff
                self._reconnect_delay = min(
                    self._reconnect_delay * 2,
                    self.MAX_RECONNECT_DELAY,
                )

    async def _connect_and_stream(self) -> None:
        """Connect to WebSocket and stream data."""
        try:
            import websockets
        except ImportError:
            logger.error("websockets package not installed")
            return

        async with websockets.connect(self.ws_url) as ws:
            self._ws = ws
            self._reconnect_delay = self.INITIAL_RECONNECT_DELAY
            logger.info("Connected to Alpaca WebSocket")

            # Authenticate
            auth_msg = {
                "action": "auth",
                "key": self.api_key,
                "secret": self.api_secret,
            }
            await ws.send(json.dumps(auth_msg))

            # Wait for auth response
            auth_response = await ws.recv()
            auth_data = json.loads(auth_response)
            if isinstance(auth_data, list) and auth_data[0].get("T") == "error":
                raise ValueError(f"Authentication failed: {auth_data}")

            logger.info("Authenticated with Alpaca")

            # Subscribe to bars
            if self._subscribed_symbols:
                sub_msg = {
                    "action": "subscribe",
                    "bars": list(self._subscribed_symbols),
                }
                await ws.send(json.dumps(sub_msg))
                logger.info(
                    "Subscribed to %d symbols",
                    len(self._subscribed_symbols),
                )

            # Stream messages
            async for message in ws:
                self._last_heartbeat = datetime.now(timezone.utc)
                await self._handle_message(message)

    async def _handle_message(self, message: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)

            if not isinstance(data, list):
                return

            for item in data:
                msg_type = item.get("T")

                if msg_type == "b":  # Bar
                    bar = BarData(
                        symbol=item.get("S", ""),
                        timestamp=datetime.fromisoformat(
                            item.get("t", "").replace("Z", "+00:00")
                        ),
                        open=float(item.get("o", 0)),
                        high=float(item.get("h", 0)),
                        low=float(item.get("l", 0)),
                        close=float(item.get("c", 0)),
                        volume=int(item.get("v", 0)),
                        vwap=float(item.get("vw", 0)) if item.get("vw") else None,
                    )
                    await self._queue.put(bar)

                elif msg_type == "error":
                    logger.error("WebSocket error: %s", item.get("msg"))

                elif msg_type == "subscription":
                    logger.debug("Subscription update: %s", item)

        except Exception as e:
            logger.error("Error handling message: %s", e)

    async def _processing_loop(self) -> None:
        """Process bars from queue."""
        while self._running:
            try:
                # Wait for bar with timeout
                try:
                    bar = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    continue

                # Publish to Redis Stream
                await self._publish_to_stream(bar)

                # Call registered callbacks
                for callback in self._callbacks:
                    try:
                        callback(bar)
                    except Exception as e:
                        logger.error("Callback error: %s", e)

            except Exception as e:
                logger.error("Processing loop error: %s", e)

    async def _publish_to_stream(self, bar: BarData) -> None:
        """Publish bar data to Redis Stream."""
        try:
            redis = await self._get_redis()
            await redis.xadd(
                self.REDIS_STREAM,
                bar.to_dict(),
                maxlen=10000,  # Keep last 10k entries
                approximate=True,  # ~ trimming: cheaper under sustained throughput
            )
            logger.debug(
                "Published bar to stream: %s @ %.2f",
                bar.symbol,
                bar.close,
            )
        except Exception as e:
            logger.error("Failed to publish to Redis Stream: %s", e)

    async def _heartbeat_loop(self) -> None:
        """Monitor connection health via heartbeat."""
        while self._running:
            await asyncio.sleep(self.HEARTBEAT_INTERVAL)

            if self._last_heartbeat:
                elapsed = (
                    datetime.now(timezone.utc) - self._last_heartbeat
                ).total_seconds()

                if elapsed > self.HEARTBEAT_INTERVAL * 2:
                    logger.warning(
                        "No heartbeat for %.0fs, connection may be stale",
                        elapsed,
                    )
                    # Force reconnect
                    if self._ws:
                        await self._ws.close()

    def get_status(self) -> dict:
        """Get service status."""
        return {
            "running": self._running,
            "connected": self._ws is not None and not self._ws.closed,
            "subscribed_symbols": len(self._subscribed_symbols),
            "queue_size": self._queue.qsize(),
            "last_heartbeat": (
                self._last_heartbeat.isoformat() if self._last_heartbeat else None
            ),
            "reconnect_delay": self._reconnect_delay,
        }


# Module-level singleton
price_feed_service = PriceFeedService()
