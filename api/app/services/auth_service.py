import secrets
import uuid

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import AuthProvider, User
from app.repositories.user import UserRepository
from app.schemas.auth import RegisterRequest
from app.utils.encryption import decrypt, encrypt
from app.utils.exceptions import ConflictError, UnauthorizedError
from app.utils.security import generate_session_token, hash_password, verify_password

SESSION_PREFIX = "session:"
CSRF_PREFIX = "csrf:"
SESSION_TTL = 7 * 24 * 60 * 60  # 7 days


async def register(db: AsyncSession, redis: Redis, data: RegisterRequest) -> tuple[User, str, str]:
    """Register a new user. Returns (user, session_token, csrf_token)."""
    repo = UserRepository(db)

    existing = await repo.get_by_email(data.email)
    if existing:
        raise ConflictError("An account with this email already exists")

    referral_code = secrets.token_urlsafe(8)

    user = await repo.create(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        full_name_encrypted=encrypt(data.full_name),
        referral_code=referral_code,
        auth_provider=AuthProvider.LOCAL,
        email_verified=False,
    )

    session_token = generate_session_token()
    csrf_token = secrets.token_urlsafe(32)

    await redis.setex(f"{SESSION_PREFIX}{session_token}", SESSION_TTL, str(user.id))
    await redis.setex(f"{CSRF_PREFIX}{session_token}", SESSION_TTL, csrf_token)

    return user, session_token, csrf_token


async def login(db: AsyncSession, redis: Redis, email: str, password: str) -> tuple[User, str, str]:
    """Authenticate user. Returns (user, session_token, csrf_token)."""
    repo = UserRepository(db)

    user = await repo.get_by_email(email)
    if not user or not user.password_hash:
        raise UnauthorizedError("Invalid email or password")

    if not verify_password(password, user.password_hash):
        raise UnauthorizedError("Invalid email or password")

    session_token = generate_session_token()
    csrf_token = secrets.token_urlsafe(32)

    await redis.setex(f"{SESSION_PREFIX}{session_token}", SESSION_TTL, str(user.id))
    await redis.setex(f"{CSRF_PREFIX}{session_token}", SESSION_TTL, csrf_token)

    return user, session_token, csrf_token


async def social_login(
    db: AsyncSession,
    redis: Redis,
    provider: AuthProvider,
    email: str,
    name: str | None,
    provider_id: str,
) -> tuple[User, str, str]:
    """Find or create a user from social login. Returns (user, session_token, csrf_token).

    Account linking: if a user already exists with this email (any provider),
    they can log in via any verified social provider. The original auth_provider
    is preserved but auth_provider_id is updated if empty.
    """
    repo = UserRepository(db)
    user = await repo.get_by_email(email)

    if user:
        if not user.auth_provider_id and provider_id:
            user.auth_provider_id = provider_id
            await db.flush()
            await db.refresh(user)
    else:
        referral_code = secrets.token_urlsafe(8)
        encrypted_name = encrypt(name) if name else None

        user = await repo.create(
            email=email,
            password_hash=None,
            full_name_encrypted=encrypted_name,
            referral_code=referral_code,
            auth_provider=provider,
            auth_provider_id=provider_id,
            email_verified=True,
        )

    session_token = generate_session_token()
    csrf_token = secrets.token_urlsafe(32)

    await redis.setex(f"{SESSION_PREFIX}{session_token}", SESSION_TTL, str(user.id))
    await redis.setex(f"{CSRF_PREFIX}{session_token}", SESSION_TTL, csrf_token)

    return user, session_token, csrf_token


async def logout(redis: Redis, session_token: str) -> None:
    """Destroy session and CSRF token."""
    await redis.delete(f"{SESSION_PREFIX}{session_token}")
    await redis.delete(f"{CSRF_PREFIX}{session_token}")


async def get_current_user(db: AsyncSession, redis: Redis, session_token: str) -> User:
    """Resolve session token to user. Raises UnauthorizedError if invalid."""
    user_id_str = await redis.get(f"{SESSION_PREFIX}{session_token}")
    if not user_id_str:
        raise UnauthorizedError("Session expired or invalid")

    repo = UserRepository(db)
    user = await repo.get_by_id(uuid.UUID(user_id_str))
    if not user:
        await redis.delete(f"{SESSION_PREFIX}{session_token}")
        raise UnauthorizedError("User not found")

    return user


async def delete_account(db: AsyncSession, redis: Redis, user: User, session_token: str) -> None:
    """Delete user and all data (CCPA). Clears session."""
    repo = UserRepository(db)
    await repo.delete_cascade(user)
    await redis.delete(f"{SESSION_PREFIX}{session_token}")
    await redis.delete(f"{CSRF_PREFIX}{session_token}")


async def get_csrf_token(redis: Redis, session_token: str) -> str | None:
    """Retrieve the CSRF token for a given session."""
    return await redis.get(f"{CSRF_PREFIX}{session_token}")


async def validate_csrf(redis: Redis, session_token: str, csrf_token: str) -> bool:
    """Check that the provided CSRF token matches the stored one."""
    stored = await redis.get(f"{CSRF_PREFIX}{session_token}")
    if not stored:
        return False
    return secrets.compare_digest(stored, csrf_token)


def user_to_response(user: User) -> dict:
    """Convert User model to a serializable dict."""
    full_name = None
    if user.full_name_encrypted:
        try:
            full_name = decrypt(user.full_name_encrypted)
        except ValueError:
            full_name = None

    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": full_name,
        "referral_code": user.referral_code,
        "auth_provider": user.auth_provider.value,
        "email_verified": user.email_verified,
        "role": user.role.value,
        "advisor_tier": user.advisor_tier.value,
        "created_at": user.created_at.isoformat(),
    }
