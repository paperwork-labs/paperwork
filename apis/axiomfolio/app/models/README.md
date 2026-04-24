# AxiomFolio Models Architecture
## Portfolio Data Sync & Management

This document explains the data model architecture for AxiomFolio's comprehensive portfolio sync system, focused on multi-brokerage integration with IBKR FlexQuery and real-time trading.

---

## 🏗️ **CORE ARCHITECTURE OVERVIEW**

### **Data Flow:**
```
User → BrokerAccount → [Instruments] → Positions → Portfolio Snapshots
              ↓
    Trades & Transactions → TaxLots → AccountBalances
              ↓
    MarginInterest & Transfers (FlexQuery Enhanced)
```

---

## 📊 **PORTFOLIO SYNC MODELS**

### **1. User Management**

#### **`user.py` - User Authentication & Access**
**Purpose**: Multi-user system with role-based access
```python
User(email="user@example.com", role="ADMIN", is_active=True)
```
- **Roles**: ADMIN, USER, READONLY
- **Features**: Authentication, preferences, data isolation
- **Relationships**: Owns all accounts and positions

---

### **2. Account Management**

#### `broker_account.py` - Broker Account Management (Broker-Agnostic)
**Purpose**: Multi-brokerage account integration
```python
BrokerAccount(user_id=1, account_number="U19491234", broker="IBKR")
```
- **Supports**: IBKR, Tastytrade, future brokerages
- **Features**: API credentials, sync status, account metadata
- **Key Fields**: account_number, broker_type, sync_status

#### **`portfolio.py` - Portfolio Snapshots & Categorization**
**Purpose**: Historical portfolio metrics and custom categories
```python
PortfolioSnapshot(account_id=1, total_value=500000, unrealized_pnl=25000)
```
- **Features**: Account categorization, portfolio snapshots
- **Holdings**: Aggregated position views
- **History**: Daily portfolio performance tracking

#### **`account_balance.py` - Enhanced Account Balances**
**Purpose**: Comprehensive account financial state (IBKR FlexQuery Account Information - 47 fields)
```python
AccountBalance(net_liquidation_value=500000, buying_power=250000, margin_used=50000)
```
- **Features**: Cash balances, margin info, buying power
- **Multi-currency**: Support for all currency exposures
- **Risk metrics**: Margin utilization, PDT status

---

### **3. Instrument & Position Management**

#### **`instrument.py` - Master Security Reference**
**Purpose**: Universal catalog of all tradeable securities
```python
Instrument(symbol="AAPL", type="STOCK", exchange="NASDAQ")
Instrument(symbol="AAPL240315C00150000", type="OPTION", underlying="AAPL")
```
- **Universal**: Stocks, options, futures, bonds, ETFs
- **Key Features**: Options link to underlying securities
- **Identifiers**: CUSIP, ISIN, CONID for cross-reference

#### **`position.py` - Current Equity Positions**
**Purpose**: Real-time equity (stocks/ETFs) positions with P&L tracking
```python
Position(symbol="AAPL", quantity=1001, average_cost=150.25, market_value=175313.00)
```
- **Real-time**: Current prices, market values, P&L
- **Risk metrics**: Position sizing, Greeks (options), sector exposure
- **Performance**: Unrealized P&L, day changes

#### **`options.py` - Options-Specific Data** 
**Purpose**: Options contracts (per-contract state) and exercise/assignment tracking (IBKR FlexQuery Option Exercises)
```python
Option(symbol="AAPL", strike=150, expiry="2024-03-15", option_type="CALL")
```
- **Exercise tracking**: Exercise dates, assignments, expirations
- **Multi-brokerage**: IBKR and Tastytrade support
- **Greeks**: Delta, gamma, theta, vega for risk management

---

### **4. Transaction & Tax Tracking**

#### **`trade.py` - Trading Activity**
**Purpose**: Individual buy/sell trading orders and strategy execution
```python
Trade(symbol="AAPL", side="BUY", quantity=100, price=150.25, strategy="ATR_ENTRY")
```
- **Strategy integration**: Entry/exit signals, stop losses
- **P&L tracking**: Realized gains/losses from trading
- **Risk management**: Position sizing, ATR distances

#### **`transaction.py` - Cash Flow Tracking**
**Purpose**: Complete cash transaction history (IBKR FlexQuery Cash Transactions - 45 fields)
```python
Transaction(type="DIVIDEND", symbol="AAPL", amount=50.25)
Transaction(type="BUY", symbol="AAPL", amount=-15025.00)
Transaction(type="COMMISSION", amount=-1.00)
```
- **Comprehensive**: All cash movements (trades, dividends, fees, taxes)
- **Tax reporting**: Essential for accurate cost basis
- **Corporate actions**: Splits, mergers, spin-offs

