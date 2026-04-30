"""Infrastructure registry reader (Render + Vercel inventory and vendors).

medallion: ops
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.schemas.infra_registry import InfraRegistryRoot, InfraRegistryService, InfraRegistryVendor

_ENV_REGISTRY = "BRAIN_INFRA_REGISTRY_JSON"


def registry_path() -> Path:
    env = os.environ.get(_ENV_REGISTRY, "").strip()
    if env:
        return Path(env)
    repo_root = os.environ.get("REPO_ROOT", "").strip()
    if repo_root:
        return Path(repo_root) / "apis" / "brain" / "data" / "infra_registry.json"
    return Path(__file__).resolve().parent.parent.parent / "data" / "infra_registry.json"


def load_registry() -> InfraRegistryRoot:
    """Load and validate ``infra_registry.json``."""
    raw = registry_path().read_text(encoding="utf-8")
    data = json.loads(raw)
    return InfraRegistryRoot.model_validate(data)


def get_service(service_id: str) -> InfraRegistryService | None:
    sid = service_id.strip()
    for s in load_registry().services:
        if s.id == sid:
            return s
    return None


def get_vendor(vendor_id: str) -> InfraRegistryVendor | None:
    vid = vendor_id.strip()
    for v in load_registry().vendors:
        if v.id == vid:
            return v
    return None


def list_services(provider: str | None = None) -> list[InfraRegistryService]:
    items = load_registry().services
    if provider is None or not (p := provider.strip()):
        return list(items)
    return [s for s in items if s.provider == p]


def list_vendors(category: str | None = None) -> list[InfraRegistryVendor]:
    items = load_registry().vendors
    if category is None or not (c := category.strip()):
        return list(items)
    return [v for v in items if v.category == c]
