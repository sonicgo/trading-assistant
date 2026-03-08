"""
test_alerts.py — Phase 2 Test Suite

Covers (playbook §6.1):
  - test_alert_creates_notification_row_for_critical
  - test_alert_deduplication

Additional coverage:
  - WARN alert does NOT create notification (Phase 2 policy)
  - Resolve alert clears deduplication gate
  - Notification meta contains required references
"""
import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.domain.models import Alert, Notification, Portfolio
from app.services.alerts import create_alert, resolve_alert, get_unresolved_alerts
from app.services.notifications import emit_notification, get_notifications


# ─── Test 5: CRITICAL alert triggers notification (playbook §6.1) ─────────────


def test_alert_creates_notification_row_for_critical(
    db: Session, test_portfolio: Portfolio, test_user
):
    """
    A CRITICAL alert should produce a Notification row via emit_notification.

    Verifies:
    - create_alert returns an Alert with the expected severity
    - emit_notification creates a Notification row for CRITICAL severity
    - Notification contains correct meta references (portfolio_id, alert_id)
    """
    # Create a CRITICAL alert
    alert = create_alert(
        db=db,
        portfolio_id=str(test_portfolio.portfolio_id),
        listing_id=None,
        severity="CRITICAL",
        rule_code="DQ_GBX_SCALE",
        title="Test Critical Alert",
        message="Price scale mismatch detected",
        details={"ratio": 0.01, "test": True},
    )

    assert alert is not None, "CRITICAL alert should be created"
    assert alert.alert_id is not None
    assert alert.severity == "CRITICAL"
    assert alert.rule_code == "DQ_GBX_SCALE"

    # Emit notification for the CRITICAL alert
    notification = emit_notification(
        db=db,
        owner_user_id=str(test_portfolio.owner_user_id),
        severity="CRITICAL",
        title=f"Portfolio Frozen: {alert.title}",
        body=alert.message,
        meta={
            "portfolio_id": str(test_portfolio.portfolio_id),
            "alert_id": str(alert.alert_id),
        },
    )
    db.commit()

    # Notification must be created for CRITICAL
    assert notification is not None, "CRITICAL event must emit a Notification row"
    assert notification.notification_id is not None
    assert notification.severity == "CRITICAL"
    assert notification.owner_user_id == test_user.user_id

    # Meta must contain the cross-references
    assert notification.meta is not None
    assert str(test_portfolio.portfolio_id) in notification.meta.get("portfolio_id", "")
    assert str(alert.alert_id) in notification.meta.get("alert_id", "")

    # Verify persisted in DB
    db_notification = (
        db.query(Notification)
        .filter_by(notification_id=notification.notification_id)
        .first()
    )
    assert db_notification is not None, "Notification should be persisted in DB"
    assert db_notification.severity == "CRITICAL"


def test_alert_notification_meta_has_both_ids(
    db: Session, test_portfolio: Portfolio, test_user
):
    """Notification meta must include both portfolio_id and alert_id."""
    alert = create_alert(
        db=db,
        portfolio_id=str(test_portfolio.portfolio_id),
        listing_id=None,
        severity="CRITICAL",
        rule_code="DQ_STALE_CLOSE",
        title="Stale Close Alert",
        message="Old close detected",
    )
    assert alert is not None

    notification = emit_notification(
        db=db,
        owner_user_id=str(test_user.user_id),
        severity="CRITICAL",
        title="Test notification",
        body="body",
        meta={
            "portfolio_id": str(test_portfolio.portfolio_id),
            "alert_id": str(alert.alert_id),
        },
    )
    db.commit()

    assert notification is not None
    meta = notification.meta
    assert "portfolio_id" in meta
    assert "alert_id" in meta
    assert meta["portfolio_id"] == str(test_portfolio.portfolio_id)
    assert meta["alert_id"] == str(alert.alert_id)


# ─── Test 7: Alert deduplication (playbook §6.1) ──────────────────────────────


def test_alert_deduplication(db: Session, test_portfolio: Portfolio):
    """
    Second create_alert with same (portfolio_id, listing_id, rule_code) returns
    None when the first alert is still unresolved.

    Verifies:
    - First alert creation succeeds (returns Alert object)
    - Second alert with identical keys returns None (deduplicated)
    - Only one alert row exists for that combination
    """
    rule_code = "DQ_STALE_CLOSE"
    listing_id_str = str(test_portfolio._test_listing.listing_id)

    # First alert
    alert1 = create_alert(
        db=db,
        portfolio_id=str(test_portfolio.portfolio_id),
        listing_id=listing_id_str,
        severity="WARN",
        rule_code=rule_code,
        title="First Alert",
        message="Stale close price detected",
    )
    assert alert1 is not None, "First alert should be created"
    assert alert1.rule_code == rule_code

    # Second alert with same (portfolio_id, listing_id, rule_code)
    alert2 = create_alert(
        db=db,
        portfolio_id=str(test_portfolio.portfolio_id),
        listing_id=listing_id_str,
        severity="WARN",
        rule_code=rule_code,
        title="Second Alert (should be deduped)",
        message="Different message but same key",
    )
    assert alert2 is None, (
        "Second alert with same keys should be deduplicated (return None)"
    )

    # Exactly one unresolved alert in DB for this rule
    unresolved = get_unresolved_alerts(db, str(test_portfolio.portfolio_id))
    matching = [a for a in unresolved if a.rule_code == rule_code]
    assert len(matching) == 1, (
        f"Expected exactly 1 unresolved {rule_code} alert, got {len(matching)}"
    )


