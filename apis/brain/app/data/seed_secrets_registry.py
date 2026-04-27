"""Bootstrap ``brain_secrets_registry`` when empty (idempotent UPSERT)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.models.secrets_intelligence import BrainSecretsRegistry
from app.services.secrets_intelligence import SecretsIntelligence

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_APPS_WIDE = [
    "studio",
    "paperworklabs",
    "filefree",
    "launchfree",
    "distill",
    "brain",
    "axiomfolio",
    "trinkets",
]
_API_SERVICES = ["brain-api", "filefree-api"]

_CLERK_SECRET_KEY_ENTRY: dict[str, Any] = {
    "name": "CLERK_SECRET_KEY",
    "purpose": "Server-side Clerk JWT verification — gates all admin and customer auth",
    "service": "clerk",
    "format_hint": "sk_live_<base32>",
    "expected_prefix": "sk_live_",
    "criticality": "critical",
    "depends_in_apps": _APPS_WIDE,
    "depends_in_services": _API_SERVICES,
    "rotation_cadence_days": 90,
    "lessons_learned": [
        {
            "date": "2026-04-27",
            "lesson": (
                "Vercel CLI paste of long secret keys can append \\r\\n on macOS, causing 401s "
                "downstream. Vault is canonical; resync from vault when drift detected."
            ),
        },
        {
            "date": "2026-04-27",
            "lesson": (
                "sk_live leaked into chat transcript during initial setup. Established Secret "
                "Intake page (Agent Q) as the canonical paste path going forward."
            ),
        },
    ],
}

# Eight Clerk-tagged registry rows + platform secrets (10+) — all UPSERTed by name.
_SEED_ENTRIES: list[dict[str, Any]] = [
    _CLERK_SECRET_KEY_ENTRY,
    {
        "name": "CLERK_PUBLISHABLE_KEY",
        "purpose": "Clerk public key (frontend)",
        "service": "clerk",
        "format_hint": "pk_live_*",
        "expected_prefix": "pk_live_",
        "criticality": "high",
        "depends_in_apps": _APPS_WIDE,
        "depends_in_services": ["brain-api"],
        "rotation_cadence_days": 0,
    },
    {
        "name": "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",
        "purpose": "Next.js public env mirror for Clerk (browser)",
        "service": "clerk",
        "format_hint": "pk_live_*",
        "expected_prefix": "pk_live_",
        "criticality": "high",
        "depends_in_apps": _APPS_WIDE,
        "depends_in_services": [],
        "rotation_cadence_days": 0,
    },
    {
        "name": "CLERK_WEBHOOK_SECRET",
        "purpose": "Verify Clerk webhooks (signing secret)",
        "service": "clerk",
        "format_hint": "whsec_*",
        "expected_prefix": "whsec_",
        "criticality": "high",
        "depends_in_apps": ["studio", "brain"],
        "depends_in_services": ["brain-api", "filefree-api"],
        "rotation_cadence_days": 180,
    },
    {
        "name": "CLERK_JWT_KEY",
        "purpose": "JWT / JWKS override for custom verification steps",
        "service": "clerk",
        "format_hint": "PEM or JWKS URL",
        "expected_prefix": None,
        "criticality": "normal",
        "depends_in_apps": ["brain", "axiomfolio"],
        "depends_in_services": ["brain-api"],
        "rotation_cadence_days": 365,
    },
    {
        "name": "CLERK_API_URL",
        "purpose": "Clerk API base URL (usually https://api.clerk.com)",
        "service": "clerk",
        "format_hint": "https://",
        "expected_prefix": "https://",
        "criticality": "low",
        "depends_in_apps": ["studio"],
        "depends_in_services": ["brain-api"],
        "rotation_cadence_days": 0,
    },
    {
        "name": "CLERK_SIGNING_SECRET",
        "purpose": "Clerk request signing (server routes)",
        "service": "clerk",
        "format_hint": "secret",
        "expected_prefix": None,
        "criticality": "normal",
        "depends_in_apps": ["studio"],
        "depends_in_services": ["brain-api"],
        "rotation_cadence_days": 180,
    },
    {
        "name": "CLERK_INSTANCE_ID",
        "purpose": "Clerk instance identifier (dashboards / support)",
        "service": "clerk",
        "format_hint": "inst_*",
        "expected_prefix": None,
        "criticality": "low",
        "depends_in_apps": ["studio"],
        "depends_in_services": [],
        "rotation_cadence_days": 0,
    },
    {
        "name": "VERCEL_API_TOKEN",
        "purpose": "Vercel API — deploys, env sync, project automation",
        "service": "vercel",
        "format_hint": "bearer token",
        "expected_prefix": None,
        "criticality": "critical",
        "depends_in_apps": _APPS_WIDE,
        "depends_in_services": [],
        "rotation_cadence_days": 90,
    },
    {
        "name": "RENDER_API_KEY",
        "purpose": "Render API — services, env, deploy hooks",
        "service": "render",
        "format_hint": "rnd_*",
        "expected_prefix": "rnd_",
        "criticality": "critical",
        "depends_in_apps": ["studio", "brain"],
        "depends_in_services": _API_SERVICES,
        "rotation_cadence_days": 90,
    },
    {
        "name": "ANTHROPIC_API_KEY",
        "purpose": "Anthropic (Claude) for Brain and product LLM",
        "service": "llm",
        "format_hint": "sk-ant-*",
        "expected_prefix": "sk-ant-",
        "criticality": "critical",
        "depends_in_apps": ["studio", "brain", "axiomfolio"],
        "depends_in_services": ["brain-api", "filefree-api"],
        "rotation_cadence_days": 90,
    },
    {
        "name": "OPENAI_API_KEY",
        "purpose": "OpenAI API for embeddings and models",
        "service": "llm",
        "format_hint": "sk-*",
        "expected_prefix": "sk-",
        "criticality": "critical",
        "depends_in_apps": ["studio", "brain"],
        "depends_in_services": ["brain-api"],
        "rotation_cadence_days": 90,
    },
    {
        "name": "NEON_API_KEY",
        "purpose": "Neon control plane (branches, roles)",
        "service": "database",
        "format_hint": "neon *",
        "expected_prefix": None,
        "criticality": "high",
        "depends_in_apps": ["studio"],
        "depends_in_services": _API_SERVICES,
        "rotation_cadence_days": 90,
    },
    {
        "name": "UPSTASH_REDIS_REST_URL",
        "purpose": "Upstash REST endpoint URL",
        "service": "cache",
        "format_hint": "https://*.upstash.io",
        "expected_prefix": "https://",
        "criticality": "high",
        "depends_in_apps": ["studio", "brain"],
        "depends_in_services": ["brain-api"],
        "rotation_cadence_days": 0,
    },
    {
        "name": "UPSTASH_REDIS_REST_TOKEN",
        "purpose": "Upstash REST token",
        "service": "cache",
        "format_hint": "long token",
        "expected_prefix": None,
        "criticality": "critical",
        "depends_in_apps": ["studio", "brain"],
        "depends_in_services": ["brain-api"],
        "rotation_cadence_days": 90,
    },
    {
        "name": "SLACK_BOT_TOKEN",
        "purpose": "Slack bot for engineering / agent notifications",
        "service": "slack",
        "format_hint": "xoxb-*",
        "expected_prefix": "xoxb-",
        "criticality": "critical",
        "depends_in_apps": ["studio", "brain"],
        "depends_in_services": ["brain-api"],
        "rotation_cadence_days": 180,
    },
    {
        "name": "SECRETS_API_KEY",
        "purpose": "Machine auth to Studio secrets vault (Brain drift uses this read-only)",
        "service": "studio",
        "format_hint": "opaque",
        "expected_prefix": None,
        "criticality": "critical",
        "depends_in_apps": ["studio"],
        "depends_in_services": ["brain-api"],
        "rotation_cadence_days": 90,
    },
    {
        "name": "ADMIN_ACCESS_PASSWORD",
        "purpose": "Basic-auth escape hatch for Studio admin and vault ops",
        "service": "studio",
        "format_hint": "opaque",
        "expected_prefix": None,
        "criticality": "critical",
        "depends_in_apps": ["studio"],
        "depends_in_services": [],
        "rotation_cadence_days": 90,
    },
]


async def run_seed_if_empty(db: AsyncSession) -> int:
    """If registry has no rows, UPSERT all seed entries. Returns rows touched."""
    n = await db.scalar(select(func.count(BrainSecretsRegistry.id)))
    if n and int(n) > 0:
        return 0
    intel = SecretsIntelligence(db)
    count = 0
    for entry in _SEED_ENTRIES:
        name = str(entry["name"])
        service = str(entry.get("service", "unknown"))
        await intel.upsert_registry_entry(
            name,
            service=service,
            purpose=entry.get("purpose"),
            format_hint=entry.get("format_hint"),
            expected_prefix=entry.get("expected_prefix"),
            criticality=entry.get("criticality", "normal"),
            depends_in_apps=entry.get("depends_in_apps", []),
            depends_in_services=entry.get("depends_in_services", []),
            rotation_cadence_days=entry.get("rotation_cadence_days"),
            lessons_learned=entry.get("lessons_learned", []),
        )
        count += 1
    await db.commit()
    logger.info("Seeded brain_secrets_registry with %d entries", count)
    return count
