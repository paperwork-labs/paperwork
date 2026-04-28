---
owner: engineering
last_reviewed: 2026-04-21
doc_kind: spec
domain: trading
status: active
---
# v1 Phase 3 — Execution Engineering Spec

**Status**: DRAFT — for founder-supervised implementation session
**Owner**: Staff Engineer (Opus orchestrator)
**Milestone**: v1 (target 2026-06-21)
**Phase**: 3 — Execution (TRIM/ADD, rebalance, tax-aware exits, signal-to-order, heat guard, per-user breaker, brackets, adaptive trailing)
**Predecessor**: `docs/axiomfolio/plans/MASTER_PLAN_2026.md` Phase 3 (`p3a`, `p3b`, `p3c`)
**Reference rules**: `.cursor/rules/protected-regions.mdc`, `.cursor/rules/portfolio-manager.mdc`, `.cursor/rules/risk-manager.mdc`, `.cursor/rules/capital-allocator.mdc`, `.cursor/rules/microstructure.mdc`

> **Note (D128, 2026-04-21)**: Alpaca was dropped from the broker roster (see `docs/KNOWLEDGE.md` D128). References to `alpaca_executor.py`, `AlpacaExecutor`, and Alpaca bracket-order semantics elsewhere in this document are historical; the roadmap targets IBKR, Schwab, TastyTrade, plus Phase 1 additions E*TRADE / Tradier / Coinbase.

This document is a precise engineering plan for the founder-supervised execution session. It cites real existing code, defines new code by signature, names every test fixture, and prescribes a merge order that minimizes coupling risk. It does NOT modify any code; that happens during the supervised session.

---

## 1. Goals and Non-Goals

### Component goals

| Component | Goal |
|---|---|
| TRIM / ADD as `OrderType` extension | Express partial-position changes as first-class order intents that flow through the existing `OrderManager` -> `RiskGate` -> `BrokerRouter` path. |
| `RebalanceEngine` | Compute the ordered set of `OrderIntent` objects required to move a current portfolio toward a target weight vector under explicit constraints. |
| Tax-aware exit selector | Make every SELL select tax lots optimally (default HIFO + wash-sale-aware), driven by the existing `TaxLossHarvester`. |
| `SignalToOrder` generator | Convert an `auto_execute=true` validated pick into an `OrderIntent` sized by tier, regime, stage, and stop. |
| `PortfolioHeatGuard` | Add a per-user volatility-weighted exposure cap on top of the existing 6% stop-distance portfolio heat gate. |
| Per-user circuit breaker | Replace the global module-level `circuit_breaker` singleton with per-user state, thresholds, and kill switch. |
| Bracket orders (OCO) | Submit entry + stop + target as a coupled order group, native where the broker supports it, client-orchestrated otherwise. |
| Adaptive trailing stop manager | Use per-pick custom stops and ATR-based trail multipliers in long-running stop management, leveraging the existing `_tier2_trailing_stop` and `_tier7_regime_trail` logic. |

### Non-goals

- TRIM and ADD do **not** bypass `RiskGate`. Both flow through the existing single execution path.
- The `RebalanceEngine` is **PREVIEW** by default. EXECUTE mode requires an explicit `confirm=true` flag plus founder-only API scope.
- Tax-aware exit selection does **not** override the existing `_check_wash_sale_risk` warning in `PreTradeValidator`; it adds lot selection on top.
- `SignalToOrder` does **not** auto-submit when the regime gate or stage cap blocks; it returns an empty intent list with structured reasons.
- `PortfolioHeatGuard` does **not** replace `PreTradeValidator._check_portfolio_heat` (6% stop-distance heat). It adds a second, additive cap that must also pass.
- Per-user circuit breaker does **not** remove the global kill switch; it adds a per-user kill switch under the global one. Global kill always wins.
- Bracket orders and adaptive trailing stops do **not** alter exit-cascade tier semantics. They are how the system **places and adjusts** the orders; the cascade continues to decide the **action**.
- No live broker writes are introduced by this spec. Everything ships behind `ALLOW_LIVE_ORDERS` and `paper-shadow` validation per `.cursor/rules/portfolio-manager.mdc`.

---

## 2. DANGER ZONE Acknowledgment

Per `.cursor/rules/protected-regions.mdc`, all changes proposed in this spec require founder line-by-line review.

### Existing files under `app/services/execution/`

| File | Current responsibility |
|---|---|
| `app/services/execution/order_manager.py` | Single execution path. `OrderManager.preview` and `OrderManager.submit` orchestrate `RiskGate.check`, `PreTradeValidator.validate`, broker preview/place via `broker_router`, slippage capture, and circuit-breaker fill recording. |
| `app/services/execution/risk_gate.py` | Stateless pre-trade risk checker. Holds `MAX_ORDER_VALUE`, `MAX_SINGLE_POSITION_PCT`, `STAGE_CAPS`, `compute_position_size` (Stage Analysis Section 9 sizing formula), and `RiskViolation`. |
| `app/services/execution/exit_cascade.py` | 9-tier long exit cascade (`_tier1_stop_loss` ... `_tier9_r5_full_exit`) plus 4-tier short exit cascade (`_short_s1_stage_improvement` ... `_short_s4_target`). `evaluate_exit_cascade` selects the highest-urgency action. |
| `app/services/execution/broker_base.py` | Protocol for brokers. Defines `ActionSide`, `IBOrderType`, `ORDER_TYPE_MAP`, `OrderRequest`, `OrderResult`, `PreviewResult`, and `BrokerExecutor`. |
| `app/services/execution/broker_router.py` | Resolves broker name to executor instance (`broker_router.get(broker_type)`). |
| `app/services/execution/ibkr_executor.py` | IBKR live executor implementing `BrokerExecutor`. |
| `app/services/execution/alpaca_executor.py` | Alpaca executor implementing `BrokerExecutor`. |
| `app/services/execution/paper_executor.py` | Paper-trading executor used when `ALLOW_LIVE_ORDERS` is false. |
| `app/services/execution/broker_adapter.py` | Compatibility layer between legacy callers and the `BrokerExecutor` protocol. |
| `app/services/execution/approval_service.py` | Trade approval workflow. Defines `ApprovalMode` (`ALL`, `THRESHOLD`, `ANALYST_ONLY`, `NONE`) and `ApprovalService.requires_approval`. |
| `app/services/execution/slippage_tracker.py` | Per-symbol, per-strategy, per-venue slippage rollups consumed by execution analytics. |
| `app/services/execution/__init__.py` | Public surface for the package. |

### Existing files under `app/services/risk/`

| File | Current responsibility |
|---|---|
| `app/services/risk/circuit_breaker.py` | Module-level `circuit_breaker = CircuitBreaker()` singleton with Redis-backed tiered state (`tier1_loss_pct=2.0`, `tier2_loss_pct=3.0`, `tier3_loss_pct=5.0`), trading-day reset, kill switch, and `record_fill` accounting. State keys are global (`circuit:daily_pnl`, `circuit:order_count`, `circuit:kill_switch`, etc.). |
| `app/services/risk/pre_trade_validator.py` | Aggregate `PreTradeValidator` running circuit breaker, position limit, sector concentration, price collar, order rate limit, wash-sale warning, and stop-distance portfolio heat (`MAX_PORTFOLIO_HEAT_PCT = 0.06`). |
| `app/services/risk/__init__.py` | Public surface for the package. |

> All edits to any file above require founder line-by-line review per the iron law in `.cursor/rules/protected-regions.mdc` and `AGENTS.md` "DANGER ZONES".

---

## 3. TRIM and ADD as `OrderType` extension

### Current order-type surface (verbatim)

From `app/services/execution/broker_base.py`:

