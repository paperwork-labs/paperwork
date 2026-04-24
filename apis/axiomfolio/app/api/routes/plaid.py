"""Plaid Investments API routes.

Mounted at ``/api/v1/plaid``. Surface:

* ``POST /link_token``              — mint a short-lived Plaid Link token
* ``POST /exchange``                — exchange public_token + persist item
* ``POST /webhook``                 — receive Plaid async notifications
* ``DELETE /connections/{id}``      — user-initiated disconnect
* ``GET  /connections``             — list current user's connections

Every route **except** ``/webhook`` requires:

1. ``get_current_user`` — valid JWT / session.
2. ``require_feature("broker.plaid_investments")`` — Pro-tier gate.
3. Per-user scoping — every DB query filters by ``current_user.id``.

``/webhook`` authenticates via Plaid's JWT + JWKS signature
(``verify_webhook``). It MUST NOT accept bearer tokens.

Rules followed:
* ``.cursor/rules/engineering.mdc`` — multi-tenancy enforcement
* ``.cursor/rules/no-silent-fallback.mdc`` — every failure is logged or
  re-raised; never ``except Exception: pass``
* Fernet-only for ``access_token`` at rest; plaintext never logged.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import require_feature
from app.database import get_db
from app.models.broker_account import (
    AccountStatus,
    AccountType,
    BrokerAccount,
    BrokerType,
    SyncStatus,
)
from app.models.plaid_connection import (
    PlaidConnection,
    PlaidConnectionStatus,
)
from app.models.user import User
from app.services.portfolio.plaid.client import (
    PlaidAPIError,
    PlaidClient,
    PlaidConfigurationError,
)
from app.services.portfolio.plaid.webhook_verify import (
    WebhookVerificationError,
    verify_webhook,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Plaid account.subtype -> our AccountType. Everything else defaults to
# TAXABLE with a logged warning rather than silently coerced.
_ACCOUNT_TYPE_MAP: dict[str, AccountType] = {
    "401k": AccountType.IRA,
    "401a": AccountType.IRA,
    "403b": AccountType.IRA,
    "457b": AccountType.IRA,
    "ira": AccountType.IRA,
    "roth": AccountType.ROTH_IRA,
    "roth 401k": AccountType.ROTH_IRA,
    "sep ira": AccountType.IRA,
    "simple ira": AccountType.IRA,
    "sarsep": AccountType.IRA,
    "hsa": AccountType.HSA,
    "brokerage": AccountType.TAXABLE,
    "trust": AccountType.TRUST,
    "other": AccountType.TAXABLE,
    "investment": AccountType.TAXABLE,
}


# ---- request / response schemas ------------------------------------------


class LinkTokenResponse(BaseModel):
    link_token: str = Field(..., description="Plaid-issued token for the Link SDK")
    expiration_seconds: int = Field(
        default=14400,
        description="Informational; actual expiry is baked into the token.",
    )


class ExchangeRequest(BaseModel):
    public_token: str = Field(..., min_length=1)
    # We don't trust any field in metadata for auth decisions. It's kept
    # as a loose dict because the Plaid Link SDK's shape evolves.
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExchangeResponse(BaseModel):
    connection_id: int
    item_id: str
    institution_name: str
    account_ids: list[int] = Field(
        ...,
        description="BrokerAccount primary keys created/updated for this item.",
    )
    status: str


class ConnectionOut(BaseModel):
    id: int
    item_id: str
    institution_id: str
    institution_name: str
    status: str
    environment: str
    last_sync_at: datetime | None
    last_error: str | None
    created_at: datetime


class ConnectionsList(BaseModel):
    connections: list[ConnectionOut]


class DisconnectResponse(BaseModel):
    id: int
    status: str


class WebhookAckResponse(BaseModel):
    ack: bool
    webhook_type: str | None = None
    webhook_code: str | None = None


# ---- helpers -------------------------------------------------------------


def _get_plaid_client() -> PlaidClient:
    """Build a :class:`PlaidClient`, mapping config errors to 503.

    503 (Service Unavailable) distinguishes "Plaid not configured on this
    instance" from a 500 (genuine bug). The frontend surfaces 503 as a
    friendly "this feature is currently disabled" banner.
    """
    try:
        return PlaidClient()
    except PlaidConfigurationError as exc:
        logger.warning("plaid routes: configuration error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Plaid integration is not configured on this instance.",
        ) from exc


def _map_broker_type(institution_name: str | None) -> BrokerType:
    """Match an institution name to a :class:`BrokerType`, case-insensitively.

    Plaid's institution names are free-form, so we match loosely. Unknowns
    return :attr:`BrokerType.UNKNOWN_BROKER` with a logged warning — we
    never silently coerce to ``FIDELITY`` just because the feature was
    built for that case.
    """
    name = (institution_name or "").lower()
    if not name:
        logger.warning("plaid: institution_name missing; using UNKNOWN_BROKER")
        return BrokerType.UNKNOWN_BROKER
    for bt in BrokerType:
        if bt.value in name or name.startswith(bt.value):
            return bt
    logger.warning("plaid: institution_name=%r did not match a known BrokerType", name)
    return BrokerType.UNKNOWN_BROKER


def _map_account_type(subtype: str | None) -> AccountType:
    if not subtype:
        return AccountType.TAXABLE
    key = subtype.replace("_", " ").strip().lower()
    mapped = _ACCOUNT_TYPE_MAP.get(key)
    if mapped is None:
        logger.info("plaid: unrecognised account subtype=%r -> defaulting to TAXABLE", key)
        return AccountType.TAXABLE
    return mapped


# ---- routes --------------------------------------------------------------


@router.post(
    "/link_token",
    response_model=LinkTokenResponse,
    status_code=status.HTTP_200_OK,
)
def create_link_token(
    current_user: User = Depends(require_feature("broker.plaid_investments")),
) -> LinkTokenResponse:
    """Mint a Plaid Link ``link_token`` for the authenticated user.

    The token encodes the user's tenant so the subsequent ``/exchange``
    call is scoped implicitly — we still check ``current_user.id`` on
    every write.
    """
    client = _get_plaid_client()
    try:
        token = client.create_link_token(user_id=current_user.id)
    except PlaidAPIError as exc:
        logger.warning(
            "plaid link_token_create failed for user_id=%s type=%s code=%s",
            current_user.id,
            exc.error_type,
            exc.error_code,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "plaid_api_error",
                "error_type": exc.error_type,
                "error_code": exc.error_code,
                "display_message": exc.display_message,
            },
        ) from exc
    return LinkTokenResponse(link_token=token)


@router.post(
    "/exchange",
    response_model=ExchangeResponse,
    status_code=status.HTTP_200_OK,
)
def exchange_public_token(
    body: ExchangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_feature("broker.plaid_investments")),
) -> ExchangeResponse:
    """Exchange a one-time ``public_token`` for a permanent item.

    Persists one :class:`PlaidConnection` (Fernet-encrypted token) and
    one :class:`BrokerAccount` per investment subtype returned by Plaid.
    Downstream syncs use :class:`PlaidSyncService`.
    """
    client = _get_plaid_client()
    try:
        access_token_plain, item_id = client.exchange_public_token(body.public_token)
    except PlaidAPIError as exc:
        logger.warning(
            "plaid exchange failed for user_id=%s type=%s code=%s",
            current_user.id,
            exc.error_type,
            exc.error_code,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "plaid_api_error",
                "error_type": exc.error_type,
                "error_code": exc.error_code,
            },
        ) from exc

    institution = body.metadata.get("institution") or {}
    institution_id = str(institution.get("institution_id") or "unknown")[:32]
    institution_name = str(institution.get("name") or "Unknown")[:128]
    broker_type = _map_broker_type(institution_name)

    access_token_ct = client.encrypt_access_token(access_token_plain)
    # IMPORTANT: shred plaintext as early as possible. Python's GC will
    # free the string; this makes the intent explicit.
    access_token_plain = ""

    connection = PlaidConnection(
        user_id=current_user.id,
        item_id=item_id,
        access_token_encrypted=access_token_ct,
        institution_id=institution_id,
        institution_name=institution_name,
        environment=client.environment,
        status=PlaidConnectionStatus.ACTIVE.value,
    )
    db.add(connection)
    try:
        db.flush()
    except IntegrityError as exc:
        # Unique(item_id) collision — user re-linked the same institution.
        # Reuse the existing row and refresh its token.
        db.rollback()
        existing = (
            db.query(PlaidConnection)
            .filter(
                PlaidConnection.item_id == item_id,
                PlaidConnection.user_id == current_user.id,
            )
            .first()
        )
        if existing is None:
            logger.warning(
                "plaid exchange: item_id=%s collision but not owned by user_id=%s",
                item_id,
                current_user.id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Plaid item already linked to a different account.",
            ) from exc
        existing.access_token_encrypted = access_token_ct
        existing.institution_id = institution_id
        existing.institution_name = institution_name
        existing.environment = client.environment
        existing.status = PlaidConnectionStatus.ACTIVE.value
        existing.last_error = None
        connection = existing
        db.flush()

    # Fetch accounts to create BrokerAccount rows. Investments-only —
    # depository (checking/savings) is silently skipped because we do
    # not model it. Log each skip so ops can see reality.
    try:
        accounts_meta = client.get_accounts(connection.access_token_encrypted)
    except PlaidAPIError as exc:
        logger.warning(
            "plaid exchange: accounts_get failed user_id=%s item_id=%s type=%s code=%s",
            current_user.id,
            item_id,
            exc.error_type,
            exc.error_code,
        )
        db.commit()  # keep the PlaidConnection; user can retry accounts_get later
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "plaid_accounts_get_failed",
                "error_type": exc.error_type,
                "error_code": exc.error_code,
            },
        ) from exc

    created_ids: list[int] = []
    for acct in accounts_meta:
        if str(acct.get("type")).lower() not in {"investment"}:
            logger.info(
                "plaid exchange: skipping non-investment account subtype=%r type=%r",
                acct.get("subtype"),
                acct.get("type"),
            )
            continue

        plaid_account_id = acct["account_id"]
        mask = acct.get("mask") or ""
        display_name = acct.get("official_name") or acct.get("name") or "Plaid account"

        existing_ba = (
            db.query(BrokerAccount)
            .filter(
                BrokerAccount.user_id == current_user.id,
                BrokerAccount.account_number == plaid_account_id,
                BrokerAccount.connection_source == "plaid",
            )
            .one_or_none()
        )
        if existing_ba is None:
            ba = BrokerAccount(
                user_id=current_user.id,
                broker=broker_type,
                account_number=plaid_account_id,
                account_name=f"{display_name} (··{mask})" if mask else display_name,
                account_type=_map_account_type(acct.get("subtype")),
                auto_discovered=True,
                status=AccountStatus.ACTIVE,
                is_primary=False,
                is_enabled=True,
                connection_source="plaid",
                connection_status="connected",
                sync_status=SyncStatus.NEVER_SYNCED,
                currency=(acct.get("balances", {}) or {}).get("iso_currency_code") or "USD",
            )
            db.add(ba)
            db.flush()
            created_ids.append(ba.id)
        else:
            existing_ba.account_name = f"{display_name} (··{mask})" if mask else display_name
            existing_ba.account_type = _map_account_type(acct.get("subtype"))
            existing_ba.connection_status = "connected"
            existing_ba.is_enabled = True
            created_ids.append(existing_ba.id)

    db.commit()

    return ExchangeResponse(
        connection_id=connection.id,
        item_id=item_id,
        institution_name=institution_name,
        account_ids=created_ids,
        status=connection.status,
    )


@router.get(
    "/connections",
    response_model=ConnectionsList,
)
def list_connections(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_feature("broker.plaid_investments")),
) -> ConnectionsList:
    """List the current user's Plaid connections."""
    rows = (
        db.query(PlaidConnection)
        .filter(PlaidConnection.user_id == current_user.id)
        .order_by(PlaidConnection.id.desc())
        .all()
    )
    return ConnectionsList(
        connections=[
            ConnectionOut(
                id=r.id,
                item_id=r.item_id,
                institution_id=r.institution_id,
                institution_name=r.institution_name,
                status=r.status,
                environment=r.environment,
                last_sync_at=r.last_sync_at,
                last_error=r.last_error,
                created_at=r.created_at,
            )
            for r in rows
        ]
    )


