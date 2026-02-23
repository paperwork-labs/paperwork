"""
AxiomFolio V1 - API Dependencies
Common dependencies for API endpoints.
"""

from fastapi import Depends, HTTPException, status, Security, Request, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import logging
from typing import Optional, List, Literal

from backend.database import get_db
from backend.models.user import User
from backend.models.user import UserRole
from backend.api.security import decode_token
from backend.services.app_settings_service import get_or_create_app_settings

logger = logging.getLogger(__name__)

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency to get current authenticated user.
    Used by all protected endpoints.
    """
    try:
        token = credentials.credentials
        payload = decode_token(token)
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
        user = db.query(User).filter(User.username == username).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is disabled",
            )

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_portfolio_user(
    user_id: Optional[int] = Query(None, description="User ID (optional)"),
    db: Session = Depends(get_db),
) -> User:
    """Resolve a user for portfolio endpoints.

    Accepts an optional ``user_id`` query parameter.  When omitted, falls back
    to the first user in the database (dev convenience).  This will be replaced
    by ``get_current_user`` once all portfolio routes require auth tokens.
    """
    if user_id is None:
        user = db.query(User).first()
    else:
        user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to ensure current user has admin privileges.
    """
    from backend.models.user import UserRole

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )

    return current_user


def require_roles(roles: List[UserRole]):
    """
    Factory dependency to enforce one of the allowed roles on an endpoint/router.
    Usage:
      router = APIRouter(dependencies=[Depends(require_roles([UserRole.ADMIN]))])
    """
    async def _dep(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role"
            )
        return current_user
    return _dep


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(optional_security),
    db: Session = Depends(get_db),
):
    """Return None if no credentials provided; otherwise validate like get_current_user."""
    if not credentials:
        return None
    try:
        token = credentials.credentials
        payload = decode_token(token)
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
        user = db.query(User).filter(User.username == username).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user"
            )
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Optional auth error: {e}")
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


SectionName = Literal["market", "portfolio", "strategy", "other"]


def _section_from_path(path: str) -> SectionName:
    if path.startswith("/api/v1/portfolio") or path.startswith("/api/v1/accounts"):
        return "portfolio"
    if path.startswith("/api/v1/strategies"):
        return "strategy"
    if path.startswith("/api/v1/market-data"):
        return "market"
    return "other"


def _non_admin_section_decision(section: SectionName, app_settings) -> tuple[bool, Optional[str]]:
    """
    Centralized release-policy decision for non-admin users.

    Policy:
    - Market: available to all authenticated users.
    - Portfolio: requires market_only_mode=false and portfolio_enabled=true.
    - Strategy: requires market_only_mode=false and strategy_enabled=true.
    - Other sections: unaffected by these release flags.
    """
    if section == "market":
        return True, None

    if section in {"portfolio", "strategy"} and bool(app_settings.market_only_mode):
        return False, "Market-only mode: access restricted"

    if section == "portfolio" and not bool(app_settings.portfolio_enabled):
        return False, "Portfolio section is not enabled"

    if section == "strategy" and not bool(app_settings.strategy_enabled):
        return False, "Strategy section is not enabled"

    return True, None


def evaluate_release_access(
    section: SectionName, current_user: Optional[User], app_settings=None
) -> tuple[bool, Optional[str]]:
    """
    Evaluate rollout policy for a section with role-aware rules.

    Notes:
    - Unauthenticated access is left to route-level auth dependencies.
    - Market access is allowed for any authenticated user.
    - Portfolio/Strategy require app_settings for non-admin decisions.
    """
    if current_user is None:
        return False, "Authentication required"
    if current_user.role == UserRole.ADMIN:
        return True, None
    if section == "market":
        return True, None
    if section == "other":
        return True, None
    if app_settings is None:
        return False, "App settings required for section policy"
    return _non_admin_section_decision(section, app_settings)


def market_visibility_scope() -> str:
    # Release policy source of truth: market is open to authenticated users.
    return "all_authenticated"


def market_exposed_to_all() -> bool:
    # Backward-compatible metadata flag used by frontend.
    return True


async def require_non_market_access(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Block non-admin access when market-only mode is enabled.

    When market-only mode is disabled, use per-section release flags for
    non-admin users:
    - portfolio/account APIs -> portfolio_enabled
    - strategies APIs -> strategy_enabled
    """
    # Keep legacy/public behavior for endpoints that do not require auth.
    # Route-specific deps (e.g. get_current_user/get_admin_user) still enforce auth.
    if current_user is None:
        return None

    # Admin should never be blocked by release toggles, and this avoids coupling
    # admin route availability to app_settings migration timing.
    if current_user.role == UserRole.ADMIN:
        return current_user

    section = _section_from_path(request.url.path or "")
    app_settings = None
    if section in {"portfolio", "strategy"}:
        try:
            app_settings = get_or_create_app_settings(db)
        except Exception as e:
            logger.error(f"❌ App settings unavailable for section policy: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="App settings are unavailable; retry shortly",
            )
    allowed, reason = evaluate_release_access(section, current_user, app_settings)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason or "Access denied")
    return current_user
