from datetime import datetime, timedelta, timezone
import jwt
import pytest
from backend.services.security.oauth_state import OAuthStateService
from backend.config import settings


def test_issue_and_validate_state():
    svc = OAuthStateService(secret=settings.SECRET_KEY)
    token = svc.issue_state(user_id=123, account_id=456, minutes_valid=5)
    data = svc.validate_state(token)
    assert data["uid"] == 123 and data["aid"] == 456 and data["sub"] == "oauth_state"


def test_expired_state_rejected():
    svc = OAuthStateService(secret=settings.SECRET_KEY)
    # Manually craft expired token
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "oauth_state",
        "uid": 1,
        "aid": 2,
        "iat": int((now - timedelta(minutes=10)).timestamp()),
        "nbf": int((now - timedelta(minutes=10)).timestamp()),
        "exp": int((now - timedelta(minutes=5)).timestamp()),
    }
    token = jwt.encode(payload, settings.SECRET_KEY.encode("utf-8"), algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        svc.validate_state(token)