```30:59:app/services/execution/broker_base.py
@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: ActionSide
    order_type: IBOrderType
    quantity: float
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    account_id: Optional[str] = None

    @classmethod
    def from_user_input(
        cls,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        account_id: Optional[str] = None,
    ) -> "OrderRequest":
        return cls(
            symbol=symbol.upper(),
            side=ActionSide.BUY if side.lower() == "buy" else ActionSide.SELL,
            order_type=ORDER_TYPE_MAP.get(order_type.lower(), IBOrderType.MKT),
            quantity=quantity,
            limit_price=limit_price,
            stop_price=stop_price,
            account_id=account_id,
        )
```

```10:27:app/services/execution/broker_base.py
class ActionSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class IBOrderType(str, Enum):
    MKT = "MKT"
    LMT = "LMT"
    STP = "STP"
    STP_LMT = "STP_LMT"


ORDER_TYPE_MAP = {
    "market": IBOrderType.MKT,
    "limit": IBOrderType.LMT,
    "stop": IBOrderType.STP,
    "stop_limit": IBOrderType.STP_LMT,
}
```

`OrderRequest.order_type` is the broker-facing primitive. TRIM and ADD are **trade intents**, not new IBKR primitives. Modeling them as a new `IBOrderType` would couple intent to broker translation. Modeling them as a new layer is correct.

### Proposed design

Introduce `IntentKind` separate from `IBOrderType`:

```python
# new in app/services/execution/intent.py
class IntentKind(str, Enum):
    NEW = "NEW"          # default, equivalent to today's behavior
    ADD = "ADD"          # buy to bring an existing position to target weight
    TRIM = "TRIM"        # sell N% of an existing position without closing it
    EXIT = "EXIT"        # full close (hint to lot selector and risk gate)


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    side: ActionSide
    kind: IntentKind = IntentKind.NEW
    target_weight_pct: Optional[Decimal] = None  # required when kind == ADD
    trim_fraction: Optional[Decimal] = None      # 0 < x <= 1; required when kind == TRIM
    order_type: IBOrderType = IBOrderType.MKT
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    account_id: Optional[str] = None
    reason: Optional[str] = None                 # free text for audit
```

`OrderIntent` is resolved into one or more `OrderRequest` objects by `OrderManager`:

- `IntentKind.NEW` resolves directly (current behavior).
- `IntentKind.ADD(target_weight_pct=W)` reads current position dollar value and equity, computes `delta_dollars = (W * equity) - current_position_value`, converts to shares using `RiskGate.estimate_price`, and produces a single BUY `OrderRequest`. `RiskGate.check` runs unmodified; `MAX_SINGLE_POSITION_PCT` and `STAGE_CAPS` continue to apply.
- `IntentKind.TRIM(trim_fraction=F)` reads current position quantity, computes `qty = round_half_down(current_quantity * F)`, and produces a single SELL `OrderRequest`. If the rounded quantity is zero, returns a clean structured error (no broker call).
- `IntentKind.EXIT` produces a SELL for `current_quantity` and tags the resulting `Order.source = "exit"` so the tax-lot selector applies the loss-harvest preference (see Section 5).

### Proposed signature changes (additive only)

```python
class OrderManager:
    async def preview(self, db, req, user_id, broker_type="ibkr",
                      risk_budget=None, portfolio_equity=None,
                      *, intent: Optional[OrderIntent] = None) -> Dict[str, Any]: ...

    async def submit(self, db, order_id, user_id) -> Dict[str, Any]: ...

    # NEW
    async def place_intent(self, db, intent: OrderIntent, user_id: int,
                           broker_type: str = "ibkr") -> Dict[str, Any]:
        """Resolve OrderIntent -> one or more OrderRequest, then run preview + submit."""
```

`place_intent` is the single new entry point. It does not change the existing `preview` / `submit` semantics; old callers continue to pass `OrderRequest` directly.

### Risk gate interaction

| Intent | RiskGate behavior |
|---|---|
| `ADD` | Full check. `MAX_SINGLE_POSITION_PCT` (`risk_gate.py` line 35) and `STAGE_CAPS` (`risk_gate.py` lines 39-50) constrain the BUY. If `_check_stage_regime_sizing` would block, `ADD` returns a structured rejection rather than a partial fill. |
| `TRIM` | Reduced check: skip `_check_stage_regime_sizing` (sizing applies to entries, not to reducing exposure) and skip `MAX_SINGLE_POSITION_PCT` (TRIM cannot increase exposure). Still enforce `MAX_ORDER_VALUE`, price collar, circuit breaker, and order rate limit. **No bypass of `OrderManager` -> `RiskGate` -> `BrokerRouter`** (iron law). |
| `EXIT` | Same as TRIM: only checks that protect against fat-finger and breaker-tripped conditions. |

These exemptions are encoded as named flags on `RiskGate.check`:

```python
def check(self, req, price_estimate, db=None, portfolio_equity=None,
          risk_budget=None, *,
          allow_reducing: bool = False) -> List[str]:
    # when allow_reducing is True, skip _check_stage_regime_sizing
    # and skip the MAX_SINGLE_POSITION_PCT branch
```

`allow_reducing` is set by `OrderManager.place_intent` only for `IntentKind.TRIM` and `IntentKind.EXIT`. It is not exposed on `OrderManager.preview` or `OrderManager.submit`. This keeps the relaxation off the default path.

### Test fixtures (PR `feat/v1-trim-add-orders`)

Located in `backend/tests/services/execution/test_order_intent.py`.

| Fixture | Asserts |
|---|---|
| `test_intent_kind_new_routes_through_existing_path` | `place_intent(IntentKind.NEW)` produces the same broker payload as the current `preview` + `submit` flow. |
| `test_trim_25pct_of_aapl_at_market` | TRIM with `trim_fraction=Decimal("0.25")` of a 100-share AAPL position produces a 25-share SELL MKT order; `RiskGate.check` is called with `allow_reducing=True`. |
| `test_trim_zero_qty_position_returns_clean_error` | TRIM against a zero-quantity position returns `{"error": "TRIM rejected: position quantity is zero"}` and never calls the broker. |
| `test_trim_rounds_half_down_to_avoid_overselling` | TRIM 33% of 7 shares produces 2 shares (not 3); never sells more than held. |
| `test_trim_below_min_lot_returns_clean_error` | TRIM that rounds to zero shares (e.g., 1% of 10 shares) returns a clean structured error and does not submit. |
| `test_add_to_target_weight_blocks_at_max_position_pct` | ADD targeting 20% of equity when `MAX_SINGLE_POSITION_PCT=0.15` raises `RiskViolation` from `RiskGate`. |
| `test_add_to_target_weight_blocks_at_stage_cap` | ADD on a 3B-stage symbol in any regime raises `RiskViolation` (stage cap = 0). |
| `test_add_to_target_when_already_at_target_returns_no_op` | ADD with `target_weight_pct` equal to current weight returns `{"status": "no_op"}` and does not submit. |
| `test_exit_intent_marks_order_source_exit` | `IntentKind.EXIT` results in an `Order` row with `source="exit"`, picked up by the tax-lot selector. |
| `test_intent_circuit_breaker_blocks_add` | ADD when `circuit_breaker.can_trade(is_exit=False)` returns `False` is rejected with the breaker reason; TRIM and EXIT in the same state are still allowed at tier 2. |

All test names follow `test_<scenario>_<expected>`.

---

## 4. Rebalance Engine

### Module: `app/services/execution/rebalance_engine.py` (NEW)

Not yet existing. Add as a new file. No edits to existing execution files.

