"""Repository for ``brain_user_vault`` (D61) — encrypted per-user secret cache."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC
from typing import TYPE_CHECKING

from sqlalchemy import delete, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vault import UserVault
from app.schemas.brain_user_vault import VaultEntry
from app.security.brain_user_vault_crypto import decrypt_secret_value, encrypt_secret_value

logger = logging.getLogger(__name__)

# Default org matches ``001_initial_schema`` seed; repo always scopes (user_id, org, name).
_DEFAULT_ORG_ID = "paperwork-labs"


def _normalize_user_id(user_id: str) -> str:
    if not user_id or not user_id.strip():
        raise ValueError("user_id must be a non-empty UUID string")
    try:
        return str(uuid.UUID(user_id.strip()))
    except ValueError as e:
        raise ValueError("user_id must be a valid UUID") from e


def _normalize_org(organization_id: str) -> str:
    stripped = organization_id.strip()
    return stripped if stripped else _DEFAULT_ORG_ID


async def _upsert_plaintext(
    user_id: str,
    key: str,
    value: str,
    *,
    db: AsyncSession,
    organization_id: str,
) -> None:
    uid = _normalize_user_id(user_id)
    if not key.strip():
        raise ValueError("key must be non-empty")
    org = _normalize_org(organization_id)
    enc, iv_b64, tag_b64 = encrypt_secret_value(value)
    name = key.strip()
    stmt = select(UserVault).where(
        UserVault.user_id == uid,
        UserVault.organization_id == org,
        UserVault.name == name,
    )
    res = await db.execute(stmt)
    row = res.scalar_one_or_none()
    if row:
        row.encrypted_value = enc
        row.iv = iv_b64
        row.auth_tag = tag_b64
    else:
        db.add(
            UserVault(
                user_id=uid,
                organization_id=org,
                name=name,
                encrypted_value=enc,
                iv=iv_b64,
                auth_tag=tag_b64,
            )
        )
    logger.info(
        "brain_user_vault set user=%s… key=%s org=%s",
        uid[:8],
        name,
        org,
    )
    await db.flush()


async def set_secret(user_id: str, key: str, value: str, *, db: AsyncSession) -> None:
    """Upsert an encrypted secret for ``(user_id, default_org, key)``."""
    await _upsert_plaintext(user_id, key, value, db=db, organization_id=_DEFAULT_ORG_ID)


async def set_secret_for_organization(
    user_id: str,
    key: str,
    value: str,
    *,
    db: AsyncSession,
    organization_id: str,
) -> None:
    """Upsert with explicit ``organization_id`` (admin / multi-org callers)."""
    await _upsert_plaintext(user_id, key, value, db=db, organization_id=organization_id)


async def _get_plaintext_optional(
    user_id: str,
    key: str,
    *,
    db: AsyncSession,
    organization_id: str,
) -> str | None:
    uid = _normalize_user_id(user_id)
    if not key.strip():
        raise ValueError("key must be non-empty")
    org = _normalize_org(organization_id)
    name = key.strip()
    stmt = select(UserVault).where(
        UserVault.user_id == uid,
        UserVault.organization_id == org,
        UserVault.name == name,
    )
    res = await db.execute(stmt)
    row = res.scalar_one_or_none()
    if row is None:
        return None
    plain = decrypt_secret_value(row.encrypted_value, row.iv, row.auth_tag)
    logger.debug(
        "brain_user_vault get hit user=%s… key=%s",
        uid[:8],
        name,
    )
    return plain


async def get_secret(user_id: str, key: str, *, db: AsyncSession) -> str | None:
    """Return decrypted plaintext or ``None`` if no row exists."""
    return await _get_plaintext_optional(user_id, key, db=db, organization_id=_DEFAULT_ORG_ID)


async def get_secret_for_organization(
    user_id: str,
    key: str,
    *,
    db: AsyncSession,
    organization_id: str,
) -> str | None:
    """Same as :func:`get_secret` with explicit ``organization_id``."""
    return await _get_plaintext_optional(user_id, key, db=db, organization_id=organization_id)


async def _list_entries(
    user_id: str,
    *,
    db: AsyncSession,
    organization_id: str,
) -> list[VaultEntry]:
    uid = _normalize_user_id(user_id)
    org = _normalize_org(organization_id)
    stmt = (
        select(UserVault.name, UserVault.created_at)
        .where(UserVault.user_id == uid, UserVault.organization_id == org)
        .order_by(UserVault.name)
    )
    res = await db.execute(stmt)
    out: list[VaultEntry] = []
    for name, created_at in res.all():
        ts = created_at
        ts = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)
        out.append(
            VaultEntry(
                key=name,
                created_at=ts,
                updated_at=ts,
            )
        )
    return out


async def list_secrets(user_id: str, *, db: AsyncSession) -> list[VaultEntry]:
    """List secret keys and timestamps — never ciphertext or plaintext."""
    return await _list_entries(user_id, db=db, organization_id=_DEFAULT_ORG_ID)


async def list_secrets_for_organization(
    user_id: str,
    *,
    db: AsyncSession,
    organization_id: str,
) -> list[VaultEntry]:
    """Same as :func:`list_secrets` with explicit ``organization_id``."""
    return await _list_entries(user_id, db=db, organization_id=organization_id)


async def _delete_row(
    user_id: str,
    key: str,
    *,
    db: AsyncSession,
    organization_id: str,
) -> bool:
    uid = _normalize_user_id(user_id)
    if not key.strip():
        raise ValueError("key must be non-empty")
    org = _normalize_org(organization_id)
    name = key.strip()
    stmt = delete(UserVault).where(
        UserVault.user_id == uid,
        UserVault.organization_id == org,
        UserVault.name == name,
    )
    result = await db.execute(stmt)
    deleted = result.rowcount > 0  # type: ignore[attr-defined]
    if deleted:
        logger.info(
            "brain_user_vault delete user=%s… key=%s",
            uid[:8],
            name,
        )
    await db.flush()
    return bool(deleted)


async def delete_secret(user_id: str, key: str, *, db: AsyncSession) -> bool:
    """Delete one secret; returns ``True`` if a row was removed."""
    return await _delete_row(user_id, key, db=db, organization_id=_DEFAULT_ORG_ID)


async def delete_secret_for_organization(
    user_id: str,
    key: str,
    *,
    db: AsyncSession,
    organization_id: str,
) -> bool:
    """Same as :func:`delete_secret` with explicit ``organization_id``."""
    return await _delete_row(user_id, key, db=db, organization_id=organization_id)
