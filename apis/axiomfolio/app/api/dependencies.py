"""
AxiomFolio V1 - API Dependencies
Common dependencies for API endpoints.
"""

import secrets

from fastapi import Depends, HTTPException, status, Security, Request
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import logging
from typing import Optional, List, Literal

from app.database import get_db
from app.models.user import User
from app.models.user import UserRole
from app.config import settings
from app.services.auth.clerk_user import (
    get_or_create_user_for_clerk,
    verify_bearer_clerk_token,
)
from paperwork_auth.jwks import ClerkAuthError

logger = logging.getLogger(__name__)

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)

_brain_api_key_header = APIKeyHeader(name="X-Brain-Api-Key", auto_error=False)


async def verify_brain_api_key(
    api_key: Optional[str] = Security(_brain_api_key_header),
) -> None:
    """Validate Brain tool API requests (machine-to-machine). Header: X-Brain-Api-Key."""
    expected = settings.BRAIN_API_KEY
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Brain API is not configured (BRAIN_API_KEY)",
        )
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Brain API key",
        )
    provided = api_key.encode("utf-8")
    expected_b = expected.encode("utf-8")
    if len(provided) != len(expected_b) or not secrets.compare_digest(
        provided, expected_b
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Brain API key",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency to get current authenticated user (Clerk session JWT).
    Used by all protected endpoints.
    """
    if not (settings.CLERK_JWT_ISSUER or "").strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Clerk authentication is not configured (CLERK_JWT_ISSUER)",
        )
    try:
        token = credentials.credentials
        try:
            claims = verify_bearer_clerk_token(token)
        except ClerkAuthError as exc:
            logger.warning("Clerk JWT rejected: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        try:
            user = get_or_create_user_for_clerk(db, claims)
        except ClerkAuthError as exc:
            logger.warning("Clerk user resolution failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is disabled",
            )

        if not user.is_approved:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account pending admin approval",
            )

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Authentication error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to ensure current user has operator (platform admin) privileges.
    """
    if current_user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )

    return current_user


def require_feature(feature_key: str):
    """Dependency factory: caller must hold an entitlement that unlocks
    ``feature_key`` (per ``app/services/billing/feature_catalog.py``).

    Raises 402 Payment Required (rather than 403 Forbidden) when the user
    is authenticated but missing tier — that lets the frontend distinguish
    "log in" from "upgrade" without a string sniff on the error body, and
    is consistent with how Stripe-gated APIs across the industry signal
    paywalls.
    """
    # Local import keeps app/api/dependencies.py free of a hard import
    # on the billing package at module load (the billing package imports
    # the User model, etc.).
    from app.services.billing.entitlement_service import EntitlementService

    async def check_feature(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        decision = EntitlementService.check(db, user, feature_key)
        if decision.allowed:
            return user
        raise HTTPException(
            status_code=402,
            detail={
                "error": "tier_required",
                "feature": decision.feature.key,
                "feature_title": decision.feature.title,
                "current_tier": decision.current_tier.value,
                "required_tier": decision.required_tier.value,
                "message": decision.reason,
            },
        )

    return check_feature


def require_role(*allowed_roles: UserRole):
    """Dependency factory: current user must have one of the allowed roles."""

    allowed_values = [r.value for r in allowed_roles]

    async def check_role(user: User = Depends(get_current_user)) -> User:
        role_val = user.role.value if isinstance(user.role, UserRole) else str(user.role)
        if role_val not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(r.value for r in allowed_roles)}",
            )
        return user

    return check_role


def require_roles(roles: List[UserRole]):
    """
    Factory dependency to enforce one of the allowed roles on an endpoint/router.
    Usage:
      router = APIRouter(dependencies=[Depends(require_roles([UserRole.OWNER]))])
    """
    allowed_values = {r.value for r in roles}

    async def _dep(current_user: User = Depends(get_current_user)) -> User:
        cur = (
            current_user.role.value
            if isinstance(current_user.role, UserRole)
            else str(current_user.role)
        )
        if cur not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role"
            )
        return current_user

    return _dep


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(optional_security),
    db: Session = Depends(get_db),
):
    """Return None if no credentials provided; otherwise validate Clerk JWT like get_current_user."""
    if not credentials:
        return None
    if not (settings.CLERK_JWT_ISSUER or "").strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Clerk authentication is not configured (CLERK_JWT_ISSUER)",
        )
    try:
        token = credentials.credentials
        try:
            claims = verify_bearer_clerk_token(token)
        except ClerkAuthError as exc:
            logger.warning("Optional Clerk JWT rejected: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            ) from exc
        try:
            user = get_or_create_user_for_clerk(db, claims)
        except ClerkAuthError as exc:
            logger.warning("Optional Clerk user resolution failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            ) from exc
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user"
            )
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Optional auth error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )


async def get_market_data_viewer(
    optional_user: Optional[User] = Depends(get_optional_user),
) -> User:
    """
    Return a user allowed to view market-data sections.
    Market is currently open to all authenticated users.
    """
    allowed, reason = evaluate_release_access("market", optional_user)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=reason or "Authentication required for market data visibility",
        )
    return optional_user


SectionName = Literal["market", "portfolio", "other"]


def _section_from_path(path: str) -> SectionName:
    if path.startswith("/api/v1/portfolio") or path.startswith("/api/v1/accounts"):
        return "portfolio"
    if path.startswith("/api/v1/market-data"):
        return "market"
    return "other"


def evaluate_release_access(
    section: SectionName, current_user: Optional[User]
) -> tuple[bool, Optional[str]]:
    """
    Evaluate rollout policy for a section with role-aware rules.

    Notes:
    - Unauthenticated access is left to route-level auth dependencies.
    - Market, portfolio, and other authenticated sections are available to
      all approved users (no global feature flags).
    """
    if current_user is None:
        return False, "Authentication required"
    if current_user.role == UserRole.OWNER:
        return True, None
    if section in ("market", "portfolio", "other"):
        return True, None
    return True, None


def market_visibility_scope() -> str:
    # Release policy source of truth: market is open to authenticated users.
    return "all_authenticated"


def market_exposed_to_all() -> bool:
    # Backward-compatible metadata flag used by frontend.
    return True


async def require_non_market_access(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user),
) -> Optional[User]:
    """Enforce section rollout policy for optional-auth routes (portfolio vs market)."""
    if current_user is None:
        return None

    if current_user.role == UserRole.OWNER:
        return current_user

    section = _section_from_path(request.url.path or "")
    allowed, reason = evaluate_release_access(section, current_user)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason or "Access denied")
    return current_user