```python
@dataclass(frozen=True)
class RebalanceConstraints:
    max_single_order_pct: Decimal = Decimal("0.05")     # no single trade > 5% of equity
    max_total_turnover_pct: Decimal = Decimal("0.20")   # no rebalance > 20% of equity
    dont_trade_below_dollars: Decimal = Decimal("100")  # skip dust trades
    prefer_existing_lots: bool = True                    # respect tax-aware lot selector on sells
    drift_threshold_pct: Decimal = Decimal("0.05")      # only rebalance positions drifted > 5% absolute weight
    block_wash_sales: bool = True                        # block sells that would create wash sales (warn + accept override otherwise)


@dataclass(frozen=True)
class RebalancePlan:
    intents: list[OrderIntent]
    skipped: list[tuple[str, str]]   # (symbol, reason)
    estimated_realized_gain: Decimal
    estimated_realized_loss: Decimal
    estimated_total_turnover: Decimal
    rationale: str                    # human-readable summary


class RebalanceEngine:
    PREVIEW = "preview"   # default
    EXECUTE = "execute"   # requires explicit founder-approval flag at API layer

    def compute_intents(
        self,
        db: Session,
        user_id: int,
        target_weights: dict[str, Decimal],   # symbol -> 0..1, must sum to <= 1
        constraints: RebalanceConstraints = RebalanceConstraints(),
    ) -> RebalancePlan: ...

    async def execute_plan(
        self,
        db: Session,
        user_id: int,
        plan: RebalancePlan,
        *,
        confirm: bool,                     # must be True; API layer requires founder role
    ) -> list[Dict[str, Any]]: ...
```

Algorithm (PREVIEW):

1. Load current positions for `user_id`. Sum market value -> `equity`.
2. For each `(symbol, target)` in `target_weights`: compute `current_weight = position_market_value / equity`. If `abs(current - target) < drift_threshold_pct` -> skip with reason `below_drift_threshold`.
3. Convert weight delta to dollar delta. If `abs(delta_dollars) < dont_trade_below_dollars` -> skip with reason `below_min_dollar_threshold`.
4. Cap `abs(delta_dollars)` at `max_single_order_pct * equity`. If capped, record reason `partial_only_cap`.
5. Convert dollar delta to `OrderIntent` using `IntentKind.ADD` (positive delta) or `IntentKind.TRIM` with `trim_fraction = abs(delta_dollars) / current_position_value` (negative delta).
6. For each SELL intent, run `TaxLossHarvester.check_wash_sale_risk(symbol, "sell")`. If `risk_level == "blocked"` and `constraints.block_wash_sales` -> skip with reason `wash_sale_blocked`.
7. Compute total turnover = `sum(abs(delta_dollars))`. If `> max_total_turnover_pct * equity` -> truncate the intent list in priority order (largest absolute drift first) until under cap; record skipped tail with reason `over_turnover_cap`.
8. Estimate realized gain/loss using HIFO lot preview from `TaxLossHarvester` (no DB writes).
9. Return `RebalancePlan`. **No broker calls.** **No DB inserts** of `Order` rows.

`execute_plan(confirm=True)` iterates `plan.intents` and calls `OrderManager.place_intent` in sequence (not parallel; rebalance is rare, sequential keeps per-symbol locks simple). API layer must enforce founder role before allowing `confirm=True`.

### Test fixtures (PR `feat/v1-rebalance-engine`)

Located in `backend/tests/services/execution/test_rebalance_engine.py`.

| Fixture | Asserts |
|---|---|
| `test_rebalance_no_change_returns_empty` | Current weights equal targets within drift threshold; `plan.intents == []`, `plan.skipped` lists every symbol with reason `below_drift_threshold`. |
| `test_rebalance_to_60_40_from_80_20_produces_correct_orders` | Two positions (AAPL 80%, MSFT 20%) targeting (60%, 40%) on $100K equity yields one TRIM AAPL ~$20K and one ADD MSFT ~$20K, both within `max_single_order_pct`. |
| `test_rebalance_below_drift_threshold_skips_position` | Position drifted 3% with default `drift_threshold_pct=0.05` is skipped; reason `below_drift_threshold`. |
| `test_rebalance_dust_trade_skipped` | Computed delta of $50 with default `dont_trade_below_dollars=100` is skipped; reason `below_min_dollar_threshold`. |
| `test_rebalance_caps_at_max_single_order_pct` | A single intent that would be 8% of equity with `max_single_order_pct=0.05` is capped at 5%; remainder logged in `plan.rationale`. |
| `test_rebalance_truncates_at_max_turnover_pct` | Total turnover 30% with cap 20% truncates lowest-priority intents until under 20%; truncated entries appear in `skipped`. |
| `test_rebalance_blocks_wash_sale_when_block_wash_sales_true` | Sell of a symbol in an active wash-sale window is omitted; reason `wash_sale_blocked`. |
| `test_rebalance_warns_wash_sale_when_block_wash_sales_false` | Same input with `block_wash_sales=False` produces the intent and adds a warning to `plan.rationale`. |
| `test_rebalance_preview_does_not_place_any_orders` | Calling `compute_intents` does not insert any `Order` rows and does not call `broker_router.get`. |
| `test_rebalance_execute_requires_confirm_true` | `execute_plan(plan, confirm=False)` raises `ValueError("rebalance execute requires confirm=True")`. |
| `test_rebalance_execute_runs_intents_sequentially` | `execute_plan(plan, confirm=True)` calls `OrderManager.place_intent` once per intent in order; failure of intent N does not invoke intent N+1 (caller decides whether to continue). |

---

## 5. Tax-Aware Exit Selector

### Wire `TaxLossHarvester` into `OrderManager` for SELL orders

`app/services/portfolio/tax_loss_harvester.py` already implements wash-sale tracking, substantially-identical mapping, and per-position evaluation (`HarvestOpportunity`). What is missing is **lot selection on the sell path**.

Add a new module `app/services/portfolio/lot_selector.py`:

```python
class LotMethod(str, Enum):
    HIFO = "HIFO"                       # highest cost basis first; default
    LIFO = "LIFO"                       # most recent first
    FIFO = "FIFO"                       # oldest first
    SPECIFIC = "SPECIFIC"               # caller passes lot_ids
    HIFO_WASH_SAFE = "HIFO_WASH_SAFE"   # HIFO, but skip lots that would trigger wash sale
    LOSS_HARVEST = "LOSS_HARVEST"       # prefer largest unrealized loss; respects wash sale


@dataclass(frozen=True)
class LotSelection:
    lot_ids: list[int]
    quantities: list[Decimal]
    estimated_realized_gain: Decimal       # positive = gain, negative = loss
    holding_period_days: list[int]
    triggers_wash_sale: bool
    wash_sale_reason: Optional[str]


class LotSelector:
    DEFAULT_METHOD = LotMethod.HIFO_WASH_SAFE

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.harvester = TaxLossHarvester(db, user_id)

    def select(
        self,
        symbol: str,
        quantity: Decimal,
        method: LotMethod = DEFAULT_METHOD,
        specific_lot_ids: Optional[list[int]] = None,
    ) -> LotSelection: ...
```

### Integration point in `OrderManager`

Add a SELL hook in `OrderManager.submit` (the existing flow already has the right spot, between PreTradeValidator and broker.place):

```python
# pseudocode at the SELL branch in submit()
if order.side.lower() == "sell":
    selector = LotSelector(db, user_id)
    method = LotMethod(order.lot_method or selector.DEFAULT_METHOD.value)
    selection = selector.select(order.symbol, Decimal(adjusted_quantity), method)
    order.selected_lot_ids = selection.lot_ids
    order.estimated_realized_gain = selection.estimated_realized_gain
    if selection.triggers_wash_sale and not order.allow_wash_sale_override:
        order.status = OrderStatus.REJECTED.value
        order.error_message = f"Wash sale would be triggered: {selection.wash_sale_reason}"
        db.commit()
        return _order_to_dict(order)
```

The existing `PreTradeValidator._check_wash_sale_risk` (advisory warning at order intake) is kept; the new lot selector is the **enforcement** point at submit time.

New columns on `app/models/order.py` (separate Alembic migration; reserve revision number when implementing - do **not** pick now):

