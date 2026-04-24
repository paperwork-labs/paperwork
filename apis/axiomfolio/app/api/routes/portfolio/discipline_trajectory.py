"""GET /api/v1/portfolio/discipline-trajectory — C7 discipline-bounded trajectory tile."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.account_balance import AccountBalance
from app.models.broker_account import BrokerAccount
from app.models.user import User
from app.services.billing.entitlement_service import EntitlementService
from app.services.portfolio.discipline_trajectory_service import (
    TrajectoryAnchors,
    compute_anchors,
    compute_projected_year_end,
    compute_trend,
    decimal_from_balance_fields,
)

router = APIRouter()

FEATURE_MULTI_BROKER = "execution.multi_broker"


def _enabled_accounts_query(db: Session, user_id: int):
    return db.query(BrokerAccount).filter(
        BrokerAccount.user_id == user_id, BrokerAccount.is_enabled.is_(True)
    )


def _resolve_default_account(db: Session, user_id: int) -> BrokerAccount | None:
    q = _enabled_accounts_query(db, user_id)
    primary = q.filter(BrokerAccount.is_primary.is_(True)).first()
    if primary:
        return primary
    return q.order_by(BrokerAccount.id.asc()).first()


def _get_account_for_user(
    db: Session,
    user_id: int,
    account_id: int | None,
) -> BrokerAccount:
    if account_id is None:
        acc = _resolve_default_account(db, user_id)
        if acc is None:
            raise HTTPException(status_code=404, detail="No enabled broker account")
        return acc
    acc = _enabled_accounts_query(db, user_id).filter(BrokerAccount.id == account_id).one_or_none()
    if acc is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return acc


def _year_start_utc(year: int) -> datetime:
    return datetime(year, 1, 1, tzinfo=UTC)


def _starting_equity_for_account(
    db: Session,
    *,
    user_id: int,
    broker_account_id: int,
    as_of: datetime,
) -> Decimal | None:
    """YTD anchor: first balance on/after 1 Jan; else last balance before year start."""
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)
    else:
        as_of = as_of.astimezone(UTC)
    ys = _year_start_utc(as_of.year)

    first_in_year = (
        db.query(AccountBalance)
        .filter(
            AccountBalance.user_id == user_id,
            AccountBalance.broker_account_id == broker_account_id,
            AccountBalance.balance_date >= ys,
            AccountBalance.balance_date <= as_of,
        )
        .order_by(AccountBalance.balance_date.asc(), AccountBalance.id.asc())
        .first()
    )
    if first_in_year is not None:
        v = decimal_from_balance_fields(first_in_year.net_liquidation, first_in_year.equity)
        return v if v > 0 else None

    prior = (
        db.query(AccountBalance)
        .filter(
            AccountBalance.user_id == user_id,
            AccountBalance.broker_account_id == broker_account_id,
            AccountBalance.balance_date < ys,
        )
        .order_by(AccountBalance.balance_date.desc(), AccountBalance.id.desc())
        .first()
    )
    if prior is None:
        return None
    v = decimal_from_balance_fields(prior.net_liquidation, prior.equity)
    return v if v > 0 else None


def _latest_equity_for_account(
    db: Session,
    *,
    user_id: int,
    broker_account_id: int,
    as_of: datetime,
) -> Decimal:
    row = (
        db.query(AccountBalance)
        .filter(
            AccountBalance.user_id == user_id,
            AccountBalance.broker_account_id == broker_account_id,
            AccountBalance.balance_date <= as_of,
        )
        .order_by(AccountBalance.balance_date.desc(), AccountBalance.id.desc())
        .first()
    )
    if row is None:
        return Decimal("0")
    return decimal_from_balance_fields(row.net_liquidation, row.equity)


def _serialize_anchors(a: TrajectoryAnchors) -> dict[str, float]:
    return {
        "unleveraged_ceiling": float(a.unleveraged_ceiling),
        "leveraged_ceiling": float(a.leveraged_ceiling),
        "speculative_ceiling": float(a.speculative_ceiling),
    }


def _row_for_account(
    db: Session,
    *,
    user_id: int,
    account: BrokerAccount,
    as_of: datetime,
) -> dict[str, Any]:
    starting = _starting_equity_for_account(
        db, user_id=user_id, broker_account_id=account.id, as_of=as_of
    )
    current = _latest_equity_for_account(
        db, user_id=user_id, broker_account_id=account.id, as_of=as_of
    )
    broker_slug = account.broker.value if hasattr(account.broker, "value") else str(account.broker)
    mask = (account.account_number or "")[-4:] if account.account_number else ""
    return {
        "account_id": str(account.id),
        "broker": broker_slug,
        "account_number_suffix": mask,
        "starting_equity": float(starting) if starting is not None else None,
        "current_equity": float(current),
    }


@router.get("/discipline-trajectory")
async def get_discipline_trajectory(
    account_id: int | None = Query(
        None,
        description="Broker account primary key; defaults to primary (else lowest id) enabled account.",
    ),
    aggregate: bool = Query(False, description="Sum across all enabled accounts (requires Pro+)."),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    as_of = datetime.now(UTC)

    if aggregate:
        decision = EntitlementService.check(db, user, FEATURE_MULTI_BROKER)
        if not decision.allowed:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "feature_required",
                    "feature": decision.feature.key,
                    "message": decision.reason,
                    "required_tier": decision.required_tier.value,
                    "current_tier": decision.current_tier.value,
                },
            )

        accounts = _enabled_accounts_query(db, user.id).order_by(BrokerAccount.id.asc()).all()
        if not accounts:
            raise HTTPException(status_code=404, detail="No enabled broker account")

        by_account: list[dict[str, Any]] = []
        total_starting_eff = Decimal("0")
        total_current = Decimal("0")
        sum_unlev = Decimal("0")
        sum_lev = Decimal("0")
        sum_spec = Decimal("0")

        for acct in accounts:
            row = _row_for_account(db, user_id=user.id, account=acct, as_of=as_of)
            by_account.append(row)
            cur_d = Decimal(str(row["current_equity"]))
            total_current += cur_d
            st_raw = row["starting_equity"]
            st_d = Decimal(str(st_raw)) if st_raw is not None else None
            # When YTD baseline is missing but we have NLV, use current as neutral
            # baseline for that slice so consolidated anchors/projection still compute.
            eff = st_d if st_d is not None and st_d > 0 else (cur_d if cur_d > 0 else None)
            if eff is None:
                continue
            total_starting_eff += eff
            anc = compute_anchors(eff)
            sum_unlev += anc.unleveraged_ceiling
            sum_lev += anc.leveraged_ceiling
            sum_spec += anc.speculative_ceiling

        if total_starting_eff <= 0:
            return {
                "account_id": None,
                "aggregate": True,
                "starting_equity": None,
                "current_equity": float(total_current),
                "anchors": None,
                "projected_year_end": None,
                "trend": "flat",
                "as_of": as_of.isoformat(),
                "by_account": by_account,
            }

        anchors = TrajectoryAnchors(
            unleveraged_ceiling=sum_unlev.quantize(Decimal("0.01")),
            leveraged_ceiling=sum_lev.quantize(Decimal("0.01")),
            speculative_ceiling=sum_spec.quantize(Decimal("0.01")),
        )
        projected = compute_projected_year_end(
            starting_equity=total_starting_eff,
            current_equity=total_current,
            as_of=as_of,
        )
        trend = compute_trend(starting_equity=total_starting_eff, current_equity=total_current)
        return {
            "account_id": None,
            "aggregate": True,
            "starting_equity": float(total_starting_eff),
            "current_equity": float(total_current),
            "anchors": _serialize_anchors(anchors),
            "projected_year_end": float(projected) if projected is not None else None,
            "trend": trend,
            "as_of": as_of.isoformat(),
            "by_account": by_account,
        }

    account = _get_account_for_user(db, user.id, account_id)
    starting = _starting_equity_for_account(
        db, user_id=user.id, broker_account_id=account.id, as_of=as_of
    )
    current = _latest_equity_for_account(
        db, user_id=user.id, broker_account_id=account.id, as_of=as_of
    )

    if starting is None or starting <= 0:
        return {
            "account_id": str(account.id),
            "aggregate": False,
            "starting_equity": None,
            "current_equity": float(current),
            "anchors": None,
            "projected_year_end": None,
            "trend": "flat",
            "as_of": as_of.isoformat(),
            "by_account": None,
        }

    anchors = compute_anchors(starting)
    projected = compute_projected_year_end(
        starting_equity=starting,
        current_equity=current,
        as_of=as_of,
    )
    trend = compute_trend(starting_equity=starting, current_equity=current)

    return {
        "account_id": str(account.id),
        "aggregate": False,
        "starting_equity": float(starting),
        "current_equity": float(current),
        "anchors": _serialize_anchors(anchors),
        "projected_year_end": float(projected) if projected is not None else None,
        "trend": trend,
        "as_of": as_of.isoformat(),
        "by_account": None,
    }
