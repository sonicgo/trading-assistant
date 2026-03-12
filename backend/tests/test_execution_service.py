"""
Tests for Phase 5 Chunk 3: Recommendation Execution Service

Tests the translation logic from recommendations to ledger entries,
idempotency guardrails, and audit trail creation.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone

from app.domain.models import (
    RecommendationBatch,
    RecommendationLine,
    AuditEvent,
    LedgerBatch,
    LedgerEntry,
    CashSnapshot,
    HoldingSnapshot,
)
from app.services.execution_service import (
    execute_recommendation_batch,
    ignore_recommendation_batch,
    LineExecution,
    InvalidStateError,
    DoubleExecutionError,
)


@pytest.fixture
def test_recommendation_batch(db, test_portfolio):
    """Create a test recommendation batch with BUY and SELL lines."""
    batch = RecommendationBatch(
        portfolio_id=test_portfolio.portfolio_id,
        status="PENDING",
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    
    # Create BUY line
    buy_line = RecommendationLine(
        recommendation_batch_id=batch.recommendation_batch_id,
        listing_id=test_portfolio._test_listing.listing_id,
        action="BUY",
        proposed_quantity=Decimal("100"),
        proposed_price_gbp=Decimal("10.00"),
        proposed_value_gbp=Decimal("1000.00"),
        proposed_fee_gbp=Decimal("5.00"),
        status="PROPOSED",
    )
    db.add(buy_line)
    
    db.commit()
    db.refresh(batch)
    return batch


class TestExecuteRecommendationBatch:
    """Test suite for executing recommendation batches."""
    
    def test_execute_buy_line_creates_ledger_entries(self, db, test_portfolio, test_recommendation_batch, test_user):
        """Test that executing a BUY line creates correct ledger entries."""
        line = test_recommendation_batch.lines[0]
        
        line_exec = LineExecution(
            line_id=line.recommendation_line_id,
            executed_quantity=Decimal("100"),
            executed_price_gbp=Decimal("10.00"),
            executed_fee_gbp=Decimal("5.00"),
        )
        
        result = execute_recommendation_batch(
            db=db,
            portfolio_id=test_portfolio.portfolio_id,
            batch_id=test_recommendation_batch.recommendation_batch_id,
            user_id=test_user.user_id,
            line_executions=[line_exec],
        )
        
        # Verify result structure
        assert result["entries_created"] == 1
        assert result["lines_executed"] == 1
        assert result["ledger_batch_id"] is not None
        assert result["audit_event_id"] is not None
        
        # Verify cash impact: BUY = -(value + fee) = -(1000 + 5) = -1005
        expected_cash_impact = Decimal("-1005.00")
        assert result["total_cash_impact"] == expected_cash_impact
    
    def test_execute_updates_batch_status(self, db, test_portfolio, test_recommendation_batch, test_user):
        """Test that execution updates batch status to EXECUTED."""
        line = test_recommendation_batch.lines[0]
        
        execute_recommendation_batch(
            db=db,
            portfolio_id=test_portfolio.portfolio_id,
            batch_id=test_recommendation_batch.recommendation_batch_id,
            user_id=test_user.user_id,
            line_executions=[
                LineExecution(
                    line_id=line.recommendation_line_id,
                    executed_quantity=Decimal("100"),
                    executed_price_gbp=Decimal("10.00"),
                    executed_fee_gbp=Decimal("5.00"),
                )
            ],
        )
        
        db.refresh(test_recommendation_batch)
        assert test_recommendation_batch.status == "EXECUTED"
        assert test_recommendation_batch.executed_at is not None
        assert test_recommendation_batch.closed_by_user_id == test_user.user_id
        assert test_recommendation_batch.execution_summary is not None
    
    def test_execute_updates_line_status(self, db, test_portfolio, test_recommendation_batch, test_user):
        """Test that execution updates line status to EXECUTED."""
        line = test_recommendation_batch.lines[0]
        
        execute_recommendation_batch(
            db=db,
            portfolio_id=test_portfolio.portfolio_id,
            batch_id=test_recommendation_batch.recommendation_batch_id,
            user_id=test_user.user_id,
            line_executions=[
                LineExecution(
                    line_id=line.recommendation_line_id,
                    executed_quantity=Decimal("50"),  # Partial
                    executed_price_gbp=Decimal("10.50"),  # Different price
                    executed_fee_gbp=Decimal("3.00"),
                    note="Test execution note",
                )
            ],
        )
        
        db.refresh(line)
        assert line.status == "EXECUTED"
        assert line.executed_quantity == Decimal("50")
        assert line.executed_price_gbp == Decimal("10.50")
        assert line.executed_value_gbp == Decimal("525.00")  # 50 * 10.50
        assert line.executed_fee_gbp == Decimal("3.00")
        assert line.execution_note == "Test execution note"
    
    def test_execute_creates_audit_event(self, db, test_portfolio, test_recommendation_batch, test_user):
        """Test that execution creates an audit event."""
        line = test_recommendation_batch.lines[0]
        
        result = execute_recommendation_batch(
            db=db,
            portfolio_id=test_portfolio.portfolio_id,
            batch_id=test_recommendation_batch.recommendation_batch_id,
            user_id=test_user.user_id,
            line_executions=[
                LineExecution(
                    line_id=line.recommendation_line_id,
                    executed_quantity=Decimal("100"),
                    executed_price_gbp=Decimal("10.00"),
                    executed_fee_gbp=Decimal("5.00"),
                )
            ],
        )
        
        audit_event = db.query(AuditEvent).filter(
            AuditEvent.audit_event_id == result["audit_event_id"]
        ).first()
        
        assert audit_event is not None
        assert audit_event.event_type == "RECOMMENDATION_EXECUTED"
        assert audit_event.entity_type == "RECOMMENDATION_BATCH"
        assert audit_event.entity_id == test_recommendation_batch.recommendation_batch_id
        assert audit_event.actor_user_id == test_user.user_id
        assert audit_event.portfolio_id == test_portfolio.portfolio_id
    
    def test_prevent_double_execution(self, db, test_portfolio, test_recommendation_batch, test_user):
        """Test that executing an already-executed batch raises DoubleExecutionError."""
        line = test_recommendation_batch.lines[0]
        
        # First execution
        execute_recommendation_batch(
            db=db,
            portfolio_id=test_portfolio.portfolio_id,
            batch_id=test_recommendation_batch.recommendation_batch_id,
            user_id=test_user.user_id,
            line_executions=[
                LineExecution(
                    line_id=line.recommendation_line_id,
                    executed_quantity=Decimal("100"),
                    executed_price_gbp=Decimal("10.00"),
                    executed_fee_gbp=Decimal("5.00"),
                )
            ],
        )
        
        # Second execution should fail
        with pytest.raises(DoubleExecutionError) as exc_info:
            execute_recommendation_batch(
                db=db,
                portfolio_id=test_portfolio.portfolio_id,
                batch_id=test_recommendation_batch.recommendation_batch_id,
                user_id=test_user.user_id,
                line_executions=[
                    LineExecution(
                        line_id=line.recommendation_line_id,
                        executed_quantity=Decimal("100"),
                        executed_price_gbp=Decimal("10.00"),
                        executed_fee_gbp=Decimal("5.00"),
                    )
                ],
            )
        
        assert "already executed" in str(exc_info.value).lower()
    
    def test_execute_with_different_portfolio_fails(self, db, test_portfolio, test_recommendation_batch, test_user):
        """Test that executing with wrong portfolio ID fails."""
        line = test_recommendation_batch.lines[0]
        
        with pytest.raises(InvalidStateError) as exc_info:
            execute_recommendation_batch(
                db=db,
                portfolio_id="12345678-1234-1234-1234-123456789abc",  # Wrong portfolio
                batch_id=test_recommendation_batch.recommendation_batch_id,
                user_id=test_user.user_id,
                line_executions=[
                    LineExecution(
                        line_id=line.recommendation_line_id,
                        executed_quantity=Decimal("100"),
                        executed_price_gbp=Decimal("10.00"),
                        executed_fee_gbp=Decimal("5.00"),
                    )
                ],
            )
        
        assert "not found" in str(exc_info.value).lower()


class TestIgnoreRecommendationBatch:
    """Test suite for ignoring recommendation batches."""
    
    def test_ignore_updates_batch_status(self, db, test_portfolio, test_recommendation_batch, test_user):
        """Test that ignoring updates batch status to IGNORED."""
        result = ignore_recommendation_batch(
            db=db,
            portfolio_id=test_portfolio.portfolio_id,
            batch_id=test_recommendation_batch.recommendation_batch_id,
            user_id=test_user.user_id,
            reason="Market conditions changed",
        )
        
        assert result["lines_ignored"] == 1
        assert result["audit_event_id"] is not None
        
        db.refresh(test_recommendation_batch)
        assert test_recommendation_batch.status == "IGNORED"
        assert test_recommendation_batch.ignored_at is not None
        assert test_recommendation_batch.execution_summary["reason"] == "Market conditions changed"
    
    def test_ignore_updates_line_status(self, db, test_portfolio, test_recommendation_batch, test_user):
        """Test that ignoring updates all line statuses to IGNORED."""
        ignore_recommendation_batch(
            db=db,
            portfolio_id=test_portfolio.portfolio_id,
            batch_id=test_recommendation_batch.recommendation_batch_id,
            user_id=test_user.user_id,
            reason="Deferred to next month",
        )
        
        for line in test_recommendation_batch.lines:
            db.refresh(line)
            assert line.status == "IGNORED"
            assert line.execution_note == "Deferred to next month"
    
    def test_ignore_creates_audit_event(self, db, test_portfolio, test_recommendation_batch, test_user):
        """Test that ignoring creates an audit event."""
        result = ignore_recommendation_batch(
            db=db,
            portfolio_id=test_portfolio.portfolio_id,
            batch_id=test_recommendation_batch.recommendation_batch_id,
            user_id=test_user.user_id,
            reason="Testing ignore",
        )
        
        audit_event = db.query(AuditEvent).filter(
            AuditEvent.audit_event_id == result["audit_event_id"]
        ).first()
        
        assert audit_event is not None
        assert audit_event.event_type == "RECOMMENDATION_IGNORED"
        assert audit_event.entity_type == "RECOMMENDATION_BATCH"
        assert "Testing ignore" in audit_event.summary
    
    def test_ignore_does_not_create_ledger_entries(self, db, test_portfolio, test_recommendation_batch, test_user):
        """Test that ignoring does NOT create any ledger entries."""
        ledger_count_before = db.query(LedgerBatch).count()
        
        ignore_recommendation_batch(
            db=db,
            portfolio_id=test_portfolio.portfolio_id,
            batch_id=test_recommendation_batch.recommendation_batch_id,
            user_id=test_user.user_id,
        )
        
        ledger_count_after = db.query(LedgerBatch).count()
        assert ledger_count_after == ledger_count_before
    
    def test_cannot_ignore_already_executed_batch(self, db, test_portfolio, test_recommendation_batch, test_user):
        """Test that ignoring an already-executed batch fails."""
        line = test_recommendation_batch.lines[0]
        
        # Execute first
        execute_recommendation_batch(
            db=db,
            portfolio_id=test_portfolio.portfolio_id,
            batch_id=test_recommendation_batch.recommendation_batch_id,
            user_id=test_user.user_id,
            line_executions=[
                LineExecution(
                    line_id=line.recommendation_line_id,
                    executed_quantity=Decimal("100"),
                    executed_price_gbp=Decimal("10.00"),
                    executed_fee_gbp=Decimal("5.00"),
                )
            ],
        )
        
        # Try to ignore
        with pytest.raises(InvalidStateError) as exc_info:
            ignore_recommendation_batch(
                db=db,
                portfolio_id=test_portfolio.portfolio_id,
                batch_id=test_recommendation_batch.recommendation_batch_id,
                user_id=test_user.user_id,
            )
        
        assert "cannot ignore" in str(exc_info.value).lower()