- `lot_method: str` (default `"HIFO_WASH_SAFE"`)
- `selected_lot_ids: JSON` (list of `tax_lot.id`)
- `estimated_realized_gain: Numeric(18, 4)` (signed)
- `allow_wash_sale_override: bool` (default `False`, founder UI toggle)

### Test fixtures (PR `feat/v1-tax-aware-exits`)

Located in `backend/tests/services/portfolio/test_lot_selector.py` and `backend/tests/services/execution/test_order_manager_lot_selection.py`.

| Fixture | Asserts |
|---|---|
| `test_hifo_selects_highest_cost_lot_first` | Three lots at $100, $120, $90 cost; selling 1 share picks the $120 lot. |
| `test_lifo_selects_most_recent_lot_first` | Three lots over 60 days; selling 1 share picks the newest. |
| `test_fifo_selects_oldest_lot_first` | Same setup; selling 1 share picks the oldest. |
| `test_hifo_wash_safe_skips_wash_sale_lot` | Highest-cost lot is in an active wash-sale window; selector picks the next-highest non-conflicting lot. |
| `test_loss_harvest_prefers_largest_unrealized_loss` | Three lots, one with a $500 unrealized loss; selector picks that lot first. |
| `test_specific_lot_passes_through` | `LotMethod.SPECIFIC` with explicit `specific_lot_ids` returns exactly those. |
| `test_specific_lot_quantity_mismatch_raises` | Specific lot quantities sum to less than requested quantity raises `ValueError`. |
| `test_order_manager_sell_invokes_lot_selector` | `OrderManager.submit` on a SELL order populates `order.selected_lot_ids` and `order.estimated_realized_gain` before broker call. |
| `test_order_manager_sell_blocks_wash_sale_without_override` | Sell that would trigger a wash sale rejects with `OrderStatus.REJECTED` when `allow_wash_sale_override=False`. |
| `test_order_manager_sell_allows_wash_sale_with_override` | Same input with `allow_wash_sale_override=True` proceeds and records `triggers_wash_sale=True` in audit log. |
| `test_lot_selector_known_wash_sale_substantially_identical` | Selling SPY when IVV was bought 10 days ago (substantially identical, per `_build_identical_map`) flags wash sale. |
| `test_lot_selector_short_term_vs_long_term_split` | Selecting across two lots (one short-term, one long-term) returns correct `holding_period_days` per lot. |

---

## 6. `SignalToOrder` Generator

### Purpose

Convert a validated pick (`auto_execute=true`) into an `OrderIntent` that flows through the existing single execution path.

### Module: `app/services/strategy/signal_to_order.py` (NEW)

```python
@dataclass(frozen=True)
class SignalToOrderResult:
    intents: list[OrderIntent]                # zero or more
    rejection_reasons: list[str]              # why no intents (regime, stage, breaker)
    sizing_breakdown: dict[str, Decimal]      # equity, atr_size, stage_cap, heat_remaining, final


class SignalToOrder:
    # tier defaults: % of equity per pick
    TIER_DEFAULTS = {
        "free": Decimal("0"),
        "pro": Decimal("0.02"),       # 2%
        "pro_plus": Decimal("0.05"),  # 5%
        "quant_desk": None,           # per-pick override required
    }

    def generate(
        self,
        db: Session,
        user_id: int,
        pick: ValidatedPick,
        portfolio_equity: Decimal,
    ) -> SignalToOrderResult: ...
```

### Sizing pipeline (in order)

1. **Tier default**: `target_dollars = TIER_DEFAULTS[user.tier] * equity`. Quant Desk requires `pick.suggested_size_pct_of_equity` (otherwise reject with reason `quant_desk_requires_per_pick_size`).
2. **ATR-based ceiling**: call `compute_position_size(...)` from `risk_gate.py` with `risk_budget = equity * 0.01` (1% per-trade cap from `.cursor/rules/risk-manager.mdc`), `atrp_14`, `stop_multiplier = max(2.0, pick.stop_distance_atr)`, `regime_state`, `stage_label`, `current_price`. Take `min(target_dollars, full_position_dollars * stage_cap)`.
3. **Stage gate**: if `STAGE_CAPS[clean_stage][regime_state] == 0` -> reject with reason `stage_blocked` (no intent generated).
4. **Regime gate**: if `pick.tier_label not in REGIME_LONG_ACCESS[regime_state]` (from `app/services/market/scan_engine.py`) -> reject with reason `regime_blocked`. R5 always blocks longs.
5. **Heat remaining**: query `PortfolioHeatGuard.remaining(user_id, equity)` (Section 7); cap dollars at `min(dollars_so_far, heat_remaining)`. If `heat_remaining <= 0` -> reject with reason `heat_cap_reached`.
6. **Stop placement**: compute `stop_price = max(pick.stated_stop, current_price - 1.5 * atr_14, current_price - 0.075 * current_price)`. If `(current_price - stop_price) / current_price > 0.08` -> reject with reason `stop_too_wide`.
7. **Max-loss guard**: `max_loss = quantity * (current_price - stop_price)`. If `max_loss > equity * 0.01` -> shrink `quantity` to fit. If shrink would round to zero -> reject with reason `max_loss_below_min_lot`.
8. Emit `OrderIntent(IntentKind.NEW, side=ActionSide.BUY, ..., reason="signal:" + pick.id)`. Bracket order context (Section 9) is captured in `pick.target_price` / computed stop and attached as a separate `BracketRequest`.

### Test fixtures (PR `feat/v1-signal-to-order`)

Located in `backend/tests/services/strategy/test_signal_to_order.py`.

| Fixture | Asserts |
|---|---|
| `test_pro_pick_sizes_at_2pct_of_equity` | Pro user, $100K equity, 2A stage, R1 regime -> `intent.target_weight_pct == 0.02` and `quantity * price` close to $2,000 within ATR ceiling. |
| `test_pro_plus_pick_sizes_at_5pct_of_equity` | Same setup with Pro+ user yields ~$5,000 notional. |
| `test_signal_to_zero_orders_when_regime_red` | Regime R5 returns `intents == []` and `rejection_reasons == ["regime_blocked"]`. |
| `test_signal_to_zero_orders_when_stage_3b` | Stage 3B in any regime returns `intents == []` and `rejection_reasons == ["stage_blocked"]`. |
| `test_quant_desk_requires_per_pick_size` | Quant Desk user with no `suggested_size_pct_of_equity` returns `rejection_reasons == ["quant_desk_requires_per_pick_size"]`. |
| `test_quant_desk_uses_per_pick_size` | Quant Desk with `suggested_size_pct_of_equity=Decimal("0.10")` produces a 10% intent. |
| `test_max_loss_above_1pct_shrinks_quantity` | Max loss would be 1.5% of equity; quantity shrinks to fit 1% cap. |
| `test_max_loss_shrink_to_zero_returns_no_intent` | Max loss math forces quantity to zero; `intents == []`, `rejection_reasons == ["max_loss_below_min_lot"]`. |
| `test_stop_too_wide_rejects` | Computed stop is 12% below entry (above 8% guard); reject with `stop_too_wide`. |
| `test_atr_ceiling_caps_below_tier_default` | Tier default is $5,000 but ATR-based size is $3,000; final is $3,000. |
| `test_heat_remaining_caps_intent` | `PortfolioHeatGuard.remaining` returns $1,000; intent is sized at $1,000 even if tier default is higher. |
| `test_pick_explicit_stop_overrides_atr_stop` | Pick with `stated_stop` tighter than `1.5 * atr_14` uses the pick stop. |

---

## 7. `PortfolioHeatGuard`

### Distinction from existing `_check_portfolio_heat`

`app/services/risk/pre_trade_validator.py` already enforces a **stop-distance heat cap**:

