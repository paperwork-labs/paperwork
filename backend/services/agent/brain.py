"""
Agent Brain
===========

LLM-powered decision engine for the auto-ops agent.
Uses OpenAI GPT-4o-mini for cost-effective intelligent operations.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.agent_action import AgentAction
from .taxonomy import RiskLevel, classify_action_risk, can_auto_execute
from .tools import get_tools_for_openai, INLINE_ONLY_AGENT_TOOLS, TOOL_TO_CELERY_TASK

logger = logging.getLogger(__name__)

# Bound Redis payload / memory for persisted chat (tool outputs can be large).
AGENT_CONVERSATION_MAX_MESSAGES = 120
AGENT_CONVERSATION_MAX_JSON_BYTES = 400_000

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"


def _resolve_backend_codebase_dir() -> Optional[str]:
    import os

    for candidate in ("/app/backend", "backend"):
        if os.path.isdir(candidate):
            return os.path.realpath(os.path.abspath(candidate))
    return None


def _full_path_within_backend(base: str, relative: str) -> Tuple[bool, str]:
    """Resolve ``relative`` under ``base`` and ensure it stays inside ``base`` (prefix-safe)."""
    import os

    if not relative:
        return True, base
    full_path = os.path.realpath(os.path.normpath(os.path.join(base, relative)))
    try:
        if os.path.commonpath([base, full_path]) != base:
            return False, full_path
    except ValueError:
        return False, full_path
    return True, full_path


SYSTEM_PROMPT = """You are AxiomFolio's AI assistant. You help the admin with questions about their portfolio, market data, the codebase, and system operations.

## What You Can Do

1. **Portfolio** — positions, P&L, risk metrics, activity, account balances
2. **Market Data** — stages, indicators, regime, tracked universe, index constituents
3. **Codebase** — read files, explain how things work, find where code lives
4. **Database** — explore schema, run queries to investigate data
5. **Operations** — monitor health, backfill data, recompute indicators

## Tool Selection Guide

| Question Type | Tools |
|---------------|-------|
| "What positions do I have?" | `get_portfolio_summary` |
| "How is NVDA doing?" | `get_position_details` or `get_market_snapshot` |
| "What's in the S&P 500?" | `get_constituents` |
| "What's the market regime?" | `get_regime` |
| "How does stage calculation work?" | `read_file` (services/market/indicator_engine.py) |
| "What files are in services/?" | `list_files` |
| "What tables exist?" | `describe_tables` |
| "Custom data query" | `query_database` (after describe_tables) |
| "Is the system healthy?" | `check_health` |

## Key Codebase Files

- **Stage/Indicators**: services/market/indicator_engine.py
- **Market Data**: services/market/market_data_service.py
- **Portfolio Sync**: services/portfolio/ibkr_sync_service.py
- **Risk Metrics**: services/portfolio/portfolio_analytics_service.py
- **Models**: models/ directory
- **API Routes**: api/routes/ directory
- **Celery Tasks**: tasks/ directory

## Remediation (when check_health shows issues)

| Issue | Tool |
|-------|------|
| coverage red | `backfill_stale_daily` or `bootstrap_coverage` |
| stage_quality red | `recompute_indicators` |
| jobs stale | `recover_stale_jobs` |
| regime missing | `compute_regime` |
| audit gaps | `record_daily` |

## Guidelines

- ALWAYS use tools to get data — never guess or make up information
- For codebase questions, use `list_files` then `read_file` to find and read relevant code
- For database questions, use `describe_tables` before `query_database`
- Be concise and helpful