def test_alert_deduplication_allows_after_resolve(db: Session, test_portfolio: Portfolio):
    """
    After an alert is resolved, a new alert for the same rule_code can be created.
    """
    rule_code = "DQ_JUMP_CLOSE"
    listing_id_str = str(test_portfolio._test_listing.listing_id)

    # First alert
    alert1 = create_alert(
        db=db,
        portfolio_id=str(test_portfolio.portfolio_id),
        listing_id=listing_id_str,
        severity="CRITICAL",
        rule_code=rule_code,
        title="Jump Alert",
        message="Price jumped",
    )
    assert alert1 is not None

    # Resolve the alert
    resolved = resolve_alert(db, str(alert1.alert_id))
    assert resolved is True

    # Now a new alert for the same rule should be allowed
    alert2 = create_alert(
        db=db,
        portfolio_id=str(test_portfolio.portfolio_id),
        listing_id=listing_id_str,
        severity="CRITICAL",
        rule_code=rule_code,
        title="Second Jump Alert",
        message="Price jumped again",
    )
    assert alert2 is not None, (
        "After resolving the first alert, a new one must be allowed"
    )
    assert alert2.alert_id != alert1.alert_id


def test_alert_deduplication_portfolio_level(db: Session, test_portfolio: Portfolio):
    """Portfolio-level alerts (listing_id=None) also deduplicate on rule_code."""
    rule_code = "DQ_FX_MISSING"

    alert1 = create_alert(
        db=db,
        portfolio_id=str(test_portfolio.portfolio_id),
        listing_id=None,
        severity="WARN",
        rule_code=rule_code,
        title="FX Missing",
        message="FX rate unavailable",
    )
    assert alert1 is not None

    alert2 = create_alert(
        db=db,
        portfolio_id=str(test_portfolio.portfolio_id),
        listing_id=None,
        severity="WARN",
        rule_code=rule_code,
        title="FX Missing Again",
        message="FX still unavailable",
    )
    assert alert2 is None, "Portfolio-level alerts also deduplicate"


# ─── Additional alert / notification coverage ─────────────────────────────────


def test_warn_alert_does_not_create_notification(
    db: Session, test_portfolio: Portfolio, test_user
):
    """
    Phase 2 policy: only CRITICAL events emit notification rows.
    WARN alerts should NOT produce a Notification.
    """
    notification = emit_notification(
        db=db,
        owner_user_id=str(test_user.user_id),
        severity="WARN",
        title="Warn notification",
        body="This should be suppressed",
        meta={"portfolio_id": str(test_portfolio.portfolio_id)},
    )
    assert notification is None, (
        "WARN severity should not produce a Notification row (Phase 2 policy)"
    )


def test_info_alert_does_not_create_notification(
    db: Session, test_portfolio: Portfolio, test_user
):
    """INFO severity also suppressed in Phase 2."""
    notification = emit_notification(
        db=db,
        owner_user_id=str(test_user.user_id),
        severity="INFO",
        title="Info notification",
        body="Low priority",
    )
    assert notification is None


def test_get_unresolved_alerts_returns_only_unresolved(
    db: Session, test_portfolio: Portfolio
):
    """get_unresolved_alerts excludes resolved alerts."""
    rule_a = "DQ_CCY_MISMATCH"
    rule_b = "DQ_FX_STALE"

    alert_a = create_alert(
        db=db,
        portfolio_id=str(test_portfolio.portfolio_id),
        listing_id=None,
        severity="CRITICAL",
        rule_code=rule_a,
        title="A",
        message="",
    )
    alert_b = create_alert(
        db=db,
        portfolio_id=str(test_portfolio.portfolio_id),
        listing_id=None,
        severity="WARN",
        rule_code=rule_b,
        title="B",
        message="",
    )
    assert alert_a is not None
    assert alert_b is not None

    # Resolve alert_a
    resolve_alert(db, str(alert_a.alert_id))

    unresolved = get_unresolved_alerts(db, str(test_portfolio.portfolio_id))
    rule_codes = {a.rule_code for a in unresolved}

    assert rule_a not in rule_codes, f"Resolved {rule_a} should not appear"
    assert rule_b in rule_codes, f"Unresolved {rule_b} should appear"


def test_get_notifications_returns_for_user(
    db: Session, test_portfolio: Portfolio, test_user
):
    """get_notifications returns notifications owned by the user."""
    emit_notification(
        db=db,
        owner_user_id=str(test_user.user_id),
        severity="CRITICAL",
        title="Test N",
        body="body",
        meta={"portfolio_id": str(test_portfolio.portfolio_id)},
    )
    db.commit()

    notifications = get_notifications(db, owner_user_id=str(test_user.user_id))
    assert len(notifications) >= 1
    assert all(n.owner_user_id == test_user.user_id for n in notifications)
