"""TastyTrade live executor tests.

Exercises :class:`backend.services.execution.tastytrade_executor.TastytradeExecutor`
against a mocked ``tastytrade`` SDK. The real SDK is installed in CI for other
unit tests (``tastytrade==12.3.2``); we still patch all network-facing calls.

Covered
-------
* preview_order happy path (equity)
* place_order happy path + broker order id round-trip
* cancel_order happy path
* get_order_status + fill aggregation
* session-refresh exercised (lock + SDK call)
* option symbol surfaces a clear error (no silent pass)
* SDK exception surfaces via ``OrderResult.error``
* non-integer order id on cancel/status fails closed
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.execution.broker_base import (
    ActionSide,
    IBOrderType,
    OrderRequest,
)

pytestmark = pytest.mark.no_db
from backend.services.execution.broker_router import create_default_router
from backend.services.execution.tastytrade_executor import (
    TastytradeExecutor,
    TastytradeExecutorError,
    _is_option_symbol,
    _lock_key_for_secret,
    _map_tt_status,
)


# --------------------------------------------------------------------- helpers


def _make_executor_with_session(
    session: Any, accounts: list[Any]
) -> TastytradeExecutor:
    """Return an executor whose ``_resolve_account`` is short-circuited so tests
    don't touch credentials/Redis/the real SDK at all."""

    ex = TastytradeExecutor()
    ex._session = session
    ex._accounts = accounts

    async def _fake_resolve(account_id: Any | None = None) -> tuple[Any, Any]:
        if account_id:
            for acct in accounts:
                if getattr(acct, "account_number", None) == account_id:
                    return session, acct
            raise TastytradeExecutorError(
                f"tastytrade account {account_id!r} not found on session"
            )
        return session, accounts[0]

    ex._resolve_account = _fake_resolve  # type: ignore[method-assign]
    return ex


def _stub_placed_order(
    order_id: int = 12345,
    status_value: str = "Live",
    account_number: str = "5WU12345",
    legs: Any = None,
) -> Any:
    return SimpleNamespace(
        id=order_id,
        status=SimpleNamespace(value=status_value),
        account_number=account_number,
        legs=legs or [],
    )


def _stub_placed_response(
    placed: Any,
    *,
    errors: list[Any] | None = None,
    warnings: list[Any] | None = None,
) -> Any:
    return SimpleNamespace(
        order=placed,
        errors=errors or [],
        warnings=warnings or [],
        buying_power_effect=SimpleNamespace(change_in_buying_power=Decimal("-1500")),
        fee_calculation=SimpleNamespace(commission=Decimal("0.65")),
    )


# --------------------------------------------------------------- router wiring


class TestBrokerRouterRegistration:
    """Sandbox is always registered; live (prod) is gated behind
    TASTYTRADE_ALLOW_LIVE so an accidental ``broker_type="tastytrade"``
    cannot route a real order until the flag is explicitly enabled."""

    def test_sandbox_always_registered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.config import settings
        monkeypatch.setattr(settings, "TASTYTRADE_ALLOW_LIVE", False, raising=False)

        router = create_default_router()
        assert "tastytrade_sandbox" in router.available_brokers
        executor = router.get("tastytrade_sandbox")
        assert isinstance(executor, TastytradeExecutor)
        assert executor.broker_name == "tastytrade"
        assert executor.is_paper_trading() is True

    def test_live_blocked_when_flag_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from backend.config import settings
        monkeypatch.setattr(settings, "TASTYTRADE_ALLOW_LIVE", False, raising=False)

        router = create_default_router()
        assert "tastytrade" not in router.available_brokers
        with pytest.raises(ValueError, match="No executor registered"):
            router.get("tastytrade")

    def test_live_registered_when_flag_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from backend.config import settings
        monkeypatch.setattr(settings, "TASTYTRADE_ALLOW_LIVE", True, raising=False)

        router = create_default_router()
        assert "tastytrade" in router.available_brokers
        executor = router.get("tastytrade")
        assert isinstance(executor, TastytradeExecutor)
        assert executor.is_paper_trading() is False

    def test_constructor_rejects_prod_without_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from backend.config import settings
        monkeypatch.setattr(settings, "TASTYTRADE_ALLOW_LIVE", False, raising=False)

        with pytest.raises(RuntimeError, match="TASTYTRADE_ALLOW_LIVE"):
            TastytradeExecutor(environment="prod")

    def test_constructor_rejects_unknown_environment(self) -> None:
        with pytest.raises(ValueError, match="environment must be"):
            TastytradeExecutor(environment="staging")  # type: ignore[arg-type]


