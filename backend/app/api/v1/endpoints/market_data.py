from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api import deps
from app.domain import models
from app.queue.redis_queue import enqueue_job
from app.schemas.market_data import PricePointResponse, FxRateResponse, RefreshResponse

router = APIRouter()


 
@router.get(
    "/{portfolio_id}/market-data/prices",
    response_model=list[PricePointResponse],
)
def get_market_prices(
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
    db: deps.SessionDep,
    limit: int = Query(50, le=500),
):
    price_points = (
        db.query(models.PricePoint)
        .join(models.InstrumentListing, models.PricePoint.listing_id == models.InstrumentListing.listing_id)
        .join(
            models.PortfolioConstituent,
            models.PortfolioConstituent.listing_id == models.InstrumentListing.listing_id,
        )
        .filter(
            models.PortfolioConstituent.portfolio_id == portfolio.portfolio_id,
            models.PortfolioConstituent.is_monitored == True,
        )
        .order_by(models.PricePoint.as_of.desc())
        .limit(limit)
        .all()
    )
    return price_points


 
@router.get(
    "/{portfolio_id}/market-data/fx",
    response_model=list[FxRateResponse],
)
def get_market_fx(
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
    db: deps.SessionDep,
    limit: int = Query(50, le=500),
):
    rows = (
        db.query(models.InstrumentListing.trading_currency)
        .join(
            models.PortfolioConstituent,
            models.PortfolioConstituent.listing_id == models.InstrumentListing.listing_id,
        )
        .filter(models.PortfolioConstituent.portfolio_id == portfolio.portfolio_id)
        .distinct()
        .all()
    )

    currencies = {r[0] for r in rows if r and r[0] is not None}
    currencies.discard(portfolio.base_currency)

    fx_rates: list[models.FxRate] = []
    for quote_ccy in currencies:
        fx_for_pair = (
            db.query(models.FxRate)
            .filter_by(base_ccy=portfolio.base_currency, quote_ccy=quote_ccy)
            .order_by(models.FxRate.as_of.desc())
            .limit(limit)
            .all()
        )
        fx_rates.extend(fx_for_pair)

    fx_rates.sort(key=lambda x: x.as_of, reverse=True)
    return fx_rates


 
@router.post(
    "/{portfolio_id}/market-data/refresh",
    response_model=RefreshResponse,
)
def refresh_market_data(
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
    current_user: Annotated[models.User, Depends(deps.CurrentUser)],
    db: deps.SessionDep,
):
    job_id = enqueue_job(
        "PRICE_REFRESH",
        str(portfolio.portfolio_id),
        str(current_user.user_id),
    )
    return RefreshResponse(job_id=job_id)
