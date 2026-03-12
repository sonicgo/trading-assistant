"""
Dashboard API endpoints - Phase 6 Portfolio Overview

Provides aggregated data for the portfolio command center dashboard.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, func, select, true
from sqlalchemy.orm import Session

from app.api import deps
from app.domain import models


def _normalize_price_to_gbp(price: Decimal, currency: str | None) -> Decimal:
    """Normalize price to GBP base currency.

    If the price currency is GBp or GBX (pence), convert to GBP by dividing by 100.
    """
    if currency == "GBp" or currency == "GBX":
        return price / Decimal("100")
    return price

router = APIRouter()


class SleeveAllocation(BaseModel):
    """Sleeve allocation summary for dashboard."""
    sleeve_code: str
    sleeve_name: str
    target_weight_pct: Decimal
    current_weight_pct: Decimal
    current_value_gbp: Decimal
    drift_pct: Decimal
    is_drifted: bool


class RecentActivityItem(BaseModel):
    """Recent activity item for activity feed."""
    activity_type: str
    description: str
    occurred_at: str
    actor_name: str | None = None
    metadata: dict[str, Any] | None = None


class PortfolioDashboardSummary(BaseModel):
    """Complete dashboard summary for portfolio command center."""
    portfolio_id: str
    as_of: str
    
    # Value Summary
    total_value_gbp: Decimal
    cash_balance_gbp: Decimal
    holdings_value_gbp: Decimal
    
    # Drift Status
    is_drifted: bool
    max_drift_pct: Decimal
    drift_threshold_pct: Decimal
    
    # Freeze Status
    is_frozen: bool
    freeze_reason: str | None = None
    
    # Allocations
    sleeve_allocations: list[SleeveAllocation]
    
    # Recent Activity (last 5 items)
    recent_activity: list[RecentActivityItem]


@router.get(
    "/{portfolio_id}/dashboard/summary",
    response_model=PortfolioDashboardSummary,
)
def get_dashboard_summary(
    portfolio_id: UUID,
    db: deps.SessionDep,
    user: deps.CurrentUser,
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
) -> PortfolioDashboardSummary:
    """
    Get comprehensive dashboard summary for portfolio command center.
    
    Aggregates data from:
    - Cash and holding snapshots for current valuation
    - Policy allocations for target weights
    - Latest prices for market values
    - Audit events for recent activity
    """
    as_of = datetime.now(timezone.utc)
    
    # Get cash snapshot
    cash_snapshot = (
        db.query(models.CashSnapshot)
        .filter(models.CashSnapshot.portfolio_id == portfolio_id)
        .first()
    )
    cash_balance = cash_snapshot.balance_gbp if cash_snapshot else Decimal("0")
    
    # Get holding snapshots with listings
    holdings_query = (
        db.query(
            models.HoldingSnapshot,
            models.InstrumentListing,
            models.Instrument,
        )
        .join(
            models.InstrumentListing,
            models.HoldingSnapshot.listing_id == models.InstrumentListing.listing_id,
        )
        .join(
            models.Instrument,
            models.InstrumentListing.instrument_id == models.Instrument.instrument_id,
        )
        .filter(models.HoldingSnapshot.portfolio_id == portfolio_id)
        .all()
    )
    
    # Get latest prices for all holdings (most recent available, even if not today)
    listing_ids = [h.listing_id for h, _, _ in holdings_query]
    latest_prices = {}
    for listing_id in listing_ids:
        price = (
            db.query(models.PricePoint)
            .filter(
                models.PricePoint.listing_id == listing_id,
                models.PricePoint.is_close == true(),
            )
            .order_by(desc(models.PricePoint.as_of))
            .first()
        )
        if price:
            latest_prices[listing_id] = price
    
    # Get policy allocations
    allocations = (
        db.query(models.PortfolioPolicyAllocation)
        .filter(models.PortfolioPolicyAllocation.portfolio_id == portfolio_id)
        .all()
    )
    
    # Build allocation map
    allocation_map = {a.listing_id: a for a in allocations}
    
    # Calculate holding values with currency normalization
    holdings_value = Decimal("0")
    sleeve_values: dict[str, Decimal] = {}
    
    for holding, listing, instrument in holdings_query:
        price = latest_prices.get(holding.listing_id)
        if price:
            # Normalize GBp (pence) to GBP if needed
            normalized_price = _normalize_price_to_gbp(price.price, price.currency)
            value = holding.quantity * normalized_price
            holdings_value += value
            
            # Get sleeve from allocation
            allocation = allocation_map.get(holding.listing_id)
            if allocation:
                sleeve_code = allocation.sleeve_code
                sleeve_values[sleeve_code] = sleeve_values.get(sleeve_code, Decimal("0")) + value
    
    total_value = cash_balance + holdings_value
    
    # Calculate sleeve allocations
    DRIFT_THRESHOLD = Decimal("5.0")
    sleeve_allocations: list[SleeveAllocation] = []
    is_drifted = False
    max_drift = Decimal("0")
    
    # Get unique sleeves from allocations
    sleeve_codes = set(a.sleeve_code for a in allocations)
    
    for sleeve_code in sleeve_codes:
        sleeve_allocs = [a for a in allocations if a.sleeve_code == sleeve_code]
        if not sleeve_allocs:
            continue
        
        # Use first allocation's sleeve name (they should all be same)
        sleeve_name = sleeve_allocs[0].sleeve_name if hasattr(sleeve_allocs[0], 'sleeve_name') else sleeve_code
        
        # Calculate target weight for sleeve (sum of targets)
        target_weight = sum(
            (a.target_weight_pct or Decimal("0")) for a in sleeve_allocs
        )
        
        # Calculate current weight
        sleeve_value = sleeve_values.get(sleeve_code, Decimal("0"))
        if total_value > 0:
            current_weight = (sleeve_value / total_value) * Decimal("100")
        else:
            current_weight = Decimal("0")
        
        drift = current_weight - target_weight
        sleeve_is_drifted = abs(drift) > DRIFT_THRESHOLD
        
        if sleeve_is_drifted:
            is_drifted = True
        
        max_drift = max(max_drift, abs(drift))
        
        sleeve_allocations.append(
            SleeveAllocation(
                sleeve_code=sleeve_code,
                sleeve_name=sleeve_code,  # Use code as name for now
                target_weight_pct=target_weight,
                current_weight_pct=current_weight,
                current_value_gbp=sleeve_value,
                drift_pct=drift,
                is_drifted=sleeve_is_drifted,
            )
        )
    
    # Sort by drift (highest absolute drift first)
    sleeve_allocations.sort(key=lambda x: abs(x.drift_pct), reverse=True)
    
    # Get freeze status
    freeze = (
        db.query(models.FreezeState)
        .filter(
            models.FreezeState.portfolio_id == portfolio_id,
            models.FreezeState.is_frozen == True,
            models.FreezeState.cleared_at.is_(None),
        )
        .first()
    )
    
    # Get recent activity (last 5 items)
    recent_activity: list[RecentActivityItem] = []
    
    # Query audit events
    audit_events = (
        db.query(models.AuditEvent)
        .filter(models.AuditEvent.portfolio_id == portfolio_id)
        .order_by(desc(models.AuditEvent.occurred_at))
        .limit(5)
        .all()
    )
    
    for event in audit_events:
        activity_type = event.event_type.replace("_", " ").title()
        recent_activity.append(
            RecentActivityItem(
                activity_type=activity_type,
                description=event.summary,
                occurred_at=event.occurred_at.isoformat(),
                actor_name=None,  # Could join with users table
                metadata=event.details,
            )
        )
    
    # If no audit events, add some placeholder activity
    if not recent_activity:
        recent_activity.append(
            RecentActivityItem(
                activity_type="Portfolio Loaded",
                description="Dashboard viewed",
                occurred_at=as_of.isoformat(),
            )
        )
    
    return PortfolioDashboardSummary(
        portfolio_id=str(portfolio_id),
        as_of=as_of.isoformat().replace("+00:00", "Z"),
        total_value_gbp=total_value,
        cash_balance_gbp=cash_balance,
        holdings_value_gbp=holdings_value,
        is_drifted=is_drifted,
        max_drift_pct=max_drift,
        drift_threshold_pct=DRIFT_THRESHOLD,
        is_frozen=freeze is not None,
        freeze_reason=freeze.reason if freeze else None,
        sleeve_allocations=sleeve_allocations,
        recent_activity=recent_activity,
    )
