"""Secrets drift audit, rotation monitor, and critical health probes (Brain intelligence)."""

from __future__ import annotations

import json
import logging
import os
from zoneinfo import ZoneInfo

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import timezone

from app.config import settings
from app.database import async_session_factory
from app.schedulers._history import run_with_scheduler_record
from app.services.agent_task_bridge import AgentTaskSpec, try_queue_agent_task
from app.services.secrets_intelligence import SecretsIntelligence

logger = logging.getLogger(__name__)

_JOB_DRIFT = "secrets_drift_audit"
_JOB_ROTATION = "secrets_rotation_monitor"
_JOB_HEALTH = "secrets_health_probe"


def _env_json_map(raw: str) -> dict[str, str]:
    if not raw.strip():
        return {}
    try:
        d = json.loads(raw)
        if not isinstance(d, dict):
            return {}
        return {str(k): str(v) for k, v in d.items()}
    except (json.JSONDecodeError, TypeError):
        return {}


def _health_url_for_service(label: str) -> str | None:
    over = _env_json_map(settings.BRAIN_SECRETS_SERVICE_HEALTH_URLS)
    if label in over:
        return over[label]
    if label == "brain-api":
        b = (settings.BRAIN_URL or "").rstrip("/")
        return f"{b}/health" if b else None
    if label in ("studio", "paperworklabs"):
        s = (settings.STUDIO_URL or "").rstrip("/")
        return f"{s}/api/health" if s else None
    if label == "filefree-api":
        u = (os.getenv("FILEFREE_API_URL") or "").strip().rstrip("/")
        return f"{u}/health" if u else None
    return None


def _owns_drift() -> bool:
    return bool(settings.BRAIN_OWNS_SECRETS_DRIFT_AUDIT)


def _owns_rotation() -> bool:
    return bool(settings.BRAIN_OWNS_SECRETS_ROTATION_MONITOR)


def _owns_health() -> bool:
    return bool(settings.BRAIN_OWNS_SECRETS_HEALTH_PROBE)


async def _body_drift_audit() -> None:
    async with async_session_factory() as db:
        intel = SecretsIntelligence(db)
        reg = await intel.list_registry()
        for row in reg:
            rep = await intel.audit_drift(row.name)
            if not rep.has_drift:
                continue
            detail = {t.target: t.status for t in rep.targets}
            await intel.record_episode(
                row.name,
                "drift_detected",
                "drift_audit",
                f"Drift or compare issue for {row.name} ({len(rep.targets)} targets)",
                details={"targets": detail, "fingerprint": "redacted"},
            )
            await intel.mark_drift(
                row.name,
                summary="; ".join(f"{t.target}:{t.status}" for t in rep.targets)[:2000],
                detected=True,
            )
            if row.criticality in ("critical", "high"):
                spec = AgentTaskSpec(
                    title=f"Drift: {row.name}",
                    summary="Registry drift — verify vault vs Vercel/Render",
                    category="secrets",
                    metadata={"secret_name": row.name, "kind": "drift"},
                )
                await try_queue_agent_task(spec)
        await db.commit()


async def _body_rotation_monitor() -> None:
    async with async_session_factory() as db:
        intel = SecretsIntelligence(db)
        due = await intel.rotations_due(threshold_days=7)
        for item in due:
            await intel.record_episode(
                item.name,
                "rotation_due",
                "rotation_monitor",
                f"Rotation due (cadence {item.rotation_cadence_days}d, last={item.last_rotated_at})",
                details={
                    "next_due_at": item.next_due_at.isoformat() if item.next_due_at else None,
                    "days_until_due": item.days_until_due,
                },
            )
            if item.criticality in ("critical", "high", "normal"):
                spec = AgentTaskSpec(
                    title=f"Rotation due: {item.name}",
                    summary="Upcoming or overdue credential rotation per registry",
                    category="secrets",
                    metadata={"secret_name": item.name, "kind": "rotation"},
                )
                await try_queue_agent_task(spec)
        await db.commit()


async def _body_health_probe() -> None:
    timeout = httpx.Timeout(10.0)
    async with async_session_factory() as db:
        intel = SecretsIntelligence(db)
        crit = await intel.list_registry(criticality="critical")
        async with httpx.AsyncClient(timeout=timeout) as client:
            for row in crit:
                for svc in row.depends_in_services:
                    url = _health_url_for_service(svc)
                    if not url:
                        continue
                    try:
                        r = await client.get(url, follow_redirects=True)
                        if r.status_code == 401:
                            await intel.record_episode(
                                row.name,
                                "health_probe_failure",
                                "health_probe",
                                f"401 from {url} (service={svc})",
                                details={"url": url, "service": svc, "status": 401},
                            )
                            spec = AgentTaskSpec(
                                title=f"Auth failure: {row.name} / {svc}",
                                summary="Health URL returned 401 — check secrets and auth",
                                category="secrets",
                                metadata={"secret_name": row.name, "url": url},
                            )
                            await try_queue_agent_task(spec)
                    except httpx.HTTPError as e:
                        await intel.record_episode(
                            row.name,
                            "health_probe_failure",
                            "health_probe",
                            f"request error: {e!s}"[:500],
                            details={"url": url, "service": svc},
                        )
        await db.commit()


async def run_drift_audit() -> None:
    await run_with_scheduler_record(
        _JOB_DRIFT,
        _body_drift_audit,
        metadata={"source": "secrets_drift_audit"},
        reraise=False,
    )


async def run_rotation_monitor() -> None:
    await run_with_scheduler_record(
        _JOB_ROTATION,
        _body_rotation_monitor,
        metadata={"source": "secrets_rotation_monitor"},
        reraise=False,
    )


async def run_health_probe() -> None:
    await run_with_scheduler_record(
        _JOB_HEALTH,
        _body_health_probe,
        metadata={"source": "secrets_health_probe"},
        reraise=False,
    )


def install(scheduler: AsyncIOScheduler) -> None:
    z = ZoneInfo("America/Los_Angeles")
    if _owns_drift():
        scheduler.add_job(
            run_drift_audit,
            trigger=CronTrigger(hour=3, minute=0, timezone=z),
            id=_JOB_DRIFT,
            name="Secrets drift audit (vault vs Vercel/Render)",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        logger.info("Registered %s (03:00 America/Los_Angeles)", _JOB_DRIFT)
    if _owns_rotation():
        scheduler.add_job(
            run_rotation_monitor,
            trigger=CronTrigger(hour=9, minute=0, timezone=z),
            id=_JOB_ROTATION,
            name="Secrets rotation monitor",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        logger.info("Registered %s (09:00 America/Los_Angeles)", _JOB_ROTATION)
    if _owns_health():
        scheduler.add_job(
            run_health_probe,
            trigger=IntervalTrigger(hours=1, timezone=timezone.utc),
            id=_JOB_HEALTH,
            name="Secrets health probe (critical registry)",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        logger.info("Registered %s (hourly UTC)", _JOB_HEALTH)
