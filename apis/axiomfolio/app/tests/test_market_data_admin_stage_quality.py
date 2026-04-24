from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.dependencies import get_admin_user
from app.models.market_data import JobRun, MarketSnapshot, MarketSnapshotHistory


client = TestClient(app, raise_server_exceptions=False)


def test_admin_stage_repair_requires_admin():
    resp = client.post("/api/v1/market-data/admin/stage/repair?days=120")
    assert resp.status_code in (401, 403)


def test_admin_stage_repair_payload(db_session):
    from app.database import get_db

    app.dependency_overrides[get_admin_user] = object
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        now = datetime.now(timezone.utc)
        db_session.add(
            MarketSnapshot(
                symbol="AAA",
                analysis_type="technical_snapshot",
                stage_label="2A",
                current_stage_days=3,
                previous_stage_label="1",
                previous_stage_days=2,
                as_of_timestamp=now,
                expiry_timestamp=now + timedelta(days=1),
            )
        )
        db_session.add(
            MarketSnapshot(
                symbol="BBB",
                analysis_type="technical_snapshot",
                stage_label="UNKNOWN",
                current_stage_days=None,
                previous_stage_label=None,
                previous_stage_days=None,
                as_of_timestamp=now - timedelta(days=200),
                expiry_timestamp=now + timedelta(days=1),
            )
        )
        for i, lbl in enumerate(["2A", "2A", "2B", "2B", "2B"]):
            db_session.add(
                MarketSnapshotHistory(
                    symbol="AAA",
                    analysis_type="technical_snapshot",
                    as_of_date=now - timedelta(days=5 - i),
                    stage_label=lbl,
                    current_stage_days=None,
                    previous_stage_label=None,
                    previous_stage_days=None,
                )
            )
        db_session.commit()

        repair = client.post("/api/v1/market-data/admin/stage/repair?days=120&symbol=AAA")
        assert repair.status_code == 200
        payload = repair.json()
        assert payload["target_symbol"] == "AAA"
        assert payload["touched_symbols"] >= 1
        assert payload["touched_rows"] >= 1

        # Ensure snapshot sync does not use UNKNOWN latest rows when snapshot
        # stage is known.
        now2 = datetime.now(timezone.utc)
        db_session.add(
            MarketSnapshot(
                symbol="CCC",
                analysis_type="technical_snapshot",
                stage_label="2B",
                current_stage_days=10,
                previous_stage_label="2A",
                previous_stage_days=3,
                as_of_timestamp=now2,
                expiry_timestamp=now2 + timedelta(days=1),
            )
        )
        db_session.add(
            MarketSnapshotHistory(
                symbol="CCC",
                analysis_type="technical_snapshot",
                as_of_date=now2 - timedelta(days=3),
                stage_label="2B",
                current_stage_days=7,
                previous_stage_label="2A",
                previous_stage_days=4,
            )
        )
        db_session.add(
            MarketSnapshotHistory(
                symbol="CCC",
                analysis_type="technical_snapshot",
                as_of_date=now2 - timedelta(days=2),
                stage_label="2B",
                current_stage_days=8,
                previous_stage_label="2A",
                previous_stage_days=4,
            )
        )
        db_session.add(
            MarketSnapshotHistory(
                symbol="CCC",
                analysis_type="technical_snapshot",
                as_of_date=now2 - timedelta(days=1),
                stage_label="UNKNOWN",
                current_stage_days=4,
                previous_stage_label=None,
                previous_stage_days=None,
            )
        )
        db_session.commit()

        repair2 = client.post("/api/v1/market-data/admin/stage/repair?days=120&symbol=CCC")
        assert repair2.status_code == 200
        ccc = (
            db_session.query(MarketSnapshot)
            .filter(
                MarketSnapshot.analysis_type == "technical_snapshot",
                MarketSnapshot.symbol == "CCC",
            )
            .first()
        )
        assert ccc is not None
        assert ccc.stage_label == "2B"
        assert ccc.current_stage_days == 2
        assert ccc.previous_stage_label is None
        assert ccc.previous_stage_days is None
    finally:
        app.dependency_overrides.pop(get_admin_user, None)
        app.dependency_overrides.pop(get_db, None)
