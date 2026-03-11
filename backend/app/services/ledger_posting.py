"""
Ledger Posting Service - Phase 3 Book of Record

Core orchestration for atomic ledger operations following Playbook Section 6.
Implements the 10-step transaction contract with strict lock ordering.

Transaction Contract (Playbook 6.1):
1. Validate auth and tenancy (assumed done by caller)
2. Validate request shape and entry-kind rules
3. Open one DB transaction
4. Insert ledger_batches
5. Insert all ledger_entries
6. Lock/upsert cash_snapshots row
7. Lock/upsert relevant holding_snapshots rows in deterministic listing order
8. Apply deltas entry by entry in deterministic order
9. Validate resulting state
10. Commit once

Lock Order (Playbook 6.2):
1. Cash snapshot first
2. Holding snapshots sorted by listing_id
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.domain.models import LedgerBatch, LedgerEntry, CashSnapshot, HoldingSnapshot
from app.schemas.ledger import (
    LedgerBatchCreate,
    LedgerEntryCreate,
    LedgerReversalRequest,
    LedgerBatchResponse,
    LedgerEntryResponse,
    EntryKind,
    BatchSource,
    CashSnapshotResponse,
    HoldingSnapshotResponse,
)
from app.services.snapshots import apply_cash_delta, apply_holding_delta


class LedgerPostingError(Exception):
    """Base exception for ledger posting failures."""
    pass


class ValidationError(LedgerPostingError):
    """Request validation failed."""
    pass


class IdempotencyError(LedgerPostingError):
    """Idempotency check failed (same key, different payload)."""
    pass


class StateError(LedgerPostingError):
    """State transition invalid (e.g., would create negative holdings)."""
    pass


def _validate_entry(entry: LedgerEntryCreate, index: int) -> None:
    """
    Validate a single ledger entry according to Playbook 6.3 rules.
    
    Raises:
        ValidationError: If entry violates business rules
    """
    kind = entry.entry_kind

    if kind == EntryKind.CONTRIBUTION:
        if entry.net_cash_delta_gbp <= 0:
            raise ValidationError(f"Entry {index}: CONTRIBUTION must have positive net_cash_delta_gbp")
        if entry.listing_id is not None:
            raise ValidationError(f"Entry {index}: CONTRIBUTION must not have listing_id")
        if entry.quantity_delta is not None:
            raise ValidationError(f"Entry {index}: CONTRIBUTION must not have quantity_delta")
        if entry.fee_gbp is not None:
            raise ValidationError(f"Entry {index}: CONTRIBUTION must not have fee_gbp")
        if entry.book_cost_delta_gbp is not None:
            raise ValidationError(f"Entry {index}: CONTRIBUTION must not have book_cost_delta_gbp")

    elif kind == EntryKind.BUY:
        if entry.listing_id is None:
            raise ValidationError(f"Entry {index}: BUY requires listing_id")
        if entry.quantity_delta is None or entry.quantity_delta <= 0:
            raise ValidationError(f"Entry {index}: BUY requires positive quantity_delta")
        if entry.net_cash_delta_gbp >= 0:
            raise ValidationError(f"Entry {index}: BUY must have negative net_cash_delta_gbp (cash outflow)")
        if entry.fee_gbp is not None and entry.fee_gbp < 0:
            raise ValidationError(f"Entry {index}: BUY fee_gbp must be non-negative")

    elif kind == EntryKind.SELL:
        if entry.listing_id is None:
            raise ValidationError(f"Entry {index}: SELL requires listing_id")
        if entry.quantity_delta is None or entry.quantity_delta >= 0:
            raise ValidationError(f"Entry {index}: SELL requires negative quantity_delta")
        if entry.net_cash_delta_gbp <= 0:
            raise ValidationError(f"Entry {index}: SELL must have positive net_cash_delta_gbp (cash inflow)")
        if entry.fee_gbp is not None and entry.fee_gbp < 0:
            raise ValidationError(f"Entry {index}: SELL fee_gbp must be non-negative")

    elif kind == EntryKind.ADJUSTMENT:
        if entry.fee_gbp is not None and entry.fee_gbp < 0:
            raise ValidationError(f"Entry {index}: ADJUSTMENT fee_gbp must be non-negative")

    elif kind == EntryKind.REVERSAL:
        raise ValidationError(f"Entry {index}: REVERSAL entries should be created via reverse_ledger_entries(), not manual posting")

    else:
        raise ValidationError(f"Entry {index}: Unknown entry_kind: {kind}")


def _check_idempotency(
    db: Session,
    portfolio_id: uuid.UUID,
    batch_request: LedgerBatchCreate,
) -> Optional[LedgerBatch]:
    """
    Check for existing batch with same idempotency_key.
    
    Returns:
        Existing LedgerBatch if found with matching payload, None if not found
        
    Raises:
        IdempotencyError: If same key but different payload
    """
    if not batch_request.idempotency_key:
        return None
    
    existing = db.query(LedgerBatch).filter(
        LedgerBatch.portfolio_id == portfolio_id,
        LedgerBatch.idempotency_key == batch_request.idempotency_key,
    ).first()
    
    if existing:
        if len(existing.entries) != len(batch_request.entries):
            raise IdempotencyError(
                f"Idempotency key conflict: same key but different entry count"
            )
        return existing
    
    return None


def _create_ledger_entry_from_schema(
    entry_schema: LedgerEntryCreate,
    batch_id: uuid.UUID,
    portfolio_id: uuid.UUID,
) -> LedgerEntry:
    """Convert a LedgerEntryCreate schema to a LedgerEntry model."""
    return LedgerEntry(
        entry_id=entry_schema.entry_id or uuid.uuid4(),
        batch_id=batch_id,
        portfolio_id=portfolio_id,
        entry_kind=entry_schema.entry_kind.value,
        effective_at=entry_schema.effective_at,
        listing_id=entry_schema.listing_id,
        quantity_delta=entry_schema.quantity_delta,
        net_cash_delta_gbp=entry_schema.net_cash_delta_gbp,
        fee_gbp=entry_schema.fee_gbp,
        book_cost_delta_gbp=entry_schema.book_cost_delta_gbp,
        reversal_of_entry_id=None,
        note=entry_schema.note,
        meta=entry_schema.meta,
    )


def post_ledger_batch(
    db: Session,
    portfolio_id: str,
    submitted_by_user_id: str,
    batch_request: LedgerBatchCreate,
    source: BatchSource = BatchSource.UI,
) -> LedgerBatchResponse:
    """
    Post a ledger batch atomically following the 10-step transaction contract.
    
    Args:
        db: SQLAlchemy session
        portfolio_id: UUID of the portfolio
        submitted_by_user_id: UUID of the user submitting
        batch_request: The batch creation request
        source: Source of the batch (UI, CSV_IMPORT, etc.)
        
    Returns:
        LedgerBatchResponse with the posted batch and entries
        
    Raises:
        ValidationError: If request validation fails
        IdempotencyError: If idempotency key conflicts with different payload
        StateError: If state transition would be invalid
    """
    portfolio_uuid = uuid.UUID(portfolio_id)
    user_uuid = uuid.UUID(submitted_by_user_id)
    
    if not batch_request.entries:
        raise ValidationError("Batch must contain at least one entry")

    for i, entry in enumerate(batch_request.entries):
        _validate_entry(entry, i)

    existing_batch = _check_idempotency(db, portfolio_uuid, batch_request)
    if existing_batch:
        return _batch_to_response(existing_batch)

    batch = LedgerBatch(
        batch_id=batch_request.batch_id or uuid.uuid4(),
        portfolio_id=portfolio_uuid,
        submitted_by_user_id=user_uuid,
        source=source.value,
        note=batch_request.note,
        meta=batch_request.meta,
        idempotency_key=batch_request.idempotency_key,
    )
    db.add(batch)
    db.flush()

    entry_models = []
    for entry_schema in batch_request.entries:
        entry = _create_ledger_entry_from_schema(entry_schema, batch.batch_id, portfolio_uuid)
        db.add(entry)
        entry_models.append(entry)

    db.flush()

    total_cash_delta = sum(entry.net_cash_delta_gbp for entry in entry_models)
    first_entry_id = entry_models[0].entry_id
    cash_snapshot = apply_cash_delta(db, portfolio_uuid, total_cash_delta, first_entry_id)

    listing_ids = sorted(set(
        entry.listing_id for entry in entry_models
        if entry.listing_id is not None
    ))

    for listing_id in listing_ids:
        db.query(HoldingSnapshot).filter(
            HoldingSnapshot.portfolio_id == portfolio_uuid,
            HoldingSnapshot.listing_id == listing_id,
        ).with_for_update().first()

    sorted_entries = sorted(entry_models, key=lambda e: str(e.entry_id))

    for entry in sorted_entries:
        kind = EntryKind(entry.entry_kind)

        if kind == EntryKind.CONTRIBUTION:
            pass

        elif kind == EntryKind.BUY:
            acquisition_cost = abs(entry.net_cash_delta_gbp)
            if entry.fee_gbp:
                acquisition_cost = acquisition_cost - entry.fee_gbp

            apply_holding_delta(
                db,
                portfolio_uuid,
                entry.listing_id,
                entry.quantity_delta,
                acquisition_cost,
                entry.entry_id,
                is_sell=False,
            )

        elif kind == EntryKind.SELL:
            apply_holding_delta(
                db,
                portfolio_uuid,
                entry.listing_id,
                entry.quantity_delta,
                None,
                entry.entry_id,
                is_sell=True,
            )

        elif kind == EntryKind.ADJUSTMENT:
            apply_holding_delta(
                db,
                portfolio_uuid,
                entry.listing_id,
                entry.quantity_delta,
                entry.book_cost_delta_gbp,
                entry.entry_id,
                is_sell=False,
            )

    if cash_snapshot is None:
        raise StateError("Cash snapshot not created after posting")

    for listing_id in listing_ids:
        holding = db.query(HoldingSnapshot).filter(
            HoldingSnapshot.portfolio_id == portfolio_uuid,
            HoldingSnapshot.listing_id == listing_id,
        ).first()

        if holding and holding.quantity < 0:
            raise StateError(f"Negative quantity detected for listing {listing_id}")

        if holding and holding.quantity == 0:
            if holding.book_cost_gbp != 0 or holding.avg_cost_gbp != 0:
                raise StateError(f"Zero quantity but non-zero cost for listing {listing_id}")

    db.commit()

    db.refresh(batch)
    for entry in entry_models:
        db.refresh(entry)

    return _batch_to_response(batch)


def reverse_ledger_entries(
    db: Session,
    portfolio_id: str,
    submitted_by_user_id: str,
    reversal_request: LedgerReversalRequest,
) -> LedgerBatchResponse:
    """
    Reverse existing ledger entries by creating compensating entries.
    
    Creates a new batch with REVERSAL entries that have equal-and-opposite deltas
    to the original entries. Does NOT mutate the original entries.
    
    Args:
        db: SQLAlchemy session
        portfolio_id: UUID of the portfolio
        submitted_by_user_id: UUID of the user reversing
        reversal_request: The reversal request with entry_ids to reverse
        
    Returns:
        LedgerBatchResponse with the reversal batch
        
    Raises:
        ValidationError: If validation fails or entries not found
        StateError: If reversal would create invalid state
    """
    portfolio_uuid = uuid.UUID(portfolio_id)
    user_uuid = uuid.UUID(submitted_by_user_id)
    
    if not reversal_request.entry_ids:
        raise ValidationError("Reversal must specify at least one entry to reverse")

    original_entries = []
    for entry_id in reversal_request.entry_ids:
        entry = db.query(LedgerEntry).filter(
            LedgerEntry.entry_id == entry_id,
            LedgerEntry.portfolio_id == portfolio_uuid,
        ).first()

        if not entry:
            raise ValidationError(f"Entry not found: {entry_id}")

        original_entries.append(entry)

    if reversal_request.idempotency_key:
        existing = db.query(LedgerBatch).filter(
            LedgerBatch.portfolio_id == portfolio_uuid,
            LedgerBatch.idempotency_key == reversal_request.idempotency_key,
        ).first()

        if existing:
            return _batch_to_response(existing)

    batch = LedgerBatch(
        batch_id=reversal_request.batch_id or uuid.uuid4(),
        portfolio_id=portfolio_uuid,
        submitted_by_user_id=user_uuid,
        source=BatchSource.REVERSAL.value,
        note=reversal_request.note or f"Reversal of entries: {', '.join(str(e) for e in reversal_request.entry_ids)}",
        idempotency_key=reversal_request.idempotency_key,
    )
    db.add(batch)
    db.flush()

    reversal_entries = []
    for original in original_entries:
        opposite_quantity = -original.quantity_delta if original.quantity_delta else None
        opposite_cash = -original.net_cash_delta_gbp
        opposite_book_cost = -original.book_cost_delta_gbp if original.book_cost_delta_gbp else None

        reversal_entry = LedgerEntry(
            entry_id=uuid.uuid4(),
            batch_id=batch.batch_id,
            portfolio_id=portfolio_uuid,
            entry_kind=EntryKind.REVERSAL.value,
            effective_at=datetime.now(timezone.utc),
            listing_id=original.listing_id,
            quantity_delta=opposite_quantity,
            net_cash_delta_gbp=opposite_cash,
            fee_gbp=None,
            book_cost_delta_gbp=opposite_book_cost,
            reversal_of_entry_id=original.entry_id,
            note=f"Reversal of entry {original.entry_id}",
        )
        db.add(reversal_entry)
        reversal_entries.append(reversal_entry)

    db.flush()

    total_cash_delta = sum(entry.net_cash_delta_gbp for entry in reversal_entries)
    first_entry_id = reversal_entries[0].entry_id
    apply_cash_delta(db, portfolio_uuid, total_cash_delta, first_entry_id)

    listing_ids = sorted(set(
        entry.listing_id for entry in reversal_entries
        if entry.listing_id is not None
    ))

    for listing_id in listing_ids:
        db.query(HoldingSnapshot).filter(
            HoldingSnapshot.portfolio_id == portfolio_uuid,
            HoldingSnapshot.listing_id == listing_id,
        ).with_for_update().first()

    sorted_entries = sorted(reversal_entries, key=lambda e: str(e.entry_id))

    for entry in sorted_entries:
        original = db.query(LedgerEntry).filter(
            LedgerEntry.entry_id == entry.reversal_of_entry_id
        ).first()

        kind = EntryKind(original.entry_kind)

        if kind == EntryKind.CONTRIBUTION:
            pass

        elif kind == EntryKind.BUY:
            apply_holding_delta(
                db,
                portfolio_uuid,
                entry.listing_id,
                entry.quantity_delta,
                None,
                entry.entry_id,
                is_sell=True,
            )

        elif kind == EntryKind.SELL:
            book_cost = abs(entry.net_cash_delta_gbp)
            apply_holding_delta(
                db,
                portfolio_uuid,
                entry.listing_id,
                entry.quantity_delta,
                book_cost,
                entry.entry_id,
                is_sell=False,
            )

        elif kind in (EntryKind.ADJUSTMENT, EntryKind.REVERSAL):
            apply_holding_delta(
                db,
                portfolio_uuid,
                entry.listing_id,
                entry.quantity_delta,
                entry.book_cost_delta_gbp,
                entry.entry_id,
                is_sell=False,
            )

    for listing_id in listing_ids:
        holding = db.query(HoldingSnapshot).filter(
            HoldingSnapshot.portfolio_id == portfolio_uuid,
            HoldingSnapshot.listing_id == listing_id,
        ).first()

        if holding and holding.quantity < 0:
            raise StateError(f"Reversal would result in negative quantity for listing {listing_id}")

    db.commit()
    db.refresh(batch)
    for entry in reversal_entries:
        db.refresh(entry)

    return _batch_to_response(batch)


def _batch_to_response(batch: LedgerBatch) -> LedgerBatchResponse:
    """Convert a LedgerBatch model to a LedgerBatchResponse schema."""
    return LedgerBatchResponse(
        batch_id=batch.batch_id,
        portfolio_id=batch.portfolio_id,
        submitted_by_user_id=batch.submitted_by_user_id,
        source=BatchSource(batch.source),
        created_at=batch.created_at,
        note=batch.note,
        meta=batch.meta,
        idempotency_key=batch.idempotency_key,
        entries=[
            LedgerEntryResponse(
                entry_id=entry.entry_id,
                batch_id=entry.batch_id,
                portfolio_id=entry.portfolio_id,
                entry_kind=EntryKind(entry.entry_kind),
                effective_at=entry.effective_at,
                listing_id=entry.listing_id,
                quantity_delta=entry.quantity_delta,
                net_cash_delta_gbp=entry.net_cash_delta_gbp,
                fee_gbp=entry.fee_gbp,
                book_cost_delta_gbp=entry.book_cost_delta_gbp,
                reversal_of_entry_id=entry.reversal_of_entry_id,
                created_at=entry.created_at,
                note=entry.note,
                meta=entry.meta,
            )
            for entry in batch.entries
        ],
    )
