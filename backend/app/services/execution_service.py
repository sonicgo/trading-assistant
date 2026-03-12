"""
Execution Service - Phase 5 Recommendation Execution Capture

Translates recommendation batches into ledger entries following the
execution-to-ledger translation rules from the Phase 5/6 playbook.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
import uuid

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select

from app.domain.models import (
    RecommendationBatch,
    RecommendationLine,
    AuditEvent,
    LedgerBatch,
    LedgerEntry,
    CashSnapshot,
    HoldingSnapshot,
)
from app.schemas.ledger import LedgerBatchCreate, LedgerEntryCreate, EntryKind, BatchSource
from app.services.ledger_posting import post_ledger_batch, LedgerPostingError


class ExecutionError(Exception):
    """Base exception for recommendation execution failures."""
    pass


class InvalidStateError(ExecutionError):
    """Recommendation batch is not in a valid state for execution."""
    pass


class DoubleExecutionError(ExecutionError):
    """Recommendation batch has already been executed."""
    pass


class LineExecution:
    """Execution details for a single recommendation line."""
    def __init__(
        self,
        line_id: uuid.UUID,
        executed_quantity: Decimal,
        executed_price_gbp: Decimal,
        executed_fee_gbp: Decimal = Decimal("0"),
        note: Optional[str] = None,
    ):
        self.line_id = line_id
        self.executed_quantity = executed_quantity
        self.executed_price_gbp = executed_price_gbp
        self.executed_fee_gbp = executed_fee_gbp
        self.note = note


def execute_recommendation_batch(
    db: Session,
    portfolio_id: uuid.UUID,
    batch_id: uuid.UUID,
    user_id: uuid.UUID,
    line_executions: List[LineExecution],
    correlation_id: Optional[str] = None,
) -> dict:
    """
    Execute a recommendation batch by translating it into ledger entries.

    This function:
    1. Validates the batch is in PENDING state
    2. Prevents double execution (idempotency guard)
    3. Translates each line into BUY/SELL ledger entries
    4. Creates the ledger batch and entries atomically
    5. Updates recommendation status and creates audit trail
    6. Returns execution summary

    Math rules per Phase 5 playbook:
    - BUY: quantity_delta > 0, net_cash_delta_gbp < 0, fee_gbp >= 0
    - SELL: quantity_delta < 0, net_cash_delta_gbp > 0, fee_gbp >= 0
    - Cash impact = -(executed_value + executed_fee) for BUY
    - Cash impact = executed_value - executed_fee for SELL

    Args:
        db: Database session
        portfolio_id: Portfolio ID for tenancy validation
        batch_id: Recommendation batch ID to execute
        user_id: User executing the batch
        line_executions: List of LineExecution with actual executed values
        correlation_id: Optional correlation ID for tracing

    Returns:
        Dict with execution summary:
        - ledger_batch_id: UUID of created ledger batch
        - entries_created: Number of ledger entries created
        - total_cash_impact: Total GBP cash impact
        - lines_executed: Number of lines executed
        - audit_event_id: UUID of audit event

    Raises:
        InvalidStateError: If batch is not PENDING
        DoubleExecutionError: If batch already executed
        LedgerPostingError: If ledger posting fails
    """
    # Fetch batch with lines
    batch = db.query(RecommendationBatch).options(
        joinedload(RecommendationBatch.lines)
    ).filter(
        RecommendationBatch.recommendation_batch_id == batch_id,
        RecommendationBatch.portfolio_id == portfolio_id,
    ).first()

    if not batch:
        raise InvalidStateError(f"Recommendation batch {batch_id} not found")

    # Idempotency guard: prevent double execution
    if batch.status != "PENDING":
        raise DoubleExecutionError(
            f"Recommendation batch already {batch.status.lower()}. "
            f"Cannot execute again."
        )

    # Validate all line executions exist in batch
    batch_line_ids = {line.recommendation_line_id for line in batch.lines}
    execution_line_ids = {exec.line_id for exec in line_executions}
    invalid_lines = execution_line_ids - batch_line_ids
    if invalid_lines:
        raise InvalidStateError(
            f"Invalid line IDs: {invalid_lines}. Not part of this batch."
        )

    # Build ledger entries from line executions
    ledger_entries = []
    lines_to_update = []
    total_cash_impact = Decimal("0")

    for line_exec in line_executions:
        line = next(
            (l for l in batch.lines if l.recommendation_line_id == line_exec.line_id),
            None
        )
        if not line:
            continue

        # Calculate values
        executed_value = line_exec.executed_quantity * line_exec.executed_price_gbp
        executed_value = executed_value.quantize(Decimal("0.0000000001"))

        if line.action == "BUY":
            # BUY: quantity positive, cash negative
            quantity_delta = line_exec.executed_quantity
            # Cash outflow = -(value + fee)
            net_cash_delta = -(executed_value + line_exec.executed_fee_gbp)
            entry_kind = EntryKind.BUY
        elif line.action == "SELL":
            # SELL: quantity negative, cash positive
            quantity_delta = -line_exec.executed_quantity
            # Cash inflow = value - fee
            net_cash_delta = executed_value - line_exec.executed_fee_gbp
            entry_kind = EntryKind.SELL
        else:
            raise InvalidStateError(f"Unknown action: {line.action}")

        # Create ledger entry
        ledger_entry = LedgerEntryCreate(
            entry_kind=entry_kind,
            effective_at=datetime.now(timezone.utc),
            listing_id=line.listing_id,
            quantity_delta=quantity_delta,
            net_cash_delta_gbp=net_cash_delta,
            fee_gbp=line_exec.executed_fee_gbp if line_exec.executed_fee_gbp > 0 else None,
            note=line_exec.note or f"Executed from recommendation {batch_id}",
        )
        ledger_entries.append(ledger_entry)

        # Track line update
        lines_to_update.append({
            "line": line,
            "executed_quantity": line_exec.executed_quantity,
            "executed_price_gbp": line_exec.executed_price_gbp,
            "executed_value_gbp": executed_value,
            "executed_fee_gbp": line_exec.executed_fee_gbp,
            "note": line_exec.note,
        })

        total_cash_impact += net_cash_delta

    if not ledger_entries:
        raise InvalidStateError("No valid lines to execute")

    # Create ledger batch request
    batch_create = LedgerBatchCreate(
        entries=ledger_entries,
        note=f"Execution of recommendation batch {batch_id}",
    )

    # Post to ledger (atomic operation)
    try:
        ledger_result = post_ledger_batch(
            db=db,
            portfolio_id=str(portfolio_id),
            submitted_by_user_id=str(user_id),
            batch_request=batch_create,
            source=BatchSource.UI,
        )
    except LedgerPostingError as e:
        raise ExecutionError(f"Ledger posting failed: {e}") from e

    # Update recommendation batch status
    now = datetime.now(timezone.utc)
    batch.status = "EXECUTED"
    batch.executed_at = now
    batch.closed_by_user_id = user_id
    batch.execution_summary = {
        "ledger_batch_id": str(ledger_result.batch_id),
        "entries_created": len(ledger_entries),
        "total_cash_impact": str(total_cash_impact),
        "lines_executed": len(lines_to_update),
        "executed_at": now.isoformat(),
    }

    # Update recommendation lines
    for update in lines_to_update:
        line = update["line"]
        line.status = "EXECUTED"
        line.executed_quantity = update["executed_quantity"]
        line.executed_price_gbp = update["executed_price_gbp"]
        line.executed_value_gbp = update["executed_value_gbp"]
        line.executed_fee_gbp = update["executed_fee_gbp"]
        line.execution_note = update["note"]
        # Link to first ledger entry for this line (in V1, 1:1 mapping)
        line.ledger_entry_id = ledger_result.entries[0].entry_id if ledger_result.entries else None

    # Create audit event
    audit_event = AuditEvent(
        audit_event_id=uuid.uuid4(),
        portfolio_id=portfolio_id,
        actor_user_id=user_id,
        event_type="RECOMMENDATION_EXECUTED",
        entity_type="RECOMMENDATION_BATCH",
        entity_id=batch_id,
        occurred_at=now,
        summary=f"Executed recommendation batch with {len(lines_to_update)} lines",
        details={
            "batch_id": str(batch_id),
            "ledger_batch_id": str(ledger_result.batch_id),
            "lines_executed": len(lines_to_update),
            "total_cash_impact": str(total_cash_impact),
            "correlation_id": correlation_id,
        },
        correlation_id=correlation_id,
    )
    db.add(audit_event)
    db.commit()

    return {
        "ledger_batch_id": ledger_result.batch_id,
        "entries_created": len(ledger_entries),
        "total_cash_impact": total_cash_impact,
        "lines_executed": len(lines_to_update),
        "audit_event_id": audit_event.audit_event_id,
    }


def ignore_recommendation_batch(
    db: Session,
    portfolio_id: uuid.UUID,
    batch_id: uuid.UUID,
    user_id: uuid.UUID,
    reason: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> dict:
    """
    Ignore a recommendation batch without executing it.

    This function:
    1. Validates the batch is in PENDING state
    2. Marks batch and all lines as IGNORED
    3. Creates audit trail
    4. Does NOT create any ledger entries

    Args:
        db: Database session
        portfolio_id: Portfolio ID for tenancy validation
        batch_id: Recommendation batch ID to ignore
        user_id: User ignoring the batch
        reason: Optional reason for ignoring
        correlation_id: Optional correlation ID for tracing

    Returns:
        Dict with ignore summary:
        - lines_ignored: Number of lines ignored
        - audit_event_id: UUID of audit event

    Raises:
        InvalidStateError: If batch is not PENDING
    """
    batch = db.query(RecommendationBatch).options(
        joinedload(RecommendationBatch.lines)
    ).filter(
        RecommendationBatch.recommendation_batch_id == batch_id,
        RecommendationBatch.portfolio_id == portfolio_id,
    ).first()

    if not batch:
        raise InvalidStateError(f"Recommendation batch {batch_id} not found")

    if batch.status != "PENDING":
        raise InvalidStateError(
            f"Cannot ignore batch with status {batch.status}. "
            f"Only PENDING batches can be ignored."
        )

    now = datetime.now(timezone.utc)

    # Update batch
    batch.status = "IGNORED"
    batch.ignored_at = now
    batch.closed_by_user_id = user_id
    batch.execution_summary = {
        "ignored_at": now.isoformat(),
        "ignored_by": str(user_id),
        "reason": reason,
    }

    # Update all lines
    for line in batch.lines:
        line.status = "IGNORED"
        line.execution_note = reason

    # Create audit event
    audit_event = AuditEvent(
        audit_event_id=uuid.uuid4(),
        portfolio_id=portfolio_id,
        actor_user_id=user_id,
        event_type="RECOMMENDATION_IGNORED",
        entity_type="RECOMMENDATION_BATCH",
        entity_id=batch_id,
        occurred_at=now,
        summary=f"Ignored recommendation batch" + (f": {reason}" if reason else ""),
        details={
            "batch_id": str(batch_id),
            "reason": reason,
            "lines_ignored": len(batch.lines),
            "correlation_id": correlation_id,
        },
        correlation_id=correlation_id,
    )
    db.add(audit_event)
    db.commit()

    return {
        "lines_ignored": len(batch.lines),
        "audit_event_id": audit_event.audit_event_id,
    }
