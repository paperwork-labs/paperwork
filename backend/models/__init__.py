"""
AxiomFolio Database Models
==========================

Centralized model imports for the AxiomFolio application.
All database models are imported here for easy access.
"""

# Core Base
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Essential Core Models (verified to exist)
from .user import User, UserRole
from .app_settings import AppSettings
from .user_invite import UserInvite
from .broker_account import BrokerAccount, BrokerType, AccountType, AccountStatus, SyncStatus

# Instruments & Market Data
from .instrument import Instrument, InstrumentType
from .market_data import PriceData, MarketSnapshot, MarketSnapshotHistory, MarketRegime, JobRun
from .market_tracked_plan import MarketTrackedPlan
from .index_constituent import IndexConstituent
from .historical_iv import HistoricalIV
from .institutional_holding import InstitutionalHolding

# Trading & Positions
from .position import Position, PositionType, PositionStatus
from .trade import Trade, TradeSignal
from .order import Order, OrderSide, OrderType, OrderStatus

# Portfolio Management
from .portfolio import PortfolioSnapshot, Category, PositionCategory

# Tax Lots & Cost Basis
from .tax_lot import TaxLot, TaxLotMethod, TaxLotSource

# Account Balances & Margin
from .account_balance import AccountBalance, AccountBalanceType

# Margin Interest Tracking
from .margin_interest import MarginInterest

# Transfers & Position Movements
from .transfer import Transfer, TransferType

# Transactions & Dividends
from .transaction import Transaction, TransactionType, Dividend

# Options Trading
from .options import Option, OptionType

# Strategy & Signals (required for User.strategies / User.strategy_executions)
from .strategy import Strategy, StrategyExecution

# Watchlist
from .watchlist import Watchlist

# Agent / Auto-Ops
from .agent_action import AgentAction

# Essential models list
__all__ = [
    "Base",
    "User",
    "UserRole",
    "AppSettings",
    "UserInvite",
    "BrokerAccount",
    "BrokerType",
    "AccountType",
    "AccountStatus",
    "SyncStatus",
    "Instrument",
    "InstrumentType",
    "PriceData",
    "MarketSnapshot",
    "MarketSnapshotHistory",
    "MarketRegime",
    "JobRun",
    "MarketTrackedPlan",
    "IndexConstituent",
    "HistoricalIV",
    "InstitutionalHolding",
    "Position",
    "PositionType",
    "PositionStatus",
    "TaxLot",
    "TaxLotMethod",
    "TaxLotSource",
    "AccountBalance",
    "AccountBalanceType",
    "MarginInterest",
    "Transfer",
    "TransferType",
    "Transaction",
    "TransactionType",
    "Dividend",
    "Option",
    "OptionType",
    "PortfolioSnapshot",
    "Category",
    "PositionCategory",
    "Trade",
    "TradeSignal",
    "Order",
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "Watchlist",
    "AgentAction",
]
