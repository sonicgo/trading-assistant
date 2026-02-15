from fastapi import APIRouter, Depends, HTTPException, status
from app.api import deps
from app.schemas import registry as schemas
from app.domain import models

router = APIRouter()

@router.post("/instruments", response_model=schemas.InstrumentResponse, status_code=201)
def create_instrument(data: schemas.InstrumentCreate, db: deps.SessionDep, user: deps.CurrentUser):
    existing = db.query(models.Instrument).filter(models.Instrument.isin == data.isin).first()
    if existing:
        raise HTTPException(status_code=409, detail="Instrument with this ISIN already exists")
    
    new_instrument = models.Instrument(**data.model_dump())
    db.add(new_instrument)
    db.commit()
    db.refresh(new_instrument)
    return new_instrument

@router.post("/listings", response_model=schemas.ListingResponse, status_code=201)
def create_listing(data: schemas.ListingCreate, db: deps.SessionDep, user: deps.CurrentUser):
    # Mapping Rule: LLD-2 §4.3
    q_scale = data.trading_currency
    if data.trading_currency == "GBP" and data.price_scale == "MINOR":
        q_scale = "GBX"
    
    new_listing = models.InstrumentListing(
        **data.model_dump(exclude={"price_scale"}),
        quote_scale=q_scale
    )
    db.add(new_listing)
    db.commit()
    db.refresh(new_listing)
    # Patch for response model
    new_listing.price_scale = data.price_scale
    return new_listing