# --------------------------------------------------------- symbol classifier


class TestOptionSymbolClassifier:
    @pytest.mark.parametrize(
        "symbol",
        ["AAPL", "SPY", "BRK.B", "BRK-B", "MSFT", "TSLA", "NVDA", "A"],
    )
    def test_equity_tickers_route_through_equity_path(self, symbol: str) -> None:
        assert _is_option_symbol(symbol) is False

    @pytest.mark.parametrize(
        "symbol",
        [
            "AAPL  240119C00150000",   # OCC-padded
            "AAPL240119C00150000",     # compressed OCC
            "SPY   241220P00450000",   # OCC with put
            "FOOBARBAZ",               # too long
            "aapl",                    # lowercase (not uppercase match)
        ],
    )
    def test_non_equity_symbols_are_flagged(self, symbol: str) -> None:
        assert _is_option_symbol(symbol) is True


# ------------------------------------------------------------------- previews


class TestPreviewOrder:
    @pytest.mark.asyncio
    async def test_preview_equity_limit_success(self) -> None:
        account = MagicMock()
        placed = _stub_placed_order()
        response = _stub_placed_response(placed)
        account.place_order = AsyncMock(return_value=response)

        ex = _make_executor_with_session(session=MagicMock(), accounts=[account])

        req = OrderRequest(
            symbol="AAPL",
            side=ActionSide.BUY,
            order_type=IBOrderType.LMT,
            quantity=10,
            limit_price=150.0,
        )
        result = await ex.preview_order(req)

        assert result.ok, result.error
        assert result.estimated_commission == pytest.approx(0.65)
        assert result.estimated_margin_impact == pytest.approx(-1500.0)
        # SDK call uses dry_run=True
        account.place_order.assert_awaited_once()
        _, kwargs = account.place_order.call_args
        assert kwargs["dry_run"] is True

    @pytest.mark.asyncio
    async def test_preview_reports_sdk_errors(self) -> None:
        account = MagicMock()
        response = _stub_placed_response(
            _stub_placed_order(),
            errors=[SimpleNamespace(code="insufficient_buying_power", message="bp")],
        )
        account.place_order = AsyncMock(return_value=response)

        ex = _make_executor_with_session(MagicMock(), [account])

        req = OrderRequest(
            symbol="AAPL",
            side=ActionSide.BUY,
            order_type=IBOrderType.LMT,
            quantity=10,
            limit_price=150.0,
        )
        result = await ex.preview_order(req)

        assert not result.ok
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_preview_rejects_option_symbol(self) -> None:
        ex = _make_executor_with_session(MagicMock(), [MagicMock()])

        req = OrderRequest(
            symbol="AAPL  240119C00150000",
            side=ActionSide.BUY,
            order_type=IBOrderType.LMT,
            quantity=1,
            limit_price=5.00,
        )
        result = await ex.preview_order(req)

        assert result.error is not None
        assert "option" in result.error.lower()


# --------------------------------------------------------------------- places


