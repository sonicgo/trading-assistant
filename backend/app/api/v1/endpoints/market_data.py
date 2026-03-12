from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api import deps
from app.domain import models
from app.queue.redis_queue import enqueue_job
from app.schemas.market_data import PricePointResponse, FxRateResponse, RefreshResponse, SyncRequest, SyncResponse
from app.services.market_data_service import sync_portfolio_prices
import asyncio

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
    results = (
        db.query(models.PricePoint, models.InstrumentListing.ticker)
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
    
    price_points = []
    for price_point, ticker in results:
        price_dict = {
            "price_point_id": price_point.price_point_id,
            "listing_id": price_point.listing_id,
            "ticker": ticker,
            "as_of": price_point.as_of,
            "price": price_point.price,
            "currency": price_point.currency,
            "is_close": price_point.is_close,
            "source_id": price_point.source_id,
            "created_at": price_point.created_at,
        }
        price_points.append(price_dict)
    
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
    current_user: deps.CurrentUser,
    db: deps.SessionDep,
):
    job_id = enqueue_job(
        "PRICE_REFRESH",
        str(portfolio.portfolio_id),
        str(current_user.user_id),
    )
    return RefreshResponse(job_id=job_id)


@router.post(
    "/{portfolio_id}/market-data/sync",
    response_model=SyncResponse,
)
async def sync_market_data(
    portfolio: Annotated[models.Portfolio, Depends(deps.require_portfolio_access)],
    db: deps.SessionDep,
    request: SyncRequest | None = None,
):
    """
    On-demand sync of market prices for portfolio holdings.
    
    Fetches latest prices from Yahoo Finance with rate limiting
    and saves them to the database.
    
    If incremental=True, skips listings that already have prices
    within the last 24 hours.
    """
    sync_request = request or SyncRequest()
    
    result = await sync_portfolio_prices(
        db=db,
        portfolio_id=str(portfolio.portfolio_id),
        incremental=sync_request.incremental,
    )
    
    await asyncio.to_thread(db.commit)
    
    return SyncResponse(
        portfolio_id=result.portfolio_id,
        total_listings=result.total_listings,
        prices_fetched=result.prices_fetched,
        prices_inserted=result.prices_inserted,
        errors=result.errors,
        status="completed" if not result.errors else "completed_with_errors",
    )
