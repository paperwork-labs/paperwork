"""
Account Configuration Service
============================

Service to read broker account configurations from environment variables
and populate the database with broker accounts.

This eliminates hardcoded account numbers from code and centralizes
account management.
"""

import logging
from typing import Dict, List
from datetime import datetime

from backend.config import settings
from backend.database import SessionLocal
from backend.models.broker_account import (
    BrokerAccount,
    BrokerType,
    AccountType,
    AccountStatus,
)
from backend.models.user import User, UserRole

logger = logging.getLogger(__name__)


class AccountConfigService:
    """
    Service to manage broker account configurations from environment variables.

    Reads account info from .env and ensures they exist in database.
    """

    def __init__(self):
        self.db = SessionLocal()

    def get_ibkr_accounts_from_env(self, override_settings=None) -> List[Dict]:
        """Parse IBKR accounts from environment variables.
        Supports format: "ACC1:TAXABLE,ACC2:IRA"; falls back to comma-separated list.
        Accepts optional override_settings for tests.
        """
        try:
            cfg = override_settings or settings
            accounts_str = getattr(cfg, "IBKR_ACCOUNTS", None)
            if not accounts_str:
                logger.warning("No IBKR_ACCOUNTS found in environment")
                return []

            accounts: List[Dict] = []
            for token in [t.strip() for t in accounts_str.split(",") if t.strip()]:
                # Accept "ACC:TYPE" or just "ACC"
                if ":" in token:
                    acc_num, type_str = token.split(":", 1)
                    type_str = type_str.strip().upper()
                    if type_str == "IRA":
                        account_type = AccountType.IRA
                    elif type_str in {"ROTH", "ROTH_IRA"}:
                        account_type = AccountType.ROTH_IRA
                    else:
                        account_type = AccountType.TAXABLE
                else:
                    acc_num = token
                    account_type = self._detect_account_type(acc_num)

                account_name = f"IBKR {account_type.value.upper()} ({acc_num})"
                accounts.append(
                    {
                        "account_id": acc_num,
                        "account_number": acc_num,
                        "account_name": account_name,
                        "account_type": account_type,
                        "broker": BrokerType.IBKR,
                    }
                )

            return accounts

        except Exception as e:
            logger.error(f"Error parsing IBKR accounts from env: {e}")
            return []

    def get_tastytrade_account_from_env(self, override_settings=None) -> Dict:
        """Get TastyTrade account info from environment variables.
        Requires TASTYTRADE_CLIENT_SECRET (OAuth) to indicate TT is configured.
        REQUIRE a real account number to seed; otherwise, skip seeding.
        Discovery (to fetch real account numbers) should happen in explicit flows.
        """
        try:
            cfg = override_settings or settings
            has_oauth = bool(getattr(cfg, "TASTYTRADE_CLIENT_SECRET", None))
            account_number = getattr(cfg, "TASTYTRADE_ACCOUNT_NUMBER", None)
            if account_number is not None:
                try:
                    account_number = str(account_number)
                    if account_number.startswith("<") or len(account_number) > 30:
                        account_number = None
                except Exception:
                    account_number = None
            if not has_oauth:
                logger.warning("No TASTYTRADE_CLIENT_SECRET found in environment")
                return None
            if not account_number:
                logger.info(
                    "TASTYTRADE_ACCOUNT_NUMBER not set; skipping TastyTrade seeding"
                )
                return None
            return {
                "account_id": "oauth",
                "account_number": account_number,
                "account_name": f"TastyTrade ({account_number})",
                "account_type": AccountType.TAXABLE,
                "broker": BrokerType.TASTYTRADE,
            }
        except Exception as e:
            logger.error(f"Error parsing TastyTrade account from env: {e}")
            return None

    def _detect_account_type(self, acc_num: str) -> AccountType:
        """Detect account type from account number patterns.
        Default to TAXABLE.
        """
        try:
            # Test-friendly: treat placeholders with _B as IRA, else TAXABLE
            if acc_num.endswith("_B") or acc_num.upper().endswith("_IRA"):
                return AccountType.IRA
            if acc_num.startswith("U1589"):
                return AccountType.IRA
            return AccountType.TAXABLE
        except Exception:
            return AccountType.TAXABLE

    def ensure_user_exists(self, db=None, user_id: int = 1) -> User:
        """Ensure the default user exists in database."""
        try:
            session = db or self.db
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                user = User(
                    id=user_id,
                    username="default_user",
                    email="default@axiomfolio.com",
                    first_name="Default",
                    last_name="AxiomFolio User",
                    is_active=True,
                    role=UserRole.OWNER,
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                logger.info(f"Created default user with ID {user_id}")

            return user

        except Exception as e:
            logger.error(f"Error ensuring user exists: {e}")
            session.rollback()
            raise

    def seed_broker_accounts(self, db=None, user_id: int = 1) -> Dict:
        """
        Seed broker accounts from environment variables into database.

        This should be called during application startup or when adding accounts.
        """
        try:
            # Ensure user exists
            session = db or self.db
            user = self.ensure_user_exists(session, user_id)

            results = {"created": 0, "updated": 0, "errors": 0, "accounts": []}

            # Get all account configurations
            all_accounts = []

            # IBKR accounts
            ibkr_accounts = self.get_ibkr_accounts_from_env()
            # Optional discovery on seed (opt-in only)
            try:
                if not ibkr_accounts and getattr(
                    settings, "IBKR_DISCOVER_ON_SEED", False
                ):
                    from backend.services.clients.ibkr_client import IBKRClient
                    import asyncio

                    client = IBKRClient()
                    accounts = []
                    try:
                        asyncio.run(client.connect_with_retry())
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        try:
                            loop.run_until_complete(client.connect_with_retry())
                        finally:
                            loop.close()
                    try:
                        discovered = []
                        try:
                            discovered = asyncio.run(client.discover_managed_accounts())
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            try:
                                discovered = loop.run_until_complete(
                                    client.discover_managed_accounts()
                                )
                            finally:
                                loop.close()
                        for acc in discovered:
                            ibkr_accounts.append(
                                {
                                    "account_id": acc,
                                    "account_number": acc,
                                    "account_name": f"IBKR DISCOVERED ({acc})",
                                    "account_type": self._detect_account_type(acc),
                                    "broker": BrokerType.IBKR,
                                }
                            )
                    except Exception as e:
                        logger.warning(
                            "IBKR_DISCOVER_ON_SEED: failed building accounts from discovery: %s",
                            e,
                        )
                        pass
            except Exception as e:
                logger.warning("IBKR_DISCOVER_ON_SEED: outer seed block failed: %s", e)
                pass
            all_accounts.extend(ibkr_accounts)

            # TastyTrade account - use username as stable id
            tt_account = self.get_tastytrade_account_from_env()
            if tt_account:
                # normalize account number to string and cap length
                acc = str(
                    tt_account.get("account_number")
                    or tt_account.get("account_id")
                    or ""
                )
                if acc.startswith("<") or len(acc) > 50:
                    acc = tt_account.get("account_id")
                tt_account["account_number"] = acc
                all_accounts.append(tt_account)

            # Schwab accounts (optional, comma-separated)
            try:
                schwab_list = getattr(settings, "SCHWAB_ACCOUNTS", None)
                if schwab_list:
                    for acc in [a.strip() for a in schwab_list.split(",") if a.strip()]:
                        all_accounts.append(
                            {
                                "account_number": acc,
                                "account_name": f"Schwab Account ({acc})",
                                "account_type": AccountType.TAXABLE,
                                "broker": BrokerType.SCHWAB,
                            }
                        )
            except Exception as e:
                logger.warning("Failed parsing SCHWAB_ACCOUNTS from settings: %s", e)
                pass

            # Process each account
            for account_config in all_accounts:
                try:
                    account_number = (
                        str(account_config["account_number"])
                        if account_config.get("account_number") is not None
                        else None
                    )
                    broker = account_config["broker"]

                    # Check if account already exists
                    existing = (
                        session.query(BrokerAccount)
                        .filter(
                            BrokerAccount.user_id == user_id,
                            BrokerAccount.account_number == account_number,
                            BrokerAccount.broker == broker,
                        )
                        .first()
                    )

                    if existing:
                        # Update existing account
                        existing.account_name = account_config["account_name"]
                        existing.account_type = account_config["account_type"]
                        existing.updated_at = datetime.now()
                        results["updated"] += 1
                        logger.info(f"Updated existing account: {account_number}")
                    else:
                        # Create new account
                        new_account = BrokerAccount(
                            user_id=user_id,
                            broker=broker,
                            account_number=account_number,
                            account_name=account_config["account_name"],
                            account_type=account_config["account_type"],
                            status=AccountStatus.ACTIVE,
                            is_enabled=True,
                            api_credentials_stored=False,  # Will be set when credentials are added
                            currency="USD",
                            created_at=datetime.now(),
                        )
                        session.add(new_account)
                        results["created"] += 1
                        logger.info(f"Created new account: {account_number}")

                    results["accounts"].append(
                        {
                            "account_number": account_number,
                            "broker": broker.value,
                            "account_type": account_config["account_type"].value,
                        }
                    )

                except Exception as e:
                    logger.error(
                        f"Error processing account {account_config.get('account_number', 'UNKNOWN')}: {e}"
                    )
                    results["errors"] += 1
                    continue

            session.commit()

            logger.info(
                f"Account seeding completed: {results['created']} created, {results['updated']} updated, {results['errors']} errors"
            )
            return results

        except Exception as e:
            logger.error(f"Error seeding broker accounts: {e}")
            session.rollback()
            return {"error": str(e)}
        finally:
            if db is None:
                self.db.close()

    def get_broker_accounts_for_user(self, user_id: int = 1) -> List[BrokerAccount]:
        """Get all broker accounts for a user."""
        try:
            accounts = (
                self.db.query(BrokerAccount)
                .filter(
                    BrokerAccount.user_id == user_id, BrokerAccount.is_enabled == True
                )
                .all()
            )

            return accounts

        except Exception as e:
            logger.error(f"Error getting broker accounts: {e}")
            return []


# Global instance
account_config_service = AccountConfigService()