class TestPlaceOrder:
    @pytest.mark.asyncio
    async def test_place_equity_market_success(self) -> None:
        account = MagicMock()
        placed = _stub_placed_order(order_id=99001, status_value="Live")
        account.place_order = AsyncMock(return_value=_stub_placed_response(placed))

        ex = _make_executor_with_session(MagicMock(), [account])

        req = OrderRequest(
            symbol="AAPL",
            side=ActionSide.BUY,
            order_type=IBOrderType.MKT,
            quantity=5,
        )
        result = await ex.place_order(req)

        assert result.ok, result.error
        assert result.broker_order_id == "99001"
        assert result.status == "submitted"
        _, kwargs = account.place_order.call_args
        assert kwargs["dry_run"] is False

    @pytest.mark.asyncio
    async def test_place_rejects_option_symbol_with_clear_error(self) -> None:
        """F4 ships equity-first. Option symbols must surface an explicit error
        (no silent fallback per `.cursor/rules/no-silent-fallback.mdc`)."""

        ex = _make_executor_with_session(MagicMock(), [MagicMock()])
        req = OrderRequest(
            symbol="AAPL  240119C00150000",
            side=ActionSide.BUY,
            order_type=IBOrderType.LMT,
            quantity=1,
            limit_price=5.00,
        )
        result = await ex.place_order(req)

        assert result.error is not None
        assert "option" in result.error.lower()
        assert "equity" in result.error.lower()
        assert result.broker_order_id is None

    @pytest.mark.asyncio
    async def test_place_propagates_sdk_exception(self) -> None:
        account = MagicMock()
        account.place_order = AsyncMock(
            side_effect=RuntimeError("tastytrade 400: insufficient_buying_power")
        )

        ex = _make_executor_with_session(MagicMock(), [account])

        req = OrderRequest(
            symbol="AAPL",
            side=ActionSide.BUY,
            order_type=IBOrderType.LMT,
            quantity=10,
            limit_price=150.0,
        )
        result = await ex.place_order(req)

        assert result.error is not None
        assert "insufficient_buying_power" in result.error
        # The only way to express the failure is via OrderResult.error —
        # status must not be "submitted"/"filled" on SDK exceptions.
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_place_rejects_missing_limit_price(self) -> None:
        account = MagicMock()
        account.place_order = AsyncMock()
        ex = _make_executor_with_session(MagicMock(), [account])

        req = OrderRequest(
            symbol="AAPL",
            side=ActionSide.BUY,
            order_type=IBOrderType.LMT,
            quantity=10,
            limit_price=None,
        )
        result = await ex.place_order(req)

        assert result.error is not None
        assert "limit_price" in result.error.lower()
        account.place_order.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_place_empty_order_id_surfaces_error(self) -> None:
        account = MagicMock()
        placed = SimpleNamespace(id=None, status=SimpleNamespace(value="Live"), legs=[])
        account.place_order = AsyncMock(return_value=_stub_placed_response(placed))

        ex = _make_executor_with_session(MagicMock(), [account])

        req = OrderRequest(
            symbol="AAPL",
            side=ActionSide.BUY,
            order_type=IBOrderType.MKT,
            quantity=1,
        )
        result = await ex.place_order(req)

        assert result.error is not None
        assert "order id" in result.error.lower()


# --------------------------------------------------------------------- cancel


class TestCancelOrder:
    @pytest.mark.asyncio
    async def test_cancel_success(self) -> None:
        account = MagicMock()
        account.delete_order = AsyncMock(return_value=None)

        ex = _make_executor_with_session(MagicMock(), [account])
        result = await ex.cancel_order("12345")

        assert result.ok, result.error
        assert result.status == "cancelled"
        assert result.broker_order_id == "12345"
        account.delete_order.assert_awaited_once()
        args, _ = account.delete_order.call_args
        assert args[1] == 12345  # int order id

    @pytest.mark.asyncio
    async def test_cancel_non_integer_id_fails_closed(self) -> None:
        account = MagicMock()
        account.delete_order = AsyncMock()
        ex = _make_executor_with_session(MagicMock(), [account])

        result = await ex.cancel_order("not-an-int")

        assert result.error is not None
        account.delete_order.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cancel_propagates_sdk_exception(self) -> None:
        account = MagicMock()
        account.delete_order = AsyncMock(
            side_effect=RuntimeError("404 order_not_found")
        )
        ex = _make_executor_with_session(MagicMock(), [account])

        result = await ex.cancel_order("99999")

        assert result.error is not None
        assert "order_not_found" in result.error


