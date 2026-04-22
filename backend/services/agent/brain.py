"""
Agent Brain
===========

LLM-powered decision engine for the auto-ops agent.
Uses OpenAI GPT-4o-mini for cost-effective intelligent operations.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from urllib.parse import urlparse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.agent_action import AgentAction
from backend.models.entitlement import SubscriptionTier
from backend.models.user import User
from backend.services.agent.byok_anomaly import record_fallback as _record_byok_fallback
from backend.services.billing.entitlement_service import EntitlementService
from backend.services.security.credential_vault import credential_vault
from .taxonomy import RiskLevel, classify_action_risk, can_auto_execute
from .tools import get_tools_for_openai, INLINE_ONLY_AGENT_TOOLS, TOOL_TO_CELERY_TASK

logger = logging.getLogger(__name__)

# Bound Redis payload / memory for persisted chat (tool outputs can be large).
AGENT_CONVERSATION_MAX_MESSAGES = 120
AGENT_CONVERSATION_MAX_JSON_BYTES = 400_000

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"
BYOK_ALLOWED_HOSTS = frozenset({"api.openai.com", "api.anthropic.com"})
BYOK_PROVIDER_URLS: Dict[str, str] = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/messages",
}


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


CODEBASE_ALLOWED_PREFIXES = ("services/", "api/", "tasks/", "models/", "utils/", "tests/")
CODEBASE_DENIED_PATTERNS = (".env", ".pem", ".key", "secret", "credential", "password", "__pycache__")


def _assert_codebase_path_allowed(rel_path: str) -> Optional[str]:
    """
    Check if a relative path is allowed for codebase exploration.
    Returns an error string if denied, None if allowed.
    """
    if not rel_path:
        return None
    rel_lower = rel_path.lower()
    for pattern in CODEBASE_DENIED_PATTERNS:
        if pattern in rel_lower:
            return f"Access denied: path contains sensitive pattern '{pattern}'"
    for prefix in CODEBASE_ALLOWED_PREFIXES:
        if rel_path.startswith(prefix):
            return None
    return f"Access denied: path must start with one of {CODEBASE_ALLOWED_PREFIXES}"


def _sanitize_tool_calls(raw_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter out malformed tool_calls from OpenAI response.
    Returns only valid calls with non-empty id and function.name.
    """
    valid = []
    for i, tc in enumerate(raw_calls or []):
        fn = tc.get("function") or {}
        call_id = tc.get("id")
        call_name = fn.get("name")
        if not call_id or not call_name:
            logger.warning(
                "Dropping malformed tool_call[%d]: missing id=%s or name=%s",
                i, call_id, call_name
            )
            continue
        valid.append(tc)
    return valid


SYSTEM_PROMPT = """You are AxiomFolio's AI admin assistant. You are the operator's right hand — proactive, capable, and resourceful. When asked to do something, find a way using your tools. Only refuse if there is a genuine safety or security concern.

## What You Can Do

1. **Portfolio** — positions, P&L, risk metrics, activity, account balances
2. **Market Data** — stages, indicators, regime, tracked universe, index constituents
3. **Codebase** — read files, explain how things work, find where code lives
4. **Database** — explore schema, run read-only queries to investigate data
5. **Operations** — monitor health, backfill data, recompute indicators, cancel stuck jobs
6. **Users** — list users and their details (read-only, sensitive fields redacted)
7. **Data Integrity** — check data accuracy, provider metrics, pre-market readiness

## Tool Selection Guide

| Question Type | Tools |
|---------------|-------|
| "What positions do I have?" | `get_portfolio_summary` |
| "How is NVDA doing?" | `get_position_details` or `get_market_snapshot` |
| "What's in the S&P 500?" | `get_constituents` |
| "What's the market regime?" | `get_regime` |
| "Show me all users" | `list_users` |
| "Cancel that stuck job" | `cancel_job` (list active workers first if task_id unknown) |
| "Show running jobs" | `list_jobs` |
| "How does stage calculation work?" | `read_file` (services/market/indicator_engine.py) |
| "What files are in services/?" | `list_files` |
| "What tables exist?" | `describe_tables` |
| "Custom data query" | `query_database` (after describe_tables) |
| "Is the system healthy?" | `check_health` |
| "Is data accurate?" | `check_data_accuracy` |
| "How are API providers doing?" | `get_provider_metrics` |

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
| coverage red | `recompute_indicators` (DB-only); `backfill_stale_daily` only with explicit user approval (uses FMP bandwidth) |
| stage_quality red | `recompute_indicators` then `repair_stage_history` |
| jobs stale | `recover_stale_jobs` |
| jobs stuck | `list_jobs` to find task_id, then `cancel_job` |
| regime missing | `compute_regime` |
| audit gaps | `record_daily` |
| fundamentals low | `fill_missing_fundamentals` |
| data accuracy issues | `check_data_accuracy` for details |

## Guidelines

- ALWAYS use tools to get data — never guess or make up information
- For codebase questions, use `list_files` then `read_file` to find and read relevant code
- For database questions, use `describe_tables` before `query_database`
- When a user asks you to do something, try your best to help. You have powerful tools — use them.
- Be concise, direct, and action-oriented

## FMP Bandwidth Protection

FMP API bandwidth is a precious, limited resource (50 GB / 30-day rolling).
Historical OHLCV data is already fully backfilled in the database.
This section overrides any earlier remediation guidance that suggests bandwidth-heavy backfills.
NEVER trigger `deep_backfill`, `backfill_stale_daily`, or `bootstrap_coverage`
unless the user explicitly requests it and understands the bandwidth cost.
Treat those tools as approval-required and bandwidth-expensive, not default remediation.
For coverage issues, use DB-only remediation first: prefer `recompute_indicators`
or `repair_stage_history` before considering any bandwidth-heavy action.
For missing daily bars, the nightly pipeline handles incremental updates automatically.

## Out of Scope

These require the admin UI or direct access:
- Broker credential setup or OAuth flows
- Direct database writes (INSERT/UPDATE/DELETE)
- Order placement or trade execution
- Alembic migrations or schema changes

Current time: {current_time}
Autonomy level: {autonomy_level}
"""


