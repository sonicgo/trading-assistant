"""Ledger API endpoints."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc

from app.api import deps
from app.domain import models
from app.schemas import ledger as schemas
from app.schemas.common import OffsetPage
from app.services.ledger_posting import post_ledger_batch, reverse_ledger_entries, ValidationError, IdempotencyError, StateError

router = APIRouter()


@router.post(
    "/{portfolio_id}/ledger/batches",
    response_model=schemas.LedgerBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ledger_batch(
    portfolio_id: UUID,
    data: schemas.LedgerBatchCreate,
    db: deps.SessionDep,
    user: deps.CurrentUser,
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
):
    """Post a new ledger batch with entries."""
    try:
        return post_ledger_batch(
            db=db,
            portfolio_id=str(portfolio_id),
            submitted_by_user_id=str(user.user_id),
            batch_request=data,
        )
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except IdempotencyError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except StateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{portfolio_id}/ledger/reversals",
    response_model=schemas.LedgerBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
def reverse_ledger_batch(
    portfolio_id: UUID,
    data: schemas.LedgerReversalRequest,
    db: deps.SessionDep,
    user: deps.CurrentUser,
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
):
    """Reverse existing ledger entries by creating compensating entries."""
    try:
        return reverse_ledger_entries(
            db=db,
            portfolio_id=str(portfolio_id),
            submitted_by_user_id=str(user.user_id),
            reversal_request=data,
        )
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except IdempotencyError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except StateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{portfolio_id}/ledger/batches",
    response_model=OffsetPage[schemas.LedgerBatchResponse],
)
def list_ledger_batches(
    portfolio_id: UUID,
    db: deps.SessionDep,
    user: deps.CurrentUser,
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
    limit: int = 50,
    offset: int = 0,
    source: schemas.BatchSource | None = None,
):
    """List ledger batches for a portfolio (tenancy-checked)."""
    query = db.query(models.LedgerBatch).filter(
        models.LedgerBatch.portfolio_id == portfolio_id
    )
    
    if source:
        query = query.filter(models.LedgerBatch.source == source.value)
    
    total = query.count()
    
    batches = (
        query.order_by(desc(models.LedgerBatch.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    return OffsetPage(
        items=[
            schemas.LedgerBatchResponse(
                batch_id=batch.batch_id,
                portfolio_id=batch.portfolio_id,
                submitted_by_user_id=batch.submitted_by_user_id,
                source=schemas.BatchSource(batch.source),
                created_at=batch.created_at,
                note=batch.note,
                meta=batch.meta,
                idempotency_key=batch.idempotency_key,
                entries=[
                    schemas.LedgerEntryResponse(
                        entry_id=entry.entry_id,
                        batch_id=entry.batch_id,
                        portfolio_id=entry.portfolio_id,
                        entry_kind=schemas.EntryKind(entry.entry_kind),
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
            for batch in batches
        ],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.get(
    "/{portfolio_id}/ledger/entries",
    response_model=OffsetPage[schemas.LedgerEntryResponse],
)
def list_ledger_entries(
    portfolio_id: UUID,
    db: deps.SessionDep,
    user: deps.CurrentUser,
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
    limit: int = 50,
    offset: int = 0,
    entry_kind: schemas.EntryKind | None = None,
    listing_id: UUID | None = None,
):
    """List ledger entries for a portfolio (tenancy-checked)."""
    query = db.query(models.LedgerEntry).filter(
        models.LedgerEntry.portfolio_id == portfolio_id
    )
    
    if entry_kind:
        query = query.filter(models.LedgerEntry.entry_kind == entry_kind.value)
    
    if listing_id:
        query = query.filter(models.LedgerEntry.listing_id == listing_id)
    
    total = query.count()
    
    entries = (
        query.order_by(desc(models.LedgerEntry.effective_at), desc(models.LedgerEntry.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    return OffsetPage(
        items=[
            schemas.LedgerEntryResponse(
                entry_id=entry.entry_id,
                batch_id=entry.batch_id,
                portfolio_id=entry.portfolio_id,
                entry_kind=schemas.EntryKind(entry.entry_kind),
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
            for entry in entries
        ],
        limit=limit,
        offset=offset,
        total=total,
    )