#### **`tax_lot.py` - Cost Basis Tracking**
**Purpose**: Individual tax lots for accurate cost basis (IBKR FlexQuery Trades with Closed Lots)
```python
TaxLot(symbol="AAPL", quantity=500, cost_basis=75125.50, acquisition_date="2024-01-15")
```
- **FIFO/LIFO**: Multiple accounting methods
- **Wash sales**: Automatic wash sale tracking
- **Real data**: Direct from IBKR FlexQuery trades

---

### **5. FlexQuery Enhanced Models** 
#### **`margin_interest.py` - Margin Cost Tracking**
**Purpose**: Margin borrowing costs (IBKR FlexQuery Interest Accruals - 11 fields)
```python
MarginInterest(from_date="2024-01-01", interest_accrued=125.50, interest_rate=5.5)
```
- **Cost tracking**: Daily margin interest calculations
- **Rate monitoring**: Interest rate changes over time
- **P&L impact**: Accurate margin cost allocation

#### **`transfer.py` - Position Transfers**
**Purpose**: Inter-account position movements (IBKR FlexQuery Transfers - 84 fields)
```python
Transfer(symbol="AAPL", quantity=100, direction="INCOMING", transfer_company="SCHWAB")
```
- **Position tracking**: Account-to-account transfers
- **Cost basis**: Proper cost basis transfer handling
- **Corporate actions**: Transfer-related corporate events

---

## 🔄 **KEY RELATIONSHIPS**

### **Data Dependencies:**
1. **User** → owns → **BrokerAccounts** → contain → **Positions** (equities) and **Options** (contracts)
2. **Instruments** ← reference ← **Positions**
3. **Trades** → generate → **Transactions** → create → **TaxLots**
4. **AccountBalances** ← sync from ← **BrokerAccount** → powers → **PortfolioSnapshots**

### **FlexQuery Integration:**
- **Account Information** → AccountBalance
- **Cash Transactions** → Transaction, Dividend
- **Interest Accruals** → MarginInterest
- **Transfers** → Transfer
- **Option Exercises** → Option
- **Open Positions** → Position (equities), Option (contracts)
- **Trades** → Trade, TaxLot

---

## 📋 **MODEL STATUS**

### **✅ COMPLETE (Production Ready):**
- `user.py` - User management
- `broker_account.py` - Broker accounts (multi-brokerage)
- `portfolio.py` - Portfolio snapshots & categorization
- `account_balance.py` - Enhanced account balances
- `instrument.py` - Security master
- `position.py` - Current equity positions
- `options.py` - Options tracking
- `transaction.py` - Cash transactions
- `tax_lot.py` - Cost basis
- `margin_interest.py` - Margin costs
- `transfer.py` - Position transfers
- `strategy.py` - Trading strategies
- `market_data.py` - Market data feeds
- `signals.py` - Trading signals
- `notification.py` - User notifications
- `alert.py` - System alerts
- `audit.py` - Audit logging

### **🚧 NEXT UP (Planned Enhancements):**
- **Model versioning / migrations 2.0** – automatic migration helpers
- **Historical fundamentals** – separate `fundamental_data.py` model for multi-provider fundamentals
- **Risk analytics** – VaR / stress-test result models
- **Machine-learning feature store** – schema for training data

---

## 🎯 **PRACTICAL EXAMPLE**

### **Your Live Data Flow:**
```python
# User (You)
User(id=1, email="your@email.com", role="ADMIN")

# Your IBKR Accounts  
BrokerAccount(user_id=1, account_number="IBKR_TAXABLE_PLACEHOLDER")
BrokerAccount(user_id=1, account_number="IBKR_IRA_PLACEHOLDER")

# Your AAPL Position
Instrument(symbol="AAPL", type="STOCK")
Position(user_id=1, account_id="IBKR_TAXABLE_PLACEHOLDER", symbol="AAPL", quantity=1001)

# Your AAPL Purchase
Trade(symbol="AAPL", side="BUY", quantity=1001)
Transaction(type="BUY", symbol="AAPL", amount=-150251.00)

# Your Tax Lots (from FlexQuery)
TaxLot(symbol="AAPL", quantity=500, cost_basis=75125.50)
TaxLot(symbol="AAPL", quantity=501, cost_basis=75125.50)  # Total: 1001 shares

# Your Account Balance
AccountBalance(net_liquidation_value=500000, buying_power=250000)
```

This architecture ensures:
- ✅ **Accurate cost basis tracking** (your AAPL 1,001 shares test)
- ✅ **Multi-account support** (multiple IBKR accounts)
- ✅ **Real-time portfolio monitoring**
- ✅ **Complete tax reporting** (all transactions & lots)
- ✅ **Future scalability** (additional users & brokerages) 