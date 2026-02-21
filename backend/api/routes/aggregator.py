from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import hashlib
import urllib.parse
import asyncio
import time
from uuid import uuid4

from backend.database import get_db, SessionLocal
from backend.api.dependencies import get_current_user
from backend.models.user import User
from backend.models.broker_account import BrokerAccount, AccountCredentials
from backend.services.aggregator.schwab_connector import SchwabConnector
import httpx
from backend.services.security.oauth_state import oauth_state_service
from backend.services.security.credential_vault import credential_vault
from backend.config import settings
from backend.services.security.pkce_state import (
    generate_code_verifier,
    compute_code_challenge,
    save_verifier_for_state,
    pop_verifier_for_state,
)
from backend.services.clients.tastytrade_client import TastyTradeClient, TASTYTRADE_AVAILABLE
from backend.services.security.credential_vault import credential_vault as _vault
from backend.services.security.connect_job_store import connect_job_store


logger = logging.getLogger(__name__)

router = APIRouter()


def _persist_connect_error(user_id: int, broker: str, error_msg: str) -> None:
    """Persist last connect error to AccountCredentials for user's broker accounts."""
    from backend.models.broker_account import BrokerAccount, BrokerType
    broker_map = {"tastytrade": BrokerType.TASTYTRADE, "ibkr": BrokerType.IBKR}
    bt = broker_map.get(broker)
    if not bt:
        return
    sess = SessionLocal()
    try:
        accounts = (
            sess.query(BrokerAccount)
            .filter(BrokerAccount.user_id == user_id, BrokerAccount.broker == bt)
            .all()
        )
        for acc in accounts:
            cred = sess.query(AccountCredentials).filter(AccountCredentials.account_id == acc.id).first()
            if cred:
                cred.last_error = error_msg
        sess.commit()
    except Exception:
        sess.rollback()
    finally:
        sess.close()


def _is_truthy_value(val: Optional[str]) -> bool:
    if not val:
        return False
    v = str(val).strip().lower()
    return v not in {"", "none", "null", "false"}

def _is_schwab_configured() -> bool:
    return _is_truthy_value(settings.SCHWAB_CLIENT_ID) and _is_truthy_value(settings.SCHWAB_REDIRECT_URI)

class SchwabProbeResult(BaseModel):
    tried_bases: List[str]
    working_base: Optional[str] = None
    status_map: dict = {}
    built_authorize_url: Optional[str] = None


class ProviderConfig(BaseModel):
    configured: bool
    redirect_uri: Optional[str] = None
    probe: Optional[SchwabProbeResult] = None

class AggregatorConfigResponse(BaseModel):
    schwab: ProviderConfig

@router.get("/config", response_model=AggregatorConfigResponse)
async def get_aggregator_config() -> AggregatorConfigResponse:
    """Return minimal provider configuration status (no secrets)."""
    configured = _is_schwab_configured()
    redirect_uri = settings.SCHWAB_REDIRECT_URI if _is_truthy_value(settings.SCHWAB_REDIRECT_URI) else None
    probe: Optional[SchwabProbeResult] = None
    if configured:
        # Build current authorize URL and probe common bases to guide configuration
        connector = SchwabConnector()
        try:
            dummy_state = "schwab_probe"
            authorize = connector.get_authorization_url(state=dummy_state, trading=False)
        except Exception:
            authorize = None
        bases = [
            getattr(settings, "SCHWAB_AUTH_BASE", None) or connector.AUTH_BASE,
            "https://api.schwab.com/authorize",
            "https://api.schwab.com/oauth2/authorize",
            "https://api.schwab.com/oauth/authorize",
        ]
        status_map = {}
        working = None
        async with httpx.AsyncClient(follow_redirects=False, timeout=8) as client:
            for b in bases:
                try:
                    # Use GET without following redirects; 200/302/303 considered acceptable
                    r = await client.get(b, params={"response_type": "code"}, timeout=8)
                    status_map[b] = r.status_code
                    if r.status_code in (200, 301, 302, 303, 307, 308):
                        if not working:
                            working = b
                except Exception as e:
                    status_map[b] = f"error:{type(e).__name__}"
        probe = SchwabProbeResult(
            tried_bases=list(dict.fromkeys(bases)),
            working_base=working,
            status_map=status_map,
            built_authorize_url=authorize,
        )
    schwab_cfg = ProviderConfig(configured=configured, redirect_uri=redirect_uri, probe=probe)
    return AggregatorConfigResponse(schwab=schwab_cfg)

