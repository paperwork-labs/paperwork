"""
AxiomFolio V1 - Authentication Routes
=====================================

User authentication, registration, OAuth, email verification, and session management.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Query
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr, ConfigDict, Field
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from fastapi.responses import RedirectResponse
import hashlib
import hmac
import httpx
import jwt as jwt_lib
import logging
import time as _time
import uuid

from backend.database import get_db
from backend.models.user import User, UserRole
from backend.models.user_invite import UserInvite
from backend.config import settings
from backend.api.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from backend.api.dependencies import get_current_user

logger = logging.getLogger(__name__)

security = HTTPBearer()
pwd_context = CryptContext(schemes=["sha256_crypt", "bcrypt"], deprecated="auto")

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    role: Optional[str] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_approved: bool = False
    created_at: datetime
    timezone: Optional[str] = None
    currency_preference: Optional[str] = None
    notification_preferences: Optional[Dict[str, Any]] = None
    ui_preferences: Optional[Dict[str, Any]] = None
    role: Optional[str] = None
    has_password: Optional[bool] = None
    avatar_url: Optional[str] = None
    is_verified: Optional[bool] = None


class RegisterUserResponse(UserResponse):
    """Response for POST /register: user profile plus pending-approval notice."""

    message: str = Field(
        default=(
            "Registration successful. Verify your email. "
            "Your account is pending admin approval before you can sign in."
        )
    )


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    current_password: Optional[str] = None
    timezone: Optional[str] = None
    currency_preference: Optional[str] = None
    notification_preferences: Optional[Dict[str, Any]] = None
    ui_preferences: Optional[Dict[str, Any]] = None


class ChangePasswordRequest(BaseModel):
    current_password: Optional[str] = None
    new_password: str


class InviteAcceptRequest(BaseModel):
    token: str
    username: str
    password: str
    full_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_token(token: str) -> Optional[str]:
    """Deprecated: use dependencies.get_current_user instead."""
    return None


def _find_active_invite_for_email(db: Session, email: str) -> Optional[UserInvite]:
    """Pending, non-expired invite for this email (not yet accepted)."""
    now = datetime.now(timezone.utc)
    return (
        db.query(UserInvite)
        .filter(
            UserInvite.email == email,
            UserInvite.accepted_at.is_(None),
            UserInvite.expires_at >= now,
        )
        .first()
    )


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    normalized_email = email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()
    if not user:
        logger.warning("Login failed: user not found (email redacted)")
        return None
    if not user.password_hash:
        logger.warning("Login failed: user %s has no password set", user.id)
        return None
    if not verify_password(password, user.password_hash):
        logger.warning("Login failed: password mismatch for user %s", user.id)
        return None
    return user


def _issue_tokens(user: User, response: Optional[Response] = None) -> Dict[str, Any]:
    """Issue access + refresh token pair. Sets refresh as httpOnly cookie if response given."""
    family = str(uuid.uuid4())
    user.refresh_token_family = family

    access = create_access_token(
        claims={"sub": user.username, "role": getattr(user.role, "value", None)},
    )
    refresh = create_refresh_token(
        claims={"sub": user.username},
        family=family,
    )

    if response:
        response.set_cookie(
            key="refresh_token",
            value=refresh,
            httponly=True,
            secure=_is_secure_cookie(),
            samesite="lax",
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            path="/api/v1/auth",
        )

    return {
        "access_token": access,
        "token_type": "bearer",
        "role": getattr(user.role, "value", None),
    }


def _send_verification_email(email: str, token: str) -> None:
    """Send email verification link. Gracefully skips when RESEND_API_KEY is absent."""
    verify_url = f"{settings.FRONTEND_ORIGIN or 'http://localhost:3000'}/auth/verify-email?token={token}"

    if not settings.RESEND_API_KEY:
        logger.info("Email verification URL (no RESEND_API_KEY): %s", verify_url)
        return

    try:
        import resend

        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send(
            {
                "from": "AxiomFolio <noreply@axiomfolio.com>",
                "to": [email],
                "subject": "Verify your AxiomFolio email",
                "html": (
                    f"<p>Welcome to AxiomFolio! Click below to verify your email:</p>"
                    f'<p><a href="{verify_url}">Verify Email</a></p>'
                    f"<p>This link expires in 24 hours.</p>"
                ),
            }
        )
    except Exception as e:
        logger.warning("Failed to send verification email to %s: %s", email, e)


def _is_secure_cookie() -> bool:
    return settings.ENVIRONMENT != "development"


def _sign_oauth_state(max_age: int = 600) -> str:
    """Create a HMAC-signed OAuth state token for CSRF protection."""
    nonce = str(uuid.uuid4())
    ts = str(int(_time.time()))
    msg = f"{nonce}:{ts}"
    secret = getattr(settings, "SECRET_KEY", "fallback-secret-key-for-development")
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{nonce}:{ts}:{sig}"


def _verify_oauth_state(state: Optional[str], max_age: int = 600) -> bool:
    """Verify a HMAC-signed OAuth state token. Returns True if valid and not expired."""
    if not state:
        return False
    try:
        parts = state.split(":")
        if len(parts) != 3:
            return False
        nonce, ts, sig = parts
        msg = f"{nonce}:{ts}"
        secret = getattr(settings, "SECRET_KEY", "fallback-secret-key-for-development")
        expected = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected):
            return False
        if _time.time() - int(ts) > max_age:
            return False
        return True
    except Exception:
        return False


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------

@router.get("/google/login")
async def google_login(request: Request):
    """Redirect to Google's authorization endpoint."""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_REDIRECT_URI:
        raise HTTPException(status_code=400, detail="Google OAuth not configured")

    state = _sign_oauth_state()
    scope = "openid email profile"
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={scope}"
        f"&state={state}"
        f"&access_type=offline"
        f"&prompt=consent"
    )
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Handle Google OAuth callback: exchange code, find-or-create user, redirect with token."""
    if not _verify_oauth_state(state):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=400, detail="Google OAuth not configured")

    async with httpx.AsyncClient(timeout=15) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            logger.warning("Google token exchange failed: %s", token_resp.text)
            raise HTTPException(status_code=400, detail="Google token exchange failed")

        tokens = token_resp.json()
        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch Google user info")

        info = userinfo_resp.json()

    google_sub = info.get("sub")
    raw_email = info.get("email", "")
    if not google_sub or not raw_email:
        raise HTTPException(status_code=400, detail="Google did not return required user info (sub/email)")
    email = raw_email.strip().lower()
    given_name = info.get("given_name", "")
    family_name = info.get("family_name", "")
    picture = info.get("picture")

    user = (
        db.query(User)
        .filter(User.oauth_provider == "google", User.oauth_id == google_sub)
        .first()
    )

    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.oauth_provider = "google"
            user.oauth_id = google_sub
        else:
            username = email.split("@")[0]
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                username = f"{username}_{google_sub[:6]}"

            active_invite = _find_active_invite_for_email(db, email)
            role = UserRole.ANALYST
            if active_invite is not None:
                role = (
                    active_invite.role
                    if isinstance(active_invite.role, UserRole)
                    else UserRole.ANALYST
                )

            user = User(
                email=email,
                username=username,
                oauth_provider="google",
                oauth_id=google_sub,
                first_name=given_name,
                last_name=family_name,
                is_active=True,
                is_verified=True,
                is_approved=active_invite is not None,
                role=role,
            )
            db.add(user)
            if active_invite is not None:
                active_invite.accepted_at = datetime.now(timezone.utc)

    user.avatar_url = picture
    user.is_verified = True

    family = str(uuid.uuid4())
    user.refresh_token_family = family
    db.commit()

    access = create_access_token(
        claims={"sub": user.username, "role": getattr(user.role, "value", None)},
    )
    refresh = create_refresh_token(claims={"sub": user.username}, family=family)

    frontend = settings.FRONTEND_ORIGIN or "http://localhost:3000"
    redirect_url = f"{frontend}/auth/callback#token={access}"

    resp = RedirectResponse(url=redirect_url, status_code=302)
    resp.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        secure=_is_secure_cookie(),
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )
    return resp


# ---------------------------------------------------------------------------
# Apple Sign-In
# ---------------------------------------------------------------------------

def _build_apple_client_secret() -> str:
    """Build a short-lived JWT client secret signed with Apple's ES256 private key.

    Apple requires the client_secret to be a JWT containing:
    iss=team_id, sub=client_id, aud=https://appleid.apple.com, iat, exp (max 6mo).
    """
    import time
    now = int(time.time())
    headers = {"kid": settings.APPLE_KEY_ID, "alg": "ES256"}
    payload = {
        "iss": settings.APPLE_TEAM_ID,
        "iat": now,
        "exp": now + 86400 * 180,
        "aud": "https://appleid.apple.com",
        "sub": settings.APPLE_CLIENT_ID,
    }
    return jwt_lib.encode(payload, settings.APPLE_PRIVATE_KEY, algorithm="ES256", headers=headers)


def _decode_apple_id_token(id_token: str) -> Dict[str, Any]:
    """Decode and verify Apple's id_token against their public JWKS."""
    jwks_resp = httpx.get("https://appleid.apple.com/auth/keys", timeout=10)
    jwks_resp.raise_for_status()
    apple_keys = jwks_resp.json()["keys"]

    unverified_header = jwt_lib.get_unverified_header(id_token)
    kid = unverified_header.get("kid")

    key_data = next((k for k in apple_keys if k["kid"] == kid), None)
    if not key_data:
        raise HTTPException(status_code=400, detail="Apple id_token key not found in JWKS")

    from jwt.algorithms import RSAAlgorithm
    public_key = RSAAlgorithm.from_jwk(key_data)

    return jwt_lib.decode(
        id_token,
        public_key,
        algorithms=["RS256"],
        audience=settings.APPLE_CLIENT_ID,
        issuer="https://appleid.apple.com",
    )


