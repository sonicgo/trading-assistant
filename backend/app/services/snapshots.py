"""
Snapshot Mutation Service - Phase 3 Book of Record

Deterministic helpers for updating cash and holding snapshots.
All functions assume they are called within an active DB transaction.

Lock order (Playbook 6.2):
1. Cash snapshot first
2. Holding snapshots sorted by listing_id

Accounting rules (Playbook 6.3):
- CONTRIBUTION: net_cash_delta_gbp > 0, no holding delta
- BUY: quantity_delta > 0, net_cash_delta_gbp < 0, book_cost increases
- SELL: quantity_delta < 0, net_cash_delta_gbp > 0, book_cost reduced proportionally
- ADJUSTMENT: explicit deltas for reconciliation
- REVERSAL: equal-and-opposite deltas to original entry
"""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.domain.models import CashSnapshot, HoldingSnapshot, LedgerEntry


def recalculate_avg_cost(book_cost: Decimal, quantity: Decimal) -> Decimal:
    """
    Recalculate average cost per unit.
    
    Args:
        book_cost: Total book cost in GBP
        quantity: Total quantity held
        
    Returns:
        Average cost per unit, or 0 if quantity is 0
    """
    if quantity <= 0:
        return Decimal("0")
    return (book_cost / quantity).quantize(Decimal("0.0000000001"), rounding=ROUND_HALF_UP)


def apply_cash_delta(
    db: Session,
    portfolio_id: uuid.UUID,
    delta_gbp: Decimal,
    entry_id: uuid.UUID,
) -> CashSnapshot:
    """
    Apply a cash delta to the portfolio's cash snapshot.
    Creates the snapshot row if it doesn't exist (upsert behavior).
    
    Args:
        db: SQLAlchemy session (must be in transaction)
        portfolio_id: Portfolio UUID
        delta_gbp: Signed cash delta (positive = credit, negative = debit)
        entry_id: The ledger entry causing this change
        
    Returns:
        Updated CashSnapshot
        
    Note:
        Negative cash balances are allowed per Playbook P3-D02.
    """
    snapshot = db.query(CashSnapshot).filter(
        CashSnapshot.portfolio_id == portfolio_id
    ).with_for_update().first()
    
    if snapshot is None:
        snapshot = CashSnapshot(
            portfolio_id=portfolio_id,
            balance_gbp=delta_gbp,
            updated_at=datetime.now(timezone.utc),
            last_entry_id=entry_id,
            version_no=Decimal("1"),
        )
        db.add(snapshot)
    else:
        snapshot.balance_gbp += delta_gbp
        snapshot.updated_at = datetime.now(timezone.utc)
        snapshot.last_entry_id = entry_id
        snapshot.version_no += Decimal("1")
    
    return snapshot