@router.get("/schwab/probe", response_model=SchwabProbeResult)
async def probe_schwab_authorize() -> SchwabProbeResult:
    """Actively probe known Schwab authorize bases and report which responds without 404."""
    connector = SchwabConnector()
    bases = [
        getattr(settings, "SCHWAB_AUTH_BASE", None) or connector.AUTH_BASE,
        "https://api.schwab.com/authorize",
        "https://api.schwab.com/oauth2/authorize",
        "https://api.schwab.com/oauth/authorize",
    ]
    status_map = {}
    working = None
    async with httpx.AsyncClient(follow_redirects=False, timeout=8) as client:
        for b in bases:
            try:
                r = await client.get(b, params={"response_type": "code"}, timeout=8)
                status_map[b] = r.status_code
                if r.status_code in (200, 301, 302, 303, 307, 308):
                    if not working:
                        working = b
            except Exception as e:
                status_map[b] = f"error:{type(e).__name__}"
    try:
        built = connector.get_authorization_url(state="schwab_probe", trading=False)
    except Exception:
        built = None
    return SchwabProbeResult(
        tried_bases=list(dict.fromkeys(bases)),
        working_base=working,
        status_map=status_map,
        built_authorize_url=built,
    )


class BrokersResponse(BaseModel):
    brokers: List[str]


@router.post("/brokers", response_model=BrokersResponse)
async def list_brokers() -> BrokersResponse:
    return BrokersResponse(brokers=["schwab"])


class LinkRequest(BaseModel):
    account_id: int
    trading: Optional[bool] = False


class LinkResponse(BaseModel):
    url: str


@router.post("/schwab/link", response_model=LinkResponse)
async def schwab_link(
    req: LinkRequest, user: User = Depends(get_current_user)
) -> LinkResponse:
    # Verify account ownership
    # Note: account_management uses user_id=1 for now; auth is enforced here
    if not req.account_id:
        raise HTTPException(status_code=400, detail="account_id required")
    # Validate OAuth config early to avoid generic 500s; treat 'None'/'null' as unset
    if not _is_schwab_configured():
        raise HTTPException(
            status_code=400,
            detail="Schwab OAuth not configured. Set SCHWAB_CLIENT_ID and SCHWAB_REDIRECT_URI.",
        )
    state = oauth_state_service.issue_state(user_id=user.id, account_id=req.account_id)
    connector = SchwabConnector()
    try:
        # Pick a working authorize base (avoid 404s)
        bases = [
            getattr(settings, "SCHWAB_AUTH_BASE", None) or connector.AUTH_BASE,
            "https://api.schwab.com/authorize",
            "https://api.schwab.com/oauth2/authorize",
            "https://api.schwab.com/oauth/authorize",
        ]
        working = None
        async with httpx.AsyncClient(follow_redirects=False, timeout=8) as client:
            for b in bases:
                try:
                    r = await client.get(b, params={"response_type": "code"})
                    if r.status_code in (200, 301, 302, 303, 307, 308):
                        working = b
                        break
                except Exception:
                    continue
        if not working:
            raise HTTPException(
                status_code=502,
                detail="No working Schwab authorize endpoint detected. Check SCHWAB_AUTH_BASE and client_id suffix.",
            )
        # Override base for this link
        connector.auth_base = working
        # PKCE: create verifier and derived challenge; persist verifier keyed by state
        verifier = generate_code_verifier()
        challenge = compute_code_challenge(verifier)
        save_verifier_for_state(state, verifier, ttl_seconds=600)
        # Build URL
        base_url = connector.get_authorization_url(state=state, trading=bool(req.trading))
        # Append PKCE params
        sep = "&" if "?" in base_url else "?"
        url = f"{base_url}{sep}code_challenge={urllib.parse.quote(challenge)}&code_challenge_method=S256"
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Ensure we return JSON with CORS headers instead of raw 500
        raise HTTPException(status_code=500, detail=f"schwab_link failed: {e}")
    return LinkResponse(url=url)


