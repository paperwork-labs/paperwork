import pytest

from backend.models.index_constituent import IndexConstituent

from backend.tasks.market import backfill as market_backfill_tasks


@pytest.mark.destructive
def test_refresh_index_constituents_records_counters(monkeypatch, db_session):
    # Monkeypatch service to return a small set deterministically
    from backend.services.market.market_data_service import index_universe

    async def fake_get_index_constituents(name: str):
        if name == "SP500":
            return ["AAPL", "MSFT"]
        if name == "NASDAQ100":
            return ["AAPL", "MSFT", "NVDA"]
        if name == "DOW30":
            return ["AAPL"]
        return []

    monkeypatch.setattr(index_universe, "get_index_constituents", fake_get_index_constituents)

    # Route SessionLocal inside task to our test session
    monkeypatch.setattr(market_backfill_tasks, "SessionLocal", lambda: db_session)
    # Clean existing
    db_session.query(IndexConstituent).delete()
    db_session.commit()

    res = market_backfill_tasks.constituents()
    assert res["status"] == "ok"
    idx = res["indices"]
    # Ensure keys present
    for k in ["SP500", "NASDAQ100", "DOW30"]:
        assert "fetched" in idx[k]
        assert "inserted" in idx[k]
        assert "inactivated" in idx[k]

    # Verify rows written
    count = db_session.query(IndexConstituent).count()
    assert count > 0



