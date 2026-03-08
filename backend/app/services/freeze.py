"""
Freeze Service - Circuit Breaker for Portfolios
Phase 2: Data Quality & Safety
"""
from sqlalchemy.orm import Session
from app.domain.models import FreezeState
from datetime import datetime, timezone
from typing import Optional
import uuid


def freeze_portfolio(
    db: Session,
    portfolio_id: str,
    reason_alert_id: Optional[str] = None,
) -> FreezeState:
    """
    Freeze a portfolio (circuit breaker).
    Idempotent: if already frozen, returns existing freeze state.
    
    Args:
        db: SQLAlchemy session
        portfolio_id: UUID of the portfolio to freeze
        reason_alert_id: Optional UUID of the alert that triggered the freeze
        
    Returns:
        FreezeState: The freeze state record (new or existing)
    """
    # Check if already frozen
    existing_freeze = is_portfolio_frozen(db, portfolio_id)
    if existing_freeze:
        # Return the existing active freeze state
        return db.query(FreezeState).filter(
            FreezeState.portfolio_id == uuid.UUID(portfolio_id),
            FreezeState.is_frozen == True,
            FreezeState.cleared_at == None,
        ).first()
    
    # Create new freeze state
    freeze_state = FreezeState(
        freeze_id=uuid.uuid4(),
        portfolio_id=uuid.UUID(portfolio_id),
        is_frozen=True,
        reason_alert_id=uuid.UUID(reason_alert_id) if reason_alert_id else None,
        created_at=datetime.now(timezone.utc),
    )
    db.add(freeze_state)
    db.commit()
    db.refresh(freeze_state)
    return freeze_state


def unfreeze_portfolio(
    db: Session,
    portfolio_id: str,
    cleared_by_user_id: Optional[str] = None,
) -> Optional[FreezeState]:
    """
    Unfreeze a portfolio.
    Clears the active freeze by setting cleared_at and cleared_by_user_id.
    
    Args:
        db: SQLAlchemy session
        portfolio_id: UUID of the portfolio to unfreeze
        cleared_by_user_id: Optional UUID of the user who cleared the freeze
        
    Returns:
        FreezeState: The updated freeze state record, or None if no active freeze
    """
    # Find active freeze (is_frozen=True, cleared_at is None)
    freeze_state = db.query(FreezeState).filter(
        FreezeState.portfolio_id == uuid.UUID(portfolio_id),
        FreezeState.is_frozen == True,
        FreezeState.cleared_at == None,
    ).first()
    
    if not freeze_state:
        return None
    
    # Update the freeze state
    freeze_state.cleared_at = datetime.now(timezone.utc)
    if cleared_by_user_id:
        freeze_state.cleared_by_user_id = uuid.UUID(cleared_by_user_id)
    
    db.commit()
    db.refresh(freeze_state)
    return freeze_state


def is_portfolio_frozen(db: Session, portfolio_id: str) -> bool:
    """
    Check if portfolio is currently frozen.
    Looks for FreezeState with is_frozen=True and cleared_at is None.
    
    Args:
        db: SQLAlchemy session
        portfolio_id: UUID of the portfolio to check
        
    Returns:
        bool: True if portfolio is frozen, False otherwise
    """
    freeze_state = db.query(FreezeState).filter(
        FreezeState.portfolio_id == uuid.UUID(portfolio_id),
        FreezeState.is_frozen == True,
        FreezeState.cleared_at == None,
    ).first()
    
    return freeze_state is not None


def get_freeze_state(db: Session, portfolio_id: str) -> Optional[FreezeState]:
    """
    Get the latest freeze state for a portfolio (whether active or cleared).
    
    Args:
        db: SQLAlchemy session
        portfolio_id: UUID of the portfolio
        
    Returns:
        FreezeState: The latest freeze state record, or None if no freeze history
    """
    freeze_state = db.query(FreezeState).filter(
        FreezeState.portfolio_id == uuid.UUID(portfolio_id),
    ).order_by(FreezeState.created_at.desc()).first()
    
    return freeze_state
