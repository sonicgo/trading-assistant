"""Ledger Import API endpoints."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
from app.domain import models
from app.schemas import ledger as schemas
from app.services.ledger_import import preview_import, apply_import

router = APIRouter()


@router.post(
    "/{portfolio_id}/ledger/imports/preview",
    response_model=schemas.CsvImportPreviewResponse,
)
def preview_csv_import(
    portfolio_id: UUID,
    data: schemas.CsvImportPreviewRequest,
    db: deps.SessionDep,
    user: deps.CurrentUser,
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
):
    """Preview a CSV import without applying changes (tenancy-checked)."""
    return preview_import(
        db=db,
        portfolio_id=str(portfolio_id),
        submitted_by_user_id=str(user.user_id),
        file_content_base64=data.file_content_base64,
        csv_profile=data.csv_profile,
    )


@router.post(
    "/{portfolio_id}/ledger/imports/apply",
    response_model=schemas.CsvImportApplyResponse,
    status_code=status.HTTP_201_CREATED,
)
def apply_csv_import(
    portfolio_id: UUID,
    data: schemas.CsvImportApplyRequest,
    db: deps.SessionDep,
    user: deps.CurrentUser,
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
):
    """Apply a previously-previewed CSV import plan (tenancy-checked)."""
    try:
        return apply_import(
            db=db,
            portfolio_id=str(portfolio_id),
            submitted_by_user_id=str(user.user_id),
            apply_request=data,
        )
    except ValueError as e:
        if "drift detected" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