@router.get("/apple/login")
async def apple_login():
    """Redirect to Apple's authorization endpoint."""
    if not settings.APPLE_CLIENT_ID or not settings.APPLE_REDIRECT_URI:
        raise HTTPException(status_code=400, detail="Apple Sign-In not configured")

    state = _sign_oauth_state()
    auth_url = (
        "https://appleid.apple.com/auth/authorize"
        f"?client_id={settings.APPLE_CLIENT_ID}"
        f"&redirect_uri={settings.APPLE_REDIRECT_URI}"
        f"&response_type=code id_token"
        f"&response_mode=form_post"
        f"&scope=name email"
        f"&state={state}"
    )
    return RedirectResponse(url=auth_url)


@router.post("/apple/callback")
async def apple_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    """Handle Apple Sign-In callback (form POST with code + id_token)."""
    if not settings.APPLE_CLIENT_ID or not settings.APPLE_PRIVATE_KEY:
        raise HTTPException(status_code=400, detail="Apple Sign-In not configured")

    form = await request.form()
    state_value = form.get("state")
    if not _verify_oauth_state(str(state_value) if state_value else None):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    id_token_raw = form.get("id_token")
    user_json = form.get("user")

    if not id_token_raw:
        raise HTTPException(status_code=400, detail="Missing id_token from Apple")

    try:
        claims = _decode_apple_id_token(str(id_token_raw))
    except Exception as e:
        logger.warning("Apple id_token verification failed: %s", e)
        raise HTTPException(status_code=400, detail="Invalid Apple id_token")

    apple_sub = claims.get("sub")
    email = claims.get("email", "")
    if not apple_sub:
        raise HTTPException(status_code=400, detail="Apple id_token missing subject identifier")

    first_name = ""
    last_name = ""
    if user_json:
        try:
            import json
            user_data = json.loads(str(user_json))
            name = user_data.get("name", {})
            first_name = name.get("firstName", "")
            last_name = name.get("lastName", "")
        except Exception:
            pass

    user = (
        db.query(User)
        .filter(User.oauth_provider == "apple", User.oauth_id == apple_sub)
        .first()
    )

    if not user:
        user = db.query(User).filter(User.email == email).first() if email else None
        if user:
            user.oauth_provider = "apple"
            user.oauth_id = apple_sub
        else:
            username = email.split("@")[0] if email else f"apple_{apple_sub[:8]}"
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                username = f"{username}_{apple_sub[:6]}"

            active_invite = _find_active_invite_for_email(db, email)
            role = UserRole.ANALYST
            if active_invite is not None:
                role = (
                    active_invite.role
                    if isinstance(active_invite.role, UserRole)
                    else UserRole.ANALYST
                )

            user = User(
                email=email or f"{apple_sub}@privaterelay.appleid.com",
                username=username,
                oauth_provider="apple",
                oauth_id=apple_sub,
                first_name=first_name or None,
                last_name=last_name or None,
                is_active=True,
                is_verified=True,
                is_approved=active_invite is not None,
                role=role,
            )
            db.add(user)
            if active_invite is not None:
                active_invite.accepted_at = datetime.now(timezone.utc)

    if first_name and not user.first_name:
        user.first_name = first_name
    if last_name and not user.last_name:
        user.last_name = last_name

    user.is_verified = True

    family = str(uuid.uuid4())
    user.refresh_token_family = family
    db.commit()

    access = create_access_token(
        claims={"sub": user.username, "role": getattr(user.role, "value", None)},
    )
    refresh = create_refresh_token(claims={"sub": user.username}, family=family)

    frontend = settings.FRONTEND_ORIGIN or "http://localhost:3000"
    redirect_url = f"{frontend}/auth/callback#token={access}"

    resp = RedirectResponse(url=redirect_url, status_code=302)
    resp.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        secure=_is_secure_cookie(),
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )
    return resp


