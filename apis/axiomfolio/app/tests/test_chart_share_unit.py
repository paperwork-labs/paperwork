"""Unit tests for chart share tokens and OG PNG rendering (no FastAPI app import)."""

import jwt
import pytest

pytestmark = pytest.mark.no_db

from app.config import settings
from app.services.share.chart_og_image import render_chart_og_png
from app.services.share.chart_share_token import (
    create_chart_share_token,
    decode_chart_share_token,
)


def test_decode_chart_share_token_round_trip():
    tok = create_chart_share_token(
        user_id=42,
        symbol="AAPL",
        period="1y",
        indicators=["emas", "stage"],
    )
    data = decode_chart_share_token(tok)
    assert data["symbol"] == "AAPL"
    assert data["period"] == "1y"
    assert data["scope"] == "chart-share"
    assert data["sub"] == "chart_share"
    assert "emas" in data["indicators"]


def test_oauth_state_jwt_rejected_for_chart_decode():
    bad = jwt.encode(
        {"sub": "oauth_state", "uid": 1, "aid": 1, "iat": 1, "exp": 9999999999},
        settings.SECRET_KEY.encode("utf-8"),
        algorithm="HS256",
    )
    with pytest.raises(ValueError):
        decode_chart_share_token(bad)


def test_render_og_png_produces_valid_png_header():
    png = render_chart_og_png(
        symbol="TEST",
        last_price=123.45,
        sparkline=list(range(100, 130)),
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 500
