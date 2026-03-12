"""
Recommendation API Endpoints - Phase 5 Execution Capture

Provides endpoints for executing and ignoring recommendation batches.
"""
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.domain.models import User
from app.services.execution_service import (
    execute_recommendation_batch,
    ignore_recommendation_batch,
    LineExecution,
    ExecutionError,
    InvalidStateError,
    DoubleExecutionError,
)

router = APIRouter()


class LineExecutionRequest(BaseModel):
    """Request model for executing a single recommendation line."""
    line_id: UUID
    executed_quantity: Decimal = Field(..., gt=0, description="Actual executed quantity")
    executed_price_gbp: Decimal = Field(..., gt=0, description="Actual executed price in GBP")
    executed_fee_gbp: Decimal = Field(default=Decimal("0"), ge=0, description="Actual fee in GBP")
    note: Optional[str] = Field(default=None, description="Optional execution note")


class ExecuteBatchRequest(BaseModel):
    """Request model for executing a recommendation batch."""
    lines: List[LineExecutionRequest] = Field(..., min_length=1, description="Lines to execute")
    correlation_id: Optional[str] = Field(default=None, description="Optional correlation ID for tracing")


class ExecuteBatchResponse(BaseModel):
    """Response model for batch execution."""
    success: bool
    ledger_batch_id: UUID
    entries_created: int
    total_cash_impact: Decimal
    lines_executed: int
    audit_event_id: UUID
    message: str


class IgnoreBatchRequest(BaseModel):
    """Request model for ignoring a recommendation batch."""
    reason: Optional[str] = Field(default=None, description="Optional reason for ignoring")
    correlation_id: Optional[str] = Field(default=None, description="Optional correlation ID for tracing")


class IgnoreBatchResponse(BaseModel):
    """Response model for batch ignore."""
    success: bool
    lines_ignored: int
    audit_event_id: UUID
    message: str


@router.post(
    "/{portfolio_id}/recommendations/{batch_id}/execute",
    response_model=ExecuteBatchResponse,
    status_code=status.HTTP_200_OK,
)
def execute_recommendation(
    portfolio_id: UUID,
    batch_id: UUID,
    request: ExecuteBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExecuteBatchResponse:
    """
    Execute a recommendation batch by translating it into ledger entries.

    This endpoint:
    - Validates the batch is in PENDING state
    - Prevents double execution (idempotency guard)
    - Translates each line into BUY/SELL ledger entries
    - Updates cash and holding snapshots atomically
    - Creates audit trail

    Math rules:
    - BUY: Increases holdings, decreases cash (including fees)
    - SELL: Decreases holdings, increases cash (minus fees)

    Args:
        portfolio_id: Portfolio ID
        batch_id: Recommendation batch ID to execute
        request: Execution details including actual executed prices/fees

    Returns:
        ExecuteBatchResponse with execution summary

    Raises:
        400: If batch not in valid state or already executed
        404: If batch not found
        422: If request validation fails
    """
    try:
        # Convert request lines to LineExecution objects
        line_executions = [
            LineExecution(
                line_id=line.line_id,
                executed_quantity=line.executed_quantity,
                executed_price_gbp=line.executed_price_gbp,
                executed_fee_gbp=line.executed_fee_gbp,
                note=line.note,
            )
            for line in request.lines
        ]

        result = execute_recommendation_batch(
            db=db,
            portfolio_id=portfolio_id,
            batch_id=batch_id,
            user_id=current_user.user_id,
            line_executions=line_executions,
            correlation_id=request.correlation_id,
        )

        return ExecuteBatchResponse(
            success=True,
            ledger_batch_id=result["ledger_batch_id"],
            entries_created=result["entries_created"],
            total_cash_impact=result["total_cash_impact"],
            lines_executed=result["lines_executed"],
            audit_event_id=result["audit_event_id"],
            message=f"Successfully executed {result['lines_executed']} lines",
        )

    except DoubleExecutionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except InvalidStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ExecutionError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {e}",
        )


@router.post(
    "/{portfolio_id}/recommendations/{batch_id}/ignore",
    response_model=IgnoreBatchResponse,
    status_code=status.HTTP_200_OK,
)
def ignore_recommendation(
    portfolio_id: UUID,
    batch_id: UUID,
    request: IgnoreBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IgnoreBatchResponse:
    """
    Ignore a recommendation batch without executing it.

    This endpoint:
    - Validates the batch is in PENDING state
    - Marks batch and all lines as IGNORED
    - Creates audit trail
    - Does NOT create any ledger entries

    Args:
        portfolio_id: Portfolio ID
        batch_id: Recommendation batch ID to ignore
        request: Optional reason for ignoring

    Returns:
        IgnoreBatchResponse with ignore summary

    Raises:
        400: If batch not in PENDING state
        404: If batch not found
    """
    try:
        result = ignore_recommendation_batch(
            db=db,
            portfolio_id=portfolio_id,
            batch_id=batch_id,
            user_id=current_user.user_id,
            reason=request.reason,
            correlation_id=request.correlation_id,
        )

        return IgnoreBatchResponse(
            success=True,
            lines_ignored=result["lines_ignored"],
            audit_event_id=result["audit_event_id"],
            message="Recommendation batch ignored" + (f": {request.reason}" if request.reason else ""),
        )

    except InvalidStateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ExecutionError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ignore operation failed: {e}",
        )