# ---------------------------------------------------------------------------
# Schwab OAuth scaffolding
# ---------------------------------------------------------------------------

@router.get("/schwab/login")
async def schwab_login():
    if not settings.SCHWAB_CLIENT_ID or not settings.SCHWAB_REDIRECT_URI:
        raise HTTPException(status_code=400, detail="Schwab OAuth not configured")
    auth_url = (
        "https://api.schwabapi.com/v1/oauth/authorize?response_type=code"
        f"&client_id={settings.SCHWAB_CLIENT_ID}"
        f"&redirect_uri={settings.SCHWAB_REDIRECT_URI}"
        "&scope=read,trade"
    )
    return RedirectResponse(url=auth_url)


@router.get("/schwab/callback")
async def schwab_callback(code: str):
    if (
        not settings.SCHWAB_CLIENT_ID
        or not settings.SCHWAB_CLIENT_SECRET
        or not settings.SCHWAB_REDIRECT_URI
    ):
        raise HTTPException(status_code=400, detail="Schwab OAuth not configured")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            token = await client.post(
                "https://api.schwabapi.com/v1/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.SCHWAB_REDIRECT_URI,
                    "client_id": settings.SCHWAB_CLIENT_ID,
                    "client_secret": settings.SCHWAB_CLIENT_SECRET,
                },
            )
            if token.status_code >= 400:
                raise HTTPException(
                    status_code=token.status_code, detail="Schwab token exchange failed"
                )
            return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Registration + Email Verification