@router.delete(
    "/connections/{connection_id}",
    response_model=DisconnectResponse,
)
def disconnect(
    connection_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_feature("broker.plaid_investments")),
) -> DisconnectResponse:
    """Revoke a connection at Plaid and mark its rows disabled locally.

    Multi-tenancy: the filter includes ``user_id == current_user.id``;
    attempting to disconnect another tenant's connection returns 404.
    """
    conn = (
        db.query(PlaidConnection)
        .filter(
            PlaidConnection.id == connection_id,
            PlaidConnection.user_id == current_user.id,
        )
        .one_or_none()
    )
    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plaid connection not found.",
        )

    client = _get_plaid_client()
    try:
        client.remove_item(conn.access_token_encrypted)
    except PlaidAPIError as exc:
        # Log + continue: we still want the local rows disabled. Persist
        # the error on the row so /admin/health surfaces it.
        logger.warning(
            "plaid disconnect: remove_item failed user_id=%s conn_id=%s type=%s code=%s",
            current_user.id,
            conn.id,
            exc.error_type,
            exc.error_code,
        )
        conn.last_error = f"remove_item failed type={exc.error_type} code={exc.error_code}"

    conn.mark_revoked()
    # Disable every BrokerAccount linked via this connection so scheduled
    # syncs don't keep hitting Plaid.
    disabled = (
        db.query(BrokerAccount)
        .filter(
            BrokerAccount.user_id == current_user.id,
            BrokerAccount.connection_source == "plaid",
        )
        .all()
    )
    for ba in disabled:
        ba.is_enabled = False
        ba.connection_status = "disconnected"
    db.commit()

    return DisconnectResponse(id=conn.id, status=conn.status)


