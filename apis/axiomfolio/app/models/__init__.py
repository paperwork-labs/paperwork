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
# Account Balances & Margin
from .account_balance import AccountBalance, AccountBalanceType
from .account_risk_profile import BrokerAccountRiskProfile

# Agent / Auto-Ops
from .agent_action import AgentAction
from .agent_message import AgentMessage, load_conversation_from_db, save_conversation_to_db
from .auto_ops_explanation import AutoOpsExplanation

# Backtesting
from .backtest import BacktestStatus, StrategyBacktest
from .broker_account import AccountStatus, AccountType, BrokerAccount, BrokerType, SyncStatus
from .broker_oauth_connection import (
    BrokerOAuthConnection,
    OAuthBrokerType,
    OAuthConnectionStatus,
)
from .conviction_pick import ConvictionPick

# Corporate Actions (splits, dividends, mergers)
from .corporate_action import (
    AppliedCorporateAction,
    CorporateAction,
    CorporateActionSource,
    CorporateActionStatus,
    CorporateActionType,
)

# Deploy health guardrail (G28, D120)
from .deploy_health_event import DeployHealthEvent
from .entitlement import Entitlement, EntitlementStatus, SubscriptionTier
from .execution import ExecutionMetrics

# Auxiliary external signals (Finviz/Zacks scaffolds; not primary strategy inputs)
from .external_signal import ExternalSignal
from .historical_import_run import (
    HistoricalImportRun,
    HistoricalImportSource,
    HistoricalImportStatus,
)
from .historical_iv import HistoricalIV
from .index_constituent import IndexConstituent
from .institutional_holding import InstitutionalHolding

# Instruments & Market Data
from .instrument import Instrument, InstrumentType

# Margin Interest Tracking
from .margin_interest import MarginInterest
from .market.options_chain_snapshot import OptionsChainSnapshot
from .market_data import (
    EarningsCalendarEvent,
    JobRun,
    MarketRegime,
    MarketSnapshot,
    MarketSnapshotHistory,
    PriceData,
)
from .market_tracked_plan import MarketTrackedPlan

# MCP (Model Context Protocol) bearer tokens for read-only AI agent access
from .mcp_token import MCPToken

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

# Narrative
from .narrative import PortfolioNarrative

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
from .option_tax_lot import OptionTaxLot

# Options Trading
from .options import Option, OptionType
from .order import Order, OrderSide, OrderStatus, OrderType

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
    PicksAuditLog,
    PickStatus,
    PositionChange,
    SourceAttribution,
    SourceType,
    ValidatedPick,
)
from .plaid_connection import PlaidConnection, PlaidConnectionStatus

# Portfolio Management
from .portfolio import Category, PortfolioHistory, PortfolioSnapshot, PositionCategory

# Trading & Positions
from .position import Position, PositionStatus, PositionType, Sleeve

# Data Quality (multi-source quorum + per-provider drift)
from .provider_quorum import (
    ProviderDriftAlert,
    ProviderQuorumLog,
    QuorumAction,
    QuorumStatus,
)
from .shadow_order import ShadowOrder, ShadowOrderStatus

# Strategy & Signals (required for User.strategies / User.strategy_executions)
from .strategy import Strategy, StrategyExecution

# Symbol Master — single source of truth for symbol identity over time.
# Global table (no user_id); see app/services/symbols/ for callers.
from .symbol_master import (
    AliasSource,
    AssetClass,
    SymbolAlias,
    SymbolChangeType,
    SymbolHistory,
    SymbolMaster,
    SymbolStatus,
)

# Tax Lots & Cost Basis
from .tax_lot import TaxLot, TaxLotMethod, TaxLotSource
from .trade import Trade, TradeSignal
from .trade_decision_explanation import TradeDecisionExplanation

# Transactions & Dividends
from .transaction import Dividend, Transaction, TransactionType

# Transfers & Position Movements
from .transfer import Transfer, TransferType
from .user import User, UserRole
from .user_invite import UserInvite
from .walk_forward_study import WalkForwardStatus, WalkForwardStudy

# Watchlist
from .watchlist import Watchlist

# Essential models list
__all__ = [
    "Base",
    "User",
    "UserRole",
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
    "BrokerAccountRiskProfile",
    "BrokerOAuthConnection",
    "OAuthBrokerType",
    "OAuthConnectionStatus",
    "PlaidConnection",
    "PlaidConnectionStatus",
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
    "Sleeve",
    "ConvictionPick",
    "TaxLot",
    "TaxLotMethod",
    "TaxLotSource",
    "OptionTaxLot",
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
    "ShadowOrder",
    "ShadowOrderStatus",
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
    "ExternalSignal",
]
