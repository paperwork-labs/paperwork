from app.services.market.coverage_utils import compute_coverage_status


def test_coverage_status_ignores_5m_when_disabled():
    snap = {
        "symbols": 10,
        "tracked_count": 10,
        "daily": {
            "count": 10,
            "freshness": {"<=24h": 10, "24-48h": 0, ">48h": 0, "none": 0},
            "stale_48h": 0,
            "missing": 0,
            "stale": [],
        },
        "m5": {
            "count": 0,
            "freshness": {"<=24h": 0, "24-48h": 0, ">48h": 0, "none": 10},
            "stale": [],
        },
        "meta": {"backfill_5m_enabled": False},
    }
    status = compute_coverage_status(snap)
    assert status["label"] == "ok"
    assert "ignored" in str(status.get("thresholds", {}).get("m5_expectation", "")).lower()