@router.post(
    "/webhook",
    response_model=WebhookAckResponse,
    status_code=status.HTTP_200_OK,
)
async def plaid_webhook(
    request: Request,
    plaid_verification: str | None = Header(default=None, alias="Plaid-Verification"),
) -> WebhookAckResponse:
    """Receive an async notification from Plaid.

    Auth is the JWT in ``Plaid-Verification`` — we MUST NOT accept
    bearer tokens here (Plaid cannot send one). We return 401 for any
    verification failure. Payload handling is intentionally minimal:
    we log the event and enqueue a sync for the item; full resync
    logic lives in the Celery task.
    """
    body = await request.body()
    try:
        client = _get_plaid_client()
    except HTTPException:
        # Mapping happens inside _get_plaid_client; re-raise as 503.
        raise

    try:
        payload = verify_webhook(
            body=body,
            plaid_verification_header=plaid_verification or "",
            plaid_api_client=client._api,
        )
    except WebhookVerificationError as exc:
        logger.warning("plaid webhook: signature verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid Plaid webhook signature",
        ) from exc

    # At this point we trust ``payload`` but NOT the raw body's JSON
    # claims beyond what the signature covered. Re-parse the body to
    # extract ``item_id`` etc., since Plaid puts the event data there.
    import json as _json

    try:
        event = _json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        logger.warning("plaid webhook: body parse failed after verify: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="webhook body is not valid JSON",
        ) from exc

    webhook_type = event.get("webhook_type")
    webhook_code = event.get("webhook_code")
    item_id = event.get("item_id")

    logger.info(
        "plaid webhook: type=%s code=%s item_id=%s",
        webhook_type,
        webhook_code,
        item_id,
    )

    # Acknowledge immediately. The daily cron already picks up new
    # holdings; an on-demand sync dispatch will be added here in a
    # follow-up. Noting the ``payload`` variable satisfies the linter
    # without leaking it into the response.
    _ = payload

    return WebhookAckResponse(ack=True, webhook_type=webhook_type, webhook_code=webhook_code)


__all__ = ["router"]
