"""D61: Vault tool — Tier 0 auto tool for Brain secret access.
Values returned to tool execution layer only, never injected into LLM prompt."""

import logging
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

STUDIO_URL = "https://paperworklabs.com"


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
            res = await client.get(f"{STUDIO_URL}/api/secrets")
            res.raise_for_status()
            data = res.json()
            names = [s["name"] for s in data.get("data", [])]
            return VaultResult(success=True, value=", ".join(names))
    except Exception as e:
        return VaultResult(success=False, error=str(e))


async def vault_get(name: str) -> VaultResult:
    """Fetch a secret value by name. Value is returned to tool layer ONLY.
    The agent loop must NOT inject this into the LLM prompt."""
    try:
        async with _client() as client:
            list_res = await client.get(f"{STUDIO_URL}/api/secrets")
            list_res.raise_for_status()
            secrets = list_res.json().get("data", [])

            match = next((s for s in secrets if s["name"] == name), None)
            if not match:
                return VaultResult(success=False, error=f"Secret '{name}' not found")

            get_res = await client.get(f"{STUDIO_URL}/api/secrets/{match['id']}")
            get_res.raise_for_status()
            secret_data = get_res.json().get("data", {})
            return VaultResult(
                success=True,
                value=secret_data.get("value"),
                metadata={"service": secret_data.get("service"), "name": name},
            )
    except Exception as e:
        return VaultResult(success=False, error=str(e))


async def vault_set(name: str, value: str, service: str) -> VaultResult:
    """Upsert a secret. Requires proper authorization."""
    try:
        async with _client() as client:
            res = await client.post(
                f"{STUDIO_URL}/api/secrets",
                json={"name": name, "value": value, "service": service},
            )
            res.raise_for_status()
            return VaultResult(success=True, value=f"Secret '{name}' saved")
    except Exception as e:
        return VaultResult(success=False, error=str(e))


def _client() -> httpx.AsyncClient:
    api_key = settings.VAULT_API_KEY
    if not api_key:
        raise RuntimeError("VAULT_API_KEY not configured")
    return httpx.AsyncClient(
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=10.0,
    )