# ---------------------------------------------------------------------------

@router.post("/register", response_model=RegisterUserResponse)
async def register_user(
    user_data: UserCreate, response: Response, db: Session = Depends(get_db)
) -> RegisterUserResponse:
    if not user_data.password or len(user_data.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )

    normalized_email = user_data.email.strip().lower()
    existing_user = (
        db.query(User)
        .filter((User.username == user_data.username) | (User.email == normalized_email))
        .first()
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        )

    active_invite = _find_active_invite_for_email(db, normalized_email)
    has_invite = active_invite is not None

    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        username=user_data.username,
        email=normalized_email,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        role=active_invite.role if has_invite and isinstance(active_invite.role, UserRole) else UserRole.VIEWER,
        is_active=True,
        is_verified=False,
        is_approved=has_invite,
    )
    db.add(db_user)

    if has_invite:
        active_invite.accepted_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(db_user)

    verify_token_str = create_access_token(
        claims={"sub": db_user.username, "purpose": "verify_email"},
        expires=timedelta(hours=24),
    )
    _send_verification_email(db_user.email, verify_token_str)

    logger.info("New user registered: %s (invite=%s)", user_data.username, has_invite)
    resp = RegisterUserResponse.model_validate(db_user)
    resp.role = getattr(db_user.role, "value", None)
    resp.has_password = bool(db_user.password_hash)
    if has_invite:
        resp.message = "Registration successful. Verify your email to sign in."
    return resp


