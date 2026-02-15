import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

# --- Portfolio Schemas ---

class PortfolioBase(BaseModel):
    name: str
    base_currency: str = "GBP"
    tax_profile: str

class PortfolioCreate(PortfolioBase):
    pass

class PortfolioResponse(PortfolioBase):
    portfolio_id: uuid.UUID
    owner_user_id: uuid.UUID
    is_enabled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- Constituent Schemas ---

class ConstituentItem(BaseModel):
    listing_id: uuid.UUID
    sleeve_code: str
    is_monitored: bool = True

class ConstituentBulkUpsert(BaseModel):
    items: List[ConstituentItem]
    replace_missing: bool = False

class PortfolioConstituentResponse(BaseModel):
    portfolio_id: uuid.UUID
    listing_id: uuid.UUID
    sleeve_code: str
    is_monitored: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- Instrument/Listing Schemas ---

class InstrumentCreate(BaseModel):
    isin: str = Field(..., min_length=12, max_length=12)
    name: str
    instrument_type: str

class InstrumentResponse(InstrumentCreate):
    instrument_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ListingCreate(BaseModel):
    instrument_id: uuid.UUID
    ticker: str
    exchange: str
    trading_currency: str = "GBP"
    quote_scale: str = "GBX"
    is_primary: bool = False

class ListingResponse(ListingCreate):
    listing_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)