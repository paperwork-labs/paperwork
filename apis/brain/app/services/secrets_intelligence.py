"""Brain operational intelligence over secrets — registry, episodes, drift, rotation."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.secrets_intelligence import BrainSecretsEpisode, BrainSecretsRegistry

logger = logging.getLogger(__name__)

EventType = Literal[
    "intake",
    "rotation",
    "drift_detected",
    "drift_corrected",
    "failure",
    "revocation",
    "registry_update",
    "rotation_due",
    "health_probe_failure",
]


@dataclass
class SecretFingerprint:
    """Non-reversible summary for comparing secret material (never log raw values)."""

    length: int
    prefix8: str
    sha256_hex: str

    def to_log_dict(self) -> dict[str, Any]:
        return {
            "length": self.length,
            "prefix8": f"{self.prefix8}...",
            "sha256_hex": f"{self.sha256_hex[:12]}...",
        }


def compute_fingerprint(raw: str) -> SecretFingerprint:
    """Length + 8-char prefix + SHA-256 of UTF-8 bytes (no logging of full value)."""
    b = raw.encode("utf-8")
    digest = hashlib.sha256(b).hexdigest()
    prefix = raw[:8] if len(raw) >= 8 else raw
    return SecretFingerprint(length=len(b), prefix8=prefix, sha256_hex=digest)


def fingerprints_match(a: SecretFingerprint, b: SecretFingerprint) -> bool:
    return a.length == b.length and a.sha256_hex == b.sha256_hex and a.prefix8 == b.prefix8


@dataclass
class DriftTargetStatus:
    target: str
    kind: Literal["vercel", "render", "vault", "other"]
    status: Literal["in_sync", "drift", "skipped", "error", "unavailable"]
    detail: str
    remote_fingerprint: dict[str, Any] | None = None


@dataclass
class DriftReport:
    secret_name: str
    vault_fingerprint: SecretFingerprint | None
    targets: list[DriftTargetStatus] = field(default_factory=list)
    has_drift: bool = False


@dataclass
class RotationDueItem:
    name: str
    criticality: str
    next_due_at: datetime | None
    last_rotated_at: datetime | None
    rotation_cadence_days: int | None
    days_until_due: int | None


@dataclass
class Pattern:
    pattern: str
    count: int
    sample_secret_names: list[str]


@dataclass
class RegistryRow:
    id: UUID
    name: str
    purpose: str | None
    service: str
    format_hint: str | None
    expected_prefix: str | None
    criticality: str
    depends_in_apps: list[str]
    depends_in_services: list[str]
    rotation_cadence_days: int | None
    last_rotated_at: datetime | None
    last_verified_synced_at: datetime | None
    drift_detected_at: datetime | None
    drift_summary: str | None
    lessons_learned: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


@dataclass
class EpisodeRow:
    id: UUID
    secret_name: str
    event_type: str
    event_at: datetime
    source: str
    summary: str
    details: dict[str, Any]
    triggered_task_id: UUID | None
    created_at: datetime


def _registry_to_row(r: BrainSecretsRegistry) -> RegistryRow:
    return RegistryRow(
        id=r.id,
        name=r.name,
        purpose=r.purpose,
        service=r.service,
        format_hint=r.format_hint,
        expected_prefix=r.expected_prefix,
        criticality=r.criticality,
        depends_in_apps=list(r.depends_in_apps or []),
        depends_in_services=list(r.depends_in_services or []),
        rotation_cadence_days=r.rotation_cadence_days,
        last_rotated_at=r.last_rotated_at,
        last_verified_synced_at=r.last_verified_synced_at,
        drift_detected_at=r.drift_detected_at,
        drift_summary=r.drift_summary,
        lessons_learned=list(r.lessons_learned or []),
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def _episode_to_row(e: BrainSecretsEpisode) -> EpisodeRow:
    return EpisodeRow(
        id=e.id,
        secret_name=e.secret_name,
        event_type=e.event_type,
        event_at=e.event_at,
        source=e.source,
        summary=e.summary,
        details=dict(e.details or {}),
        triggered_task_id=e.triggered_task_id,
        created_at=e.created_at,
    )


def _parse_json_mapping(raw: str | None) -> dict[str, str]:
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        return {str(k): str(v) for k, v in data.items()}
    except (json.JSONDecodeError, TypeError):
        return {}


def _vercel_project_for_app(app: str) -> str | None:
    m = _parse_json_mapping(settings.BRAIN_SECRETS_VERCEL_APP_PROJECTS)
    return m.get(app)


def _render_service_id(service: str) -> str | None:
    m = _parse_json_mapping(settings.BRAIN_SECRETS_RENDER_SERVICE_IDS)
    return m.get(service)


class SecretsIntelligence:
    """Registry, episode logging, drift audit, and rotation due analysis."""

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def upsert_registry_entry(self, name: str, **kwargs: Any) -> RegistryRow:
        now = datetime.now(UTC)
        allowed = {
            "purpose",
            "service",
            "format_hint",
            "expected_prefix",
            "criticality",
            "depends_in_apps",
            "depends_in_services",
            "rotation_cadence_days",
            "last_rotated_at",
            "last_verified_synced_at",
            "drift_detected_at",
            "drift_summary",
            "lessons_learned",
        }
        update_fields = {k: v for k, v in kwargs.items() if k in allowed}
        row = await self._db.scalar(
            select(BrainSecretsRegistry).where(BrainSecretsRegistry.name == name)
        )
        if row is None:
            svc = update_fields.get("service")
            if not svc or not isinstance(svc, str):
                raise ValueError("service is required for new registry entries")
            row = BrainSecretsRegistry(name=name, service=svc, updated_at=now)
            for k, v in update_fields.items():
                if k == "service":
                    continue
                setattr(row, k, v)
            self._db.add(row)
        else:
            for k, v in update_fields.items():
                setattr(row, k, v)
            row.updated_at = now
        await self._db.flush()
        return _registry_to_row(row)

    async def get_registry(self, name: str) -> RegistryRow | None:
        r = await self._db.scalar(
            select(BrainSecretsRegistry).where(BrainSecretsRegistry.name == name)
        )
        return _registry_to_row(r) if r else None

    async def list_registry(self, criticality: str | None = None) -> list[RegistryRow]:
        q = select(BrainSecretsRegistry).order_by(BrainSecretsRegistry.name)
        if criticality:
            q = q.where(BrainSecretsRegistry.criticality == criticality)
        rows = (await self._db.execute(q)).scalars().all()
        return [_registry_to_row(r) for r in rows]

    async def record_episode(
        self,
        secret_name: str,
        event_type: str,
        source: str,
        summary: str,
        details: dict[str, Any] | None = None,
        triggered_task_id: UUID | None = None,
    ) -> EpisodeRow:
        ep = BrainSecretsEpisode(
            secret_name=secret_name,
            event_type=event_type,
            source=source,
            summary=summary,
            details=details or {},
            triggered_task_id=triggered_task_id,
            event_at=datetime.now(UTC),
        )
        self._db.add(ep)
        await self._db.flush()
        return _episode_to_row(ep)

    async def episodes_for(self, secret_name: str, limit: int = 50) -> list[EpisodeRow]:
        q = (
            select(BrainSecretsEpisode)
            .where(BrainSecretsEpisode.secret_name == secret_name)
            .order_by(BrainSecretsEpisode.event_at.desc())
            .limit(limit)
        )
        rows = (await self._db.execute(q)).scalars().all()
        return [_episode_to_row(e) for e in rows]

    async def detect_patterns(self, since: datetime | None = None) -> list[Pattern]:
        since = since or (datetime.now(UTC) - timedelta(days=30))
        q2 = (
            select(BrainSecretsEpisode.event_type, func.count(BrainSecretsEpisode.id))
            .where(BrainSecretsEpisode.event_at >= since)
            .group_by(BrainSecretsEpisode.event_type)
        )
        rows = (await self._db.execute(q2)).all()
        patterns: list[Pattern] = []
        for event_type, cnt in rows:
            sub = await self._db.execute(
                select(BrainSecretsEpisode.secret_name)
                .where(
                    BrainSecretsEpisode.event_at >= since,
                    BrainSecretsEpisode.event_type == event_type,
                )
                .distinct()
                .limit(5)
            )
            names = [str(x[0]) for x in sub.all()]
            patterns.append(
                Pattern(pattern=f"event_type:{event_type}", count=int(cnt), sample_secret_names=names)
            )
        return patterns

    async def audit_drift(self, secret_name: str) -> DriftReport:
        reg = await self.get_registry(secret_name)
        if not reg:
            return DriftReport(
                secret_name=secret_name,
                vault_fingerprint=None,
                targets=[
                    DriftTargetStatus("registry", "other", "error", "Unknown secret in registry")
                ],
                has_drift=True,
            )

        base = (settings.STUDIO_URL or "").rstrip("/")
        api_key = (settings.SECRETS_API_KEY or "").strip()
        if not base or not api_key:
            return DriftReport(
                secret_name=secret_name,
                vault_fingerprint=None,
                targets=[
                    DriftTargetStatus("vault", "vault", "skipped", "STUDIO_URL or SECRETS_API_KEY not set")
                ],
                has_drift=False,
            )

        headers = {"Authorization": f"Bearer {api_key}"}
        timeout = httpx.Timeout(30.0)
        targets: list[DriftTargetStatus] = []
        vault_fp: SecretFingerprint | None = None

        async with httpx.AsyncClient(timeout=timeout) as client:
            list_url = f"{base}/api/secrets"
            r = await client.get(list_url, headers=headers)
            if r.status_code != 200:
                detail = f"vault list HTTP {r.status_code}"
                logger.warning("audit_drift %s: %s", secret_name, detail)
                return DriftReport(
                    secret_name=secret_name,
                    vault_fingerprint=None,
                    targets=[DriftTargetStatus("vault", "vault", "error", detail)],
                    has_drift=True,
                )
            body = r.json()
            data = body.get("data")
            if not isinstance(data, list):
                return DriftReport(
                    secret_name=secret_name,
                    vault_fingerprint=None,
                    targets=[DriftTargetStatus("vault", "vault", "error", "unexpected list response")],
                    has_drift=True,
                )
            sid = None
            for item in data:
                if isinstance(item, dict) and item.get("name") == secret_name:
                    raw_id = item.get("id")
                    if raw_id:
                        sid = str(raw_id)
                    break
            if not sid:
                targets.append(
                    DriftTargetStatus(
                        "vault", "vault", "unavailable", "Secret not found in Studio vault"
                    )
                )
            else:
                gr = await client.get(f"{base}/api/secrets/{sid}", headers=headers)
                if gr.status_code != 200:
                    targets.append(
                        DriftTargetStatus(
                            "vault",
                            "vault",
                            "error",
                            f"get secret HTTP {gr.status_code}",
                        )
                    )
                else:
                    gjson = gr.json()
                    d = gjson.get("data") if isinstance(gjson, dict) else None
                    val = d.get("value") if isinstance(d, dict) else None
                    if not isinstance(val, str):
                        targets.append(
                            DriftTargetStatus("vault", "vault", "error", "no value in response")
                        )
                    else:
                        vault_fp = compute_fingerprint(val)

            # Vercel
            vteam = (settings.VERCEL_TEAM_ID or "").strip() or None
            vtoken = (settings.VERCEL_API_TOKEN or "").strip()
            for app in reg.depends_in_apps:
                proj = _vercel_project_for_app(app)
                if not proj or not vtoken:
                    targets.append(
                        DriftTargetStatus(
                            f"vercel:{app}",
                            "vercel",
                            "skipped",
                            "no project map or token",
                        )
                    )
                    continue
                tstatus, tf_detail, tfp = await self._vercel_env_fingerprint(
                    client, vtoken, vteam, proj, secret_name
                )
                st: Literal["in_sync", "drift", "skipped", "error", "unavailable"]
                if tstatus == "ok" and vault_fp and tfp:
                    st = "in_sync" if fingerprints_match(vault_fp, tfp) else "drift"
                elif tstatus == "ok":
                    st = "unavailable" if (not vault_fp or not tfp) else "in_sync"
                else:
                    st = tstatus
                targets.append(
                    DriftTargetStatus(
                        f"vercel:{app}:{proj}",
                        "vercel",
                        st,
                        tf_detail,
                        remote_fingerprint=tfp.to_log_dict() if tfp else None,
                    )
                )

            # Render
            rtoken = (settings.RENDER_API_KEY or "").strip()
            for svc in reg.depends_in_services:
                sid_render = _render_service_id(svc)
                if not sid_render or not rtoken:
                    targets.append(
                        DriftTargetStatus(
                            f"render:{svc}",
                            "render",
                            "skipped",
                            "no service id map or RENDER_API_KEY",
                        )
                    )
                    continue
                st_r, det_r, fp_r = await self._render_env_fingerprint(
                    client, rtoken, sid_render, secret_name
                )
                st2: Literal["in_sync", "drift", "skipped", "error", "unavailable"]
                if st_r == "ok" and vault_fp and fp_r:
                    st2 = "in_sync" if fingerprints_match(vault_fp, fp_r) else "drift"
                elif st_r == "ok":
                    st2 = "unavailable" if (not vault_fp or not fp_r) else "in_sync"
                else:
                    st2 = st_r
                targets.append(
                    DriftTargetStatus(
                        f"render:{svc}",
                        "render",
                        st2,
                        det_r,
                        remote_fingerprint=fp_r.to_log_dict() if fp_r else None,
                    )
                )

        has_drift = any(t.status == "drift" for t in targets) or any(
            t.status == "error" for t in targets
        )
        return DriftReport(
            secret_name=secret_name, vault_fingerprint=vault_fp, targets=targets, has_drift=has_drift
        )

    async def _vercel_env_fingerprint(
        self,
        client: httpx.AsyncClient,
        token: str,
        team_id: str | None,
        project: str,
        key_name: str,
    ) -> tuple[Literal["ok", "error", "unavailable"], str, SecretFingerprint | None]:
        q: dict[str, str] = {}
        if team_id:
            q["teamId"] = team_id
        url = f"https://api.vercel.com/v9/projects/{project}/env"
        headers = {"Authorization": f"Bearer {token}"}
        try:
            r = await client.get(url, headers=headers, params=q, timeout=30.0)
            if r.status_code != 200:
                return "error", f"vercel list HTTP {r.status_code}", None
            envs = r.json()
            if isinstance(envs, dict) and "envs" in envs:
                envs = envs["envs"]
            if not isinstance(envs, list):
                return "unavailable", "unexpected env list shape", None
            for e in envs:
                if not isinstance(e, dict):
                    continue
                if e.get("key") == key_name:
                    val = e.get("value")
                    if not isinstance(val, str):
                        return "unavailable", "vercel var without decrypted value", None
                    return "ok", "matched", compute_fingerprint(val)
            return "unavailable", f"key {key_name!r} not in project", None
        except httpx.HTTPError as ex:
            return "error", str(ex)[:200], None

    async def _render_env_fingerprint(
        self,
        client: httpx.AsyncClient,
        token: str,
        service_id: str,
        key_name: str,
    ) -> tuple[Literal["ok", "error", "unavailable"], str, SecretFingerprint | None]:
        url = f"https://api.render.com/v1/services/{service_id}/env-vars"
        headers = {"Authorization": f"Bearer {token}"}
        try:
            r = await client.get(url, headers=headers, timeout=30.0)
            if r.status_code != 200:
                return "error", f"render list HTTP {r.status_code}", None
            data = r.json()
            if not isinstance(data, list):
                return "unavailable", "unexpected render response", None
            for e in data:
                if not isinstance(e, dict):
                    continue
                ev = e.get("envVar")
                if isinstance(ev, dict):
                    if ev.get("key") != key_name:
                        continue
                    val = ev.get("value")
                elif e.get("key") == key_name:
                    val = e.get("value")
                else:
                    continue
                if isinstance(val, str):
                    return "ok", "matched", compute_fingerprint(val)
                if val is not None:
                    return "unavailable", "non-string value", None
            return "unavailable", f"key {key_name!r} not on service", None
        except httpx.HTTPError as ex:
            return "error", str(ex)[:200], None

    async def rotations_due(self, threshold_days: int = 7) -> list[RotationDueItem]:
        now = datetime.now(UTC)
        rows = (await self._db.execute(select(BrainSecretsRegistry))).scalars().all()
        out: list[RotationDueItem] = []
        window = timedelta(days=threshold_days)
        for r in rows:
            if r.rotation_cadence_days is None or r.rotation_cadence_days <= 0:
                continue
            last = r.last_rotated_at
            if last and last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            cadence = int(r.rotation_cadence_days)
            if last is None:
                out.append(
                    RotationDueItem(
                        name=r.name,
                        criticality=r.criticality,
                        next_due_at=None,
                        last_rotated_at=None,
                        rotation_cadence_days=cadence,
                        days_until_due=0,
                    )
                )
                continue
            next_due = last + timedelta(days=cadence)
            if next_due.tzinfo is None:
                next_due = next_due.replace(tzinfo=UTC)
            if next_due <= now + window:
                days_until = (next_due - now).days
                out.append(
                    RotationDueItem(
                        name=r.name,
                        criticality=r.criticality,
                        next_due_at=next_due,
                        last_rotated_at=last,
                        rotation_cadence_days=cadence,
                        days_until_due=days_until,
                    )
                )
        return sorted(out, key=lambda x: (x.days_until_due is not None, x.days_until_due or 0))

    async def mark_drift(
        self, secret_name: str, summary: str, detected: bool
    ) -> None:
        now = datetime.now(UTC)
        await self._db.execute(
            update(BrainSecretsRegistry)
            .where(BrainSecretsRegistry.name == secret_name)
            .values(
                drift_detected_at=now if detected else None,
                drift_summary=summary if detected else None,
                updated_at=now,
            )
        )
        await self._db.flush()

    async def update_rotation_sync(
        self,
        secret_name: str,
        *,
        last_rotated: datetime | None = None,
        last_verified: datetime | None = None,
    ) -> None:
        now = datetime.now(UTC)
        vals: dict[str, Any] = {"updated_at": now}
        if last_rotated is not None:
            vals["last_rotated_at"] = last_rotated
        if last_verified is not None:
            vals["last_verified_synced_at"] = last_verified
        await self._db.execute(
            update(BrainSecretsRegistry)
            .where(BrainSecretsRegistry.name == secret_name)
            .values(**vals)
        )
        await self._db.flush()
