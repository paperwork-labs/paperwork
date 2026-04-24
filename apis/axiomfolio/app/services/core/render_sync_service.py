"""Render API cron-job sync service.

Mirrors ``CronSchedule`` rows in PostgreSQL to Render cron-job services
via the Render REST API (https://api.render.com/v1/).

When ``RENDER_API_KEY`` is unset the service becomes a no-op so that
local-dev and CI environments are never affected.

medallion: ops
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.market_data import CronSchedule

logger = logging.getLogger(__name__)

RENDER_API_BASE = "https://api.render.com/v1"
DOCKERFILE_PATH = "./Dockerfile"
COMMAND_PREFIX = "python -m app.scripts.run_task"
DEFAULT_PLAN = "starter"
DEFAULT_REGION = "oregon"

CRON_ENV_VAR_KEYS = [
    "ENVIRONMENT",
    "DATABASE_URL",
    "REDIS_URL",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
    "FMP_API_KEY",
]


def _collect_cron_env_vars() -> List[Dict[str, str]]:
    """Build env-var list for Render cron jobs from settings, falling back to os.environ."""
    out: List[Dict[str, str]] = []
    for key in CRON_ENV_VAR_KEYS:
        val = getattr(settings, key, None) or os.environ.get(key)
        if val:
            out.append({"key": key, "value": val})
    return out


class RenderCronSyncService:
    """Synchronise CronSchedule DB rows with Render cron-job services."""

    def __init__(self) -> None:
        self._api_key: Optional[str] = settings.RENDER_API_KEY
        self._owner_id: Optional[str] = settings.RENDER_OWNER_ID

    @property
    def enabled(self) -> bool:
        return bool(self._api_key and self._owner_id)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        url = f"{RENDER_API_BASE}{path}"
        resp: Optional[httpx.Response] = None
        with httpx.Client(timeout=30) as client:
            for attempt in range(2):
                resp = client.request(method, url, headers=self._headers(), json=json, params=params)
                if resp.status_code != 429:
                    break
                retry_after_raw = resp.headers.get("Retry-After")
                try:
                    retry_after_s = int(retry_after_raw) if retry_after_raw else 1
                except Exception:
                    retry_after_s = 1
                retry_after_s = max(1, min(retry_after_s, 10))
                logger.warning(
                    "Render API %s %s rate-limited (429), retrying in %ss (attempt %s/2)",
                    method,
                    path,
                    retry_after_s,
                    attempt + 1,
                )
                if attempt == 0:
                    time.sleep(retry_after_s)
        if resp is None:
            raise RuntimeError("Render API request did not execute")
        if resp.status_code >= 400:
            retry_after = resp.headers.get("Retry-After")
            logger.error(
                "Render API %s %s -> %s (response body redacted)%s",
                method,
                path,
                resp.status_code,
                f", retry_after={retry_after}" if retry_after else "",
            )
        return resp

    # ------------------------------------------------------------------
    # Low-level Render API wrappers
    # ------------------------------------------------------------------

    def list_render_crons(self) -> List[Dict[str, Any]]:
        """List all cron-job services owned by this account."""
        params: Dict[str, str] = {"type": "cron_job", "limit": "100"}
        if self._owner_id:
            params["ownerId"] = self._owner_id
        resp = self._request("GET", "/services", params=params)
        if resp.status_code != 200:
            return []
        items = resp.json()
        return [
            {
                "id": svc.get("service", svc).get("id", svc.get("id")),
                "name": svc.get("service", svc).get("name", svc.get("name")),
                "schedule": svc.get("service", svc).get("schedule", ""),
                "suspended": svc.get("service", svc).get("suspended", "not_suspended"),
            }
            for svc in items
        ]

    def create_render_cron(self, schedule: CronSchedule) -> Optional[str]:
        """Create a Render cron-job service. Returns the new service ID."""
        docker_command = f"{COMMAND_PREFIX} {schedule.task}"
        if schedule.kwargs_json:
            docker_command += f" --kwargs '{json.dumps(schedule.kwargs_json)}'"

        payload: Dict[str, Any] = {
            "type": "cron_job",
            "name": schedule.id,
            "ownerId": self._owner_id,
            "plan": DEFAULT_PLAN,
            "region": DEFAULT_REGION,
            "schedule": schedule.cron,
            "repo": settings.RENDER_REPO_URL,
            # Cron jobs do not auto-deploy on code push. Rollouts are explicit and UI-driven
            # to avoid unexpected job runs or schedule changes when deploying the API.
            "autoDeploy": "no",
            "serviceDetails": {
                "envVars": _collect_cron_env_vars(),
                "dockerfilePath": DOCKERFILE_PATH,
                "dockerCommand": docker_command,
            },
        }
        resp = self._request("POST", "/services", json=payload)
        if resp.status_code in (200, 201):
            data = resp.json()
            service_id = data.get("service", data).get("id", data.get("id"))
            logger.info("Created Render cron %s -> %s", schedule.id, service_id)
            return service_id
        logger.error("Failed to create Render cron %s: response body redacted (status=%s)", schedule.id, resp.status_code)
        return None

    def update_render_cron(self, schedule: CronSchedule) -> bool:
        """Update schedule and command on an existing Render cron-job."""
        if not schedule.render_service_id:
            return False
        docker_command = f"{COMMAND_PREFIX} {schedule.task}"
        if schedule.kwargs_json:
            docker_command += f" --kwargs '{json.dumps(schedule.kwargs_json)}'"

        payload: Dict[str, Any] = {
            "schedule": schedule.cron,
            "serviceDetails": {
                "dockerCommand": docker_command,
            },
        }
        resp = self._request("PATCH", f"/services/{schedule.render_service_id}", json=payload)
        ok = resp.status_code in (200, 201)
        if ok:
            logger.info("Updated Render cron %s", schedule.id)
        return ok

    def delete_render_cron(self, service_id: str) -> bool:
        resp = self._request("DELETE", f"/services/{service_id}")
        ok = resp.status_code in (200, 204)
        if ok:
            logger.info("Deleted Render cron service %s", service_id)
        return ok

    def suspend_render_cron(self, service_id: str) -> bool:
        resp = self._request("POST", f"/services/{service_id}/suspend")
        return resp.status_code in (200, 202)

    def resume_render_cron(self, service_id: str) -> bool:
        resp = self._request("POST", f"/services/{service_id}/resume")
        return resp.status_code in (200, 202)

    # ------------------------------------------------------------------
    # High-level sync
    # ------------------------------------------------------------------

    def sync_one(self, schedule: CronSchedule, db: Session) -> Dict[str, Any]:
        """Sync a single schedule row to Render. Returns status dict."""
        if not self.enabled:
            return {"status": "skipped", "reason": "render_api_not_configured"}

        try:
            if schedule.render_service_id:
                if schedule.enabled:
                    ok = self.update_render_cron(schedule)
                    if ok:
                        self.resume_render_cron(schedule.render_service_id)
                    action = "updated"
                else:
                    self.suspend_render_cron(schedule.render_service_id)
                    action = "suspended"
                    ok = True
            else:
                if not schedule.enabled:
                    return {"status": "skipped", "reason": "disabled_no_service"}
                service_id = self.create_render_cron(schedule)
                if service_id:
                    schedule.render_service_id = service_id
                    ok = True
                    action = "created"
                else:
                    ok = False
                    action = "create_failed"

            now = datetime.now(timezone.utc)
            if ok:
                schedule.render_synced_at = now
                schedule.render_sync_error = None
            else:
                schedule.render_sync_error = f"{action} failed at {now.isoformat()}"
            db.commit()
            return {"status": action, "ok": ok}
        except Exception as exc:
            logger.exception("sync_one failed for %s", schedule.id)
            schedule.render_sync_error = str(exc)[:500]
            db.commit()
            return {"status": "error", "error": str(exc)[:200]}

    def sync_all(self, db: Session) -> Dict[str, Any]:
        """Full reconciliation: DB schedules -> Render cron jobs."""
        if not self.enabled:
            logger.info("Render sync skipped (RENDER_API_KEY or RENDER_OWNER_ID not set)")
            return {"status": "skipped", "reason": "render_api_not_configured"}

        counters = {"created": 0, "updated": 0, "suspended": 0, "deleted": 0, "errors": 0}

        db_schedules: List[CronSchedule] = db.query(CronSchedule).all()
        db_by_id = {s.id: s for s in db_schedules}

        render_crons = self.list_render_crons()
        render_by_name: Dict[str, Dict[str, Any]] = {rc["name"]: rc for rc in render_crons}

        # Match existing Render crons to DB rows by render_service_id
        render_by_service_id: Dict[str, Dict[str, Any]] = {rc["id"]: rc for rc in render_crons}

        for schedule in db_schedules:
            try:
                op_ok = True
                # Try to find existing Render service
                if schedule.render_service_id and schedule.render_service_id in render_by_service_id:
                    existing = render_by_service_id[schedule.render_service_id]
                elif schedule.id in render_by_name:
                    existing = render_by_name[schedule.id]
                    schedule.render_service_id = existing["id"]
                else:
                    existing = None

                if existing:
                    if not schedule.enabled:
                        if self.suspend_render_cron(existing["id"]):
                            counters["suspended"] += 1
                        else:
                            counters["errors"] += 1
                            op_ok = False
                    else:
                        if self.update_render_cron(schedule):
                            self.resume_render_cron(existing["id"])
                            counters["updated"] += 1
                        else:
                            counters["errors"] += 1
                            op_ok = False
                else:
                    if schedule.enabled:
                        service_id = self.create_render_cron(schedule)
                        if service_id:
                            schedule.render_service_id = service_id
                            counters["created"] += 1
                        else:
                            counters["errors"] += 1
                            op_ok = False

                if op_ok:
                    schedule.render_synced_at = datetime.now(timezone.utc)
                    schedule.render_sync_error = None
                else:
                    schedule.render_sync_error = "sync operation failed"
            except Exception as exc:
                logger.exception("sync_all: error for %s", schedule.id)
                schedule.render_sync_error = str(exc)[:500]
                counters["errors"] += 1

        # Delete orphaned Render crons (exist in Render but not in DB)
        db_render_ids = {s.render_service_id for s in db_schedules if s.render_service_id}
        db_names = set(db_by_id.keys())
        for rc in render_crons:
            if rc["id"] not in db_render_ids and rc["name"] not in db_names:
                try:
                    if self.delete_render_cron(rc["id"]):
                        counters["deleted"] += 1
                except Exception:
                    counters["errors"] += 1

        db.commit()
        logger.info("Render sync complete: %s", counters)
        return counters


render_sync_service = RenderCronSyncService()
