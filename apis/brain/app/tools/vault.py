"""D61: Vault tool — Tier 0 auto tool for Brain secret access.
Values returned to tool execution layer only, never injected into LLM prompt."""

import logging
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class VaultResult:
    success: bool
    value: str | None = None
    error: str | None = None
    metadata: dict | None = None


async def vault_list() -> VaultResult:
    """List all secret names (no values). Safe to show in LLM context."""
    try:
        async with _client() as client:
            res = await client.get("/api/secrets")
            res.raise_for_status()
            body = res.json()
            if not body.get("success"):
                return VaultResult(success=False, error=body.get("error", "Unknown error"))
            names = [s["name"] for s in body.get("data", [])]
            return VaultResult(success=True, value=", ".join(names))
    except Exception as e:
        logger.warning("vault_list failed: %s", e)
        return VaultResult(success=False, error=str(e))


async def vault_get(name: str) -> VaultResult:
    """Fetch a secret value by name. Value is returned to tool layer ONLY.
    The agent loop must NOT inject this into the LLM prompt."""
    try:
        async with _client() as client:
            list_res = await client.get("/api/secrets")
            list_res.raise_for_status()
            list_body = list_res.json()
            if not list_body.get("success"):
                return VaultResult(
                    success=False, error=list_body.get("error", "Failed to list secrets")
                )
            secrets = list_body.get("data", [])

            match = next((s for s in secrets if s["name"] == name), None)
            if not match:
                return VaultResult(success=False, error=f"Secret '{name}' not found")

            get_res = await client.get(f"/api/secrets/{match['id']}")
            get_res.raise_for_status()
            get_body = get_res.json()
            if not get_body.get("success"):
                return VaultResult(
                    success=False, error=get_body.get("error", "Failed to get secret")
                )
            secret_data = get_body.get("data", {})
            return VaultResult(
                success=True,
                value=secret_data.get("value"),
                metadata={"service": secret_data.get("service"), "name": name},
            )
    except Exception as e:
        logger.warning("vault_get(%s) failed: %s", name, e)
        return VaultResult(success=False, error=str(e))


async def vault_set(name: str, value: str, service: str) -> VaultResult:
    """Upsert a secret. Requires proper authorization."""
    try:
        async with _client() as client:
            res = await client.post(
                "/api/secrets",
                json={"name": name, "value": value, "service": service},
            )
            res.raise_for_status()
            body = res.json()
            if not body.get("success"):
                return VaultResult(success=False, error=body.get("error", "Failed to save secret"))
            return VaultResult(success=True, value=f"Secret '{name}' saved")
    except Exception as e:
        logger.warning("vault_set(%s) failed: %s", name, e)
        return VaultResult(success=False, error=str(e))


def _client() -> httpx.AsyncClient:
    api_key = settings.SECRETS_API_KEY
    if not api_key:
        raise RuntimeError("SECRETS_API_KEY not configured")
    return httpx.AsyncClient(
        base_url=settings.STUDIO_URL.rstrip("/"),
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=10.0,
    )