```312:394:app/services/risk/pre_trade_validator.py
    MAX_PORTFOLIO_HEAT_PCT = 0.06  # 6% max concurrent risk

    def _check_portfolio_heat(
        self, order: Order, portfolio_equity: float
    ) -> ValidationCheck:
        """Block new entries if aggregate open risk exceeds 6% of equity.

        Portfolio heat = sum of (|position_value| × ATR%14 × stop_multiplier) for
        all open positions (long and short). This represents the total dollar
        amount at risk if every position hits its stop simultaneously.
        """
```

This is the **stop-distance** heat (capital at risk if all stops fire). Per `.cursor/rules/risk-manager.mdc`, this 6% cap stays.

`PortfolioHeatGuard` adds a **volatility-weighted exposure cap**, which is a different metric:

```
heat_exposure = sum( open_position_dollar_exposure * position_volatility ) / total_portfolio_value
```

Where `position_volatility = ATR%14 / 100`. Default cap = 20% of portfolio (configurable per user). This is conceptually "expected daily P&L volatility from current exposure", not "loss at stop".

Both gates run; the new gate is additive. An order must satisfy both.

### Module: `app/services/risk/portfolio_heat_guard.py` (NEW)

```python
DEFAULT_HEAT_CAP_PCT = Decimal("0.20")


@dataclass(frozen=True)
class HeatBudget:
    cap_pct: Decimal
    used_pct: Decimal
    used_dollars: Decimal
    remaining_dollars: Decimal


class PortfolioHeatGuard:
    def __init__(self, db: Session, user_id: int, cap_pct: Optional[Decimal] = None):
        self.db = db
        self.user_id = user_id
        self.cap_pct = cap_pct or self._user_cap(user_id)

    def current(self, equity: Decimal) -> HeatBudget: ...
    def remaining(self, equity: Decimal) -> Decimal: ...
    def would_exceed(self, equity: Decimal, new_exposure_dollars: Decimal,
                     new_atrp_14: Decimal) -> bool: ...
```

`PortfolioHeatGuard.would_exceed` is added to `PreTradeValidator.validate` as a new check (`_check_portfolio_heat_exposure`) before broker submission. It is independent of `_check_portfolio_heat`.

### Test fixtures (PR `feat/v1-portfolio-heat-guard`)

Located in `backend/tests/services/risk/test_portfolio_heat_guard.py`.

| Fixture | Asserts |
|---|---|
| `test_heat_cap_default_20pct` | New user with no override -> `cap_pct == Decimal("0.20")`. |
| `test_heat_cap_per_user_override_respected` | User row with `heat_cap_override=Decimal("0.10")` -> `cap_pct == Decimal("0.10")`. |
| `test_empty_portfolio_returns_full_remaining` | No open positions, $100K equity, 20% cap -> `remaining_dollars == 20000`. |
| `test_one_position_at_2pct_atr_uses_correct_heat` | $50K AAPL position, ATR%=2 -> heat used = $1,000 -> `used_pct == Decimal("0.01")`. |
| `test_block_order_pushing_heat_above_cap` | Existing heat at 19%; new order would add 2% -> `would_exceed == True`. |
| `test_allow_order_within_cap` | Existing heat at 10%; new order adds 5% -> `would_exceed == False`. |
| `test_heat_guard_runs_alongside_stop_distance_heat_check` | Order passes `_check_portfolio_heat` (stop-distance, 6%) but fails `_check_portfolio_heat_exposure` (volatility, 20%) -> `validation.allowed == False`. |
| `test_heat_guard_isolates_per_user` | User A has 19% heat; user B's order is sized against user B's own positions only. |
| `test_heat_guard_handles_missing_atrp_with_fallback` | Position with no `atrp_14` snapshot uses 3.0 fallback (matches existing `_check_portfolio_heat`) and logs a warning (no silent zero). |

---

## 8. Per-User Circuit Breaker

### Current global design (verbatim header excerpt)

```52:76:app/services/risk/circuit_breaker.py
class CircuitBreaker:
    """
    Redis-backed circuit breaker with tiered response.

    Tiers:
        0: Normal operation
        1: Warning - reduce position sizes 50%
        2: Entries blocked - exits only allowed
        3: Full halt - cancel all open orders

    State keys in Redis:
        circuit:daily_pnl - float, resets at trading_day_reset_hour in trading_day_timezone
        circuit:trading_day - Trading day identifier (YYYY-MM-DD based on trading timezone)
        circuit:consecutive_losses - int
        circuit:order_count - int
        circuit:order_count:{symbol} - int
        circuit:trip_reason - str (if tripped)
        circuit:trip_time - ISO timestamp
        circuit:kill_switch - str (admin override)
```

```384:386:app/services/risk/circuit_breaker.py
# Module-level singleton
circuit_breaker = CircuitBreaker()
```

State is **global**. One user's losses trip the breaker for everyone. This violates the multi-tenancy invariant in `engineering.mdc` ("every new route, service, or background task must accept and respect `user_id`").

### Proposed per-user design

1. Replace the module-level singleton with a factory:

   ```python
   def get_circuit_breaker(user_id: int) -> CircuitBreaker:
       return CircuitBreaker(user_id=user_id)
   ```

2. Add `user_id` to all Redis keys: `circuit:{user_id}:daily_pnl`, `circuit:{user_id}:order_count`, etc. The global `circuit:kill_switch` key remains and acts as a master kill that supersedes any per-user state.

3. Introduce `CircuitBreakerState` table for durable, queryable state (Redis is volatile):

   ```python
   class CircuitBreakerState(Base):
       __tablename__ = "circuit_breaker_state"

       user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                        primary_key=True)
       tier = Column(Integer, nullable=False, default=0)
       daily_pnl = Column(Numeric(18, 4), nullable=False, default=0)
       starting_equity = Column(Numeric(18, 4), nullable=False, default=100000)
       trading_day = Column(Date, nullable=False)
       consecutive_losses = Column(Integer, nullable=False, default=0)
       order_count = Column(Integer, nullable=False, default=0)
       kill_switch_reason = Column(String, nullable=True)
       kill_switch_user = Column(String, nullable=True)
       kill_switch_time = Column(DateTime(timezone=True), nullable=True)
       tier1_loss_pct = Column(Numeric(6, 4), nullable=False, default=Decimal("2.0"))
       tier2_loss_pct = Column(Numeric(6, 4), nullable=False, default=Decimal("3.0"))
       tier3_loss_pct = Column(Numeric(6, 4), nullable=False, default=Decimal("5.0"))
       updated_at = Column(DateTime(timezone=True), nullable=False)
   ```

4. Add an Alembic migration. **Do not pick a revision number now**; reserve at implementation time (current head is `0046`). Migration filename: `<NEXT_REVISION>_add_circuit_breaker_state.py`.

5. Rewrite `PreTradeValidator._check_circuit_breaker` to call `get_circuit_breaker(self.user_id)` instead of the module singleton. Confirm `self.user_id` is always set (already is when instantiated from `OrderManager.submit`; see `pre_trade_validator.py` line 70-75).

6. Rewrite `OrderManager.submit` line 426 (`circuit_breaker.record_fill(...)`) to call the per-user breaker.

### Migration plan (zero downtime)

| Step | Action |
|---|---|
| 1. Shadow-write | Write to both the global Redis keys and per-user keys. Reads continue from global. Ship with feature flag `CIRCUIT_BREAKER_PER_USER_ENABLED=false`. |
| 2. Backfill | Background task copies any existing per-symbol order counts and `daily_pnl` from global keys into the founder's `user_id` (1) state. Other users start fresh. |
| 3. Dual-read for one week | Reads check per-user keys first; fall back to global if missing. Compare values in logs; alert on divergence. |
| 4. Cutover | Flip `CIRCUIT_BREAKER_PER_USER_ENABLED=true`. Reads stop falling back to global. Writes stop hitting global keys (except master kill switch). |
| 5. Cleanup | After 30 days of clean per-user operation, remove the global keys (except `circuit:kill_switch`). |