def apply_holding_delta(
    db: Session,
    portfolio_id: uuid.UUID,
    listing_id: uuid.UUID,
    quantity_delta: Optional[Decimal],
    book_cost_delta: Optional[Decimal],
    entry_id: uuid.UUID,
    is_sell: bool = False,
) -> HoldingSnapshot:
    """
    Apply a holding delta to the portfolio's holding snapshot.
    Creates the snapshot row if it doesn't exist (upsert behavior).
    
    Args:
        db: SQLAlchemy session (must be in transaction)
        portfolio_id: Portfolio UUID
        listing_id: Listing UUID
        quantity_delta: Signed quantity delta (positive = add, negative = remove)
        book_cost_delta: Explicit book cost delta (for ADJUSTMENT/REVERSAL)
        entry_id: The ledger entry causing this change
        is_sell: Whether this is a SELL operation (triggers avg_cost reduction logic)
        
    Returns:
        Updated HoldingSnapshot
        
    Raises:
        ValueError: If resulting quantity would be negative (P3-D03: no short positions)
    """
    snapshot = db.query(HoldingSnapshot).filter(
        HoldingSnapshot.portfolio_id == portfolio_id,
        HoldingSnapshot.listing_id == listing_id,
    ).with_for_update().first()
    
    if snapshot is None:
        if quantity_delta is None or quantity_delta <= 0:
            if quantity_delta is not None and quantity_delta < 0:
                raise ValueError(
                    f"Cannot reduce quantity for non-existent holding: portfolio={portfolio_id}, listing={listing_id}"
                )
            return None
        
        new_quantity = quantity_delta
        new_book_cost = book_cost_delta if book_cost_delta else Decimal("0")
        new_avg_cost = recalculate_avg_cost(new_book_cost, new_quantity)
        
        snapshot = HoldingSnapshot(
            portfolio_id=portfolio_id,
            listing_id=listing_id,
            quantity=new_quantity,
            book_cost_gbp=new_book_cost,
            avg_cost_gbp=new_avg_cost,
            updated_at=datetime.now(timezone.utc),
            last_entry_id=entry_id,
            version_no=Decimal("1"),
        )
        db.add(snapshot)
    else:
        old_quantity = snapshot.quantity
        old_book_cost = snapshot.book_cost_gbp
        old_avg_cost = snapshot.avg_cost_gbp
        
        if quantity_delta is not None:
            new_quantity = old_quantity + quantity_delta
            
            # P3-D03: Negative holdings not allowed
            if new_quantity < 0:
                raise ValueError(
                    f"Sell would result in negative quantity: portfolio={portfolio_id}, "
                    f"listing={listing_id}, current={old_quantity}, delta={quantity_delta}"
                )
        else:
            new_quantity = old_quantity
        
        if is_sell and quantity_delta is not None and quantity_delta < 0:
            # SELL: Reduce book_cost by pre-sell avg_cost × sold quantity
            sold_quantity = abs(quantity_delta)
            cost_reduction = (old_avg_cost * sold_quantity).quantize(
                Decimal("0.0000000001"), rounding=ROUND_HALF_UP
            )
            new_book_cost = old_book_cost - cost_reduction
            
            if new_book_cost < 0:
                new_book_cost = Decimal("0")
        elif book_cost_delta is not None:
            new_book_cost = old_book_cost + book_cost_delta
        else:
            new_book_cost = old_book_cost
        
        if new_quantity > 0:
            new_avg_cost = recalculate_avg_cost(new_book_cost, new_quantity)
        else:
            # When quantity becomes 0, reset costs to 0 (constraint: ck_holding_snapshot_cost_consistency)
            new_book_cost = Decimal("0")
            new_avg_cost = Decimal("0")
        
        snapshot.quantity = new_quantity
        snapshot.book_cost_gbp = new_book_cost
        snapshot.avg_cost_gbp = new_avg_cost
        snapshot.updated_at = datetime.now(timezone.utc)
        snapshot.last_entry_id = entry_id
        snapshot.version_no += Decimal("1")
    
    return snapshot


def get_or_create_holding_snapshot(
    db: Session,
    portfolio_id: uuid.UUID,
    listing_id: uuid.UUID,
) -> Optional[HoldingSnapshot]:
    """
    Get existing holding snapshot or return None if not exists.
    Used for reading current state without modifying.
    
    Args:
        db: SQLAlchemy session
        portfolio_id: Portfolio UUID
        listing_id: Listing UUID
        
    Returns:
        HoldingSnapshot or None
    """
    return db.query(HoldingSnapshot).filter(
        HoldingSnapshot.portfolio_id == portfolio_id,
        HoldingSnapshot.listing_id == listing_id,
    ).first()


def get_or_create_cash_snapshot(
    db: Session,
    portfolio_id: uuid.UUID,
) -> CashSnapshot:
    """
    Get existing cash snapshot or create empty one.
    Used for reading current state. Does NOT lock.
    
    Args:
        db: SQLAlchemy session
        portfolio_id: Portfolio UUID
        
    Returns:
        CashSnapshot (existing or new unsaved instance)
    """
    snapshot = db.query(CashSnapshot).filter(
        CashSnapshot.portfolio_id == portfolio_id
    ).first()
    
    if snapshot is None:
        snapshot = CashSnapshot(
            portfolio_id=portfolio_id,
            balance_gbp=Decimal("0"),
            updated_at=datetime.now(timezone.utc),
            last_entry_id=None,
            version_no=Decimal("0"),
        )
    
    return snapshot