class AgentBrain:
    """LLM-powered agent brain for intelligent operations."""
    
    def __init__(self, db: Session, user_id: Optional[int] = None):
        """Construct an agent scoped to a tenant.

        ``user_id`` MUST be passed for all per-user tools (portfolio
        summary, position details, activity). For pure ops/diagnostic
        callers that don't query user data, ``None`` is accepted but
        any per-user tool will raise rather than silently fall back to
        ``user_id=1`` (the old prod-corruption hazard, D88).
        """
        self.db = db
        self.user_id = user_id
        self.session_id = str(uuid.uuid4())[:8]
        self._conversation: List[Dict[str, Any]] = []
        self._last_openai_error: Optional[str] = None

    def _require_user_id(self, tool_name: str) -> int:
        if self.user_id is None:
            raise RuntimeError(
                f"AgentBrain.{tool_name} requires user_id; "
                "construct AgentBrain(db, user_id=...) for per-tenant calls."
            )
        return int(self.user_id)

    def _resolve_llm_target(self) -> Tuple[str, str]:
        """Resolve provider URL + API key, preferring paid-tier BYOK."""
        default_key = settings.OPENAI_API_KEY
        if not default_key or self.user_id is None:
            return OPENAI_API_URL, default_key or ""
        user = (
            self.db.query(User)
            .filter(User.id == int(self.user_id))
            .one_or_none()
        )
        if user is None:
            return OPENAI_API_URL, default_key
        tier = EntitlementService.effective_tier(self.db, user)
        if (
            SubscriptionTier.rank(tier) < SubscriptionTier.rank(SubscriptionTier.PRO)
            or not user.llm_provider_key_encrypted
        ):
            return OPENAI_API_URL, default_key
        try:
            payload = credential_vault.decrypt_dict(user.llm_provider_key_encrypted)
            provider = str(payload.get("provider") or "").strip().lower()
            api_key = str(payload.get("api_key") or "").strip()
            provider_url = BYOK_PROVIDER_URLS.get(provider)
            if not provider_url:
                _record_byok_fallback(
                    self.user_id, "provider_not_allowed", provider=provider
                )
                return OPENAI_API_URL, default_key
            if not api_key:
                _record_byok_fallback(
                    self.user_id, "empty_api_key", provider=provider
                )
                return OPENAI_API_URL, default_key
            if provider != "openai":
                # Anthropic BYOK storage is supported; wire transport in follow-up.
                _record_byok_fallback(
                    self.user_id, "anthropic_transport_pending", provider=provider
                )
                return OPENAI_API_URL, default_key
            host = (urlparse(provider_url).hostname or "").lower()
            if host not in BYOK_ALLOWED_HOSTS:
                _record_byok_fallback(
                    self.user_id, "host_not_allowlisted", provider=provider
                )
                raise ValueError(f"provider host not allow-listed: {host}")
            return provider_url, api_key
        except Exception as e:
            logger.warning("BYOK key resolution failed for user_id=%s: %s", self.user_id, e)
            _record_byok_fallback(self.user_id, "decrypt_failed")
            return OPENAI_API_URL, default_key
    
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
            
            raw_tool_calls = message.get("tool_calls")
            if raw_tool_calls:
                valid_tool_calls = _sanitize_tool_calls(raw_tool_calls)
                if not valid_tool_calls:
                    logger.warning("All tool_calls were invalid in analyze_and_act, breaking loop")
                    break
                message_to_store = dict(message)
                message_to_store["tool_calls"] = valid_tool_calls
                self._conversation.append(message_to_store)
                
                for tool_call in valid_tool_calls:
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
        """Build the initial user message with full health dimension details."""
        parts = [
            "Current system health status:",
            f"Composite: {health_data.get('composite_status', 'unknown')}",
            "",
            "Dimension details:",
        ]

        for dim_name, dim_data in health_data.get("dimensions", {}).items():
            if not isinstance(dim_data, dict):
                continue
            status = dim_data.get("status", "unknown")
            parts.append(f"  [{dim_name}] status={status}")

            if dim_name == "coverage":
                parts.append(f"    daily_pct={dim_data.get('daily_pct')}%  stale_daily={dim_data.get('stale_daily')}")
                parts.append(f"    tracked_count={dim_data.get('tracked_count')}")
                issues = dim_data.get("constituent_issues", [])
                if issues:
                    parts.append(f"    CONSTITUENT ALERT: {', '.join(issues)} have 0 constituents")
                indices = dim_data.get("indices", {})
                if indices:
                    idx_parts = []
                    for k, v in indices.items():
                        if isinstance(v, dict):
                            count = v.get("count")
                        else:
                            count = v
                        idx_parts.append(f"{k}={'?' if count is None else count}")
                    parts.append(f"    indices: {', '.join(idx_parts)}")
            elif dim_name == "stage_quality":
                parts.append(f"    unknown_rate={dim_data.get('unknown_rate')}  invalid={dim_data.get('invalid_count')}  monotonicity={dim_data.get('monotonicity_issues')}")
            elif dim_name == "audit":
                parts.append(f"    daily_fill={dim_data.get('daily_fill_pct')}%  snapshot_fill={dim_data.get('snapshot_fill_pct')}%")
                depth = dim_data.get("history_depth_years")
                if depth is not None:
                    parts.append(f"    history_depth={depth} years")
                missing = dim_data.get("missing_sample", [])
                if missing:
                    parts.append(f"    missing_sample: {', '.join(missing[:10])}")
            elif dim_name == "fundamentals":
                parts.append(f"    fill_pct={dim_data.get('fundamentals_fill_pct')}%  filled={dim_data.get('filled_count')}/{dim_data.get('tracked_total')}")
            elif dim_name == "regime":
                parts.append(f"    state={dim_data.get('regime_state')}  score={dim_data.get('composite_score')}  age={dim_data.get('age_hours')}h")
            elif dim_name == "jobs":
                parts.append(f"    success_rate={dim_data.get('success_rate')}  errors={dim_data.get('error_count')}/{dim_data.get('total')}")
            else:
                message = dim_data.get("message", "")
                if message:
                    parts.append(f"    {message}")

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
        target_url, target_key = self._resolve_llm_target()
        headers = {
            "Authorization": f"Bearer {target_key}",
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
                    target_url,
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

        Resilient design: Audit trail (AgentAction) failures never block tool
        execution. Users get their results even if the audit record fails to write.
        
        Returns:
            Tuple of (result_dict, AgentAction or None)
        """
        risk = classify_action_risk(tool_name)
        auto_exec = can_auto_execute(tool_name, settings.AGENT_AUTONOMY_LEVEL)

        # Try to create audit record, but don't block on failure
        action: Optional[AgentAction] = None
        audit_ok = False
        try:
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
            audit_ok = True
        except Exception as db_err:
            logger.warning(
                "Audit record failed for tool %s (proceeding anyway): %s",
                tool_name, db_err, exc_info=True
            )
            try:
                self.db.rollback()
            except Exception as rb_err:
                logger.warning(
                    "Rollback after audit record failure for %s failed: %s",
                    tool_name,
                    rb_err,
                )
            action = None

        def _finalize_action(result: Dict[str, Any], status: str) -> None:
            """Update and commit the action record if it exists."""
            if action is None:
                return
            try:
                action.status = status
                action.result = result
                action.executed_at = datetime.now(timezone.utc)
                action.completed_at = datetime.now(timezone.utc)
                action.auto_approved = True
                self.db.commit()
            except Exception as db_err:
                logger.warning(
                    "Failed to finalize audit record for %s: %s",
                    tool_name, db_err
                )
                try:
                    self.db.rollback()
                except Exception as rb_err:
                    logger.warning(
                        "Rollback after finalize audit failure for %s failed: %s",
                        tool_name,
                        rb_err,
                    )

        # SAFE or INLINE_ONLY tools: execute inline
        if risk == RiskLevel.SAFE or tool_name in INLINE_ONLY_AGENT_TOOLS:
            result = await self._execute_safe_tool(tool_name, tool_args)
            _finalize_action(result, "completed")
            return result, action

        # MODERATE tools with auto_exec: dispatch to Celery
        if auto_exec:
            result = await self._dispatch_celery_task(tool_name, tool_args)
            if action:
                action.task_id = result.get("task_id")
                if result.get("error"):
                    action.error = result["error"]
                    _finalize_action(result, "failed")
                else:
                    action.status = "executing"
                    action.executed_at = datetime.now(timezone.utc)
                    action.auto_approved = True
                    try:
                        self.db.commit()
                    except Exception as db_err:
                        logger.warning(
                            "Failed to update audit record for celery task %s: %s",
                            tool_name, db_err
                        )
                        try:
                            self.db.rollback()
                        except Exception as rb_err:
                            logger.warning(
                                "Rollback after celery audit update failure for %s failed: %s",
                                tool_name,
                                rb_err,
                            )
            return result, action

        # RISKY/CRITICAL tools: require approval
        if action:
            action.status = "pending_approval"
            try:
                self.db.commit()
            except Exception as db_err:
                logger.warning(
                    "Failed to set pending_approval status for %s: %s",
                    tool_name, db_err
                )
                try:
                    self.db.rollback()
                except Exception as rb_err:
                    logger.warning(
                        "Rollback after pending_approval commit failure for %s failed: %s",
                        tool_name,
                        rb_err,
                    )

        return {
            "status": "pending_approval",
            "message": f"Action '{tool_name}' requires human approval (risk: {risk.value})",
            "action_id": action.id if action else None,
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

        # Schedule management tools
        if tool_name == "list_schedules":
            return await self._tool_list_schedules()

        if tool_name == "run_task_now":
            return await self._tool_run_task_now(args.get("task_id", ""))

        # Market insight tools
        if tool_name == "get_stage_distribution":
            return await self._tool_get_stage_distribution()

        if tool_name == "get_sector_strength":
            return await self._tool_get_sector_strength()

        if tool_name == "get_top_scans":
            return await self._tool_get_top_scans(
                args.get("scan_tier", "Breakout Elite"),
                args.get("limit", 10),
            )

        if tool_name == "get_exit_alerts":
            return await self._tool_get_exit_alerts()

        if tool_name == "get_regime_history":
            return await self._tool_get_regime_history(args.get("days", 30))

        # Market Context tools
        if tool_name == "get_rotation_analysis":
            return await self._tool_get_rotation_analysis()

        if tool_name == "get_breadth_momentum":
            return await self._tool_get_breadth_momentum(args.get("days", 20))

        if tool_name == "compare_historical_regime":
            return await self._tool_compare_historical_regime(args.get("lookback_years", 2))

        if tool_name == "get_market_internals":
            return await self._tool_get_market_internals()

        # Research & Strategy tools
        if tool_name == "backtest_scan":
            return await self._tool_backtest_scan(
                args.get("scan_tier", "Breakout Elite"),
                args.get("days", 90),
                args.get("holding_period", 20),
            )

        if tool_name == "get_similar_setups":
            return await self._tool_get_similar_setups(
                args.get("symbol", ""),
                args.get("limit", 10),
            )

        if tool_name == "get_strategy_stats":
            return await self._tool_get_strategy_stats(args.get("strategy_id"))

        if tool_name == "analyze_historical_entry":
            return await self._tool_analyze_historical_entry(
                args.get("stage", "2A"),
                args.get("regime", "R3"),
                args.get("days", 180),
            )

        if tool_name == "list_strategies":
            return await self._tool_list_strategies()

        if tool_name == "run_backtest":
            return await self._tool_run_backtest(
                args.get("strategy_id"),
                args.get("start_date"),
                args.get("end_date"),
                args.get("initial_capital", 100000),
            )

        if tool_name == "list_strategy_templates":
            return await self._tool_list_strategy_templates()

        if tool_name == "create_strategy":
            return await self._tool_create_strategy(
                args.get("name", ""),
                args.get("template_id", ""),
                args.get("description"),
                args.get("overrides", {}),
            )

        # Technical Analysis tools
        if tool_name == "calculate_support_resistance":
            return await self._tool_calculate_support_resistance(
                args.get("symbol", ""),
                args.get("lookback_days", 60),
            )

        # Data Integrity tools
        if tool_name == "check_data_accuracy":
            return await self._tool_check_data_accuracy()

        if tool_name == "get_provider_metrics":
            return await self._tool_get_provider_metrics()

        if tool_name == "check_pre_market_readiness":
            return await self._tool_check_pre_market_readiness()

        if tool_name == "cancel_job":
            return await self._tool_cancel_job(**args)

        if tool_name == "list_users":
            return await self._tool_list_users()

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
        """Send an alert to Brain webhook."""
        from backend.services.brain.webhook_client import brain_webhook

        if not brain_webhook.webhook_url:
            logger.info("Alert (no webhook): [%s] %s", severity, message)
            return {"status": "logged", "message": "No webhook configured"}

        try:
            ok = await brain_webhook.notify(
                "agent_alert",
                {"message": message, "severity": severity},
                user_id=None,
            )
            return {"status": "sent" if ok else "failed"}
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
                # Use module singleton (same as AdminHealthService), not a non-existent get_instance().
                from backend.services.clients.ibkr_client import ibkr_client

                health = getattr(ibkr_client, "connection_health", {}) or {}
                results["ibkr"] = {
                    "connected": ibkr_client.is_connected(),
                    "health_status": health.get("status", "unknown"),
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

            user_id = self._require_user_id("_tool_get_portfolio_summary")
            
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
            user_id = self._require_user_id("_tool_get_position_details")
            
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

            user_id = self._require_user_id("_tool_get_activity")
            
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
            from backend.services.market.market_data_service import snapshot_builder

            snapshot = snapshot_builder.get_snapshot_from_store(self.db, symbol.upper())
            
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
    
    # ==================== SCHEDULE MANAGEMENT TOOLS ====================

    async def _tool_list_schedules(self) -> Dict[str, Any]:
        """List all scheduled tasks from the job catalog with last run status."""
        from backend.tasks.job_catalog import CATALOG
        from backend.models.market_data import JobRun

        schedules = []
        for job in CATALOG:
            entry: Dict[str, Any] = {
                "id": job.id,
                "display_name": job.display_name,
                "group": job.group,
                "task": job.task,
                "cron": job.default_cron,
                "timezone": job.default_tz,
            }
            if job.job_run_label:
                try:
                    last = (
                        self.db.query(JobRun)
                        .filter(JobRun.task_name == job.job_run_label)
                        .order_by(JobRun.started_at.desc())
                        .first()
                    )
                    if last:
                        entry["last_run"] = {
                            "status": last.status,
                            "started_at": last.started_at.isoformat() if last.started_at else None,
                            "finished_at": last.finished_at.isoformat() if last.finished_at else None,
                        }
                except Exception as hist_err:
                    logger.warning(
                        "Failed to load last JobRun for schedule %s: %s",
                        getattr(job, "job_run_label", job.id),
                        hist_err,
                    )
            schedules.append(entry)

        return {"schedules": schedules, "count": len(schedules), "scheduler": "celery_beat"}

    async def _tool_run_task_now(self, task_id: str) -> Dict[str, Any]:
        """Trigger a catalog task to run immediately via Celery."""
        from backend.tasks.job_catalog import CATALOG
        from backend.tasks.celery_app import celery_app

        catalog_map = {j.id: j for j in CATALOG}
        job = catalog_map.get(task_id)
        if not job:
            return {
                "error": f"Unknown task_id: {task_id}",
                "available": sorted(catalog_map.keys()),
            }

        try:
            result = celery_app.send_task(
                job.task,
                kwargs=job.kwargs or {},
                args=job.args or [],
                queue=job.queue or "celery",
            )
            return {
                "status": "dispatched",
                "task_id": result.id,
                "task": job.task,
                "display_name": job.display_name,
            }
        except Exception as e:
            logger.warning("run_task_now failed for %s: %s", task_id, e)
            return {"error": "Failed to dispatch task", "type": type(e).__name__}

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

        access_error = _assert_codebase_path_allowed(path)
        if access_error:
            return {"error": access_error}

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

        if path:
            access_error = _assert_codebase_path_allowed(path)
            if access_error:
                return {"error": access_error}

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

    # ==================== MARKET INSIGHT TOOLS ====================

    async def _tool_get_stage_distribution(self) -> Dict[str, Any]:
        """Get distribution of stocks by stage across tracked universe."""
        try:
            from sqlalchemy import func
            from backend.models.market_data import MarketSnapshot

            results = (
                self.db.query(MarketSnapshot.stage_label, func.count(MarketSnapshot.id))
                .filter(MarketSnapshot.stage_label.isnot(None))
                .group_by(MarketSnapshot.stage_label)
                .all()
            )

            distribution = {r[0]: r[1] for r in results if r[0]}
            total = sum(distribution.values())

            bullish_stages = ["2A", "2B", "2C"]
            bearish_stages = ["4A", "4B", "4C"]
            bullish_count = sum(distribution.get(s, 0) for s in bullish_stages)
            bearish_count = sum(distribution.get(s, 0) for s in bearish_stages)

            return {
                "distribution": distribution,
                "total": total,
                "bullish_count": bullish_count,
                "bullish_pct": round(bullish_count / total * 100, 1) if total else 0,
                "bearish_count": bearish_count,
                "bearish_pct": round(bearish_count / total * 100, 1) if total else 0,
                "interpretation": (
                    "Bullish breadth" if bullish_count > bearish_count * 1.5
                    else "Bearish breadth" if bearish_count > bullish_count * 1.5
                    else "Mixed breadth"
                ),
            }
        except Exception as e:
            logger.error("Failed to get stage distribution: %s", e)
            return {"error": str(e)}

    async def _tool_get_sector_strength(self) -> Dict[str, Any]:
        """Rank sectors by % of stocks in constructive stages (2A/2B/2C)."""
        try:
            from sqlalchemy import func, case
            from backend.models.market_data import MarketSnapshot

            bullish_stages = ["2A", "2B", "2C"]

            results = (
                self.db.query(
                    MarketSnapshot.sector,
                    func.count(MarketSnapshot.id).label("total"),
                    func.sum(
                        case((MarketSnapshot.stage_label.in_(bullish_stages), 1), else_=0)
                    ).label("bullish"),
                )
                .filter(MarketSnapshot.sector.isnot(None))
                .filter(MarketSnapshot.sector != "")
                .group_by(MarketSnapshot.sector)
                .having(func.count(MarketSnapshot.id) >= 5)
                .all()
            )

            sectors = []
            for r in results:
                bullish_pct = round(r.bullish / r.total * 100, 1) if r.total else 0
                sectors.append({
                    "sector": r.sector,
                    "total": r.total,
                    "bullish": r.bullish,
                    "bullish_pct": bullish_pct,
                })

            sectors.sort(key=lambda x: x["bullish_pct"], reverse=True)

            return {
                "sectors": sectors[:15],
                "leaders": [s["sector"] for s in sectors[:3]],
                "laggards": [s["sector"] for s in sectors[-3:]],
            }
        except Exception as e:
            logger.error("Failed to get sector strength: %s", e)
            return {"error": str(e)}

    async def _tool_get_top_scans(
        self, scan_tier: str = "Breakout Elite", limit: int = 10
    ) -> Dict[str, Any]:
        """Get top stocks passing scan overlay filters."""
        try:
            from backend.models.market_data import MarketSnapshot

            query = self.db.query(MarketSnapshot).filter(
                MarketSnapshot.scan_tier.isnot(None)
            )

            if scan_tier:
                query = query.filter(MarketSnapshot.scan_tier == scan_tier)

            results = (
                query.order_by(MarketSnapshot.rs_mansfield_pct.desc().nullslast())
                .limit(limit)
                .all()
            )

            stocks = []
            for r in results:
                stocks.append({
                    "symbol": r.symbol,
                    "name": r.name,
                    "stage": r.stage_label,
                    "scan_tier": r.scan_tier,
                    "action": r.action_label,
                    "rs_rank": round(r.rs_mansfield_pct, 1) if r.rs_mansfield_pct else None,
                    "sector": r.sector,
                })

            return {
                "tier": scan_tier,
                "count": len(stocks),
                "stocks": stocks,
            }
        except Exception as e:
            logger.error("Failed to get top scans: %s", e)
            return {"error": str(e)}

    async def _tool_get_exit_alerts(self) -> Dict[str, Any]:
        """Get positions that may need attention based on stage deterioration."""
        try:
            from backend.models import Position
            from backend.models.market_data import MarketSnapshot

            warning_stages = ["3A", "3B", "4A", "4B", "4C"]

            positions = (
                self.db.query(Position)
                .filter(Position.quantity > 0)
                .all()
            )

            alerts = []
            for pos in positions:
                snapshot = (
                    self.db.query(MarketSnapshot)
                    .filter(MarketSnapshot.symbol == pos.symbol)
                    .first()
                )

                if snapshot and snapshot.stage_label in warning_stages:
                    alerts.append({
                        "symbol": pos.symbol,
                        "quantity": pos.quantity,
                        "stage": snapshot.stage_label,
                        "action": snapshot.action_label,
                        "recommendation": (
                            "Consider reducing" if snapshot.stage_label in ["3A", "3B"]
                            else "Exit recommended" if snapshot.stage_label in ["4A", "4B", "4C"]
                            else "Monitor"
                        ),
                    })

            return {
                "alerts": alerts,
                "count": len(alerts),
                "has_critical": any(a["stage"] in ["4A", "4B", "4C"] for a in alerts),
            }
        except Exception as e:
            logger.error("Failed to get exit alerts: %s", e)
            return {"error": str(e)}

    async def _tool_get_regime_history(self, days: int = 30) -> Dict[str, Any]:
        """Get regime changes over specified period."""
        try:
            from datetime import date, timedelta
            from backend.models.market_data import MarketRegime

            cutoff = date.today() - timedelta(days=days)
            results = (
                self.db.query(MarketRegime)
                .filter(MarketRegime.as_of_date >= cutoff)
                .order_by(MarketRegime.as_of_date.desc())
                .all()
            )

            if not results:
                return {"error": "No regime data available"}

            history = []
            transitions = 0
            prev_regime = None

            for r in reversed(results):
                regime = r.regime_state
                if prev_regime and regime != prev_regime:
                    transitions += 1
                prev_regime = regime
                history.append({
                    "date": r.as_of_date.strftime("%Y-%m-%d") if r.as_of_date else None,
                    "regime": regime,
                    "score": float(r.composite_score) if r.composite_score else None,
                })

            history.reverse()

            return {
                "current": results[0].regime_state,
                "current_score": float(results[0].composite_score) if results[0].composite_score else None,
                "days_in_current": self._count_consecutive_regime(results),
                "history": history[:10],
                "transitions": transitions,
                "volatility": "High" if transitions > 3 else "Moderate" if transitions > 1 else "Stable",
            }
        except Exception as e:
            logger.error("Failed to get regime history: %s", e)
            return {"error": str(e)}

    def _count_consecutive_regime(self, results: list) -> int:
        """Count days the current regime has been active."""
        if not results:
            return 0
        current = results[0].regime_state
        count = 0
        for r in results:
            if r.regime_state == current:
                count += 1
            else:
                break
        return count

    # ==================== MARKET CONTEXT TOOLS ====================

    async def _tool_get_rotation_analysis(self) -> Dict[str, Any]:
        """Analyze sector rotation by comparing performance across time windows."""
        try:
            from sqlalchemy import func
            from backend.models.market_data import MarketSnapshot

            results = (
                self.db.query(
                    MarketSnapshot.sector,
                    func.avg(MarketSnapshot.perf_5d).label("avg_5d"),
                    func.avg(MarketSnapshot.perf_20d).label("avg_20d"),
                    func.avg(MarketSnapshot.perf_60d).label("avg_60d"),
                    func.count(MarketSnapshot.id).label("count"),
                )
                .filter(MarketSnapshot.sector.isnot(None))
                .group_by(MarketSnapshot.sector)
                .all()
            )

            sectors = []
            for r in results:
                if r.count < 3:
                    continue
                avg_5d = float(r.avg_5d) if r.avg_5d else 0
                avg_20d = float(r.avg_20d) if r.avg_20d else 0
                avg_60d = float(r.avg_60d) if r.avg_60d else 0
                momentum = avg_5d - avg_20d
                sectors.append({
                    "sector": r.sector,
                    "perf_5d": round(avg_5d, 2),
                    "perf_20d": round(avg_20d, 2),
                    "perf_60d": round(avg_60d, 2),
                    "momentum": round(momentum, 2),
                    "stocks": r.count,
                })

            sectors.sort(key=lambda x: x["momentum"], reverse=True)
            leaders = [s["sector"] for s in sectors[:3]]
            laggards = [s["sector"] for s in sectors[-3:]]

            return {
                "sectors": sectors,
                "leaders": leaders,
                "laggards": laggards,
                "rotation_signal": (
                    "Risk-on" if sectors and sectors[0]["momentum"] > 1
                    else "Risk-off" if sectors and sectors[-1]["momentum"] < -1
                    else "Neutral"
                ),
            }
        except Exception as e:
            logger.error("Failed to get rotation analysis: %s", e)
            return {"error": str(e)}

    async def _tool_get_breadth_momentum(self, days: int = 20) -> Dict[str, Any]:
        """Get market breadth indicators over time."""
        try:
            from datetime import date, timedelta
            from backend.models.market_data import MarketRegime

            cutoff = date.today() - timedelta(days=days)
            results = (
                self.db.query(MarketRegime)
                .filter(MarketRegime.as_of_date >= cutoff)
                .order_by(MarketRegime.as_of_date.desc())
                .all()
            )

            if not results:
                return {"error": "No breadth data available"}

            latest = results[0]
            oldest = results[-1] if len(results) > 1 else latest

            nh_nl_trend = (
                (float(latest.nh_nl or 0) - float(oldest.nh_nl or 0))
                if latest.nh_nl and oldest.nh_nl else 0
            )
            pct_200d_trend = (
                (float(latest.pct_above_200d or 0) - float(oldest.pct_above_200d or 0))
                if latest.pct_above_200d and oldest.pct_above_200d else 0
            )

            return {
                "current": {
                    "pct_above_200d": round(float(latest.pct_above_200d or 0), 1),
                    "pct_above_50d": round(float(latest.pct_above_50d or 0), 1),
                    "nh_nl": round(float(latest.nh_nl or 0), 2),
                },
                "trend": {
                    "nh_nl_change": round(nh_nl_trend, 2),
                    "pct_200d_change": round(pct_200d_trend, 1),
                    "days": days,
                },
                "interpretation": (
                    "Improving breadth" if nh_nl_trend > 0.1 and pct_200d_trend > 2
                    else "Deteriorating breadth" if nh_nl_trend < -0.1 and pct_200d_trend < -2
                    else "Mixed breadth"
                ),
            }
        except Exception as e:
            logger.error("Failed to get breadth momentum: %s", e)
            return {"error": str(e)}

    async def _tool_compare_historical_regime(self, lookback_years: int = 2) -> Dict[str, Any]:
        """Find historical periods with similar regime characteristics."""
        try:
            from datetime import date, timedelta
            from backend.models.market_data import MarketRegime

            current = (
                self.db.query(MarketRegime)
                .order_by(MarketRegime.as_of_date.desc())
                .first()
            )
            if not current:
                return {"error": "No current regime data"}

            cutoff = date.today() - timedelta(days=lookback_years * 365)
            historical = (
                self.db.query(MarketRegime)
                .filter(
                    MarketRegime.as_of_date >= cutoff,
                    MarketRegime.as_of_date < date.today() - timedelta(days=30),
                )
                .all()
            )

            def similarity_score(h):
                score = 0
                if h.regime_state == current.regime_state:
                    score += 50
                if current.composite_score and h.composite_score:
                    diff = abs(float(current.composite_score) - float(h.composite_score))
                    score += max(0, 30 - diff * 10)
                if current.vix_spot and h.vix_spot:
                    vix_diff = abs(float(current.vix_spot) - float(h.vix_spot))
                    score += max(0, 20 - vix_diff)
                return score

            matches = []
            for h in historical:
                sim = similarity_score(h)
                if sim > 50:
                    matches.append({
                        "date": h.as_of_date.strftime("%Y-%m-%d"),
                        "regime": h.regime_state,
                        "score": round(sim, 1),
                        "vix": round(float(h.vix_spot), 1) if h.vix_spot else None,
                    })

            matches.sort(key=lambda x: x["score"], reverse=True)

            return {
                "current_regime": current.regime_state,
                "current_score": round(float(current.composite_score), 1) if current.composite_score else None,
                "similar_periods": matches[:10],
                "match_count": len(matches),
            }
        except Exception as e:
            logger.error("Failed to compare historical regime: %s", e)
            return {"error": str(e)}

    async def _tool_get_market_internals(self) -> Dict[str, Any]:
        """Get VIX analysis and market internals."""
        try:
            from backend.models.market_data import MarketRegime

            latest = (
                self.db.query(MarketRegime)
                .order_by(MarketRegime.as_of_date.desc())
                .first()
            )
            if not latest:
                return {"error": "No market internals data"}

            vix_spot = float(latest.vix_spot) if latest.vix_spot else None
            vix3m_ratio = float(latest.vix3m_vix_ratio) if latest.vix3m_vix_ratio else None
            vvix_ratio = float(latest.vvix_vix_ratio) if latest.vvix_vix_ratio else None

            term_structure = "Contango" if vix3m_ratio and vix3m_ratio > 1.05 else (
                "Backwardation" if vix3m_ratio and vix3m_ratio < 0.95 else "Flat"
            )

            return {
                "vix": {
                    "spot": round(vix_spot, 2) if vix_spot else None,
                    "vix3m_ratio": round(vix3m_ratio, 3) if vix3m_ratio else None,
                    "vvix_ratio": round(vvix_ratio, 3) if vvix_ratio else None,
                    "term_structure": term_structure,
                },
                "breadth": {
                    "pct_above_200d": round(float(latest.pct_above_200d), 1) if latest.pct_above_200d else None,
                    "pct_above_50d": round(float(latest.pct_above_50d), 1) if latest.pct_above_50d else None,
                    "nh_nl": round(float(latest.nh_nl), 2) if latest.nh_nl else None,
                },
                "regime": latest.regime_state,
                "volatility_assessment": (
                    "Elevated fear" if vix_spot and vix_spot > 25
                    else "Complacent" if vix_spot and vix_spot < 15
                    else "Normal"
                ),
            }
        except Exception as e:
            logger.error("Failed to get market internals: %s", e)
            return {"error": str(e)}

    # ==================== RESEARCH & STRATEGY TOOLS ====================

    async def _tool_backtest_scan(
        self, scan_tier: str = "Breakout Elite", days: int = 90, holding_period: int = 20
    ) -> Dict[str, Any]:
        """Get historical performance for a scan tier."""
        try:
            from datetime import date, timedelta
            from sqlalchemy import func
            from backend.models.market_data import MarketSnapshotHistory

            cutoff = date.today() - timedelta(days=days)
            perf_field = {
                5: MarketSnapshotHistory.perf_5d,
                10: MarketSnapshotHistory.perf_10d,
                20: MarketSnapshotHistory.perf_20d,
                60: MarketSnapshotHistory.perf_60d,
            }.get(holding_period, MarketSnapshotHistory.perf_20d)

            results = (
                self.db.query(
                    func.count(MarketSnapshotHistory.id).label("total"),
                    func.avg(perf_field).label("avg_return"),
                    func.count(func.nullif(perf_field > 0, False)).label("winners"),
                )
                .filter(
                    MarketSnapshotHistory.scan_tier == scan_tier,
                    MarketSnapshotHistory.as_of_date >= cutoff,
                    perf_field.isnot(None),
                )
                .first()
            )

            total = results.total or 0
            winners = results.winners or 0
            avg_ret = float(results.avg_return) if results.avg_return else 0

            return {
                "scan_tier": scan_tier,
                "period_days": days,
                "holding_period": holding_period,
                "total_signals": total,
                "win_rate": round(winners / total * 100, 1) if total > 0 else 0,
                "avg_return": round(avg_ret, 2),
                "note": "Based on historical snapshot data" if total > 0 else "Insufficient data",
            }
        except Exception as e:
            logger.error("Failed to backtest scan: %s", e)
            return {"error": str(e)}

    async def _tool_get_similar_setups(self, symbol: str, limit: int = 10) -> Dict[str, Any]:
        """Find stocks with similar technical setups."""
        try:
            from backend.models.market_data import MarketSnapshot

            sym = (symbol or "").strip().upper()
            if not sym:
                return {"error": "symbol is required"}

            ref = (
                self.db.query(MarketSnapshot)
                .filter(MarketSnapshot.symbol == sym)
                .first()
            )
            if not ref:
                return {"error": f"No data for {sym}"}

            # Cap candidates to avoid memory issues on large universes
            candidates = (
                self.db.query(MarketSnapshot)
                .filter(
                    MarketSnapshot.symbol != sym,
                    MarketSnapshot.stage_label == ref.stage_label,
                )
                .limit(500)
                .all()
            )

            def similarity(c):
                score = 100
                if ref.rs_mansfield_pct and c.rs_mansfield_pct:
                    score -= abs(float(ref.rs_mansfield_pct) - float(c.rs_mansfield_pct)) * 2
                if ref.scan_tier and c.scan_tier and ref.scan_tier == c.scan_tier:
                    score += 20
                return max(0, score)

            matches = []
            for c in candidates:
                sim = similarity(c)
                if sim > 50:
                    matches.append({
                        "symbol": c.symbol,
                        "stage": c.stage_label,
                        "scan_tier": c.scan_tier,
                        "rs_rank": round(float(c.rs_mansfield_pct), 1) if c.rs_mansfield_pct else None,
                        "sector": c.sector,
                        "similarity": round(sim, 1),
                    })

            matches.sort(key=lambda x: x["similarity"], reverse=True)

            return {
                "reference": {
                    "symbol": sym,
                    "stage": ref.stage_label,
                    "rs_rank": round(float(ref.rs_mansfield_pct), 1) if ref.rs_mansfield_pct else None,
                },
                "similar": matches[:limit],
                "count": len(matches),
            }
        except Exception as e:
            logger.error("Failed to get similar setups: %s", e)
            return {"error": str(e)}

    async def _tool_get_strategy_stats(self, strategy_id: Optional[int] = None) -> Dict[str, Any]:
        """Get performance statistics for strategies."""
        try:
            from backend.models.strategy import Strategy

            if strategy_id:
                strat = self.db.query(Strategy).filter(Strategy.id == strategy_id).first()
                if not strat:
                    return {"error": f"Strategy {strategy_id} not found"}
                return {
                    "id": strat.id,
                    "name": strat.name,
                    "status": strat.status,
                    "created": strat.created_at.isoformat() if strat.created_at else None,
                }

            strategies = self.db.query(Strategy).all()
            return {
                "strategies": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "status": s.status,
                    }
                    for s in strategies
                ],
                "count": len(strategies),
            }
        except Exception as e:
            logger.error("Failed to get strategy stats: %s", e)
            return {"error": str(e)}

    async def _tool_analyze_historical_entry(
        self, stage: str, regime: str = "R3", days: int = 180
    ) -> Dict[str, Any]:
        """Analyze how entries in a specific stage performed under a regime."""
        try:
            from datetime import date, timedelta
            from sqlalchemy import func
            from backend.models.market_data import MarketSnapshotHistory

            cutoff = date.today() - timedelta(days=days)
            results = (
                self.db.query(
                    func.count(MarketSnapshotHistory.id).label("total"),
                    func.avg(MarketSnapshotHistory.perf_20d).label("avg_20d"),
                    func.avg(MarketSnapshotHistory.perf_60d).label("avg_60d"),
                    func.count(func.nullif(MarketSnapshotHistory.perf_20d > 0, False)).label("winners_20d"),
                )
                .filter(
                    MarketSnapshotHistory.stage_label == stage,
                    MarketSnapshotHistory.regime_state == regime,
                    MarketSnapshotHistory.as_of_date >= cutoff,
                )
                .first()
            )

            total = results.total or 0
            winners = results.winners_20d or 0

            return {
                "stage": stage,
                "regime": regime,
                "period_days": days,
                "total_entries": total,
                "win_rate_20d": round(winners / total * 100, 1) if total > 0 else 0,
                "avg_return_20d": round(float(results.avg_20d), 2) if results.avg_20d else 0,
                "avg_return_60d": round(float(results.avg_60d), 2) if results.avg_60d else 0,
                "interpretation": (
                    f"Stage {stage} entries in {regime} have "
                    + (f"{round(winners/total*100)}% win rate" if total > 0 else "insufficient data")
                ),
            }
        except Exception as e:
            logger.error("Failed to analyze historical entry: %s", e)
            return {"error": str(e)}

    async def _tool_list_strategies(self) -> Dict[str, Any]:
        """List all saved strategies."""
        try:
            from backend.models.strategy import Strategy

            strategies = self.db.query(Strategy).order_by(Strategy.created_at.desc()).all()
            return {
                "strategies": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "status": s.status,
                        "description": s.description[:100] if s.description else None,
                    }
                    for s in strategies
                ],
                "count": len(strategies),
            }
        except Exception as e:
            logger.error("Failed to list strategies: %s", e)
            return {"error": str(e)}

    async def _tool_run_backtest(
        self,
        strategy_id: Optional[int],
        start_date: Optional[str],
        end_date: Optional[str],
        initial_capital: float = 100000,
    ) -> Dict[str, Any]:
        """Run a backtest for a strategy."""
        try:
            if not strategy_id or not start_date or not end_date:
                return {"error": "strategy_id, start_date, and end_date are required"}

            from datetime import datetime
            from backend.models.strategy import Strategy
            from backend.models.market_data import MarketSnapshot
            from backend.services.strategy.backtest_engine import BacktestEngine
            from backend.services.strategy.rule_evaluator import (
                ConditionGroup, Condition, LogicalOperator, ConditionOperator
            )

            strategy = self.db.query(Strategy).filter(Strategy.id == strategy_id).first()
            if not strategy:
                return {"error": f"Strategy {strategy_id} not found"}

            params = strategy.parameters or {}
            entry_rules_raw = params.get("entry_rules")
            exit_rules_raw = params.get("exit_rules")
            if not entry_rules_raw or not exit_rules_raw:
                return {"error": "Strategy must have entry_rules and exit_rules in parameters"}

            def parse_group(data: dict) -> ConditionGroup:
                conditions = [
                    Condition(
                        field=c["field"],
                        operator=ConditionOperator(c["operator"]),
                        value=c["value"],
                        value_high=c.get("value_high"),
                    )
                    for c in data.get("conditions", [])
                ]
                groups = [parse_group(g) for g in data.get("groups", [])]
                return ConditionGroup(
                    logic=LogicalOperator(data.get("logic", "and")),
                    conditions=conditions,
                    groups=groups,
                )

            entry_rules = parse_group(entry_rules_raw)
            exit_rules = parse_group(exit_rules_raw)

            try:
                start = datetime.strptime(start_date, "%Y-%m-%d").date()
                end = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                return {"error": "Invalid date format. Use YYYY-MM-DD"}

            symbols = params.get("universe_symbols", [])
            if not symbols:
                snaps = (
                    self.db.query(MarketSnapshot.symbol)
                    .filter(MarketSnapshot.is_valid.is_(True))
                    .distinct()
                    .limit(100)
                    .all()
                )
                symbols = [s[0] for s in snaps]

            engine = BacktestEngine()
            result = engine.run(
                db=self.db,
                entry_rules=entry_rules,
                exit_rules=exit_rules,
                symbols=symbols,
                start_date=start,
                end_date=end,
                initial_capital=initial_capital,
                position_size_pct=params.get("position_size_pct", 5.0) / 100,
            )

            return {
                "strategy": strategy.name,
                "period": f"{start_date} to {end_date}",
                "initial_capital": result.metrics.initial_capital,
                "final_capital": round(result.metrics.final_capital, 2),
                "total_return_pct": round(result.metrics.total_return_pct, 2),
                "max_drawdown_pct": round(result.metrics.max_drawdown_pct, 2),
                "sharpe_ratio": round(result.metrics.sharpe_ratio, 2) if result.metrics.sharpe_ratio else None,
                "total_trades": result.metrics.total_trades,
                "win_rate": round(result.metrics.win_rate * 100, 1),
            }
        except Exception as e:
            logger.error("Failed to run backtest: %s", e)
            return {"error": str(e)}

    async def _tool_list_strategy_templates(self) -> Dict[str, Any]:
        """List available strategy templates."""
        try:
            from backend.services.strategy.templates import list_templates

            templates = list_templates()
            return {
                "templates": [
                    {
                        "id": t["id"],
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "strategy_type": t.get("strategy_type", "custom"),
                    }
                    for t in templates
                ],
                "count": len(templates),
                "tip": "Use create_strategy with template_id to create a strategy based on any template.",
            }
        except Exception as e:
            logger.error("Failed to list strategy templates: %s", e)
            return {"error": str(e)}

    async def _tool_create_strategy(
        self,
        name: str,
        template_id: str,
        description: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a strategy from a template."""
        try:
            if not name or not name.strip():
                return {"error": "Strategy name is required"}
            if not template_id:
                return {"error": "template_id is required - use list_strategy_templates to see options"}

            from backend.services.strategy.templates import get_template
            from backend.models.strategy import Strategy, StrategyType
            from backend.models import User

            template = get_template(template_id)
            if not template:
                return {"error": f"Template '{template_id}' not found"}

            try:
                stype = StrategyType(template.get("strategy_type", "custom"))
            except ValueError:
                stype = StrategyType.CUSTOM

            config = dict(template.get("default_config", {}))
            if overrides:
                for k, v in overrides.items():
                    if k in config:
                        if isinstance(config[k], dict) and isinstance(v, dict):
                            config[k].update(v)
                        else:
                            config[k] = v
                    else:
                        config[k] = v

            # TODO: Pass authenticated user to brain for proper ownership
            # For now, get admin user (agent is admin-only)
            from backend.models.user import UserRole
            user = (
                self.db.query(User)
                .filter(User.role == UserRole.OWNER)
                .first()
            )
            if not user:
                return {"error": "No admin user found - strategy creation requires admin"}

            existing = (
                self.db.query(Strategy)
                .filter(Strategy.user_id == user.id, Strategy.name == name.strip())
                .first()
            )
            if existing:
                return {"error": f"Strategy named '{name}' already exists"}

            strategy = Strategy(
                user_id=user.id,
                name=name.strip(),
                description=description or template.get("description", ""),
                strategy_type=stype,
                parameters=config,
                status="active",
                position_size_pct=template.get("position_size_pct", 5.0),
                max_positions=template.get("max_positions", 10),
            )
            self.db.add(strategy)
            self.db.commit()
            self.db.refresh(strategy)

            return {
                "success": True,
                "strategy_id": strategy.id,
                "name": strategy.name,
                "template_used": template_id,
                "tip": f"Strategy created! Use run_backtest with strategy_id={strategy.id} to test it.",
            }
        except Exception as e:
            logger.error("Failed to create strategy: %s", e)
            self.db.rollback()
            return {"error": str(e)}

    async def _tool_calculate_support_resistance(
        self,
        symbol: str,
        lookback_days: int = 60,
    ) -> Dict[str, Any]:
        """Calculate support and resistance levels for a symbol.
        
        Uses multiple methods:
        - Classic pivot points (high/low/close)
        - Swing highs/lows detection
        - Volume-weighted price clusters
        """
        from backend.models.market_data import PriceData
        from datetime import datetime, timedelta
        from collections import defaultdict

        try:
            sym = symbol.upper().strip()
            if not sym:
                return {"error": "Symbol is required"}

            # Validate lookback_days (clamp to reasonable range)
            lookback = max(10, min(365, lookback_days))
            if lookback != lookback_days:
                logger.info(
                    "Clamped lookback_days from %d to %d for %s",
                    lookback_days, lookback, sym
                )

            cutoff = datetime.now(timezone.utc) - timedelta(days=lookback)
            bars = (
                self.db.query(PriceData)
                .filter(
                    PriceData.symbol == sym,
                    PriceData.interval == "1d",
                    PriceData.date >= cutoff,
                )
                .order_by(PriceData.date.asc())
                .all()
            )

            if len(bars) < 10:
                return {"error": f"Insufficient price data for {sym} (need at least 10 bars)"}

            # Extract OHLCV (PriceData uses _price suffix)
            highs = [float(b.high_price) for b in bars]
            lows = [float(b.low_price) for b in bars]
            closes = [float(b.close_price) for b in bars]
            volumes = [float(b.volume or 0) for b in bars]

            latest_close = closes[-1]
            latest_high = highs[-1]
            latest_low = lows[-1]

            # Classic Pivot Points (using most recent bar)
            pivot = (latest_high + latest_low + latest_close) / 3
            r1 = 2 * pivot - latest_low
            s1 = 2 * pivot - latest_high
            r2 = pivot + (latest_high - latest_low)
            s2 = pivot - (latest_high - latest_low)

            # Swing highs/lows (local maxima/minima with 2-bar lookback)
            swing_highs = []
            swing_lows = []
            for i in range(2, len(highs) - 2):
                if highs[i] >= max(highs[i - 2 : i]) and highs[i] >= max(highs[i + 1 : i + 3]):
                    swing_highs.append(highs[i])
                if lows[i] <= min(lows[i - 2 : i]) and lows[i] <= min(lows[i + 1 : i + 3]):
                    swing_lows.append(lows[i])

            # Find nearest resistance levels (swing highs above current price)
            resistance_levels = sorted([h for h in swing_highs if h > latest_close])[:3]
            
            # Find nearest support levels (swing lows below current price)
            support_levels = sorted([l for l in swing_lows if l < latest_close], reverse=True)[:3]

            # Volume-weighted price clusters (group prices into buckets)
            price_range = max(highs) - min(lows)
            bucket_size = price_range / 20 if price_range > 0 else 1
            vwap_clusters: Dict[int, float] = defaultdict(float)
            for i, close in enumerate(closes):
                bucket = int((close - min(lows)) / bucket_size) if bucket_size > 0 else 0
                vwap_clusters[bucket] += volumes[i]

            # Find high-volume clusters
            sorted_clusters = sorted(vwap_clusters.items(), key=lambda x: x[1], reverse=True)[:5]
            volume_clusters = [min(lows) + (b * bucket_size) + bucket_size / 2 for b, _ in sorted_clusters]

            # Key statistics
            period_high = max(highs)
            period_low = min(lows)
            avg_volume = sum(volumes) / len(volumes) if volumes else 0

            return {
                "symbol": sym,
                "current_price": round(latest_close, 2),
                "lookback_days": lookback_days,
                "bars_analyzed": len(bars),
                "pivot_points": {
                    "pivot": round(pivot, 2),
                    "r1": round(r1, 2),
                    "r2": round(r2, 2),
                    "s1": round(s1, 2),
                    "s2": round(s2, 2),
                },
                "immediate_resistance": [round(r, 2) for r in resistance_levels[:2]] or [round(r1, 2)],
                "immediate_support": [round(s, 2) for s in support_levels[:2]] or [round(s1, 2)],
                "major_resistance": round(resistance_levels[0], 2) if resistance_levels else round(period_high, 2),
                "major_support": round(support_levels[0], 2) if support_levels else round(period_low, 2),
                "period_high": round(period_high, 2),
                "period_low": round(period_low, 2),
                "volume_clusters": [round(v, 2) for v in volume_clusters[:3]],
                "avg_volume": int(avg_volume),
                "analysis_tip": (
                    f"Key levels: Support at {round(support_levels[0] if support_levels else s1, 2)}, "
                    f"Resistance at {round(resistance_levels[0] if resistance_levels else r1, 2)}. "
                    f"Consider entries near support with stops below {round(period_low, 2)}."
                ),
            }
        except Exception as e:
            logger.error("Failed to calculate support/resistance for %s: %s", symbol, e)
            return {"error": str(e)}

    # ==================== DATA INTEGRITY TOOLS ====================

    async def _tool_check_data_accuracy(self, **kwargs) -> Dict[str, Any]:
        import json
        from backend.services.market.market_data_service import infra
        try:
            r = infra.redis_client
            raw = r.get("ohlcv:reconciliation:last")
            if not raw:
                return {"status": "no_data", "message": "Reconciliation has not run yet"}
            return json.loads(raw.decode() if isinstance(raw, (bytes, bytearray)) else raw)
        except Exception as exc:
            return {"error": str(exc)}

    async def _tool_get_provider_metrics(self, **kwargs) -> Dict[str, Any]:
        from backend.services.market.admin_health_service import AdminHealthService
        try:
            svc = AdminHealthService()
            return svc._build_provider_metrics()
        except Exception as exc:
            return {"error": str(exc)}

    async def _tool_check_pre_market_readiness(self, **kwargs) -> Dict[str, Any]:
        import json
        from backend.services.market.market_data_service import infra
        try:
            r = infra.redis_client
            cached = r.get("health:pre_market_readiness")
            if cached:
                return json.loads(cached.decode() if isinstance(cached, (bytes, bytearray)) else cached)
            from backend.services.market.admin_health_service import AdminHealthService
            svc = AdminHealthService()
            return svc.check_pre_market_readiness(self.db)
        except Exception as exc:
            return {"error": str(exc)}

    async def _tool_cancel_job(self, task_id: str = "", **kwargs) -> Dict[str, Any]:
        """Cancel/revoke a Celery task, or list active tasks if no task_id given."""
        try:
            from backend.tasks.celery_app import celery_app
            if not task_id:
                inspector = celery_app.control.inspect()
                active = inspector.active() or {}
                tasks = []
                for worker, task_list in active.items():
                    for t in task_list:
                        tasks.append({
                            "worker": worker,
                            "task_id": t.get("id"),
                            "name": t.get("name"),
                            "started": t.get("time_start"),
                        })
                if not tasks:
                    return {"status": "no_active_tasks", "note": "No tasks currently running. Nothing to cancel."}
                return {"status": "active_tasks", "tasks": tasks, "note": "Provide a task_id to cancel a specific task."}
            celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
            return {"status": "revoked", "task_id": task_id, "note": "Termination signal sent. Task may take a moment to stop."}
        except Exception as exc:
            return {"error": f"Failed to cancel job: {exc}"}

    async def _tool_list_users(self, **kwargs) -> Dict[str, Any]:
        """List all users with sensitive fields redacted."""
        try:
            from backend.models import User
            users = self.db.query(User).all()
            return {"users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email[:2] + "***@" + u.email.split("@")[-1] if u.email and "@" in u.email else "(no email)",
                    "role": getattr(u, "role", None),
                    "is_active": getattr(u, "is_active", True),
                    "created_at": str(u.created_at) if u.created_at else None,
                }
                for u in users
            ]}
        except Exception as exc:
            return {"error": f"Failed to list users: {exc}"}

    # ==================== CONVERSATION PERSISTENCE ====================
    
    def _get_redis(self):
        """Get Redis client from market data service."""
        try:
            from backend.services.market.market_data_service import infra
            return infra.redis_client
        except Exception as redis_err:
            logger.warning(
                "Could not obtain Redis client from market infra: %s",
                redis_err,
            )
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
        """Save conversation to PostgreSQL (primary) and Redis (cache).

        Conversations are now persisted to PostgreSQL for indefinite retention.
        Redis is used as a cache for fast access during active sessions.
        """
        self._trim_conversation_for_persistence()

        saved_to_db = False
        try:
            from backend.models.agent_message import save_conversation_to_db

            saved_to_db = save_conversation_to_db(
                self.db, self.session_id, self._conversation
            )
            if not saved_to_db:
                logger.warning(
                    "Failed to save conversation to DB for session %s (%d messages)",
                    self.session_id, len(self._conversation),
                )
        except Exception as e:
            logger.warning("Failed to save conversation to DB: %s", e)

        redis = self._get_redis()
        if redis:
            try:
                key = f"agent:conversation:{self.session_id}"
                ttl = int(os.getenv("AGENT_CONVERSATION_TTL_SECONDS", "604800"))
                redis.setex(key, ttl, json.dumps(self._conversation))
            except Exception as e:
                logger.warning("Failed to save conversation to Redis cache: %s", e)

        return saved_to_db

    def _load_conversation(self, session_id: str) -> str:
        """Load conversation from Redis (cache) or PostgreSQL (permanent).

        Checks Redis first for fast access during active sessions.
        Falls back to PostgreSQL for sessions with expired Redis keys.

        Returns:
            ``loaded``, ``missing``, or ``unavailable``.
        """
        redis = self._get_redis()
        if redis:
            try:
                key = f"agent:conversation:{session_id}"
                data = redis.get(key)
                if data:
                    self._conversation = json.loads(
                        data.decode("utf-8") if isinstance(data, bytes) else data
                    )
                    self.session_id = session_id
                    return "loaded"
            except Exception as e:
                logger.warning("Failed to load conversation from Redis: %s", e)

        try:
            from backend.models.agent_message import load_conversation_from_db

            conversation = load_conversation_from_db(self.db, session_id)
            if conversation:
                self._conversation = conversation
                self.session_id = session_id
                return "loaded"
            return "missing"
        except Exception as e:
            logger.warning("Failed to load conversation from DB: %s", e)
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
            # Match analyze_and_act: use automatic tool selection on first LLM call of this turn.
            if iteration == 0:
                tool_choice = "auto"
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
            
            raw_tool_calls = message.get("tool_calls")
            if raw_tool_calls:
                valid_tool_calls = _sanitize_tool_calls(raw_tool_calls)
                if not valid_tool_calls:
                    logger.warning("All tool_calls were invalid in chat, breaking loop")
                    break
                message_to_store = dict(message)
                message_to_store["tool_calls"] = valid_tool_calls
                self._conversation.append(message_to_store)
                
                for tool_call in valid_tool_calls:
                    func = tool_call.get("function", {})
                    tool_name = func.get("name")
                    logger.info("Executing tool: %s", tool_name)
                    try:
                        tool_args = json.loads(func.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        tool_args = {}
                    
                    try:
                        result, action = await self._execute_tool(
                            tool_name, tool_args, message.get("content") or ""
                        )
                    except Exception as tool_err:
                        logger.warning("Tool execution failed for %s: %s", tool_name, tool_err)
                        result = {"error": "Tool execution failed", "type": type(tool_err).__name__}
                        action = None
                    
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