### Test fixtures (PR `feat/v1-per-user-circuit-breaker`)

Located in `backend/tests/services/risk/test_circuit_breaker_per_user.py`.

| Fixture | Asserts |
|---|---|
| `test_user_a_loss_does_not_trip_user_b_breaker` | User A records -3% loss; user B's `can_trade` still returns `(True, "OK", 0)`. |
| `test_user_a_kill_switch_does_not_block_user_b` | `get_circuit_breaker(1).trigger_kill_switch(...)`; user 2's `can_trade` returns allowed. |
| `test_global_kill_switch_blocks_all_users` | Setting global `circuit:kill_switch` blocks user 1, 2, and 3. |
| `test_per_user_thresholds_respected` | User A `tier3_loss_pct=Decimal("8.0")`; -5% loss does not trip user A but trips user B at default 5%. |
| `test_dual_read_fallback_to_global_during_migration` | With flag off, missing per-user key reads from global key. |
| `test_per_user_record_fill_isolated` | `record_fill(user_id=1, ...)` does not change `daily_pnl` for user_id=2. |
| `test_circuit_breaker_state_table_persists_across_redis_flush` | After Redis flush, per-user state rehydrates from `CircuitBreakerState` table. |
| `test_pre_trade_validator_uses_user_specific_breaker` | `PreTradeValidator(db, user_id=2).validate(...)` calls `get_circuit_breaker(2)`. |
| `test_order_manager_records_fill_per_user` | `OrderManager.submit` for user 7's order records the fill on user 7's breaker only. |
| `test_per_user_breaker_starting_equity_synced_separately` | Each user's `starting_equity` reflects their own `AccountBalance`, not user 1's. |

---

## 9. Bracket Orders (OCO Stop + Target)

### Broker capability matrix

| Broker | Native bracket support | Implementation strategy |
|---|---|---|
| IBKR (`ibkr_executor.py`) | Yes — parent + child OCA group via `ib_insync.Bracket` | Native: emit a `BracketRequest`, IBKR sends parent + 2 child orders with same OCA group. Cancellation of one auto-cancels the other. |
| Alpaca (`alpaca_executor.py`) | Yes — `order_class="bracket"` with `take_profit` and `stop_loss` legs in a single submit | Native: pass `take_profit={"limit_price": target}` and `stop_loss={"stop_price": stop, "limit_price": stop_limit}` in `submit_order`. |
| TastyTrade | No native OCO across stop + target | Client-side orchestration: place entry; on fill, submit two separate orders; subscribe to fills; when one fills, cancel the other via `cancel_order`. State tracked in new `BracketGroup` table. |
| Schwab | Conditional orders supported but inconsistent | Same as TastyTrade: client-side orchestration via `BracketGroup`. |
| Plaid (read-only) | N/A | Not applicable; brokers connected via Plaid Investments are read-only by design. |

### New module: `app/services/execution/bracket_manager.py` (NEW)

```python
@dataclass(frozen=True)
class BracketRequest:
    entry: OrderRequest
    stop_loss: OrderRequest          # side opposite to entry; STP or STP_LMT
    take_profit: OrderRequest        # side opposite to entry; LMT
    oca_group: Optional[str] = None  # auto-generated if None


@dataclass(frozen=True)
class BracketResult:
    parent_broker_order_id: Optional[str]
    child_broker_order_ids: list[str]
    bracket_group_id: int            # row in bracket_groups table
    status: str                      # "submitted", "partial", "error"


class BracketManager:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    async def submit(self, req: BracketRequest, broker_type: str) -> BracketResult: ...
    async def on_fill(self, broker_order_id: str) -> None: ...
    async def cancel(self, bracket_group_id: int) -> None: ...
```

A `bracket_groups` table tracks the group, parent, two children, and which child has filled. The reconciliation loop (already in place for order status polling, `OrderManager.poll_status`) is extended to call `BracketManager.on_fill` when a child fills, which cancels its sibling.

### Test fixtures (PR `feat/v1-bracket-orders`)

Located in `backend/tests/services/execution/test_bracket_manager.py`.

| Fixture | Asserts |
|---|---|
| `test_ibkr_bracket_uses_native_oca_group` | `BracketManager.submit(req, "ibkr")` calls IBKR executor once with native bracket payload; no client-side polling created. |
| `test_alpaca_bracket_uses_native_order_class` | Alpaca submit includes `order_class="bracket"` and both leg specs. |
| `test_tastytrade_bracket_uses_client_orchestration` | TastyTrade submit creates 1 `BracketGroup` row + 1 entry order; stop and target are NOT submitted yet. |
| `test_tastytrade_on_entry_fill_submits_both_legs` | When entry fill is detected, `BracketManager.on_fill` submits stop and target as siblings. |
| `test_tastytrade_on_stop_fill_cancels_target` | Stop child fills -> target child is cancelled via `cancel_order`. |
| `test_tastytrade_on_target_fill_cancels_stop` | Target child fills -> stop child is cancelled. |
| `test_schwab_bracket_uses_client_orchestration` | Schwab uses same client-side path as TastyTrade. |
| `test_bracket_validates_stop_below_entry_for_long` | Stop above entry for a long entry raises `ValueError("stop must be below entry for long")`. |
| `test_bracket_validates_target_above_entry_for_long` | Target below entry for a long entry raises `ValueError("target must be above entry for long")`. |
| `test_bracket_request_runs_through_risk_gate` | Each leg of the bracket is run through `RiskGate.check` before submission; parent is rejected if any leg fails. |
| `test_bracket_cancel_cancels_all_unfilled_children` | `BracketManager.cancel(group_id)` cancels every unfilled child and marks the group as cancelled. |

---

## 10. Adaptive Trailing Stop Manager

### Existing partial implementation

`app/services/execution/exit_cascade.py` already implements adaptive trailing logic in `_tier2_trailing_stop` (lines 102-155). It computes a per-bar multiplier from stage, regime, and ATR%, and exits when `current_price < high_water_price - trail_distance`. `_tier7_regime_trail` does the same with tighter multipliers in worse regimes.

What is **not yet wired**:

1. Per-pick custom stops are not consulted; the cascade always uses the formula. Pick-author intent is lost.
2. The trail decision is computed in-memory each evaluation; there is no persistent `trailing_stop_state` for **submitted broker stop orders** that need to be updated.
3. There is no scheduled task that translates a cascade decision into an actual stop-order modification for brokers that do not support server-side trailing stops natively.

### Proposed module: `app/services/execution/trailing_stop_manager.py` (NEW)

```python
@dataclass(frozen=True)
class TrailingStopState:
    position_id: int
    high_water_price: Decimal
    current_stop_price: Decimal
    base_atr_multiplier: Decimal      # from pick or stage default
    last_updated: datetime
    broker_stop_order_id: Optional[str]


class TrailingStopManager:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    def initialize(self, position_id: int, entry_price: Decimal,
                   pick_stop: Optional[Decimal] = None,
                   pick_stop_atr_mult: Optional[Decimal] = None) -> TrailingStopState: ...

    def evaluate(self, position_id: int, current_price: Decimal,
                 ctx: PositionContext) -> Optional[OrderIntent]: ...

    async def sync_to_broker(self, state: TrailingStopState) -> None: ...
```

- `initialize` records pick-author stop preferences. Defaults fall back to the existing `_tier2_trailing_stop` formula.
- `evaluate` reuses the **same multiplier math** from `_tier2_trailing_stop` and `_tier7_regime_trail` to keep one source of truth, but reads/writes `TrailingStopState.high_water_price` so the trail is persistent.
- `sync_to_broker` modifies the broker stop order if the new stop price differs from `state.current_stop_price` by more than a configurable epsilon (default 0.5%). For brokers without modify-stop, cancel-and-replace inside `BracketManager`.

