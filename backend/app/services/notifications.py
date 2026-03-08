"""
Notifications Service
Phase 2: Emit notification rows for CRITICAL events (polling feed).
"""

from sqlalchemy.orm import Session
from app.domain.models import Notification
from datetime import datetime, timezone
from typing import Optional
import uuid


def emit_notification(
    db: Session,
    owner_user_id: str,
    severity: str,  # INFO, WARN, CRITICAL
    title: str,
    body: Optional[str] = None,
    meta: Optional[dict] = None,  # {portfolio_id, alert_id, run_id, ...}
) -> Optional[Notification]:
    """
    Emit a notification for an event.
    Phase 2 minimum: only emit for CRITICAL severity.
    
    Args:
        db: SQLAlchemy session
        owner_user_id: UUID of the user who owns the notification
        severity: Severity level (INFO, WARN, CRITICAL)
        title: Notification title
        body: Optional notification body/message
        meta: Optional JSONB metadata (portfolio_id, alert_id, run_id, etc.)
    
    Returns:
        Notification object if created, None if filtered out (non-CRITICAL in Phase 2)
    """
    # Phase 2: Only create notification if severity == "CRITICAL"
    if severity != "CRITICAL":
        return None
    
    notification = Notification(
        notification_id=uuid.uuid4(),
        owner_user_id=uuid.UUID(owner_user_id) if isinstance(owner_user_id, str) else owner_user_id,
        severity=severity,
        title=title,
        body=body,
        meta=meta,
        created_at=datetime.now(timezone.utc),
        read_at=None,
    )
    
    db.add(notification)
    db.flush()  # Ensure it's persisted before returning
    
    return notification


def get_notifications(
    db: Session,
    owner_user_id: str,
    since: Optional[datetime] = None,
    unread_only: bool = False,
    limit: int = 50,
) -> list[Notification]:
    """
    Get notifications for a user, optionally filtered.
    
    Args:
        db: SQLAlchemy session
        owner_user_id: UUID of the user
        since: Optional datetime to filter notifications created after this time
        unread_only: If True, only return unread notifications (read_at is None)
        limit: Maximum number of notifications to return (default 50)
    
    Returns:
        List of Notification objects ordered by created_at DESC
    """
    query = db.query(Notification).filter(
        Notification.owner_user_id == uuid.UUID(owner_user_id) if isinstance(owner_user_id, str) else owner_user_id
    )
    
    if since is not None:
        query = query.filter(Notification.created_at > since)
    
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    
    return query.order_by(Notification.created_at.desc()).limit(limit).all()


def mark_notification_read(db: Session, notification_id: str) -> bool:
    """
    Mark a notification as read (set read_at).
    
    Args:
        db: SQLAlchemy session
        notification_id: UUID of the notification
    
    Returns:
        True if notification was found and updated, False otherwise
    """
    notification = db.query(Notification).filter(
        Notification.notification_id == uuid.UUID(notification_id) if isinstance(notification_id, str) else notification_id
    ).first()
    
    if notification is None:
        return False
    
    notification.read_at = datetime.now(timezone.utc)
    db.flush()
    
    return True


def mark_all_notifications_read(db: Session, owner_user_id: str) -> int:
    """
    Mark all unread notifications for a user as read.
    
    Args:
        db: SQLAlchemy session
        owner_user_id: UUID of the user
    
    Returns:
        Count of notifications marked as read
    """
    now = datetime.now(timezone.utc)
    count = db.query(Notification).filter(
        Notification.owner_user_id == uuid.UUID(owner_user_id) if isinstance(owner_user_id, str) else owner_user_id,
        Notification.read_at.is_(None),
    ).update({Notification.read_at: now})
    
    db.flush()
    
    return count
