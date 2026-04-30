"""Tests for WS-76 PR-26 — Bill service state machine (JSON store)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas.bill import BillCreate, BillUpdate


def _use_tmp_bills(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    path = tmp_path / "bills.json"
    path.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("BRAIN_BILLS_JSON", str(path))
    return path


def _svc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _use_tmp_bills(monkeypatch, tmp_path)
    import importlib

    import app.services.bills as svc

    importlib.reload(svc)
    return svc


def _sample_create(**kwargs) -> BillCreate:
    d = {
        "vendor_id": "vendor_acme",
        "due_date": "2026-05-15",
        "amount_usd": 125.5,
        "description": "Consulting",
        "attachments": [],
    }
    d.update(kwargs)
    return BillCreate(**d)


class TestStateMachineHappyPath:
    def test_pending_approve_pay(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        b = svc.create_bill(_sample_create())
        assert b.status == "pending"
        a = svc.approve_bill(b.id)
        assert a is not None
        assert a.status == "approved"
        p = svc.pay_bill(b.id)
        assert p is not None
        assert p.status == "paid"

    def test_pending_reject(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        b = svc.create_bill(_sample_create())
        r = svc.reject_bill(b.id)
        assert r is not None
        assert r.status == "rejected"

    def test_approved_reject(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        b = svc.create_bill(_sample_create())
        svc.approve_bill(b.id)
        r = svc.reject_bill(b.id)
        assert r is not None
        assert r.status == "rejected"


class TestInvalidTransitions:
    def test_pending_to_pay_rejected(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        b = svc.create_bill(_sample_create())
        with pytest.raises(ValueError, match="Cannot transition pending → paid"):
            svc.pay_bill(b.id)

    def test_paid_is_terminal(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        b = svc.create_bill(_sample_create())
        svc.approve_bill(b.id)
        svc.pay_bill(b.id)
        with pytest.raises(ValueError, match="Cannot transition paid → approved"):
            svc.approve_bill(b.id)
        with pytest.raises(ValueError, match="Cannot transition paid → rejected"):
            svc.reject_bill(b.id)

    def test_rejected_is_terminal(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        b = svc.create_bill(_sample_create())
        svc.reject_bill(b.id)
        with pytest.raises(ValueError, match="Cannot transition rejected → approved"):
            svc.approve_bill(b.id)

    def test_double_approve_rejected(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        b = svc.create_bill(_sample_create())
        svc.approve_bill(b.id)
        with pytest.raises(ValueError, match="Cannot transition approved → approved"):
            svc.approve_bill(b.id)


class TestCrud:
    def test_list_and_get(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        svc.create_bill(_sample_create(vendor_id="a"))
        svc.create_bill(_sample_create(vendor_id="b"))
        page = svc.list_bills()
        assert page.total == 2
        one = svc.get_bill(page.items[0].id)
        assert one is not None
        assert one.vendor_id in {"a", "b"}

    def test_filter_by_status(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        x = svc.create_bill(_sample_create())
        svc.approve_bill(x.id)
        pending_only = svc.list_bills(status="pending")
        assert pending_only.total == 0
        approved_only = svc.list_bills(status="approved")
        assert approved_only.total == 1

    def test_patch_and_delete(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        svc = _svc(monkeypatch, tmp_path)
        b = svc.create_bill(_sample_create())
        u = svc.update_bill(b.id, BillUpdate(description="Updated"))
        assert u is not None
        assert u.description == "Updated"
        assert svc.delete_bill(b.id) is True
        assert svc.get_bill(b.id) is None

    def test_persist_round_trip(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        path = _use_tmp_bills(monkeypatch, tmp_path)
        import importlib

        import app.services.bills as svc1

        importlib.reload(svc1)
        b = svc1.create_bill(_sample_create())
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["id"] == b.id

        import app.services.bills as svc2

        importlib.reload(svc2)
        got = svc2.get_bill(b.id)
        assert got is not None
        assert got.amount_usd == 125.5