A new Alembic migration creates `trailing_stop_state` (one row per open position). **Do not pick a revision number now.** Filename at implementation: `<NEXT_REVISION>_add_trailing_stop_state.py`.

### Per-pick custom stop integration

`SignalToOrder` (Section 6) attaches `pick.stated_stop` and `pick.stop_distance_atr` to the resulting `OrderIntent`. After fill, `OrderManager` calls `TrailingStopManager.initialize(position_id, entry_price, pick_stop, pick_stop_atr_mult)`.

### Test fixtures (PR `feat/v1-adaptive-trailing-stop`)

Located in `backend/tests/services/execution/test_trailing_stop_manager.py`.

| Fixture | Asserts |
|---|---|
| `test_initialize_uses_pick_stop_when_provided` | `pick_stop=Decimal("95")` -> `state.current_stop_price == Decimal("95")` even if formula would yield 92. |
| `test_initialize_falls_back_to_atr_formula` | No pick stop -> `state.current_stop_price == entry_price - 1.5 * atr_14` for stage 2A. |
| `test_evaluate_raises_stop_when_price_advances` | Entry $100, stop $98; price hits $110 -> stop trails up; `state.high_water_price == 110`; `state.current_stop_price > 98`. |
| `test_evaluate_does_not_lower_stop` | Price retraces from $110 to $105 -> stop stays at the trailed level (never widens; aligns with `risk-manager.mdc` "never widen stops"). |
| `test_evaluate_reuses_tier2_multiplier_for_stage_2c` | Stage 2C -> base multiplier 2.0 (matches `_tier2_trailing_stop` line 121-122). |
| `test_evaluate_tightens_in_r4` | Regime R4 -> multiplier reduced by 0.5 (matches `_tier2_trailing_stop` line 130-131). |
| `test_evaluate_emits_exit_intent_when_price_breaks_stop` | Current price below stop -> returns `OrderIntent(IntentKind.EXIT, side=ActionSide.SELL)`. |
| `test_sync_to_broker_only_updates_when_delta_above_epsilon` | New stop differs by 0.2% -> no broker call. New stop differs by 1.0% -> broker stop modified. |
| `test_sync_to_broker_uses_cancel_and_replace_for_tastytrade` | Broker without modify-stop API -> `BracketManager` cancels old stop and submits new stop. |
| `test_state_persists_across_process_restart` | After process restart, `TrailingStopManager` reads `TrailingStopState` from DB and resumes with same `high_water_price`. |
| `test_per_pick_atr_mult_overrides_stage_default` | Pick author specifies `stop_distance_atr=Decimal("1.0")` -> trail uses 1.0 multiplier even when stage default is 1.5. |
| `test_manual_intervention_pauses_trailing_state` | User manually places SELL or modifies stop via UI -> `TrailingStopState.active = False`; subsequent `evaluate` returns `None`. |

---

## 11. Implementation Order

This sequence minimizes coupling. Each PR ships behind a feature flag (`ALLOW_LIVE_ORDERS=false` is the global no-op for any execution path).

| # | Sub-PR | Depends on | Why this position |
|---|---|---|---|
| 1 | `feat/v1-per-user-circuit-breaker` | none (refactor + new table) | Multi-tenancy fix. Every later PR assumes the breaker is per-user; doing this first prevents rework. Adds DB table + dual-read window before cutover. |
| 2 | `feat/v1-trim-add-orders` | (1) | Introduces `OrderIntent` and `place_intent`. All later PRs (rebalance, signal-to-order, brackets, trailing) emit `OrderIntent`, so the type and entry point must exist first. No business logic depends on it yet. |
| 3 | `feat/v1-portfolio-heat-guard` | (1), (2) | Adds the new exposure-volatility cap as an additional `PreTradeValidator` check. Needed before `SignalToOrder` because the generator queries `remaining(equity)` to size intents. |
| 4 | `feat/v1-tax-aware-exits` | (1), (2) | Adds `LotSelector` and wires it into `OrderManager` SELL path. Decoupled from rebalance, but rebalance benefits from it (lower realized gain). |
| 5 | `feat/v1-signal-to-order` | (2), (3), (4) | Converts validated picks into intents. Uses `PortfolioHeatGuard` for sizing and `LotMethod` defaults for any auto-exit hook. |
| 6 | `feat/v1-rebalance-engine` | (2), (3), (4), (5) | Highest leverage on the other components. PREVIEW only at first; EXECUTE behind founder-only API role. |
| 7 | `feat/v1-bracket-orders` | (1), (2) | Independent of (3)-(6) functionally, but ordered late so the supervised review focuses on simpler PRs first. Adds `BracketManager` and per-broker capability handling. |
| 8 | `feat/v1-adaptive-trailing-stop` | (2), (7) | Final layer. Needs `BracketManager.cancel` + child re-submit for brokers without modify-stop. Persists `TrailingStopState` for crash safety. |

Rationale notes:

- (1) before (2) because changing `OrderManager` signatures while also rewriting circuit breaker state introduces too much surface area in one diff.
- (3) before (5) because heat remaining is a sizing input.
- (4) before (6) because rebalance produces SELLs that should already pass through the lot selector.
- (7) before (8) because adaptive trailing depends on bracket-managed stops being modifiable or replaceable atomically.

---

## 12. Risk Register

| Failure mode | Mitigation |
|---|---|
| TRIM rounds to zero shares on small positions (e.g., 1% of 10 shares) | `IntentKind.TRIM` returns a structured error before broker call. Test: `test_trim_below_min_lot_returns_clean_error`. |
| TRIM uses banker's rounding and accidentally sells more than held | Use `Decimal.quantize(rounding=ROUND_HALF_DOWN)`. Test: `test_trim_rounds_half_down_to_avoid_overselling`. |
| Rebalance produces wash-sale-triggering orders | `RebalanceConstraints.block_wash_sales=True` by default. Wash-sale check runs per intent in `compute_intents`. Test: `test_rebalance_blocks_wash_sale_when_block_wash_sales_true`. |
| Rebalance EXECUTE called by non-founder via API | API layer enforces founder role on `confirm=true`; `RebalanceEngine.execute_plan` raises `ValueError` if `confirm=False`. Test: `test_rebalance_execute_requires_confirm_true`. |
| Per-user breaker introduces N-times Redis state and increases memory | Use Redis Hash per user (`HSET circuit:{user_id} ...`) instead of N separate keys; one hash per user. Backfill task batches users; alerting at 10K user threshold. |
| Migration window leaves stale state across global and per-user | Dual-read for one week with logged divergence; cutover only after 7 days of zero divergence. |
| Tax-aware lot selector picks wash-sale lot when `HIFO_WASH_SAFE` is selected | Selector iterates lots in HIFO order and skips lots within an active wash window via existing `TaxLossHarvester.check_wash_sale_risk`. Test: `test_hifo_wash_safe_skips_wash_sale_lot`. |
| Bracket child cancel race (both children fill before cancel) on TastyTrade | `BracketManager.on_fill` is idempotent and uses a Redis lock per `bracket_group_id`. Reconciliation loop reaps double-fills and writes to `risk_violation` table. |
| Adaptive trail "race up" on a fast spike then trail-stop hits in the next bar | `TrailingStopManager.sync_to_broker` rate-limits modifications to once per N seconds; epsilon guard (default 0.5%) prevents thrash. Test: `test_sync_to_broker_only_updates_when_delta_above_epsilon`. |
| `SignalToOrder` sizes a position above heat cap because `remaining_dollars` is stale | Heat is recomputed on every `generate` call (no caching). Heat check runs again in `PreTradeValidator` at submit time. |
| `place_intent` re-entry: validated pick fires twice and produces two ADDs | Idempotency key per `(user_id, pick_id, kind)`; `Order.signal_id` already exists. New orders are deduped by `(user_id, signal_id, kind, created_at::date)`. |
| Stage cap relaxed accidentally during refactor | Existing `STAGE_CAPS` table is referenced verbatim in `risk_gate.py`; tests assert specific cap values per stage and regime. |
| Per-broker bracket capability misclassified | Broker capability matrix is encoded as `BrokerCapabilities` enum on each executor; `BracketManager.submit` reads from the executor instance, never from a constant table. Tests assert per-broker behavior. |
| Founder kill-switch trigger affects only one user when intent was global | Global kill-switch path retained at `circuit:kill_switch` Redis key (no `user_id` prefix); `CircuitBreaker.can_trade` checks global key first. Test: `test_global_kill_switch_blocks_all_users`. |
| Per-user breaker write storm on a busy account | Use Redis pipeline for `record_fill` (group `incr` and `set` calls); periodic flush to `CircuitBreakerState` table every N seconds, not on every fill. |
| `RebalanceEngine` runs during T2/T3 breaker lockout and produces orders that all fail | `RebalanceEngine.compute_intents` calls `circuit_breaker.can_trade(is_exit=False)` early; if blocked, returns an empty plan with `rationale="circuit_breaker_blocked: <reason>"`. |
| Adaptive trailing stop exits a position the user manually intervened on | `TrailingStopState` is paused (`active=False`) when the user manually places a SELL or modifies the stop via UI. Test: `test_manual_intervention_pauses_trailing_state`. |

