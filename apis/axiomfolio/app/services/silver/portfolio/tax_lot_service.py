#!/usr/bin/env python3
"""medallion: silver"""

from __future__ import annotations

"""
Tax Lot Service - Production Implementation
Handles tax lot calculations, cost basis, and tax optimization strategies.
"""

import logging
from typing import Dict, List, Optional
from datetime import UTC, datetime

from app.models.tax_lot import TaxLot, TaxLotMethod, TaxLotSource
from app.models.broker_account import BrokerAccount
from app.database import SessionLocal

# Service imports
from app.services.silver.market.market_data_service import quote

logger = logging.getLogger(__name__)


class TaxLotService:
    """
    Tax Lot Service - Updated for new architecture.
    Handles tax lots, cost basis, and tax optimization using models.
    """

    def __init__(self, db_session: Optional[SessionLocal] = None):
        self.db = db_session or SessionLocal()

    def _parse_acquisition_date(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            # ISO string
            return datetime.fromisoformat(value)
        except Exception as e:
            logger.warning("Acquisition date ISO parse failed for %r: %s", value, e)
        try:
            # YYYYMMDD (FlexQuery tradeDate)
            return datetime.strptime(value, "%Y%m%d").replace(tzinfo=UTC)
        except Exception as e:
            logger.warning("Acquisition date YYYYMMDD parse failed for %r: %s", value, e)
        try:
            # YYYY-MM-DD
            return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
        except Exception:
            return None

    async def create_tax_lot(
        self,
        user_id: int,
        account_id: str,
        symbol: str,
        acquisition_date: datetime,
        quantity: float,
        cost_per_share: float,
        fees: float = 0.0,
        tax_treatment: str = "taxable",
        import_job_id: Optional[int] = None,
    ) -> TaxLot:
        """Create a new tax lot for a purchase (version)"""
        try:
            cost_basis = (quantity * cost_per_share) + fees

            tax_lot = TaxLot(
                user_id=user_id,
                account_id=account_id,
                symbol=symbol,
                acquisition_date=acquisition_date,
                quantity=quantity,
                cost_per_share=cost_per_share,
                cost_basis=cost_basis,
                fees=fees,
                remaining_quantity=quantity,
                tax_treatment=tax_treatment,
                source_import_id=import_job_id,
            )

            # Calculate time-based attributes
            days_held = (datetime.now(UTC) - acquisition_date).days
            tax_lot.days_held = days_held
            tax_lot.is_long_term = days_held >= 365

            self.db.add(tax_lot)
            self.db.commit()
            self.db.refresh(tax_lot)

            logger.info(
                f"✅ Created tax lot for {symbol}: {quantity} shares at ${cost_per_share}"
            )
            return tax_lot

        except Exception as e:
            logger.error(f"❌ Error creating tax lot: {e}")
            self.db.rollback()
            raise

    async def sync_official_tax_lots(
        self,
        user_id: int,
        broker_account: BrokerAccount,
        official_lots: List[Dict],
    ) -> Dict:
        """Persist official IBKR tax lots into the database with upsert semantics.
        Uses unique lot_id when provided; otherwise deduplicates by (account_id, symbol, acquisition_date, quantity, cost_per_share).
        """
        created = 0
        updated = 0
        try:
            for lot in official_lots:
                symbol = lot.get("symbol")
                if not symbol:
                    continue
                lot_id = lot.get("lot_id")
                quantity = float(
                    lot.get("quantity", lot.get("remaining_quantity", 0)) or 0
                )
                cps = lot.get("cost_per_share")
                cost_per_share = float(cps) if cps is not None else None
                cost_basis = (
                    float(lot.get("cost_basis"))
                    if lot.get("cost_basis") is not None
                    else None
                )
                acq_raw = (
                    lot.get("acquisition_date")
                    or lot.get("trade_date")
                    or lot.get("tradeDate")
                )
                acq_dt = self._parse_acquisition_date(acq_raw)

                # Upsert target
                existing: Optional[TaxLot] = None
                if lot_id:
                    existing = (
                        self.db.query(TaxLot).filter(TaxLot.lot_id == lot_id).first()
                    )
                if not existing and acq_dt and cost_per_share is not None:
                    existing = (
                        self.db.query(TaxLot)
                        .filter(
                            TaxLot.account_id == broker_account.id,
                            TaxLot.symbol == symbol,
                            TaxLot.acquisition_date == acq_dt.date(),
                            TaxLot.cost_per_share == cost_per_share,
                            TaxLot.quantity == quantity,
                        )
                        .first()
                    )

                if existing:
                    # Update valuations if provided
                    mv = lot.get("market_value")
                    cp = lot.get("current_price")
                    upnl = lot.get("unrealized_pnl")
                    upnl_pct = lot.get("unrealized_pnl_pct")
                    if mv is not None:
                        existing.market_value = float(mv)
                    if cp is not None:
                        existing.current_price = float(cp)
                    if upnl is not None:
                        existing.unrealized_pnl = float(upnl)
                    if upnl_pct is not None:
                        existing.unrealized_pnl_pct = float(upnl_pct)
                    self.db.add(existing)
                    updated += 1
                    continue

                # Create new tax lot
                tl = TaxLot(
                    user_id=user_id,
                    account_id=broker_account.id,
                    symbol=symbol,
                    contract_id=lot.get("contract_id"),
                    quantity=quantity,
                    cost_per_share=cost_per_share,
                    cost_basis=cost_basis,
                    acquisition_date=acq_dt.date() if acq_dt else None,
                    trade_id=lot.get("trade_id") or lot.get("tradeID"),
                    execution_id=lot.get("execution_id"),
                    order_id=lot.get("order_id"),
                    exchange=lot.get("exchange"),
                    asset_category=lot.get("asset_category"),
                    current_price=float(lot.get("current_price", 0) or 0) or None,
                    market_value=float(lot.get("market_value", 0) or 0) or None,
                    unrealized_pnl=float(lot.get("unrealized_pnl", 0) or 0) or None,
                    unrealized_pnl_pct=float(lot.get("unrealized_pnl_pct", 0) or 0)
                    or None,
                    currency=lot.get("currency", "USD"),
                    commission=float(lot.get("commission", 0) or 0) or None,
                    fees=float(lot.get("fees", 0) or 0) or None,
                    lot_id=lot_id,
                    settlement_date=None,
                    holding_period=None,
                    source=TaxLotSource.OFFICIAL_STATEMENT,
                )
                self.db.add(tl)
                created += 1

            self.db.commit()
            return {"created": created, "updated": updated, "total": created + updated}
        except Exception as e:
            logger.error(f"❌ Error syncing official tax lots: {e}")
            self.db.rollback()
            raise

    async def get_tax_lots_for_user(
        self, user_id: int, symbol: Optional[str] = None
    ) -> List[TaxLot]:
        """Get all tax lots for a user, optionally filtered by symbol"""
        query = self.db.query(TaxLot).filter(TaxLot.user_id == user_id)

        if symbol:
            query = query.filter(TaxLot.symbol == symbol)

        return query.order_by(TaxLot.acquisition_date).all()

    async def get_tax_lots_for_account(
        self, user_id: int, account_id: str, symbol: Optional[str] = None
    ) -> List[TaxLot]:
        """Get tax lots for a specific account"""
        query = self.db.query(TaxLot).filter(
            TaxLot.user_id == user_id,
            TaxLot.account_id == account_id,
        )

        if symbol:
            query = query.filter(TaxLot.symbol == symbol)

        return query.order_by(TaxLot.acquisition_date).all()

    async def calculate_cost_basis(
        self, user_id: int, symbol: str, account_id: Optional[str] = None
    ) -> Dict:
        """Calculate detailed cost basis for a position (version)"""

        query = self.db.query(TaxLot).filter(
            TaxLot.user_id == user_id,
            TaxLot.symbol == symbol,
        )

        if account_id:
            query = query.filter(TaxLot.account_id == account_id)

        tax_lots = query.all()

        if not tax_lots:
            return {
                "symbol": symbol,
                "user_id": user_id,
                "total_shares": 0,
                "total_cost_basis": 0,
                "average_cost": 0,
                "tax_lots": [],
            }

        total_shares = sum(lot.remaining_quantity for lot in tax_lots)
        total_cost_basis = sum(
            lot.remaining_quantity * lot.cost_per_share for lot in tax_lots
        )
        average_cost = total_cost_basis / total_shares if total_shares > 0 else 0

        # Get current price for unrealized calculations
        current_price = await quote.get_current_price(symbol)

        lot_details = []
        for lot in tax_lots:
            current_mv = lot.quantity * current_price if current_price else 0
            unrealized_pnl = current_mv - (lot.remaining_quantity * lot.cost_per_share)

            lot_details.append(
                {
                    "lot_id": lot.id,
                    "acquisition_date": lot.acquisition_date.isoformat(),
                    "quantity": float(lot.remaining_quantity),
                    "cost_per_share": float(lot.cost_per_share),
                    "cost_basis": float(lot.remaining_quantity * lot.cost_per_share),
                    "market_value": float(current_mv),
                    "unrealized_pnl": float(unrealized_pnl),
                    "unrealized_pnl_pct": (
                        float(lot.unrealized_pnl_pct) if lot.unrealized_pnl_pct else 0
                    ),
                    "days_held": lot.days_held,
                    "is_long_term": lot.is_long_term,
                    "account_id": lot.account_id,
                    "tax_treatment": (
                        lot.tax_treatment.value if lot.tax_treatment else "taxable"
                    ),
                }
            )

        return {
            "symbol": symbol,
            "user_id": user_id,
            "total_shares": float(total_shares),
            "total_cost_basis": float(total_cost_basis),
            "average_cost": float(average_cost),
            "current_price": float(current_price) if current_price else 0,
            "total_market_value": (
                float(sum(l.quantity for l in tax_lots) * current_price)
                if current_price
                else 0
            ),
            "total_unrealized_pnl": sum(lot["unrealized_pnl"] for lot in lot_details),
            "tax_lots": lot_details,
        }

    async def simulate_sale(
        self,
        user_id: int,
        symbol: str,
        shares_to_sell: float,
        sale_price: float,
        account_id: Optional[str] = None,
        lot_method: TaxLotMethod = TaxLotMethod.FIFO,
    ) -> Dict:
        """Simulate a sale to show tax impact before execution (version)"""

        query = self.db.query(TaxLot).filter(
            TaxLot.user_id == user_id,
            TaxLot.symbol == symbol,
        )

        if account_id:
            query = query.filter(TaxLot.account_id == account_id)

        tax_lots = query.all()

        if not tax_lots:
            raise ValueError(f"No tax lots found for {symbol}")

        # Sort lots based on method
        if lot_method == TaxLotMethod.FIFO:
            tax_lots.sort(key=lambda x: x.acquisition_date)
        elif lot_method == TaxLotMethod.LIFO:
            tax_lots.sort(key=lambda x: x.acquisition_date, reverse=True)
        elif lot_method == TaxLotMethod.HIFO:
            tax_lots.sort(key=lambda x: x.cost_per_share, reverse=True)

        remaining_to_sell = shares_to_sell
        affected_lots = []
        total_cost_basis = 0
        total_proceeds = shares_to_sell * sale_price

        for lot in tax_lots:
            if remaining_to_sell <= 0:
                break

            shares_from_lot = min(remaining_to_sell, lot.remaining_quantity)
            cost_basis = shares_from_lot * lot.cost_per_share
            proceeds = shares_from_lot * sale_price
            realized_pnl = proceeds - cost_basis

            affected_lots.append(
                {
                    "lot_id": lot.id,
                    "acquisition_date": lot.acquisition_date.isoformat(),
                    "shares_sold": float(shares_from_lot),
                    "cost_per_share": float(lot.cost_per_share),
                    "cost_basis": float(cost_basis),
                    "proceeds": float(proceeds),
                    "realized_pnl": float(realized_pnl),
                    "is_long_term": lot.days_held >= 365,
                    "days_held": lot.days_held,
                    "account_id": lot.account_id,
                    "tax_treatment": (
                        lot.tax_treatment.value if lot.tax_treatment else "taxable"
                    ),
                }
            )

            total_cost_basis += cost_basis
            remaining_to_sell -= shares_from_lot

        if remaining_to_sell > 0:
            raise ValueError(
                f"Not enough shares to sell. Need {shares_to_sell}, available {shares_to_sell - remaining_to_sell}"
            )

        total_realized_pnl = total_proceeds - total_cost_basis
        short_term_pnl = sum(
            lot["realized_pnl"] for lot in affected_lots if not lot["is_long_term"]
        )
        long_term_pnl = sum(
            lot["realized_pnl"] for lot in affected_lots if lot["is_long_term"]
        )

        return {
            "user_id": user_id,
            "symbol": symbol,
            "shares_sold": shares_to_sell,
            "sale_price": sale_price,
            "total_proceeds": total_proceeds,
            "total_cost_basis": total_cost_basis,
            "total_realized_pnl": total_realized_pnl,
            "short_term_pnl": short_term_pnl,
            "long_term_pnl": long_term_pnl,
            "lot_method": lot_method.value,
            "affected_lots": affected_lots,
            "estimated_tax_impact": self._estimate_tax_impact(
                short_term_pnl, long_term_pnl
            ),
        }

    # NOTE: TaxLotSale model not defined in current models set; keep method signature generic
    async def execute_sale(
        self,
        user_id: int,
        symbol: str,
        shares_to_sell: float,
        sale_price: float,
        sale_date: datetime,
        account_id: Optional[str] = None,
        lot_method: TaxLotMethod = TaxLotMethod.FIFO,
        fees: float = 0.0,
    ) -> List[dict]:
        """Execute a sale and record tax lot sales (version)"""
        try:
            # First simulate to validate
            simulation = await self.simulate_sale(
                user_id, symbol, shares_to_sell, sale_price, account_id, lot_method
            )

            query = self.db.query(TaxLot).filter(
                TaxLot.user_id == user_id,
                TaxLot.symbol == symbol,
                TaxLot.remaining_quantity > 0,
            )

            if account_id:
                query = query.filter(TaxLot.account_id == account_id)

            tax_lots = query.all()

            # Sort based on method (same as simulation)
            if lot_method == TaxLotMethod.FIFO:
                tax_lots.sort(key=lambda x: x.acquisition_date)
            elif lot_method == TaxLotMethod.LIFO:
                tax_lots.sort(key=lambda x: x.acquisition_date, reverse=True)
            elif lot_method == TaxLotMethod.HIFO:
                tax_lots.sort(key=lambda x: x.cost_per_share, reverse=True)

            remaining_to_sell = shares_to_sell
            sales_records = []

            for lot in tax_lots:
                if remaining_to_sell <= 0:
                    break

                shares_from_lot = min(remaining_to_sell, lot.remaining_quantity)
                cost_basis = shares_from_lot * lot.cost_per_share
                gross_proceeds = shares_from_lot * sale_price
                net_proceeds = gross_proceeds - fees
                realized_pnl = net_proceeds - cost_basis

                # Create sale record (version)
                # Placeholder dict until TaxLotSale model is implemented
                sale_record = {
                    "tax_lot_id": lot.id,
                    "user_id": user_id,
                    "sale_date": sale_date,
                    "quantity_sold": float(shares_from_lot),
                    "sale_price_per_share": float(sale_price),
                    "gross_proceeds": float(gross_proceeds),
                    "fees": float(fees),
                    "net_proceeds": float(net_proceeds),
                    "cost_basis": float(cost_basis),
                    "realized_pnl": float(realized_pnl),
                    "holding_period_days": lot.days_held,
                    "is_long_term": lot.days_held >= 365,
                    "lot_selection_method": lot_method.value,
                    "tax_year": sale_date.year,
                }

                # Update tax lot (domain update; persisted TaxLotSale omitted)
                lot.execute_partial_sale(shares_from_lot)
                sales_records.append(sale_record)
                remaining_to_sell -= shares_from_lot

            self.db.commit()
            logger.info(f"✅ Executed sale of {shares_to_sell} shares of {symbol}")
            return sales_records

        except Exception as e:
            logger.error(f"❌ Error executing sale: {e}")
            self.db.rollback()
            raise

    async def update_market_values(self, user_id: int, symbol: Optional[str] = None):
        """Update market values for tax lots"""
        try:
            query = self.db.query(TaxLot).filter(TaxLot.user_id == user_id)

            if symbol:
                query = query.filter(TaxLot.symbol == symbol)

            tax_lots = query.all()

            # Group by symbol to minimize price lookups
            symbols_to_update = set(lot.symbol for lot in tax_lots)

            for symbol in symbols_to_update:
                try:
                    current_price = await quote.get_current_price(symbol)
                    if current_price:
                        symbol_lots = [lot for lot in tax_lots if lot.symbol == symbol]
                        for lot in symbol_lots:
                            lot.update_market_values(current_price)
                except Exception as e:
                    logger.warning(f"⚠️ Could not update price for {symbol}: {e}")

            self.db.commit()
            logger.info(
                f"✅ Updated market values for {len(symbols_to_update)} symbols"
            )

        except Exception as e:
            logger.error(f"❌ Error updating market values: {e}")
            self.db.rollback()

    async def generate_tax_summary(
        self, user_id: int, tax_year: int, account_id: Optional[str] = None
    ) -> Dict:
        """Generate comprehensive tax report for a year (version)"""
        try:
            # Get all sales for the tax year
            start_date = datetime(tax_year, 1, 1, tzinfo=UTC)
            end_date = datetime(tax_year, 12, 31, 23, 59, 59, tzinfo=UTC)

            # TaxLotSale persistence not available; return empty aggregates
            sales = []

            # Calculate totals
            short_term_gains = sum(
                sale.realized_pnl
                for sale in sales
                if not sale.is_long_term and sale.realized_pnl > 0
            )
            short_term_losses = sum(
                sale.realized_pnl
                for sale in sales
                if not sale.is_long_term and sale.realized_pnl < 0
            )
            long_term_gains = sum(
                sale.realized_pnl
                for sale in sales
                if sale.is_long_term and sale.realized_pnl > 0
            )
            long_term_losses = sum(
                sale.realized_pnl
                for sale in sales
                if sale.is_long_term and sale.realized_pnl < 0
            )

            net_short_term = short_term_gains + short_term_losses
            net_long_term = long_term_gains + long_term_losses
            total_net = net_short_term + net_long_term

            # Get unrealized positions
            unrealized_query = self.db.query(TaxLot).filter(TaxLot.user_id == user_id)

            if account_id:
                unrealized_query = unrealized_query.filter(
                    TaxLot.account_id == account_id
                )

            current_lots = unrealized_query.all()

            # Update current market values first
            await self.update_market_values(user_id)

            unrealized_gains = sum(
                lot.unrealized_pnl
                for lot in current_lots
                if lot.unrealized_pnl and lot.unrealized_pnl > 0
            )
            unrealized_losses = sum(
                lot.unrealized_pnl
                for lot in current_lots
                if lot.unrealized_pnl and lot.unrealized_pnl < 0
            )

            return {
                "user_id": user_id,
                "account_id": account_id,
                "tax_year": tax_year,
                "realized_gains_losses": {
                    "short_term_gains": float(short_term_gains),
                    "short_term_losses": float(short_term_losses),
                    "net_short_term": float(net_short_term),
                    "long_term_gains": float(long_term_gains),
                    "long_term_losses": float(long_term_losses),
                    "net_long_term": float(net_long_term),
                    "total_net": float(total_net),
                },
                "unrealized_positions": {
                    "unrealized_gains": float(unrealized_gains),
                    "unrealized_losses": float(unrealized_losses),
                    "net_unrealized": float(unrealized_gains + unrealized_losses),
                },
                "tax_efficiency_metrics": {
                    "loss_harvesting_potential": float(abs(unrealized_losses)),
                    "total_transactions": len(sales),
                    "long_term_percentage": (
                        (
                            (long_term_gains + abs(long_term_losses))
                            / (
                                short_term_gains
                                + abs(short_term_losses)
                                + long_term_gains
                                + abs(long_term_losses)
                            )
                            * 100
                        )
                        if (
                            short_term_gains
                            + abs(short_term_losses)
                            + long_term_gains
                            + abs(long_term_losses)
                        )
                        > 0
                        else 0
                    ),
                },
                "generated_at": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            logger.error(f"❌ Error generating tax report: {e}")
            return {}

    def _estimate_tax_impact(self, short_term_pnl: float, long_term_pnl: float) -> Dict:
        """Estimate tax impact (simplified calculation)"""
        # Simplified tax rates - in reality this would be much more complex
        short_term_rate = 0.37  # Assume highest bracket for short-term
        long_term_rate = 0.20  # Long-term capital gains rate

        short_term_tax = max(0, short_term_pnl * short_term_rate)
        long_term_tax = max(0, long_term_pnl * long_term_rate)

        return {
            "short_term_tax": short_term_tax,
            "long_term_tax": long_term_tax,
            "total_estimated_tax": short_term_tax + long_term_tax,
            "assumptions": {
                "short_term_rate": short_term_rate,
                "long_term_rate": long_term_rate,
                "note": "Simplified calculation - consult tax professional",
            },
        }

    def close(self):
        """Close database session"""
        if self.db:
            self.db.close()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def get_user_tax_summary(user_id: int, tax_year: int = None) -> Dict:
    """Convenience function to get tax summary for a user"""
    service = TaxLotService()
    try:
        if not tax_year:
            tax_year = datetime.now(UTC).year
        return await service.generate_tax_summary(user_id, tax_year)
    finally:
        service.close()


# Create global instance
v2_tax_lot_service = TaxLotService()