# -------------------------
# Tastytrade Connections
# -------------------------
class TTConnectRequest(BaseModel):
    client_id: str
    client_secret: str
    refresh_token: str


class TTStatusResponse(BaseModel):
    available: bool
    connected: bool
    accounts: List[dict] = []
    last_error: Optional[str] = None
    job_id: Optional[str] = None
    job_state: Optional[str] = None  # pending|running|success|error
    job_error: Optional[str] = None


async def _tt_connect_job(job_id: str, client_id: str, client_secret: str, refresh_token: str, user_id: int):
    connect_job_store.set(job_id, {"state": "running", "started_at": time.time(), "broker": "tastytrade"})
    db = SessionLocal()
    try:
        client = TastyTradeClient()
        ok = await client.connect_with_credentials(client_secret, refresh_token)
        if not ok:
            last_err = getattr(client, "connection_health", {}).get("last_error") or "Login failed"
            connect_job_store.set(job_id, {
                "state": "error",
                "error": last_err,
                "finished_at": time.time(),
                "broker": "tastytrade",
            })
            _persist_connect_error(user_id, "tastytrade", last_err)
            return
        accounts = await client.get_accounts()
        from backend.models.broker_account import BrokerAccount, BrokerType, AccountType, AccountStatus, SyncStatus
        for acc in accounts or []:
            acct_num = acc.get("account_number")
            if not acct_num:
                continue
            existing = (
                db.query(BrokerAccount)
                .filter(
                    BrokerAccount.user_id == user_id,
                    BrokerAccount.broker == BrokerType.TASTYTRADE,
                    BrokerAccount.account_number == acct_num,
                )
                .first()
            )
            if existing:
                existing.account_name = acc.get("nickname") or existing.account_name or f"Tastytrade ({acct_num})"
                existing.account_type = AccountType.TAXABLE
                existing.status = AccountStatus.ACTIVE
                existing.is_enabled = True
                existing.connection_status = "connected"
                existing.api_credentials_stored = True
                acc_id = existing.id
            else:
                ba = BrokerAccount(
                    user_id=user_id,
                    broker=BrokerType.TASTYTRADE,
                    account_number=acct_num,
                    account_name=acc.get("nickname") or f"Tastytrade ({acct_num})",
                    account_type=AccountType.TAXABLE,
                    status=AccountStatus.ACTIVE,
                    is_enabled=True,
                    sync_status=SyncStatus.NEVER_SYNCED,
                    currency="USD",
                    api_credentials_stored=True,
                    connection_status="connected",
                )
                db.add(ba)
                db.flush()
                acc_id = ba.id
            from backend.models.broker_account import AccountCredentials
            cred = (
                db.query(AccountCredentials)
                .filter(AccountCredentials.account_id == acc_id)
                .first()
            )
            payload = {"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token}
            enc = _vault.encrypt_dict(payload)
            if cred:
                cred.encrypted_credentials = enc
                cred.provider = BrokerType.TASTYTRADE
                cred.credential_type = "oauth"
            else:
                cred = AccountCredentials(
                    account_id=acc_id,
                    encrypted_credentials=enc,
                    provider=BrokerType.TASTYTRADE,
                    credential_type="oauth",
                )
                db.add(cred)
        db.commit()
        connect_job_store.set(job_id, {
            "state": "success",
            "finished_at": time.time(),
            "broker": "tastytrade",
        })
    except Exception as e:
        db.rollback()
        connect_job_store.set(job_id, {"state": "error", "error": str(e), "finished_at": time.time(), "broker": "tastytrade"})
        _persist_connect_error(user_id, "tastytrade", str(e))
    finally:
        db.close()


@router.post("/tastytrade/connect")
async def tastytrade_connect(
    req: TTConnectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not TASTYTRADE_AVAILABLE:
        raise HTTPException(status_code=503, detail="TastyTrade SDK not installed")
    job_id = uuid4().hex
    connect_job_store.set(job_id, {"state": "pending", "created_at": time.time(), "broker": "tastytrade"})
    asyncio.create_task(_tt_connect_job(job_id, req.client_id, req.client_secret, req.refresh_token, user.id))
    return {"job_id": job_id}


@router.post("/tastytrade/disconnect", response_model=TTStatusResponse)
async def tastytrade_disconnect(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TTStatusResponse:
    if not TASTYTRADE_AVAILABLE:
        raise HTTPException(status_code=503, detail="TastyTrade SDK not installed")
    from backend.models.broker_account import BrokerAccount, BrokerType
    tt_accounts = (
        db.query(BrokerAccount)
        .filter(BrokerAccount.user_id == user.id, BrokerAccount.broker == BrokerType.TASTYTRADE)
        .all()
    )
    for a in tt_accounts:
        a.is_enabled = False
        a.api_credentials_stored = False
        a.connection_status = "disconnected"
        db.query(AccountCredentials).filter(AccountCredentials.account_id == a.id).delete()
    db.commit()
    return TTStatusResponse(available=True, connected=False, accounts=[])


@router.get("/tastytrade/status", response_model=TTStatusResponse)
async def tastytrade_status(
    job_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TTStatusResponse:
    if not TASTYTRADE_AVAILABLE:
        return TTStatusResponse(available=False, connected=False, accounts=[], last_error="SDK not installed", job_id=job_id, job_state=("error" if job_id else None), job_error="SDK not installed")
    from backend.models.broker_account import BrokerType
    tt_accounts = (
        db.query(BrokerAccount)
        .filter(BrokerAccount.user_id == user.id, BrokerAccount.broker == BrokerType.TASTYTRADE)
        .all()
    )
    has_creds = any(
        db.query(AccountCredentials).filter(AccountCredentials.account_id == a.id).first()
        for a in tt_accounts
    )
    accounts_list = [
        {"account_number": a.account_number, "nickname": a.account_name}
        for a in tt_accounts
    ]
    last_error = None
    for a in tt_accounts:
        cred = db.query(AccountCredentials).filter(AccountCredentials.account_id == a.id).first()
        if cred and cred.last_error:
            last_error = cred.last_error
            break
    resp = TTStatusResponse(
        available=True,
        connected=has_creds,
        accounts=accounts_list,
        last_error=last_error,
    )
    if job_id:
        job = connect_job_store.get(job_id)
        if job:
            resp.job_id = job_id
            resp.job_state = job.get("state")
            resp.job_error = job.get("error")
    return resp


# -------------------------
# IBKR Flex (MVP read-only)
# -------------------------
class IBKRFlexConnectRequest(BaseModel):
    flex_token: str
    query_id: str
    account_number: Optional[str] = None


async def _ibkr_connect_job(
    job_id: str,
    flex_token: str,
    query_id: str,
    user_id: int,
    account_number: Optional[str] = None,
):
    connect_job_store.set(job_id, {"state": "running", "started_at": time.time(), "broker": "ibkr"})
    db = SessionLocal()
    try:
        from backend.models.broker_account import BrokerAccount, BrokerType, AccountType, AccountStatus, SyncStatus, AccountCredentials
        from backend.services.clients.ibkr_flexquery_client import IBKRFlexQueryClient

        acct_num = (account_number or "").strip()

        # If no account number was supplied, try to discover it from IBKR
        if not acct_num:
            try:
                _client = IBKRFlexQueryClient(token=flex_token, query_id=query_id)
                report = await _client.get_full_report("_discover")
                if report:
                    discovered = _client.extract_account_ids(report)
                    if discovered:
                        acct_num = discovered[0]
                        logger.info("Auto-discovered IBKR account: %s", acct_num)
            except Exception as exc:
                logger.warning("IBKR account discovery failed: %s", exc)

        if not acct_num:
            acct_num = f"IBKR-{user_id}"

        # Find existing or create new BrokerAccount
        account = (
            db.query(BrokerAccount)
            .filter(
                BrokerAccount.user_id == user_id,
                BrokerAccount.broker == BrokerType.IBKR,
                BrokerAccount.account_number == acct_num,
            )
            .first()
        )
        if not account:
            account = BrokerAccount(
                user_id=user_id,
                broker=BrokerType.IBKR,
                account_number=acct_num,
                account_name=f"IBKR ({acct_num})",
                account_type=AccountType.TAXABLE,
                status=AccountStatus.ACTIVE,
                is_enabled=True,
                sync_status=SyncStatus.NEVER_SYNCED,
                currency="USD",
                api_credentials_stored=True,
                connection_status="connected",
            )
            db.add(account)
            db.flush()
        payload = {"flex_token": flex_token, "query_id": query_id}
        enc = _vault.encrypt_dict(payload)
        cred = (
            db.query(AccountCredentials)
            .filter(AccountCredentials.account_id == account.id)
            .first()
        )
        if cred:
            cred.encrypted_credentials = enc
            cred.provider = BrokerType.IBKR
            cred.credential_type = "ibkr_flex"
            cred.username_hint = None
        else:
            cred = AccountCredentials(
                account_id=account.id,
                encrypted_credentials=enc,
                provider=BrokerType.IBKR,
                credential_type="ibkr_flex",
            )
            db.add(cred)
        db.commit()

        # Lightweight credential validation: fire a single SendRequest to check
        # token/query_id are accepted by IBKR. Doesn't block on report generation.
        warning = None
        try:
            client = IBKRFlexQueryClient(token=flex_token, query_id=query_id)
            valid, msg = await client.validate_credentials()
            if not valid:
                warning = msg
                logger.warning("IBKR credential validation warning for user %s: %s", user_id, msg)
        except Exception as exc:
            warning = f"Could not validate credentials: {exc}"
            logger.warning("IBKR credential validation error: %s", exc)

        job_result: dict = {"state": "success", "finished_at": time.time(), "broker": "ibkr"}
        if warning:
            job_result["warning"] = warning
        connect_job_store.set(job_id, job_result)
    except Exception as e:
        db.rollback()
        connect_job_store.set(job_id, {"state": "error", "error": str(e), "finished_at": time.time(), "broker": "ibkr"})
        _persist_connect_error(user_id, "ibkr", str(e))
    finally:
        db.close()


@router.post("/ibkr/connect")
async def ibkr_flex_connect(
    req: IBKRFlexConnectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job_id = uuid4().hex
    connect_job_store.set(job_id, {"state": "pending", "created_at": time.time(), "broker": "ibkr"})
    asyncio.create_task(
        _ibkr_connect_job(
            job_id,
            req.flex_token,
            req.query_id,
            user.id,
            account_number=req.account_number,
        )
    )
    return {"job_id": job_id}


@router.get("/ibkr/status")
async def ibkr_flex_status(
    job_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from backend.models.broker_account import BrokerAccount, BrokerType

    accounts = (
        db.query(BrokerAccount)
        .filter(BrokerAccount.user_id == user.id, BrokerAccount.broker == BrokerType.IBKR)
        .all()
    )
    result = {
        "connected": any(a.api_credentials_stored for a in accounts),
        "accounts": [{"id": a.id, "account_number": a.account_number, "name": a.account_name} for a in accounts],
    }
    if job_id:
        job = connect_job_store.get(job_id)
        if job:
            result["job_id"] = job_id
            result["job_state"] = job.get("state")
            result["job_error"] = job.get("error")
    return result


@router.post("/ibkr/disconnect")
async def ibkr_flex_disconnect(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    from backend.models.broker_account import BrokerAccount, BrokerType
    q = (
        db.query(BrokerAccount)
        .filter(BrokerAccount.user_id == user.id, BrokerAccount.broker == BrokerType.IBKR)
        .all()
    )
    for a in q:
        a.is_enabled = False
        a.connection_status = "disconnected"
    db.commit()
    return {"status": "disconnected"}


# -------------------------
# Other broker stubs (Fidelity/Robinhood/Public)
# -------------------------
class GenericConnectRequest(BaseModel):
    credentials: dict


@router.post("/fidelity/connect")
async def fidelity_connect(req: GenericConnectRequest, user: User = Depends(get_current_user)):
    # Placeholder: accept credentials and store encrypted later
    return {"status": "unsupported", "message": "Fidelity connector not yet implemented"}


@router.get("/fidelity/status")
async def fidelity_status(user: User = Depends(get_current_user)):
    return {"connected": False, "available": False, "message": "Not implemented"}


@router.post("/robinhood/connect")
async def robinhood_connect(req: GenericConnectRequest, user: User = Depends(get_current_user)):
    return {"status": "unsupported", "message": "Robinhood connector not yet implemented"}


@router.get("/robinhood/status")
async def robinhood_status(user: User = Depends(get_current_user)):
    return {"connected": False, "available": False, "message": "Not implemented"}


@router.post("/public/connect")
async def public_connect(req: GenericConnectRequest, user: User = Depends(get_current_user)):
    return {"status": "unsupported", "message": "Public connector not yet implemented"}


@router.get("/public/status")
async def public_status(user: User = Depends(get_current_user)):
    return {"connected": False, "available": False, "message": "Not implemented"}

@router.get("/schwab/callback")
async def schwab_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    try:
        data = oauth_state_service.validate_state(state)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid state: {e}")

    uid = int(data["uid"])
    aid = int(data["aid"])

    # Locate account
    account = (
        db.query(BrokerAccount)
        .filter(BrokerAccount.id == aid, BrokerAccount.user_id == uid)
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Exchange code for tokens
    connector = SchwabConnector()
    try:
        code_verifier = pop_verifier_for_state(state)
        tokens = await connector.exchange_code_for_tokens(code, code_verifier=code_verifier)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Token exchange failed: {e}")

    # Persist encrypted credentials
    encrypted = credential_vault.encrypt_dict(tokens)
    cred = (
        db.query(AccountCredentials)
        .filter(AccountCredentials.account_id == account.id)
        .first()
    )
    token_fingerprint = hashlib.sha256(
        str(tokens.get("access_token", "")).encode("utf-8")
    ).hexdigest()
    if cred:
        cred.encrypted_credentials = encrypted
        cred.credential_hash = token_fingerprint
        cred.provider = account.broker
        cred.credential_type = "oauth"
        cred.username_hint = None
        cred.last_refreshed_at = None
        cred.refresh_token_expires_at = None
    else:
        cred = AccountCredentials(
            account_id=account.id,
            encrypted_credentials=encrypted,
            credential_hash=token_fingerprint,
            provider=account.broker,
            credential_type="oauth",
        )
        db.add(cred)

    account.api_credentials_stored = True
    account.connection_status = "connected"
    db.commit()

    return {"status": "linked", "account_id": account.id}


