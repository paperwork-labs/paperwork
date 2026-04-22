"""BYOK anomaly counters: specific reasons must not also increment the generic bucket."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.models.entitlement import SubscriptionTier
from backend.models.user import User
from backend.services.agent import brain
from backend.services.agent.brain import AgentBrain


@pytest.fixture
def db_user_pro_byok() -> MagicMock:
    u = MagicMock(spec=User)
    u.id = 42
    u.llm_provider_key_encrypted = b"enc"
    return u


def test_host_not_allowlisted_only_increments_specific_reason(
    db_user_pro_byok: MagicMock,
) -> None:
    reasons: list[str] = []

    def _capture(_uid: int, reason: str, **kwargs) -> None:
        reasons.append(reason)

    db = MagicMock()
    db.query.return_value.filter.return_value.one_or_none.return_value = db_user_pro_byok

    with (
        patch.object(brain, "BYOK_ALLOWED_HOSTS", frozenset()),
        patch.object(brain.settings, "OPENAI_API_KEY", "sk-platform"),
        patch.object(
            brain.EntitlementService,
            "effective_tier",
            return_value=SubscriptionTier.PRO,
        ),
        patch.object(
            brain.credential_vault,
            "decrypt_dict",
            return_value={"provider": "openai", "api_key": "sk-test"},
        ),
        patch.object(brain, "_record_byok_fallback", side_effect=_capture),
    ):
        b = AgentBrain(db, user_id=42)
        url, key = b._resolve_llm_target()

    assert url == brain.OPENAI_API_URL
    assert key == "sk-platform"
    assert reasons == ["host_not_allowlisted"]
