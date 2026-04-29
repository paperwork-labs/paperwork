"""Tests for persona admin surface helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import persona_surface as ps


def test_aggregate_persona_cost_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ps, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(ps, "_COST_FILE", tmp_path / "persona_cost.json")
    out = ps.aggregate_persona_cost(window="7d")
    assert out["has_file"] is False
    assert out["personas"] == []


def test_aggregate_persona_cost_windows_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ps, "_DATA_DIR", tmp_path)
    cost_file = tmp_path / "persona_cost.json"
    monkeypatch.setattr(ps, "_COST_FILE", cost_file)
    cost_file.write_text(
        json.dumps(
            {
                "windows": {
                    "7d": [
                        {"persona": "ea", "tokens_in": 10, "tokens_out": 20, "usd": 0.5},
                        {"persona": "ea", "tokens_in": 5, "tokens_out": 5, "usd": 0.25},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    out = ps.aggregate_persona_cost(window="7d")
    assert out["has_file"] is True
    assert len(out["personas"]) == 1
    row = out["personas"][0]
    assert row["persona"] == "ea"
    assert row["tokens_in"] == 15
    assert row["tokens_out"] == 25
    assert row["usd"] == 0.75


def test_load_routing_derived(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ps, "_ROUTING_FILE", Path("/nonexistent/persona_routing.json"))
    data = ps.load_routing_rules()
    assert data["derived_from_code"] is True
    assert data["default_persona"] == "ea"
    assert "engineering" in data["content_keyword_to_persona"]