@router.get("/verify-email")
async def verify_email(token: str = Query(...), db: Session = Depends(get_db)):
    """Verify a user's email address via signed token."""
    try:
        payload = decode_token(token, expected_type=None)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    if payload.get("purpose") != "verify_email":
        raise HTTPException(status_code=400, detail="Invalid token purpose")

    username = payload.get("sub")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_verified = True
    db.commit()

    frontend = settings.FRONTEND_ORIGIN or "http://localhost:3000"
    return RedirectResponse(url=f"{frontend}/login?verified=true", status_code=302)


@router.post("/resend-verification")
async def resend_verification(current_user: User = Depends(get_current_user)):
    """Resend the email verification link for the current user."""
    if current_user.is_verified:
        return {"message": "Email already verified"}

    verify_token_str = create_access_token(
        claims={"sub": current_user.username, "purpose": "verify_email"},
        expires=timedelta(hours=24),
    )
    _send_verification_email(current_user.email, verify_token_str)
    return {"message": "Verification email sent"}


# ---------------------------------------------------------------------------
# Invite flow
# ---------------------------------------------------------------------------

@router.get("/invite/{token}")
async def get_invite(token: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    invite = db.query(UserInvite).filter(UserInvite.token == token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.accepted_at is not None:
        raise HTTPException(status_code=409, detail="Invite already used")
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Invite expired")
    return {
        "email": invite.email,
        "role": invite.role.value,
        "expires_at": invite.expires_at.isoformat(),
    }


@router.post("/invite/accept", response_model=UserResponse)
async def accept_invite(
    payload: InviteAcceptRequest,
    db: Session = Depends(get_db),
) -> UserResponse:
    invite = db.query(UserInvite).filter(UserInvite.token == payload.token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.accepted_at is not None:
        raise HTTPException(status_code=409, detail="Invite already used")
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Invite expired")

    normalized_invite_email = invite.email.strip().lower()
    existing_user = (
        db.query(User)
        .filter((User.username == payload.username) | (User.email == normalized_invite_email))
        .first()
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        )

    if not payload.password or len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )

    db_user = User(
        username=payload.username,
        email=normalized_invite_email,
        password_hash=get_password_hash(payload.password),
        full_name=payload.full_name,
        role=invite.role if isinstance(invite.role, UserRole) else UserRole.VIEWER,
        is_active=True,
        is_verified=True,
        is_approved=True,
    )
    db.add(db_user)
    invite.accepted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_user)
    resp = UserResponse.model_validate(db_user)
    resp.role = getattr(db_user.role, "value", None)
    resp.has_password = bool(db_user.password_hash)
    return resp


# ---------------------------------------------------------------------------
# Login / Refresh / Logout
# ---------------------------------------------------------------------------

@router.post("/login", response_model=Token)
async def login_user(
    user_data: UserLogin, response: Response, db: Session = Depends(get_db)
) -> Token:
    user = authenticate_user(db, user_data.email, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    if user.password_hash and not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before signing in",
        )

    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending admin approval",
        )

    user.last_login = datetime.now(timezone.utc)
    result = _issue_tokens(user, response)
    db.commit()
    logger.info("User logged in: %s", user.username)
    return result


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    request: Request, response: Response, db: Session = Depends(get_db)
) -> Token:
    """Exchange a valid refresh token (httpOnly cookie) for a new access token."""
    refresh_cookie = request.cookies.get("refresh_token")
    if not refresh_cookie:
        raise HTTPException(status_code=401, detail="No refresh token")

    try:
        payload = decode_token(refresh_cookie, expected_type="refresh")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    username = payload.get("sub")
    family = payload.get("family")
    user = db.query(User).filter(User.username == username).first()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    if user.refresh_token_family != family:
        user.refresh_token_family = None
        db.commit()
        logger.warning("Refresh token family mismatch for user %s — possible token reuse", user.id)
        raise HTTPException(status_code=401, detail="Token family revoked")

    result = _issue_tokens(user, response)
    db.commit()
    return result


