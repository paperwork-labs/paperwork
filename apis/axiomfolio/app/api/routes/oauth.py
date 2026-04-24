"""Generic OAuth broker connection endpoints.

URL surface (mounted at ``/api/v1/oauth`` in ``app/api/main.py``):

* ``GET  /brokers``                     — list supported brokers
* ``POST /{broker}/initiate``           — start OAuth flow, return authorize_url + state
* ``POST /{broker}/callback``           — exchange code/verifier, persist encrypted tokens
* ``GET  /connections``                 — list current user's connections
* ``DELETE /connections/{id}``          — revoke + mark connection REVOKED

Multi-tenancy is enforced everywhere by ``current_user.id`` filters; never
trust ``user_id`` from the request body.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.config import settings
from app.database import get_db
from app.models.broker_oauth_connection import (
    BrokerOAuthConnection,
    OAuthConnectionStatus,
)
from app.models.user import User
from app.services.oauth import (
    OAuthCallbackContext,
    OAuthError,
    get_adapter,
    supported_brokers,
)
from app.services.oauth.encryption import decrypt, encrypt
from app.services.oauth.state_store import load_extra, save_extra

logger = logging.getLogger(__name__)

router = APIRouter()


def _normalize_oauth_state(state: str) -> str:
    """Strip surrounding whitespace; preserve case (cryptographic nonce)."""

    return (state or "").strip()


def _validate_oauth_callback_url(broker: str, callback_url: str) -> str:
    """Reject tampered callback URLs unless allowlisted or dev-local."""

    raw = (callback_url or "").strip()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="callback_url is required",
        )
    allow_csv = getattr(settings, "OAUTH_ALLOWED_CALLBACK_URLS", None) or ""
    allowed = {u.strip() for u in allow_csv.split(",") if u.strip()}
    if allowed:
        if raw not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="callback_url is not in the configured allowlist",
            )
        return raw
    pinned = getattr(settings, "ETRADE_OAUTH_CALLBACK_URL", None)
    if broker in ("etrade_sandbox", "etrade") and pinned:
        if raw != pinned.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="callback_url must match the registered OAuth callback URL",
            )
        return raw
    if settings.ENVIRONMENT == "development" or settings.DEBUG:
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower()
        if parsed.scheme in ("http", "https") and host in (
            "localhost",
            "127.0.0.1",
            "::1",
        ):
            return raw
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "Configure OAUTH_ALLOWED_CALLBACK_URLS or ETRADE_OAUTH_CALLBACK_URL for OAuth callbacks"
        ),
    )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class InitiateRequest(BaseModel):
    callback_url: str = Field(..., description="URL the broker redirects back to")


class InitiateResponse(BaseModel):
    broker: str
    state: str
    authorize_url: str
    expires_in_seconds: int = 600


class CallbackRequest(BaseModel):
    state: str = Field(..., min_length=8, description="CSRF nonce returned from /initiate")
    code: str = Field(..., min_length=1, description="OAuth code or 1.0a verifier")


class ConnectionRead(BaseModel):
    id: int
    broker: str
    environment: str
    status: str
    provider_account_id: str | None = None
    token_expires_at: datetime | None = None
    last_refreshed_at: datetime | None = None
    last_error: str | None = None
    rotation_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CallbackResponse(BaseModel):
    connection: ConnectionRead


class ConnectionsList(BaseModel):
    connections: list[ConnectionRead]


class RevokeResponse(BaseModel):
    id: int
    status: str


class BrokersResponse(BaseModel):
    brokers: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/brokers", response_model=BrokersResponse)
def list_brokers() -> BrokersResponse:
    """Return the OAuth brokers we know how to talk to."""

    return BrokersResponse(brokers=supported_brokers())


@router.post("/{broker}/initiate", response_model=InitiateResponse)
def initiate(
    broker: str = Path(..., min_length=2, max_length=32),
    payload: InitiateRequest = ...,
    current_user: User = Depends(get_current_user),
) -> InitiateResponse:
    """Begin an OAuth flow for ``broker`` on behalf of the current user.

    The CSRF state and any flow-specific extras (e.g. OAuth 1.0a request
    token secret) are stashed in Redis under ``oauth:state:{broker}:{state}``
    so the callback handler can replay them without trusting the client.
    """

    try:
        adapter = get_adapter(broker)
    except OAuthError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    validated_callback = _validate_oauth_callback_url(broker, payload.callback_url)

    try:
        result = adapter.initiate_url(
            user_id=current_user.id,
            callback_url=validated_callback,
        )
    except OAuthError as exc:
        # Permanent = config/credentials problem -> 400; transient -> 503
        http_status = (
            status.HTTP_400_BAD_REQUEST if exc.permanent else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        logger.warning(
            "oauth.initiate failed broker=%s user=%s permanent=%s err=%s",
            broker,
            current_user.id,
            exc.permanent,
            exc,
        )
        raise HTTPException(status_code=http_status, detail=str(exc))

    extra = dict(result.extra)
    extra["_user_id"] = current_user.id  # callback re-validates ownership
    save_extra(broker, result.state, extra)

    return InitiateResponse(
        broker=broker,
        state=result.state,
        authorize_url=result.authorize_url,
    )


@router.post("/{broker}/callback", response_model=CallbackResponse)
def callback(
    broker: str = Path(..., min_length=2, max_length=32),
    payload: CallbackRequest = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CallbackResponse:
    """Exchange the OAuth code/verifier for tokens and persist (encrypted)."""

    try:
        adapter = get_adapter(broker)
    except OAuthError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    norm_state = _normalize_oauth_state(payload.state)
    extra = load_extra(broker, norm_state)
    if extra is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OAuth state expired or unknown; restart the connection flow",
        )
    state_user_id = extra.pop("_user_id", None)
    if state_user_id is not None and int(state_user_id) != int(current_user.id):
        # CSRF / cross-tenant attempt — refuse.
        logger.warning(
            "oauth.callback cross-tenant refused broker=%s state_user=%s caller=%s",
            broker,
            state_user_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OAuth state does not belong to the authenticated user",
        )

    ctx = OAuthCallbackContext(code=payload.code, state=norm_state, extra=extra)
    try:
        tokens = adapter.exchange_code(ctx)
    except OAuthError as exc:
        http_status = (
            status.HTTP_400_BAD_REQUEST if exc.permanent else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        logger.warning(
            "oauth.callback exchange failed broker=%s user=%s permanent=%s err=%s",
            broker,
            current_user.id,
            exc.permanent,
            exc,
        )
        raise HTTPException(status_code=http_status, detail=str(exc))
    except Exception as exc:
        logger.exception(
            "oauth.callback unexpected error broker=%s user=%s",
            broker,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth callback failed.",
        ) from exc

    conn = (
        db.query(BrokerOAuthConnection)
        .filter(
            BrokerOAuthConnection.user_id == current_user.id,
            BrokerOAuthConnection.broker == broker,
            BrokerOAuthConnection.provider_account_id == tokens.provider_account_id,
        )
        .first()
    )
    if conn is None:
        conn = BrokerOAuthConnection(
            user_id=current_user.id,
            broker=broker,
            provider_account_id=tokens.provider_account_id,
            environment=adapter.environment,
            rotation_count=0,
        )
        db.add(conn)

    conn.access_token_encrypted = encrypt(tokens.access_token)
    conn.refresh_token_encrypted = encrypt(tokens.refresh_token) if tokens.refresh_token else None
    conn.token_expires_at = tokens.expires_at
    conn.scope = tokens.scope
    conn.environment = adapter.environment
    conn.status = OAuthConnectionStatus.ACTIVE.value
    conn.last_refreshed_at = datetime.now(UTC)
    conn.last_error = None
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning(
            "oauth.callback duplicate connection broker=%s user=%s: %s",
            broker,
            current_user.id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This broker account is already connected",
        ) from exc
    db.refresh(conn)
    return CallbackResponse(connection=ConnectionRead.model_validate(conn))


@router.get("/connections", response_model=ConnectionsList)
def list_connections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConnectionsList:
    """Return all OAuth connections owned by the current user."""

    rows = (
        db.query(BrokerOAuthConnection)
        .filter(BrokerOAuthConnection.user_id == current_user.id)
        .order_by(BrokerOAuthConnection.id.desc())
        .all()
    )
    return ConnectionsList(connections=[ConnectionRead.model_validate(r) for r in rows])


@router.delete("/connections/{connection_id}", response_model=RevokeResponse)
def revoke_connection(
    connection_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RevokeResponse:
    """Revoke at provider (best effort) and mark connection REVOKED locally."""

    conn = (
        db.query(BrokerOAuthConnection)
        .filter(
            BrokerOAuthConnection.id == connection_id,
            BrokerOAuthConnection.user_id == current_user.id,
        )
        .first()
    )
    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OAuth connection not found",
        )

    try:
        adapter = get_adapter(conn.broker)
    except OAuthError:
        adapter = None

    conn.last_error = None
    if adapter is not None and conn.access_token_encrypted:
        try:
            access = decrypt(conn.access_token_encrypted)
            refresh = (
                decrypt(conn.refresh_token_encrypted) if conn.refresh_token_encrypted else None
            )
            adapter.revoke(access_token=access, refresh_token=refresh)
        except Exception as exc:
            # We still want to mark REVOKED locally even if provider call fails;
            # surface the error in last_error rather than silently swallowing.
            logger.warning(
                "oauth.revoke provider call failed user=%s connection=%s broker=%s err=%s",
                current_user.id,
                conn.id,
                conn.broker,
                exc,
            )
            conn.last_error = f"revoke at provider failed: {exc}"

    conn.status = OAuthConnectionStatus.REVOKED.value
    conn.access_token_encrypted = None
    conn.refresh_token_encrypted = None
    conn.token_expires_at = None
    db.commit()
    db.refresh(conn)
    return RevokeResponse(id=conn.id, status=conn.status)


__all__ = ["router"]