# ------------------------------------------------------------------- status


class TestGetOrderStatus:
    @pytest.mark.asyncio
    async def test_status_filled_with_fills(self) -> None:
        fills = [
            SimpleNamespace(quantity=Decimal("3"), fill_price=Decimal("100")),
            SimpleNamespace(quantity=Decimal("2"), fill_price=Decimal("101")),
        ]
        leg = SimpleNamespace(fills=fills)
        placed = _stub_placed_order(status_value="Filled", legs=[leg])
        account = MagicMock()
        account.get_order = AsyncMock(return_value=placed)

        ex = _make_executor_with_session(MagicMock(), [account])
        result = await ex.get_order_status("12345")

        assert result.status == "filled"
        assert result.filled_quantity == pytest.approx(5.0)
        # weighted avg: (3*100 + 2*101) / 5 = 100.4
        assert result.avg_fill_price == pytest.approx(100.4)

    @pytest.mark.asyncio
    async def test_status_non_integer_id_fails_closed(self) -> None:
        account = MagicMock()
        account.get_order = AsyncMock()
        ex = _make_executor_with_session(MagicMock(), [account])

        result = await ex.get_order_status("not-an-int")

        assert result.error is not None
        account.get_order.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_status_unknown_sdk_status(self) -> None:
        placed = SimpleNamespace(
            id=1, status=SimpleNamespace(value="WeirdNewStatus"), legs=[]
        )
        account = MagicMock()
        account.get_order = AsyncMock(return_value=placed)
        ex = _make_executor_with_session(MagicMock(), [account])

        result = await ex.get_order_status("1")

        # Must not silently report "filled"/"cancelled" for an unknown status.
        assert result.status == "weirdnewstatus"
        assert result.filled_quantity == 0


# ----------------------------------------------------------- status mapping


class TestStatusMap:
    @pytest.mark.parametrize(
        "sdk_value,expected",
        [
            ("Received", "submitted"),
            ("Routed", "submitted"),
            ("Live", "submitted"),
            ("Filled", "filled"),
            ("Cancelled", "cancelled"),
            ("Rejected", "rejected"),
            ("Partially Removed", "partially_filled"),
        ],
    )
    def test_known_statuses(self, sdk_value: str, expected: str) -> None:
        assert _map_tt_status(SimpleNamespace(value=sdk_value)) == expected

    def test_unknown_status_lowercased(self) -> None:
        # Fail-open to lowercase of the raw value rather than masking with
        # a bogus "submitted" — keeps the caller able to see something weird.
        assert _map_tt_status(SimpleNamespace(value="BrandNew")) == "brandnew"

    def test_none_returns_none(self) -> None:
        assert _map_tt_status(None) is None


# ------------------------------------------------------------- session refresh


