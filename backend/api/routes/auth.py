"""
AxiomFolio V1 - Authentication Routes
=====================================

User authentication, registration, and session management.
Includes JWT token handling and user profile management.
"""

from datetime import datetime, timedelta
import hashlib
from typing import Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, ConfigDict
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import logging

from backend.database import get_db
from backend.models.user import User, UserRole
from backend.models.user_invite import UserInvite
from backend.config import settings
from backend.api.security import create_access_token
from backend.api.dependencies import get_current_user
from fastapi.responses import RedirectResponse
import httpx

logger = logging.getLogger(__name__)

# Security setup
security = HTTPBearer()
# Prefer sha256_crypt for new hashes; keep bcrypt to verify legacy hashes
pwd_context = CryptContext(schemes=["sha256_crypt", "bcrypt"], deprecated="auto")

# JWT configuration
ACCESS_TOKEN_EXPIRE_MINUTES = 30

router = APIRouter()


# Schwab OAuth scaffolding
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
    # Exchange code for tokens (placeholder; real endpoints/params required)
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Pydantic models for request/response
class UserCreate(BaseModel):
    """User registration request."""

    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    """User login request."""

    username: str
    password: str


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str
    role: Optional[str] = None


class UserResponse(BaseModel):
    """User information response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime
    timezone: Optional[str] = None
    currency_preference: Optional[str] = None
    notification_preferences: Optional[Dict[str, Any]] = None
    ui_preferences: Optional[Dict[str, Any]] = None
    role: Optional[str] = None
    has_password: Optional[bool] = None


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


# Authentication helper functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def verify_token(token: str) -> Optional[str]:
    """Deprecated: use dependencies.get_current_user instead."""
    return None


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate a user with username and password."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        logger.warning("Login failed: user not found", extra={"username": username})
        return None
    if not user.password_hash:
        logger.warning("Login failed: user has no password set", extra={"user_id": user.id})
        return None
    if not verify_password(password, user.password_hash):
        logger.warning(
            "Login failed: password mismatch",
            extra={"user_id": user.id, "username": user.username},
        )
        return None
    return user


#


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency to get current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# Authentication routes
@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserCreate, db: Session = Depends(get_db)
) -> UserResponse:
    """
    Register a new user.
    Creates a new user account with hashed password.
    """
    # Check if user already exists
    existing_user = (
        db.query(User)
        .filter((User.username == user_data.username) | (User.email == user_data.email))
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        )

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        is_active=True,
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    logger.info(f"New user registered: {user_data.username}")

    return UserResponse.model_validate(db_user)


@router.get("/invite/{token}")
async def get_invite(token: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    invite = db.query(UserInvite).filter(UserInvite.token == token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.accepted_at is not None:
        raise HTTPException(status_code=409, detail="Invite already used")
    if invite.expires_at < datetime.utcnow():
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
    if invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Invite expired")

    existing_user = (
        db.query(User)
        .filter((User.username == payload.username) | (User.email == invite.email))
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
        email=invite.email,
        password_hash=get_password_hash(payload.password),
        full_name=payload.full_name,
        role=invite.role if isinstance(invite.role, UserRole) else UserRole.READONLY,
        is_active=True,
        is_verified=True,
    )
    db.add(db_user)
    invite.accepted_at = datetime.utcnow()
    db.commit()
    db.refresh(db_user)
    return UserResponse.model_validate(db_user)


@router.post("/login", response_model=Token)
async def login_user(user_data: UserLogin, db: Session = Depends(get_db)) -> Token:
    """
    Authenticate user and return JWT token.
    """
    user = authenticate_user(db, user_data.username, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        claims={"sub": user.username, "role": getattr(user.role, "value", None)},
        expires=access_token_expires,
    )

    logger.info(f"User logged in: {user.username}")

    return {"access_token": access_token, "token_type": "bearer", "role": getattr(user.role, "value", None)}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: User = Depends(get_current_user)) -> UserResponse:
    """
    Get current user information.
    Requires valid authentication token.
    """
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
    """
    Update current user information.
    Requires valid authentication token.
    """
    # full_name (property setter splits into first/last)
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name

    # email (unique + optionally require password confirmation)
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
        # Basic validation for known keys (allow additional keys for forward-compat)
        cm = merged.get("color_mode_preference")
        if cm is not None and cm not in ("system", "light", "dark"):
            raise HTTPException(status_code=400, detail="ui_preferences.color_mode_preference must be system|light|dark")
        td = merged.get("table_density")
        if td is not None and td not in ("comfortable", "compact"):
            raise HTTPException(status_code=400, detail="ui_preferences.table_density must be comfortable|compact")
        current_user.ui_preferences = merged

    db.commit()
    db.refresh(current_user)

    logger.info(f"User updated: {current_user.username}")

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
    """
    Change user password.
    Requires valid authentication token and current password.
    """
    new_password = payload.new_password
    if not new_password or len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters",
        )

    # Verify current password (if user already has one)
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

    # Update password
    current_user.password_hash = get_password_hash(new_password)
    db.commit()

    logger.info(f"Password changed for user: {current_user.username}")

    return {"message": "Password updated successfully"}


@router.post("/logout")
async def logout_user(current_user: User = Depends(get_current_user)):
    """
    Logout user (token invalidation would be handled client-side).
    """
    logger.info(f"User logged out: {current_user.username}")
    return {"message": "Successfully logged out"}


# Health check endpoint
@router.get("/health")
async def auth_health_check():
    """Health check for authentication service."""
    return {
        "status": "healthy",
        "service": "authentication",
        "timestamp": datetime.utcnow().isoformat(),
    }