Current time: {current_time}
Autonomy level: {autonomy_level}
"""


class AgentBrain:
    """LLM-powered agent brain for intelligent operations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.session_id = str(uuid.uuid4())[:8]
        self._conversation: List[Dict[str, Any]] = []
        self._last_openai_error: Optional[str] = None
    
    async def analyze_and_act(
        self,
        health_data: Dict[str, Any],
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze system health and decide on actions.
        
        Args:
            health_data: Current health status from AdminHealthService
            context: Optional additional context about the situation
            
        Returns:
            Summary of analysis and actions taken/proposed
        """
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not configured, falling back to rule-based")
            return {"error": "LLM not configured", "fallback": True}
        
        system_msg = SYSTEM_PROMPT.format(
            current_time=datetime.now(timezone.utc).isoformat(),
            autonomy_level=settings.AGENT_AUTONOMY_LEVEL,
        )
        
        user_msg = self._build_user_message(health_data, context)
        
        self._conversation = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]
        
        actions_taken = []
        actions_pending = []
        max_iterations = 10
        
        for iteration in range(max_iterations):
            # Force at least one tool call on first iteration
            tool_choice = "required" if iteration == 0 else "auto"
            response = await self._call_llm(tool_choice=tool_choice)
            
            if not response:
                break
            
            message = response.get("choices", [{}])[0].get("message", {})
            
            if message.get("tool_calls"):
                self._conversation.append(message)
                
                for tool_call in message["tool_calls"]:
                    func = tool_call.get("function", {})
                    tool_name = func.get("name")
                    try:
                        tool_args = json.loads(func.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        tool_args = {}
                    
                    result, action = await self._execute_tool(
                        tool_name, tool_args, message.get("content", "")
                    )
                    
                    self._conversation.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(result),
                    })
                    
                    if action:
                        if action.status == "completed":
                            actions_taken.append(action)
                        else:
                            actions_pending.append(action)
            else:
                self._conversation.append(message)
                break
        
        final_response = self._conversation[-1].get("content", "")
        
        return {
            "session_id": self.session_id,
            "analysis": final_response,
            "actions_taken": [self._action_to_dict(a) for a in actions_taken],
            "actions_pending": [self._action_to_dict(a) for a in actions_pending],
            "health_input": health_data.get("composite_status"),
        }
    
    def _build_user_message(
        self,
        health_data: Dict[str, Any],
        context: Optional[str],
    ) -> str:
        """Build the initial user message with health data."""
        parts = [
            "Current system health status:",
            f"Composite: {health_data.get('composite_status', 'unknown')}",
            "",
            "Dimension details:",
        ]
        
        for dim_name, dim_data in health_data.get("dimensions", {}).items():
            status = dim_data.get("status", "unknown")
            message = dim_data.get("message", "")
            parts.append(f"- {dim_name}: {status} - {message}")
        
        if context:
            parts.extend(["", "Additional context:", context])
        
        parts.extend([
            "",
            "Analyze the situation and take appropriate actions.",
            "For any non-green dimensions, investigate and remediate if possible.",
        ])
        
        return "\n".join(parts)
    
    def _messages_for_openai_request(self) -> List[Dict[str, Any]]:
        """
        Build messages safe for OpenAI Chat Completions input.
        Strips response-only fields that cause 400s when replayed (e.g. from Redis).
        """
        out: List[Dict[str, Any]] = []
        for m in self._conversation:
            role = m.get("role")
            if role == "system":
                out.append({"role": "system", "content": m.get("content") or ""})
            elif role == "user":
                out.append({"role": "user", "content": m.get("content") or ""})
            elif role == "assistant":
                item: Dict[str, Any] = {"role": "assistant"}
                content = m.get("content")
                if content:
                    item["content"] = content
                raw_calls = m.get("tool_calls")
                if raw_calls:
                    cleaned = []
                    for tc in raw_calls:
                        fn = tc.get("function") or {}
                        cleaned.append(
                            {
                                "id": tc.get("id", ""),
                                "type": tc.get("type", "function"),
                                "function": {
                                    "name": fn.get("name", ""),
                                    "arguments": fn.get("arguments") or "{}",
                                },
                            }
                        )
                    item["tool_calls"] = cleaned
                if "content" not in item and "tool_calls" not in item:
                    item["content"] = ""
                out.append(item)
            elif role == "tool":
                tid = m.get("tool_call_id")
                if not tid:
                    continue
                body = m.get("content") or ""
                max_tool_chars = 120_000
                if len(body) > max_tool_chars:
                    body = (
                        body[:max_tool_chars]
                        + "\n\n[truncated for API size limit; ask a narrower question]"
                    )
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": tid,
                        "content": body,
                    }
                )
        return out
    
    async def _call_llm(self, tool_choice: str = "auto") -> Optional[Dict[str, Any]]:
        """Call the OpenAI API."""
        self._last_openai_error = None
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        
        messages = self._messages_for_openai_request()
        payload = {
            "model": MODEL,
            "messages": messages,
            "tools": get_tools_for_openai(),
            "tool_choice": tool_choice,
            "temperature": 0.1,
            "max_tokens": 2000,
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    OPENAI_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        self._last_openai_error = f"HTTP {resp.status}: {error[:800]}"
                        logger.error("OpenAI API error: %s", self._last_openai_error)
                        return None
                    return await resp.json()
        except Exception as e:
            self._last_openai_error = str(e)
            logger.error("Failed to call OpenAI API: %s", e)
            return None
    
    async def _execute_tool(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        reasoning: str,
    ) -> Tuple[Dict[str, Any], Optional[AgentAction]]:
        """
        Execute a tool call and return the result.
        
        Returns:
            Tuple of (result_dict, AgentAction or None)
        """
        risk = classify_action_risk(tool_name)
        auto_exec = can_auto_execute(tool_name, settings.AGENT_AUTONOMY_LEVEL)
        
        action = AgentAction(
            action_type=tool_name,
            action_name=self._get_action_display_name(tool_name),
            payload=tool_args,
            risk_level=risk.value,
            status="pending",
            reasoning=reasoning,
            session_id=self.session_id,
        )
        self.db.add(action)
        self.db.flush()

        async def _run_inline_safe_tool() -> Tuple[Dict[str, Any], AgentAction]:
            result = await self._execute_safe_tool(tool_name, tool_args)
            action.status = "completed"
            action.result = result
            action.executed_at = datetime.utcnow()
            action.completed_at = datetime.utcnow()
            action.auto_approved = True
            self.db.commit()
            return result, action

        if risk == RiskLevel.SAFE:
            return await _run_inline_safe_tool()

        if tool_name in INLINE_ONLY_AGENT_TOOLS and auto_exec:
            return await _run_inline_safe_tool()

        if auto_exec:
            result = await self._dispatch_celery_task(tool_name, tool_args)
            action.status = "executing" if result.get("task_id") else "failed"
            action.task_id = result.get("task_id")
            action.executed_at = datetime.utcnow()
            action.auto_approved = True
            if result.get("error"):
                action.error = result["error"]
                action.status = "failed"
                action.completed_at = datetime.utcnow()
            self.db.commit()
            return result, action
        
        action.status = "pending_approval"
        self.db.commit()
        
        return {
            "status": "pending_approval",
            "message": f"Action '{tool_name}' requires human approval (risk: {risk.value})",
            "action_id": action.id,
        }, action
    
    async def _execute_safe_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a safe (read-only) tool."""
        if tool_name == "check_health":
            return await self._tool_check_health()
        
        if tool_name == "query_database":
            return await self._tool_query_database(args.get("query", ""), args.get("limit", 100))
        
        if tool_name == "web_search":
            return await self._tool_web_search(args.get("query", ""))
        
        if tool_name == "browse_url":
            return await self._tool_browse_url(args.get("url", ""))
        
        if tool_name == "send_alert":
            return await self._tool_send_alert(args.get("message", ""), args.get("severity", "info"))
        
        if tool_name == "list_jobs":
            return await self._tool_list_jobs(args.get("status", "all"), args.get("limit", 20))
        
        if tool_name == "check_broker_connection":
            return await self._tool_check_broker(args.get("broker", "all"))
        
        # New holistic chat tools
        if tool_name == "get_portfolio_summary":
            return await self._tool_get_portfolio_summary()
        
        if tool_name == "get_position_details":
            return await self._tool_get_position_details(args.get("symbol", ""))
        
        if tool_name == "get_activity":
            return await self._tool_get_activity(args.get("limit", 20), args.get("symbol"))
        
        if tool_name == "get_market_snapshot":
            return await self._tool_get_market_snapshot(args.get("symbol", ""))
        
        if tool_name == "get_tracked_universe":
            return await self._tool_get_tracked_universe()
        
        if tool_name == "get_constituents":
            return await self._tool_get_constituents(args.get("index", "SP500"))
        
        if tool_name == "get_regime":
            return await self._tool_get_regime()
        
        if tool_name == "describe_tables":
            return await self._tool_describe_tables(args.get("table_name"))
        
        # Codebase exploration tools
        if tool_name == "read_file":
            return await self._tool_read_file(
                args.get("path", ""),
                args.get("start_line"),
                args.get("end_line"),
            )
        
        if tool_name == "list_files":
            return await self._tool_list_files(args.get("path", ""))
        
        return {"error": f"Unknown safe tool: {tool_name}"}
    
    async def _dispatch_celery_task(
        self,
        tool_name: str,
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Dispatch a Celery task for the tool."""
        task_path = TOOL_TO_CELERY_TASK.get(tool_name)
        if not task_path:
            return {"error": f"No Celery task mapped for tool: {tool_name}"}
        
        try:
            from backend.tasks.celery_app import celery_app
            result = celery_app.send_task(task_path, kwargs=args)
            return {
                "status": "dispatched",
                "task_id": result.id,
                "task_name": task_path,
            }
        except Exception as e:
            logger.error("Failed to dispatch task %s: %s", task_path, e)
            return {"error": str(e)}
    
    async def _tool_check_health(self) -> Dict[str, Any]:
        """Check system health."""
        from backend.services.market.admin_health_service import AdminHealthService
        try:
            svc = AdminHealthService()
            return svc.get_composite_health(self.db)
        except Exception as e:
            return {"error": str(e)}
    
    async def _tool_query_database(self, query: str, limit: int) -> Dict[str, Any]:
        """Run a read-only database query."""
        import re
        
        query_clean = query.strip()
        query_upper = query_clean.upper()
        
        # Allow SELECT and WITH (CTEs)
        if not (query_upper.startswith("SELECT") or query_upper.startswith("WITH")):
            return {"error": "Only SELECT/WITH queries allowed. Use describe_tables to see available tables."}
        
        # Check forbidden keywords using word boundaries (not substrings)
        forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"]
        for word in forbidden:
            if re.search(rf'\b{word}\b', query_upper):
                return {"error": f"Query contains forbidden keyword: {word}"}
        
        # Only add LIMIT if not already present
        if "LIMIT" not in query_upper:
            query_clean = f"{query_clean} LIMIT {limit}"
        
        try:
            from sqlalchemy import text
            result = self.db.execute(text(query_clean))
            rows = [dict(row._mapping) for row in result]
            return {"rows": rows, "count": len(rows)}
        except Exception as e:
            return {"error": str(e), "hint": "Use describe_tables to see available tables and columns."}
    
    async def _tool_web_search(self, query: str) -> Dict[str, Any]:
        """Search the web using DuckDuckGo."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_redirect": "1"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "abstract": data.get("Abstract", ""),
                            "related": [t.get("Text", "") for t in data.get("RelatedTopics", [])[:5]],
                        }
                    return {"error": f"Search failed: {resp.status}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def _tool_browse_url(self, url: str) -> Dict[str, Any]:
        """Fetch content from a URL."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=15),
                    headers={"User-Agent": "AxiomFolio-Agent/1.0"},
                ) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        return {"content": text[:5000], "status": resp.status}
                    return {"error": f"Failed to fetch: {resp.status}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def _tool_send_alert(self, message: str, severity: str) -> Dict[str, Any]:
        """Send a Discord alert."""
        webhook_url = settings.DISCORD_WEBHOOK_SYSTEM_STATUS
        if not webhook_url:
            logger.info("Alert (no webhook): [%s] %s", severity, message)
            return {"status": "logged", "message": "No webhook configured"}
        
        color_map = {"info": 3447003, "warning": 16776960, "error": 15158332, "critical": 10038562}
        
        payload = {
            "embeds": [{
                "title": f"Agent Alert: {severity.upper()}",
                "description": message,
                "color": color_map.get(severity, 3447003),
                "timestamp": datetime.utcnow().isoformat(),
            }]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as resp:
                    return {"status": "sent" if resp.status < 300 else "failed"}
        except Exception as e:
            return {"error": str(e)}
    
    async def _tool_list_jobs(self, status: str, limit: int) -> Dict[str, Any]:
        """List recent job runs."""
        from backend.models import JobRun
        from sqlalchemy import desc
        
        try:
            query = self.db.query(JobRun).order_by(desc(JobRun.started_at))
            if status != "all":
                query = query.filter(JobRun.status == status)
            jobs = query.limit(limit).all()
            
            return {
                "jobs": [
                    {
                        "id": j.id,
                        "job_name": j.job_name,
                        "status": j.status,
                        "started_at": j.started_at.isoformat() if j.started_at else None,
                        "duration_ms": j.duration_ms,
                    }
                    for j in jobs
                ]
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def _tool_check_broker(self, broker: str) -> Dict[str, Any]:
        """Check broker connection status."""
        results = {}
        
        if broker in ("ibkr", "all"):
            try:
                from backend.services.clients.ibkr_client import IBKRClient
                client = IBKRClient.get_instance()
                results["ibkr"] = {
                    "connected": client.is_connected() if client else False,
                }
            except Exception as e:
                results["ibkr"] = {"error": str(e)}
        
        return results
    
    # ==================== NEW HOLISTIC CHAT TOOLS ====================
    
    async def _tool_get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio risk metrics, sector allocation, and P&L summary."""
        try:
            from backend.services.portfolio.portfolio_analytics_service import PortfolioAnalyticsService
            from backend.models import Position, BrokerAccount
            
            svc = PortfolioAnalyticsService()
            
            # Get admin user (user_id=1)
            user_id = 1
            
            # Get risk metrics
            risk_metrics = svc.compute_risk_metrics(self.db, user_id)
            
            # Get sector attribution
            sector_data = svc.compute_sector_attribution(self.db, user_id)
            
            # Get account summary
            accounts = self.db.query(BrokerAccount).filter(
                BrokerAccount.user_id == user_id
            ).all()
            
            account_summary = []
            for acc in accounts:
                account_summary.append({
                    "broker": acc.broker,
                    "account_number": acc.account_number[-4:] if acc.account_number else "****",
                    "total_value": float(acc.total_value) if acc.total_value else 0,
                    "day_pnl": float(acc.day_pnl) if acc.day_pnl else 0,
                    "total_pnl": float(acc.total_pnl) if acc.total_pnl else 0,
                })
            
            # Get position count
            position_count = self.db.query(Position).filter(
                Position.user_id == user_id,
                Position.quantity != 0
            ).count()
            
            return {
                "user_id": user_id,
                "position_count": position_count,
                "accounts": account_summary,
                "risk_metrics": risk_metrics,
                "sector_allocation": sector_data,
            }
        except Exception as e:
            logger.error("Failed to get portfolio summary: %s", e)
            return {"error": str(e)}
    
    async def _tool_get_position_details(self, symbol: str) -> Dict[str, Any]:
        """Get detailed position info including market snapshot."""
        if not symbol:
            return {"error": "Symbol is required"}
        
        try:
            from backend.models import Position, MarketSnapshot
            
            symbol_upper = symbol.upper()
            user_id = 1
            
            # Get position
            position = self.db.query(Position).filter(
                Position.user_id == user_id,
                Position.symbol == symbol_upper,
            ).first()
            
            position_data = None
            if position:
                position_data = {
                    "symbol": position.symbol,
                    "quantity": float(position.quantity) if position.quantity else 0,
                    "average_cost": float(position.average_cost) if position.average_cost else 0,
                    "current_price": float(position.current_price) if position.current_price else 0,
                    "market_value": float(position.market_value) if position.market_value else 0,
                    "unrealized_pnl": float(position.unrealized_pnl) if position.unrealized_pnl else 0,
                    "unrealized_pnl_pct": float(position.unrealized_pnl_pct) if position.unrealized_pnl_pct else 0,
                    "day_pnl": float(position.day_pnl) if position.day_pnl else 0,
                }
            
            # Get market snapshot
            snapshot = self.db.query(MarketSnapshot).filter(
                MarketSnapshot.symbol == symbol_upper,
                MarketSnapshot.analysis_type == "full",
            ).first()
            
            snapshot_data = None
            if snapshot:
                snapshot_data = {
                    "symbol": snapshot.symbol,
                    "stage_label": snapshot.stage_label,
                    "action_label": snapshot.action_label,
                    "scan_tier": snapshot.scan_tier,
                    "rs_rank": snapshot.rs_rank,
                    "rs_rating": snapshot.rs_rating,
                    "close": float(snapshot.close) if snapshot.close else None,
                    "sma_50": float(snapshot.sma_50) if snapshot.sma_50 else None,
                    "sma_150": float(snapshot.sma_150) if snapshot.sma_150 else None,
                    "sma_200": float(snapshot.sma_200) if snapshot.sma_200 else None,
                    "atr_14": float(snapshot.atr_14) if snapshot.atr_14 else None,
                    "rsi_14": float(snapshot.rsi_14) if snapshot.rsi_14 else None,
                    "td_buy_setup": snapshot.td_buy_setup,
                    "td_sell_setup": snapshot.td_sell_setup,
                    "regime_state": snapshot.regime_state,
                    "as_of_timestamp": snapshot.as_of_timestamp.isoformat() if snapshot.as_of_timestamp else None,
                }
            
            return {
                "symbol": symbol_upper,
                "position": position_data,
                "market_snapshot": snapshot_data,
                "has_position": position_data is not None,
                "has_snapshot": snapshot_data is not None,
            }
        except Exception as e:
            logger.error("Failed to get position details for %s: %s", symbol, e)
            return {"error": str(e)}
    
    async def _tool_get_activity(self, limit: int, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get recent portfolio activity (trades, dividends, etc.)."""
        try:
            from backend.models import Trade
            from sqlalchemy import desc
            
            user_id = 1
            
            query = self.db.query(Trade).filter(
                Trade.user_id == user_id
            ).order_by(desc(Trade.executed_at))
            
            if symbol:
                query = query.filter(Trade.symbol == symbol.upper())
            
            trades = query.limit(limit).all()
            
            activity = []
            for t in trades:
                activity.append({
                    "symbol": t.symbol,
                    "side": t.side,
                    "quantity": float(t.quantity) if t.quantity else 0,
                    "price": float(t.price) if t.price else 0,
                    "realized_pnl": float(t.realized_pnl) if t.realized_pnl else 0,
                    "executed_at": t.executed_at.isoformat() if t.executed_at else None,
                })
            
            return {"trades": activity, "count": len(activity)}
        except Exception as e:
            logger.error("Failed to get activity: %s", e)
            return {"error": str(e)}
    
    async def _tool_get_market_snapshot(self, symbol: str) -> Dict[str, Any]:
        """Get current market snapshot for a symbol."""
        if not symbol:
            return {"error": "Symbol is required"}
        
        try:
            from backend.services.market.market_data_service import MarketDataService
            
            svc = MarketDataService()
            snapshot = svc.get_snapshot_from_store(self.db, symbol.upper())
            
            if not snapshot:
                return {"error": f"No snapshot found for {symbol.upper()}"}
            
            return {
                "symbol": snapshot.symbol,
                "close": float(snapshot.close) if snapshot.close else None,
                "change_pct": float(snapshot.change_pct) if snapshot.change_pct else None,
                "stage_label": snapshot.stage_label,
                "action_label": snapshot.action_label,
                "scan_tier": snapshot.scan_tier,
                "rs_rank": snapshot.rs_rank,
                "rs_rating": snapshot.rs_rating,
                "sma_50": float(snapshot.sma_50) if snapshot.sma_50 else None,
                "sma_150": float(snapshot.sma_150) if snapshot.sma_150 else None,
                "sma_200": float(snapshot.sma_200) if snapshot.sma_200 else None,
                "atr_14": float(snapshot.atr_14) if snapshot.atr_14 else None,
                "rsi_14": float(snapshot.rsi_14) if snapshot.rsi_14 else None,
                "td_buy_setup": snapshot.td_buy_setup,
                "td_sell_setup": snapshot.td_sell_setup,
                "macd": float(snapshot.macd) if snapshot.macd else None,
                "macd_signal": float(snapshot.macd_signal) if snapshot.macd_signal else None,
                "regime_state": snapshot.regime_state,
                "sector": snapshot.sector,
                "industry": snapshot.industry,
                "as_of_timestamp": snapshot.as_of_timestamp.isoformat() if snapshot.as_of_timestamp else None,
            }
        except Exception as e:
            logger.error("Failed to get market snapshot for %s: %s", symbol, e)
            return {"error": str(e)}
    
    async def _tool_get_tracked_universe(self) -> Dict[str, Any]:
        """Get the tracked universe of symbols with their sources."""
        try:
            from backend.services.market.universe import tracked_symbols_with_source
            
            result = tracked_symbols_with_source(self.db)
            
            # Summarize by source
            by_source: Dict[str, int] = {}
            for sym_data in result:
                source = sym_data.get("source", "unknown")
                by_source[source] = by_source.get(source, 0) + 1
            
            return {
                "total_symbols": len(result),
                "by_source": by_source,
                "sample": result[:20],  # First 20 as sample
            }
        except Exception as e:
            logger.error("Failed to get tracked universe: %s", e)
            return {"error": str(e)}
    
    async def _tool_get_constituents(self, index: str) -> Dict[str, Any]:
        """Get constituents of a specific index."""
        try:
            from backend.models import IndexConstituent
            
            valid_indexes = ["SP500", "NASDAQ100", "RUSSELL2000"]
            index_upper = index.upper()
            
            if index_upper not in valid_indexes:
                return {"error": f"Invalid index. Choose from: {', '.join(valid_indexes)}"}
            
            constituents = self.db.query(IndexConstituent).filter(
                IndexConstituent.index_name == index_upper,
                IndexConstituent.is_active == True,
            ).order_by(IndexConstituent.symbol).all()
            
            symbols = [c.symbol for c in constituents]
            
            return {
                "index": index_upper,
                "count": len(symbols),
                "symbols": symbols,
            }
        except Exception as e:
            logger.error("Failed to get constituents for %s: %s", index, e)
            return {"error": str(e)}
    
    async def _tool_get_regime(self) -> Dict[str, Any]:
        """Get current market regime."""
        try:
            from backend.services.market.regime_engine import get_current_regime
            
            regime = get_current_regime(self.db)
            
            if not regime:
                return {"error": "No regime data available"}
            
            return {
                "regime_state": regime.regime_state,
                "composite_score": float(regime.composite_score) if regime.composite_score else None,
                "as_of_date": regime.as_of_date.isoformat() if regime.as_of_date else None,
                "inputs": {
                    "vix_current": float(regime.vix_current) if regime.vix_current else None,
                    "vix_sma_20": float(regime.vix_sma_20) if regime.vix_sma_20 else None,
                    "breadth_above_200ma": float(regime.breadth_above_200ma) if regime.breadth_above_200ma else None,
                    "breadth_above_50ma": float(regime.breadth_above_50ma) if regime.breadth_above_50ma else None,
                    "new_highs_lows_ratio": float(regime.new_highs_lows_ratio) if regime.new_highs_lows_ratio else None,
                    "sector_rs_dispersion": float(regime.sector_rs_dispersion) if regime.sector_rs_dispersion else None,
                },
                "scores": {
                    "vix_score": regime.vix_score,
                    "vix_trend_score": regime.vix_trend_score,
                    "breadth_score": regime.breadth_score,
                    "momentum_score": regime.momentum_score,
                    "new_highs_lows_score": regime.new_highs_lows_score,
                    "sector_score": regime.sector_score,
                },
                "portfolio_rules": {
                    "cash_floor_pct": float(regime.cash_floor_pct) if regime.cash_floor_pct else None,
                    "max_equity_exposure_pct": float(regime.max_equity_exposure_pct) if regime.max_equity_exposure_pct else None,
                    "regime_multiplier": float(regime.regime_multiplier) if regime.regime_multiplier else None,
                },
            }
        except Exception as e:
            logger.error("Failed to get regime: %s", e)
            return {"error": str(e)}
    
    async def _tool_describe_tables(self, table_name: Optional[str] = None) -> Dict[str, Any]:
        """Describe database tables and columns for query building."""
        try:
            from sqlalchemy import text
            
            if table_name:
                # Get columns for specific table
                result = self.db.execute(text("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = :table_name
                    ORDER BY ordinal_position
                """), {"table_name": table_name})
                
                columns = [
                    {"name": row.column_name, "type": row.data_type, "nullable": row.is_nullable}
                    for row in result
                ]
                
                if not columns:
                    return {"error": f"Table '{table_name}' not found"}
                
                return {"table": table_name, "columns": columns}
            else:
                # List all tables
                result = self.db.execute(text("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """))
                
                tables = [row.table_name for row in result]
                
                # Highlight key tables
                key_tables = [
                    "positions", "broker_accounts", "trades", "tax_lots",
                    "market_snapshot", "market_snapshot_history", "market_regime",
                    "index_constituents", "price_data", "instruments"
                ]
                
                return {
                    "tables": tables,
                    "key_tables": [t for t in key_tables if t in tables],
                    "hint": "Use describe_tables with table_name parameter to see columns",
                }
        except Exception as e:
            logger.error("Failed to describe tables: %s", e)
            return {"error": str(e)}
    
    # ==================== CODEBASE EXPLORATION TOOLS ====================
    
    async def _tool_read_file(
        self,
        path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Read a file from the backend codebase."""
        import os

        if not path:
            return {"error": "Path is required"}

        base = _resolve_backend_codebase_dir()
        if not base:
            return {"error": "Backend directory not found"}

        ok, full_path = _full_path_within_backend(base, path)
        if not ok:
            return {"error": "Path traversal not allowed"}

        if not os.path.exists(full_path):
            return {"error": f"File not found: {path}"}

        if not os.path.isfile(full_path):
            return {"error": f"Not a file: {path}. Use list_files for directories."}

        if start_line is not None and start_line < 1:
            return {"error": "start_line must be >= 1"}
        if end_line is not None and end_line < 1:
            return {"error": "end_line must be >= 1"}
        if start_line is not None and end_line is not None and end_line < start_line:
            return {"error": "end_line must be >= start_line"}

        if end_line is not None and start_line is None:
            first_line = 1
            last_cap: Optional[int] = end_line
        elif start_line is not None and end_line is None:
            first_line = start_line
            last_cap = None
        elif start_line is not None and end_line is not None:
            first_line = start_line
            last_cap = end_line
        else:
            first_line = 1
            last_cap = None

        max_lines = 300
        out_chunks: List[str] = []
        total_lines = 0
        truncated = False

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                for line in f:
                    total_lines += 1
                    if total_lines < first_line:
                        continue
                    if last_cap is not None and total_lines > last_cap:
                        for _ in f:
                            total_lines += 1
                        break
                    out_chunks.append(line)
                    if len(out_chunks) >= max_lines:
                        truncated = True
                        for _ in f:
                            total_lines += 1
                        break

            if total_lines > 0 and first_line > total_lines:
                return {
                    "error": (
                        f"start_line ({first_line}) exceeds file length ({total_lines})"
                    ),
                }

            if out_chunks:
                shown_start = first_line
                shown_end = first_line + len(out_chunks) - 1
            else:
                shown_start, shown_end = None, None

            showing_lines = (
                f"{shown_start}-{shown_end}"
                if shown_start is not None and shown_end is not None
                else "none"
            )

            return {
                "path": path,
                "content": "".join(out_chunks),
                "total_lines": total_lines,
                "showing_lines": showing_lines,
                "truncated": truncated,
            }
        except Exception as e:
            return {"error": f"Failed to read file: {e}"}

    async def _tool_list_files(self, path: str = "") -> Dict[str, Any]:
        """List files and directories in the backend codebase."""
        import os

        base = _resolve_backend_codebase_dir()
        if not base:
            return {"error": "Backend directory not found"}

        ok, full_path = _full_path_within_backend(base, path)
        if not ok:
            return {"error": "Path traversal not allowed"}

        if not os.path.exists(full_path):
            return {"error": f"Path not found: {path}"}
        
        if not os.path.isdir(full_path):
            return {"error": f"Not a directory: {path}. Use read_file for files."}
        
        try:
            entries = []
            for entry in sorted(os.listdir(full_path)):
                # Skip hidden files and __pycache__
                if entry.startswith(".") or entry == "__pycache__":
                    continue
                
                entry_path = os.path.join(full_path, entry)
                entry_type = "dir" if os.path.isdir(entry_path) else "file"
                entries.append({"name": entry, "type": entry_type})
                
                # Cap at 100 entries
                if len(entries) >= 100:
                    break
            
            return {
                "path": path or "(root)",
                "entries": entries,
                "count": len(entries),
            }
        except Exception as e:
            return {"error": f"Failed to list files: {e}"}
    
    # ==================== CONVERSATION PERSISTENCE ====================
    
    def _get_redis(self):
        """Get Redis client from market data service."""
        try:
            from backend.services.market.market_data_service import market_data_service
            return market_data_service.redis_client
        except Exception:
            return None
    
    def _trim_conversation_for_persistence(self) -> None:
        """Drop oldest messages after the system prompt so Redis payloads stay bounded."""
        conv = self._conversation
        if len(conv) <= 1:
            return

        def pop_oldest_turn() -> bool:
            if not conv:
                return False
            if conv[0].get("role") == "system":
                if len(conv) <= 1:
                    return False
                conv.pop(1)
                return True
            conv.pop(0)
            return True

        while len(conv) > AGENT_CONVERSATION_MAX_MESSAGES:
            if not pop_oldest_turn():
                break

        while (
            len(json.dumps(conv).encode("utf-8")) > AGENT_CONVERSATION_MAX_JSON_BYTES
            and len(conv) > 1
        ):
            if conv[0].get("role") == "system" and len(conv) == 1:
                break
            if not pop_oldest_turn():
                break

    def _save_conversation(self) -> bool:
        """Save conversation to Redis."""
        self._trim_conversation_for_persistence()
        redis = self._get_redis()
        if not redis:
            return False
        try:
            key = f"agent:conversation:{self.session_id}"
            redis.setex(key, 7200, json.dumps(self._conversation))  # 2hr TTL
            return True
        except Exception as e:
            logger.warning("Failed to save conversation: %s", e)
            return False

    def _load_conversation(self, session_id: str) -> str:
        """Load conversation from Redis.

        Returns:
            ``loaded``, ``missing``, or ``unavailable``.
        """
        redis = self._get_redis()
        if not redis:
            return "unavailable"
        try:
            key = f"agent:conversation:{session_id}"
            data = redis.get(key)
            if not data:
                return "missing"
            self._conversation = json.loads(
                data.decode("utf-8") if isinstance(data, bytes) else data
            )
            self.session_id = session_id
            return "loaded"
        except Exception as e:
            logger.warning("Failed to load conversation: %s", e)
            return "unavailable"
    
    async def chat(self, user_message: str) -> Dict[str, Any]:
        """
        Process a user message in a multi-turn conversation.
        
        This is the main entry point for the chat endpoint.
        """
        if not settings.OPENAI_API_KEY:
            return {"error": "LLM not configured (OPENAI_API_KEY missing)"}
        
        # Initialize system prompt if this is a new conversation
        if not self._conversation:
            system_msg = SYSTEM_PROMPT.format(
                current_time=datetime.now(timezone.utc).isoformat(),
                autonomy_level=settings.AGENT_AUTONOMY_LEVEL,
            )
            self._conversation = [{"role": "system", "content": system_msg}]
        
        # Add user message
        self._conversation.append({"role": "user", "content": user_message})
        
        tool_calls_made = []
        actions_taken = []
        max_iterations = 12
        assistant_response = None  # Track the actual assistant response
        
        for iteration in range(max_iterations):
            last_msg = self._conversation[-1] if self._conversation else {}
            last_role = last_msg.get("role")
            # Match analyze_and_act: force a tool on first LLM call of this turn.
            if iteration == 0:
                tool_choice = "required"
            elif iteration == max_iterations - 1 and last_role == "tool":
                # Avoid exhausting the loop with endless tool calls without a summary.
                tool_choice = "none"
            else:
                tool_choice = "auto"
            
            logger.info(
                "Chat iteration %d, tool_choice=%s last_role=%s",
                iteration,
                tool_choice,
                last_role,
            )
            response = await self._call_llm(tool_choice=tool_choice)
            
            if not response:
                err = getattr(self, "_last_openai_error", None) or "Unknown error"
                logger.warning("LLM returned no response on iteration %d: %s", iteration, err)
                assistant_response = (
                    f"I could not reach the language model ({err}). "
                    "Check OPENAI_API_KEY, network, and logs."
                )
                break
            
            choice0 = (response.get("choices") or [{}])[0]
            message = choice0.get("message") or {}
            logger.info(
                "LLM response has_tool_calls=%s content_len=%s finish=%s",
                bool(message.get("tool_calls")),
                len(message.get("content") or ""),
                choice0.get("finish_reason"),
            )
            
            if message.get("tool_calls"):
                self._conversation.append(message)
                
                for tool_call in message["tool_calls"]:
                    func = tool_call.get("function", {})
                    tool_name = func.get("name")
                    logger.info("Executing tool: %s", tool_name)
                    try:
                        tool_args = json.loads(func.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        tool_args = {}
                    
                    # Execute tool
                    result, action = await self._execute_tool(
                        tool_name, tool_args, message.get("content") or ""
                    )
                    
                    # Add tool result to conversation
                    self._conversation.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(result),
                    })
                    
                    tool_calls_made.append({
                        "name": tool_name,
                        "args": tool_args,
                        "result_preview": str(result)[:200] + "..." if len(str(result)) > 200 else str(result),
                    })
                    
                    if action:
                        actions_taken.append(self._action_to_dict(action))
            else:
                # No tool calls - this is the final text response
                assistant_response = message.get("content") or ""
                self._conversation.append(message)
                logger.info("Got final assistant response, length=%d", len(assistant_response))
                break
        
        # Save conversation for continuity
        self._save_conversation()
        
        # Use tracked assistant response, or provide error message
        final_response = assistant_response
        if final_response is None:
            logger.error(
                "No assistant response after %d iterations (tools=%s)",
                max_iterations,
                len(tool_calls_made),
            )
            final_response = (
                "I ran tools but did not get a final answer from the model. "
                "Try **New Chat** or a shorter question. If this persists, check backend logs."
            )
        
        return {
            "session_id": self.session_id,
            "response": final_response,
            "tool_calls": tool_calls_made,
            "actions": actions_taken,
        }
    
    def _get_action_display_name(self, tool_name: str) -> str:
        """Get a human-readable name for an action."""
        return tool_name.replace("_", " ").title()
    
    def _action_to_dict(self, action: AgentAction) -> Dict[str, Any]:
        """Convert an AgentAction to a dictionary."""
        return {
            "id": action.id,
            "action_type": action.action_type,
            "action_name": action.action_name,
            "risk_level": action.risk_level,
            "status": action.status,
            "auto_approved": action.auto_approved,
            "created_at": action.created_at.isoformat() if action.created_at else None,
        }