@router.post("/logout")
async def logout_user(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.refresh_token_family = None
    db.commit()
    response.delete_cookie("refresh_token", path="/api/v1/auth")
    logger.info("User logged out: %s", current_user.username)
    return {"message": "Successfully logged out"}


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: User = Depends(get_current_user)) -> UserResponse:
    resp = UserResponse.model_validate(user)
    resp.role = getattr(user.role, "value", None)
    resp.has_password = bool(user.password_hash)
    return resp


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name

    if user_update.email is not None and user_update.email != current_user.email:
        if current_user.password_hash:
            if not user_update.current_password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="current_password required to update email",
                )
            if not verify_password(user_update.current_password, current_user.password_hash or ""):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Incorrect current password",
                )
        existing = (
            db.query(User)
            .filter(User.email == str(user_update.email), User.id != current_user.id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use",
            )
        current_user.email = str(user_update.email)

    if user_update.timezone is not None:
        current_user.timezone = user_update.timezone

    if user_update.currency_preference is not None:
        cur = str(user_update.currency_preference).upper().strip()
        if len(cur) != 3 or not cur.isalpha():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="currency_preference must be a 3-letter currency code (e.g. USD)",
            )
        current_user.currency_preference = cur

    if user_update.notification_preferences is not None:
        if not isinstance(user_update.notification_preferences, dict):
            raise HTTPException(status_code=400, detail="notification_preferences must be an object")
        current_user.notification_preferences = user_update.notification_preferences

    if user_update.ui_preferences is not None:
        if not isinstance(user_update.ui_preferences, dict):
            raise HTTPException(status_code=400, detail="ui_preferences must be an object")
        merged = dict(current_user.ui_preferences or {})
        merged.update(user_update.ui_preferences)
        cm = merged.get("color_mode_preference")
        if cm is not None and cm not in ("system", "light", "dark"):
            raise HTTPException(status_code=400, detail="ui_preferences.color_mode_preference must be system|light|dark")
        td = merged.get("table_density")
        if td is not None and td not in ("comfortable", "compact"):
            raise HTTPException(status_code=400, detail="ui_preferences.table_density must be comfortable|compact")
        current_user.ui_preferences = merged

    db.commit()
    db.refresh(current_user)
    logger.info("User updated: %s", current_user.username)

    resp = UserResponse.model_validate(current_user)
    resp.role = getattr(current_user.role, "value", None)
    resp.has_password = bool(current_user.password_hash)
    return resp


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    new_password = payload.new_password
    if not new_password or len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters",
        )

    if current_user.password_hash:
        if not payload.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="current_password required",
            )
        if not verify_password(payload.current_password, current_user.password_hash or ""):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password"
            )

    current_user.password_hash = get_password_hash(new_password)
    db.commit()
    logger.info("Password changed for user: %s", current_user.username)
    return {"message": "Password updated successfully"}


@router.get("/health")
async def auth_health_check():
    return {
        "status": "healthy",
        "service": "authentication",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
