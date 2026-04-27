
import pytest

from app.config import settings
from app.models.episode import Episode


@pytest.mark.asyncio
async def test_learning_summary_shape(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "test-learning-secret")
    monkeypatch.setattr(settings, "BRAIN_LEARNING_DASHBOARD_ENABLED", True)
    db_session.add_all(
        [
            Episode(
                organization_id="paperwork-labs",
                source="merged_pr",
                summary="Shipped observability",
                persona="agent-ops",
                metadata_={"tags": ["lesson_extracted"], "topic": "deploy"},
            ),
            Episode(
                organization_id="paperwork-labs",
                source="brain:slack",
                summary="Casual chat",
                persona="ea",
            ),
        ]
    )
    await db_session.commit()
    res = await client.get(
        "/api/v1/admin/brain/learning/summary",
        headers={"X-Brain-Secret": "test-learning-secret"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert {k for k in data} >= {
        "as_of",
        "window_days",
        "episodes_7d",
        "lessons_captured_7d",
        "lesson_rate_pct",
        "distinct_agents_7d",
        "top_topics",
        "top_agents",
    }
    assert data["episodes_7d"] >= 2 and data["lessons_captured_7d"] >= 1 and data["lesson_rate_pct"] > 0
