import asyncio
from decimal import Decimal

from app.models.broker_account import AccountType, BrokerAccount, BrokerType
from app.services.portfolio.schwab_sync_service import SchwabSyncService


class DummySchwabClient:
    async def connect(self):
        return True

    async def connect_with_credentials(self, access_token: str, refresh_token: str, **kwargs):
        return True

    def set_token_refresh_callback(self, callback):
        pass

    async def get_positions(self, account_number: str):
        return [
            {"symbol": "AAPL", "quantity": 10, "average_cost": 150.0, "total_cost_basis": 1500.0},
            {"symbol": "MSFT", "quantity": 0, "average_cost": 0.0, "total_cost_basis": 0.0},
        ]

    async def get_options_positions(self, account_number: str):
        return [
            {
                "symbol": "AAPL",
                "option_symbol": "AAPL250117C200",
                "strike": 200.0,
                "expiration": "2025-01-17",
                "put_call": "CALL",
                "quantity": 2,
            }
        ]

    async def get_transactions(self, account_number: str):
        return []

    async def get_account_balances(self, account_number: str):
        return {}

    async def get_corporate_actions(self, account_number: str):
        # 2-for-1 split on AAPL
        return [
            {"type": "split", "symbol": "AAPL", "numerator": 2, "denominator": 1},
        ]


def _create_account(session) -> BrokerAccount:
    from app.models.user import User

    user = session.query(User).filter(User.username == "sync_tester").first()
    if not user:
        user = User(
            username="sync_tester",
            email="sync_tester@example.com",
            password_hash="x",
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    acct = BrokerAccount(
        user_id=user.id,
        broker=BrokerType.SCHWAB,
        account_number="SCHWAB123",
        account_name="Schwab Test",
        account_type=AccountType.TAXABLE,
        currency="USD",
    )
    session.add(acct)
    session.commit()
    session.refresh(acct)
    return acct


def test_schwab_sync_positions_only(db_session, monkeypatch):
    from app.services.portfolio import schwab_sync_service

    def _fake_get_decrypted(account_id, session):
        return {"access_token": "fake_at", "refresh_token": "fake_rt"}

    monkeypatch.setattr(
        schwab_sync_service.account_credentials_service, "get_decrypted", _fake_get_decrypted
    )

    account = _create_account(db_session)
    service = SchwabSyncService(client=DummySchwabClient())
    result = asyncio.get_event_loop().run_until_complete(
        service.sync_account_comprehensive(
            account_number=account.account_number, session=db_session
        )
    )
    assert result["status"] == "success"
    from app.models.position import Position, PositionStatus, PositionType

    aapl = (
        db_session.query(Position)
        .filter(Position.account_id == account.id, Position.symbol == "AAPL")
        .first()
    )
    assert aapl is not None
    assert Decimal(aapl.quantity) == Decimal("10")
    assert aapl.position_type == PositionType.LONG
    assert Decimal(aapl.average_cost) == Decimal("150")
    msft = (
        db_session.query(Position)
        .filter(Position.account_id == account.id, Position.symbol == "MSFT")
        .first()
    )
    assert msft is not None
    assert msft.status == PositionStatus.CLOSED

    # Options created
    from app.models.options import Option

    opt = (
        db_session.query(Option)
        .filter(
            Option.account_id == account.id,
            Option.underlying_symbol == "AAPL",
            Option.option_type == "CALL",
        )
        .first()
    )
    assert opt is not None and opt.open_quantity == 2
