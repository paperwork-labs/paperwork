import pandas as pd

from app.services.market.indicator_engine import compute_weinstein_stage_from_daily


def _make_daily_from_weekly(weekly_closes: list[float]) -> pd.DataFrame:
    days = len(weekly_closes) * 5
    index = pd.date_range(end=pd.Timestamp("2026-01-02"), periods=days, freq="B")
    close = []
    for w_close in weekly_closes:
        close.extend([w_close] * 5)
    close = pd.Series(close, index=index, dtype=float)
    df = pd.DataFrame(
        {
            "Open": close,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": 1_000,
        }
    )
    return df.iloc[::-1]  # newest-first


def test_weinstein_stage_refines_to_2c():
    # 60 weeks of strong uptrend -> price well above 30W SMA.
    weekly_sym = [50 + 10 * i for i in range(60)]
    weekly_bm = [50 + 5 * i for i in range(60)]

    sym_daily = _make_daily_from_weekly(weekly_sym)
    bm_daily = _make_daily_from_weekly(weekly_bm)

    stage = compute_weinstein_stage_from_daily(sym_daily, bm_daily)
    assert stage["stage_label"] == "2C"