class TestSessionRefresh:
    @pytest.mark.asyncio
    async def test_refresh_session_under_lock_acquires_and_releases(self) -> None:
        ex = TastytradeExecutor()
        ex._session = MagicMock()
        ex._session.refresh = AsyncMock(return_value=None)

        fake_redis = MagicMock()
        fake_redis.set.return_value = True
        fake_redis.delete.return_value = 1

        with patch(
            "backend.services.execution.tastytrade_executor._try_get_redis",
            return_value=fake_redis,
        ):
            await ex._refresh_session_under_lock("secret")

        ex._session.refresh.assert_awaited_once()
        fake_redis.set.assert_called_once()
        fake_redis.delete.assert_called_once()
        # Lock key must not leak the secret.
        (call_kwargs := fake_redis.set.call_args.kwargs)
        assert "secret" not in call_kwargs["name"]
        assert call_kwargs["nx"] is True

    @pytest.mark.asyncio
    async def test_refresh_session_failure_resets_state(self) -> None:
        ex = TastytradeExecutor()
        ex._session = MagicMock()
        ex._session.refresh = AsyncMock(side_effect=RuntimeError("boom"))
        ex._accounts = [MagicMock()]

        with patch(
            "backend.services.execution.tastytrade_executor._try_get_redis",
            return_value=None,
        ):
            with pytest.raises(TastytradeExecutorError):
                await ex._refresh_session_under_lock("secret")

        assert ex._session is None
        assert ex._accounts == []

    @pytest.mark.asyncio
    async def test_ensure_session_missing_credentials_raises(self) -> None:
        ex = TastytradeExecutor()

        class _Settings:
            TASTYTRADE_CLIENT_SECRET = None
            TASTYTRADE_REFRESH_TOKEN = None
            TASTYTRADE_IS_TEST = False

        with patch(
            "backend.config.settings", _Settings()
        ):
            with pytest.raises(TastytradeExecutorError) as exc_info:
                await ex._ensure_session()
        assert "credentials" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_ensure_session_full_cycle(self) -> None:
        """Covers the cycle: build Session → refresh → load accounts."""

        ex = TastytradeExecutor()

        fake_session = MagicMock()
        fake_session.refresh = AsyncMock(return_value=None)
        fake_account = SimpleNamespace(account_number="5WU12345")

        class _Settings:
            TASTYTRADE_CLIENT_SECRET = "client-secret"
            TASTYTRADE_REFRESH_TOKEN = "refresh-token"
            TASTYTRADE_IS_TEST = True

        with (
            patch(
                "backend.config.settings", _Settings()
            ),
            patch(
                "tastytrade.Session",
                return_value=fake_session,
            ) as session_ctor,
            patch(
                "tastytrade.Account.get",
                new=AsyncMock(return_value=[fake_account]),
            ) as account_get,
            patch(
                "backend.services.execution.tastytrade_executor._try_get_redis",
                return_value=None,
            ),
        ):
            session = await ex._ensure_session()

        assert session is fake_session
        fake_session.refresh.assert_awaited_once()
        session_ctor.assert_called_once_with(
            "client-secret", "refresh-token", is_test=True
        )
        account_get.assert_awaited_once()
        assert ex._accounts == [fake_account]


# ------------------------------------------------------------- account routing


class TestAccountRouting:
    """Exercise the real ``_resolve_account`` (bypass the fake installed by
    ``_make_executor_with_session``)."""

    def _bare(self, accounts: list[Any]) -> TastytradeExecutor:
        ex = TastytradeExecutor()
        ex._session = MagicMock()
        ex._accounts = accounts
        return ex

    @pytest.mark.asyncio
    async def test_resolve_account_matches_account_id(self) -> None:
        a1 = SimpleNamespace(account_number="AA1")
        a2 = SimpleNamespace(account_number="BB2")
        ex = self._bare([a1, a2])

        with patch.object(ex, "_ensure_session", new=AsyncMock(return_value=ex._session)):
            _, acct = await ex._resolve_account("BB2")

        assert acct is a2

    @pytest.mark.asyncio
    async def test_resolve_account_unknown_id_raises(self) -> None:
        ex = self._bare([SimpleNamespace(account_number="AA1")])
        with patch.object(ex, "_ensure_session", new=AsyncMock(return_value=ex._session)):
            with pytest.raises(TastytradeExecutorError):
                await ex._resolve_account("NOPE")

    @pytest.mark.asyncio
    async def test_resolve_account_no_id_returns_first(self) -> None:
        a1 = SimpleNamespace(account_number="AA1")
        a2 = SimpleNamespace(account_number="BB2")
        ex = self._bare([a1, a2])
        with patch.object(ex, "_ensure_session", new=AsyncMock(return_value=ex._session)):
            _, acct = await ex._resolve_account(None)
        assert acct is a1


# ------------------------------------------------------------------- lock key


class TestLockKey:
    def test_lock_key_is_stable_and_does_not_leak_secret(self) -> None:
        key = _lock_key_for_secret("super-secret-value")
        assert "super-secret-value" not in key
        assert key.startswith("lock:tastytrade_session_refresh:")
        # Deterministic — same input gives same key.
        assert key == _lock_key_for_secret("super-secret-value")
        # Different input gives different key.
        assert key != _lock_key_for_secret("other-secret")
