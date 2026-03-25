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

SYSTEM_PROMPT = """You are an intelligent operations agent for AxiomFolio, a quantitative portfolio intelligence platform.

Your role is to:
1. Monitor system health across dimensions: coverage (market data freshness), stage_quality (indicator computation), jobs (task execution), audit (history recording), regime (market regime tracking)
2. Diagnose issues by analyzing health data, querying the database, and researching errors
3. Take appropriate remediation actions to fix problems
4. Escalate critical issues that require human intervention

Available information:
- Coverage: Tracks daily OHLCV data freshness for ~3500 symbols (S&P 500, NASDAQ-100, Russell 2000)
- Stage Quality: Validates that indicators (stage, RS, TD Sequential) are computed correctly
- Jobs: Monitors Celery task execution for stuck or failed jobs
- Audit: Ensures daily snapshot history is recorded
- Regime: Tracks market regime (R1-R5 based on VIX, breadth, sectors)

Guidelines:
- Always check health status first before taking remediation actions
- Use database queries to investigate root causes before acting
- Prefer targeted fixes over broad recomputes
- Send alerts for issues you cannot fix automatically
- Be concise in your reasoning

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
        
        for _ in range(max_iterations):
            response = await self._call_llm()
            
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
    
    async def _call_llm(self) -> Optional[Dict[str, Any]]:
        """Call the OpenAI API."""
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": MODEL,
            "messages": self._conversation,
            "tools": get_tools_for_openai(),
            "tool_choice": "auto",
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
        query_upper = query.strip().upper()
        if not query_upper.startswith("SELECT"):
            return {"error": "Only SELECT queries are allowed"}
        
        forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"]
        for word in forbidden:
            if word in query_upper:
                return {"error": f"Query contains forbidden keyword: {word}"}
        
        try:
            from sqlalchemy import text
            result = self.db.execute(text(f"{query} LIMIT {limit}"))
            rows = [dict(row._mapping) for row in result]
            return {"rows": rows, "count": len(rows)}
        except Exception as e:
            return {"error": str(e)}
    
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
