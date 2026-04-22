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
from .entitlement import Entitlement, EntitlementStatus, SubscriptionTier
from .broker_account import BrokerAccount, BrokerType, AccountType, AccountStatus, SyncStatus
from .broker_oauth_connection import (
    BrokerOAuthConnection,
    OAuthBrokerType,
    OAuthConnectionStatus,
)

# Picks pipeline (validator-curated buy/sell/trim/add)
from .picks import (
    Candidate,
    CandidateQueueState,
    EmailInbox,
    EmailParse,
    EmailParseStatus,
    EngagementType,
    IngestionStatus,
    MacroOutlook,
    PickAction,
    PickEngagement,
    PickStatus,
    PicksAuditLog,
    PositionChange,
    SourceAttribution,
    SourceType,
    ValidatedPick,
)

# Instruments & Market Data
from .instrument import Instrument, InstrumentType
from .market_data import PriceData, MarketSnapshot, MarketSnapshotHistory, MarketRegime, JobRun, EarningsCalendarEvent
from .market_tracked_plan import MarketTrackedPlan

# Symbol Master — single source of truth for symbol identity over time.
# Global table (no user_id); see backend/services/symbols/ for callers.
from .symbol_master import (
    AliasSource,
    AssetClass,
    SymbolAlias,
    SymbolChangeType,
    SymbolHistory,
    SymbolMaster,
    SymbolStatus,
)
from .index_constituent import IndexConstituent
from .market.options_chain_snapshot import OptionsChainSnapshot
from .historical_iv import HistoricalIV
from .institutional_holding import InstitutionalHolding
from .historical_import_run import (
    HistoricalImportRun,
    HistoricalImportSource,
    HistoricalImportStatus,
)

# Trading & Positions
from .position import Position, PositionType, PositionStatus
from .trade import Trade, TradeSignal
from .order import Order, OrderSide, OrderType, OrderStatus
from .execution import ExecutionMetrics

# Portfolio Management
from .portfolio import PortfolioHistory, PortfolioSnapshot, Category, PositionCategory

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

# Backtesting
from .backtest import StrategyBacktest, BacktestStatus
from .walk_forward_study import WalkForwardStudy, WalkForwardStatus

# Watchlist
from .watchlist import Watchlist

# Narrative
from .narrative import PortfolioNarrative

# Agent / Auto-Ops
from .agent_action import AgentAction
from .agent_message import AgentMessage, load_conversation_from_db, save_conversation_to_db
from .auto_ops_explanation import AutoOpsExplanation
from .trade_decision_explanation import TradeDecisionExplanation

# Deploy health guardrail (G28, D120)
from .deploy_health_event import DeployHealthEvent

# Multi-tenant hardening (rate limits, GDPR jobs, cost rollup, incidents)
from .multitenant import (
    GDPRDeleteJob,
    GDPRExportJob,
    GDPRJobStatus,
    IncidentRow,
    IncidentSeverity,
    RateLimitViolation,
    TenantCostRollup,
    TenantRateLimit,
)
# MCP (Model Context Protocol) bearer tokens for read-only AI agent access
from .mcp_token import MCPToken

# Corporate Actions (splits, dividends, mergers)
from .corporate_action import (
    AppliedCorporateAction,
    CorporateAction,
    CorporateActionSource,
    CorporateActionStatus,
    CorporateActionType,
)

# Data Quality (multi-source quorum + per-provider drift)
from .provider_quorum import (
    ProviderDriftAlert,
    ProviderQuorumLog,
    QuorumAction,
    QuorumStatus,
)

# Notifications (required for User.notifications ↔ Notification.user)
from .notification import (
    Notification,
    NotificationChannel,
    NotificationDelivery,
    NotificationPreference,
    NotificationStatus,
    NotificationTemplate,
    NotificationType,
    Priority,
)

# Essential models list
__all__ = [
    "Base",
    "User",
    "UserRole",
    "AppSettings",
    "UserInvite",
    "Entitlement",
    "EntitlementStatus",
    "SubscriptionTier",
    "Candidate",
    "CandidateQueueState",
    "PicksAuditLog",
    "EmailInbox",
    "EmailParse",
    "EmailParseStatus",
    "EngagementType",
    "IngestionStatus",
    "MacroOutlook",
    "PickAction",
    "PickEngagement",
    "PickStatus",
    "PositionChange",
    "SourceAttribution",
    "SourceType",
    "ValidatedPick",
    "BrokerAccount",
    "BrokerType",
    "AccountType",
    "AccountStatus",
    "SyncStatus",
    "BrokerOAuthConnection",
    "OAuthBrokerType",
    "OAuthConnectionStatus",
    "Instrument",
    "InstrumentType",
    "PriceData",
    "MarketSnapshot",
    "MarketSnapshotHistory",
    "MarketRegime",
    "JobRun",
    "EarningsCalendarEvent",
    "MarketTrackedPlan",
    "IndexConstituent",
    "HistoricalIV",
    "InstitutionalHolding",
    "HistoricalImportRun",
    "HistoricalImportSource",
    "HistoricalImportStatus",
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
    "OptionsChainSnapshot",
    "PortfolioHistory",
    "PortfolioSnapshot",
    "Category",
    "PositionCategory",
    "Trade",
    "TradeSignal",
    "Order",
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "ExecutionMetrics",
    "Watchlist",
    "PortfolioNarrative",
    "AgentAction",
    "AgentMessage",
    "AutoOpsExplanation",
    "TradeDecisionExplanation",
    "DeployHealthEvent",
    "load_conversation_from_db",
    "save_conversation_to_db",
    "Notification",
    "NotificationChannel",
    "NotificationDelivery",
    "NotificationPreference",
    "NotificationStatus",
    "NotificationTemplate",
    "NotificationType",
    "Priority",
    "StrategyBacktest",
    "BacktestStatus",
    # Symbol master
    "AliasSource",
    "AssetClass",
    "SymbolAlias",
    "SymbolChangeType",
    "SymbolHistory",
    "SymbolMaster",
    "SymbolStatus",
    "TenantRateLimit",
    "RateLimitViolation",
    "GDPRExportJob",
    "GDPRDeleteJob",
    "GDPRJobStatus",
    "TenantCostRollup",
    "IncidentRow",
    "IncidentSeverity",
    "WalkForwardStudy",
    "WalkForwardStatus",
    "MCPToken",
    "AppliedCorporateAction",
    "CorporateAction",
    "CorporateActionSource",
    "CorporateActionStatus",
    "CorporateActionType",
    "ProviderDriftAlert",
    "ProviderQuorumLog",
    "QuorumAction",
    "QuorumStatus",
]