---

## 13. Pre-Merge Checklist (per sub-PR)

Each sub-PR must satisfy every item below before merge. Citations point to the test fixture in this spec.

### Common to all sub-PRs

- CI green (backend tests, frontend type-check, lint).
- No silent fallbacks (`.cursor/rules/no-silent-fallback.mdc`); per-symbol loops emit `written / skipped / errors` counters with `assert sum == total`.
- No emojis in code, comments, or PR body.
- Plan-mode plan attached in PR description (see `.cursor/rules/plan-mode-first.mdc`).
- KNOWLEDGE.md decision entry if architectural (per-user breaker, lot selector default, heat cap value).
- Production verification plan in PR body (`.cursor/rules/production-verification.mdc`); after merge, confirm `live` deploy + `/health/full` + targeted endpoint check.
- All new routes scoped to `current_user.id`; no globally scoped queries.
- Acceptance: every fixture named in the matching section of this spec exists as a passing test.

### `feat/v1-per-user-circuit-breaker` (Section 8)

- Alembic migration named `<NEXT_REVISION>_add_circuit_breaker_state.py` reserved at implementation; revision number does not collide with current head `0046`.
- Feature flag `CIRCUIT_BREAKER_PER_USER_ENABLED` defaults to `false`; flip is a separate ops PR.
- Dual-read alerting wired (divergence count surfaced in `/admin/health`).
- All ten fixtures from Section 8 pass.
- Manual smoke test: trigger global kill switch, confirm both founder and a second test user blocked.

### `feat/v1-trim-add-orders` (Section 3)

- `OrderIntent` and `IntentKind` defined in new `app/services/execution/intent.py`.
- `RiskGate.check` accepts `allow_reducing` keyword (default `False`); call sites updated only inside `OrderManager.place_intent`.
- All ten fixtures from Section 3 pass.
- No call sites to `OrderManager.preview` or `OrderManager.submit` change behavior; backwards-compatible.

### `feat/v1-portfolio-heat-guard` (Section 7)

- New `PortfolioHeatGuard` lives in `app/services/risk/`.
- `PreTradeValidator.validate` adds `_check_portfolio_heat_exposure` after `_check_portfolio_heat`; both run, both must pass.
- Per-user override column on `users` table OR a settings JSON field; choice documented in PR body.
- All nine fixtures from Section 7 pass.

### `feat/v1-tax-aware-exits` (Section 5)

- `LotSelector` with all six methods.
- `OrderManager.submit` writes `selected_lot_ids`, `estimated_realized_gain` to the order row before broker call.
- New columns added via Alembic migration named `<NEXT_REVISION>_add_lot_selection_to_orders.py`.
- All twelve fixtures from Section 5 pass.

### `feat/v1-signal-to-order` (Section 6)

- `SignalToOrder.generate` returns `SignalToOrderResult` even on rejection (never raises silently).
- `sizing_breakdown` exposes the entire pipeline so the UI can show "why did the system size this at $X".
- All twelve fixtures from Section 6 pass.

### `feat/v1-rebalance-engine` (Section 4)

- New API route `POST /api/v1/rebalance/preview` (any user, returns plan only) and `POST /api/v1/rebalance/execute` (founder role only).
- `RebalancePlan.rationale` is a human-readable summary suitable for display.
- All eleven fixtures from Section 4 pass.
- Manual smoke test: PREVIEW on the founder account during paper-trading session; no orders created.

### `feat/v1-bracket-orders` (Section 9)

- `BracketManager` lives in `app/services/execution/`.
- New `bracket_groups` table via Alembic migration named `<NEXT_REVISION>_add_bracket_groups.py`.
- Each broker executor exposes a `capabilities: BrokerCapabilities` property that `BracketManager` reads.
- All eleven fixtures from Section 9 pass.

### `feat/v1-adaptive-trailing-stop` (Section 10)

- `TrailingStopManager` lives in `app/services/execution/`.
- New `trailing_stop_state` table via Alembic migration named `<NEXT_REVISION>_add_trailing_stop_state.py`.
- Reuses the multiplier math from `exit_cascade.py:_tier2_trailing_stop` (no parallel formula).
- All eleven fixtures from Section 10 pass.

---

## Appendix: Files Touched (proposed)

> All paths below are subject to founder line-by-line review at implementation time per `.cursor/rules/protected-regions.mdc`.

### New files

- `app/services/execution/intent.py`
- `app/services/execution/rebalance_engine.py`
- `app/services/execution/bracket_manager.py`
- `app/services/execution/trailing_stop_manager.py`
- `app/services/portfolio/lot_selector.py`
- `app/services/risk/portfolio_heat_guard.py`
- `app/services/strategy/signal_to_order.py`
- `app/models/circuit_breaker_state.py`
- `app/models/bracket_group.py`
- `app/models/trailing_stop_state.py`
- `app/alembic/versions/<NEXT_REVISION>_add_circuit_breaker_state.py`
- `app/alembic/versions/<NEXT_REVISION>_add_lot_selection_to_orders.py`
- `app/alembic/versions/<NEXT_REVISION>_add_bracket_groups.py`
- `app/alembic/versions/<NEXT_REVISION>_add_trailing_stop_state.py`
- `app/api/routes/rebalance.py`
- (test files matching every fixture named above)

### Edited files (DANGER ZONE — founder line-by-line review required)

- `app/services/execution/order_manager.py` — add `place_intent`, wire `LotSelector` into SELL path.
- `app/services/execution/risk_gate.py` — add `allow_reducing` keyword on `check`.
- `app/services/risk/circuit_breaker.py` — refactor module singleton into `get_circuit_breaker(user_id)` factory; per-user Redis keys.
- `app/services/risk/pre_trade_validator.py` — add `_check_portfolio_heat_exposure` and switch to per-user breaker.
- `app/models/order.py` — add `lot_method`, `selected_lot_ids`, `estimated_realized_gain`, `allow_wash_sale_override` columns.
- `app/services/execution/ibkr_executor.py` / `alpaca_executor.py` / TastyTrade / Schwab executors — expose `capabilities` and bracket payload helpers.
- `app/api/routes/orders.py` — add `place_intent` endpoint.

### Untouched

Every other file, including the entire `app/services/market/` indicator pipeline, regime engine, scan engine, and exit cascade tier definitions. Exit cascade only **gains a consumer** (`TrailingStopManager`), it does not change behavior.

---

End of spec.
