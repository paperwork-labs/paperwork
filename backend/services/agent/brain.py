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
from .tools import get_tools_for_openai, TOOL_TO_CELERY_TASK

logger = logging.getLogger(__name__)

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """You are AxiomFolio's AI assistant for the admin user. You help with portfolio analysis, market research, and system operations.

## Your Capabilities

1. **Portfolio Questions** — positions, P&L, risk metrics, recent activity
2. **Market Questions** — stages, indicators, regime, tracked universe, constituents
3. **System Health** — coverage, jobs, data freshness monitoring
4. **Remediation** — backfill data, recompute indicators, recover stuck jobs

## Tool Usage Guidelines

**For portfolio questions:**
- `get_portfolio_summary` — risk metrics, sector allocation, P&L overview
- `get_position_details` — detailed info on specific symbols including stage/indicators
- `get_activity` — recent trades, dividends, transfers

**For market questions:**
- `get_market_snapshot` — current stage, indicators, and signals for a symbol
- `get_tracked_universe` — what symbols we track and why (index membership, holdings)
- `get_constituents` — list symbols in an index (SP500, NASDAQ100, RUSSELL2000)
- `get_regime` — current market regime (R1-R5) with inputs

**For schema/data discovery:**
- `describe_tables` — list available tables and columns (use before query_database)
- `query_database` — custom SQL for advanced queries (SELECT/WITH only)

**For system health:**
- `check_health` — composite health status across all dimensions
- `list_jobs` — recent task executions and their status

## Remediation Playbook (when issues detected)

| Dimension | Yellow/Red Status | Tool to Use |
|-----------|-------------------|-------------|
| coverage | Stale/missing price data | `backfill_stale_daily` or `bootstrap_coverage` |
| stage_quality | Indicators not computed | `recompute_indicators` |
| jobs | Stuck/stale tasks | `recover_stale_jobs` |
| regime | Missing regime data | `compute_regime` |
| audit | Missing history | `record_daily` |

## Guidelines

- ALWAYS use a tool to gather data before answering — do not guess
- For health issues, investigate with `check_health` first, then remediate
- Be concise and actionable in responses
- If you cannot answer, say so clearly

Current time: {current_time}
Autonomy level: {autonomy_level}
"""


class AgentBrain:
    """LLM-powered agent brain for intelligent operations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.session_id = str(uuid.uuid4())[:8]
        self._conversation: List[Dict[str, Any]] = []
    
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
    
    async def _call_llm(self, tool_choice: str = "auto") -> Optional[Dict[str, Any]]:
        """Call the OpenAI API."""
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": MODEL,
            "messages": self._conversation,
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
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        logger.error("OpenAI API error: %s - %s", resp.status, error)
                        return None
                    return await resp.json()
        except Exception as e:
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
        
        if risk == RiskLevel.SAFE:
            result = await self._execute_safe_tool(tool_name, tool_args)
            action.status = "completed"
            action.result = result
            action.executed_at = datetime.utcnow()
            action.completed_at = datetime.utcnow()
            action.auto_approved = True
            self.db.commit()
            return result, action
        
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
