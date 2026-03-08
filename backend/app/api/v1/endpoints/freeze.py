from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
from app.domain import models
from app.services import freeze
from app.schemas.freeze import FreezeStateResponse, FreezeStatusResponse

router = APIRouter()


@router.get("/{portfolio_id}/freeze", response_model=FreezeStatusResponse)
def get_freeze_status(
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
    db: deps.SessionDep,
):
    state = freeze.get_freeze_state(db, str(portfolio.portfolio_id))
    is_frozen = freeze.is_portfolio_frozen(db, str(portfolio.portfolio_id))
    return FreezeStatusResponse(is_frozen=is_frozen, freeze=state)


@router.post("/{portfolio_id}/freeze", response_model=FreezeStateResponse)
def freeze_portfolio_endpoint(
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
    db: deps.SessionDep,
):
    state = freeze.freeze_portfolio(db, str(portfolio.portfolio_id))
    return state


@router.post("/{portfolio_id}/unfreeze", response_model=FreezeStateResponse)
def unfreeze_portfolio_endpoint(
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
    db: deps.SessionDep,
    current_user: deps.CurrentUser,
):
    state = freeze.unfreeze_portfolio(db, str(portfolio.portfolio_id), str(current_user.user_id))
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio is not frozen")
    return state
