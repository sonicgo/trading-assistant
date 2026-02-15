from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid
from app.api import deps
from app.schemas import registry as schemas
from app.domain import models

router = APIRouter()

@router.get("", response_model=list[schemas.PortfolioResponse])
def get_portfolios(db: deps.SessionDep, user: deps.CurrentUser):
    return db.query(models.Portfolio).filter(models.Portfolio.owner_user_id == user.user_id).all()

@router.post("", response_model=schemas.PortfolioResponse, status_code=201)
def create_portfolio(data: schemas.PortfolioCreate, db: deps.SessionDep, user: deps.CurrentUser):
    new_portfolio = models.Portfolio(
        **data.model_dump(),
        owner_user_id=user.user_id,
        is_enabled=True,
        broker="Manual"
    )
    db.add(new_portfolio)
    db.commit()
    db.refresh(new_portfolio)
    return new_portfolio

@router.put("/{portfolio_id}/constituents", status_code=200)
def bulk_upsert_constituents(
    portfolio_id: uuid.UUID, 
    data: schemas.ConstituentBulkUpsert, 
    db: deps.SessionDep, 
    user: deps.CurrentUser
):
    portfolio = db.query(models.Portfolio).filter(
        models.Portfolio.portfolio_id == portfolio_id,
        models.Portfolio.owner_user_id == user.user_id
    ).first()
    
    if not portfolio:
        raise HTTPException(status_code=403, detail="Not authorized")

    if data.replace_missing:
        db.query(models.PortfolioConstituent).filter_by(portfolio_id=portfolio_id).delete()

    for item in data.items:
        constituent = models.PortfolioConstituent(
            portfolio_id=portfolio_id,
            listing_id=item.listing_id,
            sleeve_code=item.sleeve_code,
            is_monitored=item.is_monitored
        )
        db.merge(constituent)

    db.commit()
    return {"status": "success", "updated_count": len(data.items)}

@router.get("/{portfolio_id}/constituents", response_model=list[schemas.PortfolioConstituentResponse])
def get_portfolio_constituents(
    portfolio_id: uuid.UUID, # Ensure this is uuid.UUID
    db: deps.SessionDep, 
    user: deps.CurrentUser
):
    # Tenancy check first
    portfolio = db.query(models.Portfolio).filter(
        models.Portfolio.portfolio_id == portfolio_id,
        models.Portfolio.owner_user_id == user.user_id
    ).first()
    
    if not portfolio:
        raise HTTPException(status_code=403, detail="Not authorized")

    return db.query(models.PortfolioConstituent).filter_by(portfolio_id=portfolio_id).all()