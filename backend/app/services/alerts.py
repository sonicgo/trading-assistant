"""
Alerts Service with Deduplication
Phase 2: Data Quality Gate
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.domain.models import Alert
from datetime import datetime, timezone
from typing import Optional
import uuid


def create_alert(
    db: Session,
    portfolio_id: str,
    listing_id: Optional[str],
    severity: str,  # INFO, WARN, CRITICAL
    rule_code: str,  # DQ_GBX_SCALE, DQ_STALE_CLOSE, etc.
    title: str,
    message: Optional[str] = None,
    details: Optional[dict] = None,
) -> Optional[Alert]:
    """
    Create an alert with deduplication.
    
    Before creating, checks for unresolved alert with same (portfolio_id, listing_id, rule_code).
    Returns Alert if created, None if duplicate (unresolved alert already exists).
    
    Args:
        db: SQLAlchemy session (externally provided, not FastAPI Depends)
        portfolio_id: Portfolio UUID
        listing_id: Listing UUID (optional, can be None for portfolio-level alerts)
        severity: Alert severity level (INFO, WARN, CRITICAL)
        rule_code: Rule code that triggered the alert (e.g., DQ_GBX_SCALE)
        title: Alert title
        message: Optional detailed message
        details: Optional JSONB details (thresholds, observed values, etc.)
    
    Returns:
        Alert object if created, None if duplicate unresolved alert exists
    """
    # Check for existing unresolved alert with same (portfolio_id, listing_id, rule_code)
    existing_alert = db.query(Alert).filter(
        and_(
            Alert.portfolio_id == portfolio_id,
            Alert.listing_id == listing_id,
            Alert.rule_code == rule_code,
            Alert.resolved_at.is_(None)  # Only unresolved alerts count as duplicates
        )
    ).first()
    
    if existing_alert:
        # Deduplication: alert already exists and is unresolved
        return None
    
    # Create new alert
    alert = Alert(
        alert_id=uuid.uuid4(),
        portfolio_id=portfolio_id,
        listing_id=listing_id,
        severity=severity,
        rule_code=rule_code,
        title=title,
        message=message,
        details=details,
        created_at=datetime.now(timezone.utc),
        resolved_at=None
    )
    
    db.add(alert)
    db.commit()
    db.refresh(alert)
    
    return alert


def resolve_alert(db: Session, alert_id: str) -> bool:
    """
    Resolve a single alert by setting resolved_at timestamp.
    
    Args:
        db: SQLAlchemy session
        alert_id: Alert UUID to resolve
    
    Returns:
        True if alert was resolved, False if alert not found or already resolved
    """
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    
    if not alert:
        return False
    
    if alert.resolved_at is not None:
        # Already resolved
        return False
    
    alert.resolved_at = datetime.now(timezone.utc)
    db.commit()
    
    return True


def resolve_alerts_by_rule(
    db: Session,
    portfolio_id: str,
    listing_id: Optional[str],
    rule_code: str
) -> int:
    """
    Bulk resolve all unresolved alerts matching criteria.
    
    Args:
        db: SQLAlchemy session
        portfolio_id: Portfolio UUID
        listing_id: Listing UUID (optional, can be None)
        rule_code: Rule code to match
    
    Returns:
        Count of alerts resolved
    """
    alerts = db.query(Alert).filter(
        and_(
            Alert.portfolio_id == portfolio_id,
            Alert.listing_id == listing_id,
            Alert.rule_code == rule_code,
            Alert.resolved_at.is_(None)  # Only unresolved alerts
        )
    ).all()
    
    count = len(alerts)
    now = datetime.now(timezone.utc)
    
    for alert in alerts:
        alert.resolved_at = now
    
    if count > 0:
        db.commit()
    
    return count


def get_unresolved_alerts(db: Session, portfolio_id: str) -> list[Alert]:
    """
    Get all unresolved alerts for a portfolio.
    
    Args:
        db: SQLAlchemy session
        portfolio_id: Portfolio UUID
    
    Returns:
        List of unresolved Alert objects
    """
    return db.query(Alert).filter(
        and_(
            Alert.portfolio_id == portfolio_id,
            Alert.resolved_at.is_(None)
        )
    ).all()
