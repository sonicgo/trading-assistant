from typing import Annotated

from fastapi import APIRouter, Depends, Query
from app.api import deps
from app.domain import models
from app.schemas.alert import AlertResponse

router = APIRouter()


@router.get(
    "/{portfolio_id}/alerts",
    response_model=list[AlertResponse],
)
def get_portfolio_alerts(
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
    db: deps.SessionDep,
    active_only: Annotated[bool, Query()] = True,
):
    query = db.query(models.Alert).filter(models.Alert.portfolio_id == portfolio.portfolio_id)
    if active_only:
        query = query.filter(models.Alert.resolved_at.is_(None))
    alerts = query.order_by(models.Alert.created_at.desc()).all()
    return alerts
