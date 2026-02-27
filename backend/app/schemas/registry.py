"""
Registry schemas: Instruments + Listings.

API surface:
  - POST /listings accepts  `trading_currency` (GBP/USD/EUR) + `price_scale` (MAJOR/MINOR)
  - DB stores              `trading_currency` + `quote_scale` (GBX/GBP/USD/…)
  - Mapping rule: GBP + MINOR → quote_scale = GBX; else quote_scale = trading_currency
  - GET /listings response derives `price_scale` from the stored `quote_scale`.
"""
import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import ApiModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PriceScale(str, Enum):
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class InstrumentType(str, Enum):
    ETF = "ETF"
    STOCK = "STOCK"
    ETC = "ETC"
    FUND = "FUND"
    OTHER = "OTHER"


# ---------------------------------------------------------------------------
# Instrument schemas
# ---------------------------------------------------------------------------

class InstrumentCreate(ApiModel):
    isin: str = Field(..., min_length=12, max_length=12, description="12-character ISIN")
    name: str
    instrument_type: str = Field(..., description="ETF / STOCK / ETC / FUND / OTHER")


class InstrumentUpdate(ApiModel):
    """All fields optional — PATCH semantics."""
    name: str | None = None
    instrument_type: str | None = None


class InstrumentResponse(BaseModel):
    instrument_id: uuid.UUID
    isin: str
    name: str | None
    instrument_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InstrumentsPage(BaseModel):
    """Paginated instrument list."""
    items: list[InstrumentResponse]
    limit: int
    offset: int
    total: int


# ---------------------------------------------------------------------------
# Listing schemas
# ---------------------------------------------------------------------------

class ListingCreate(ApiModel):
    instrument_id: uuid.UUID
    ticker: str
    exchange: str
    trading_currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="ISO-4217 currency code, e.g. GBP / USD / EUR",
    )
    price_scale: PriceScale = Field(
        default=PriceScale.MAJOR,
        description="MAJOR = full currency unit; MINOR = pence/cents (GBX for GBP listings)",
    )
    is_primary: bool = False


class ListingUpdate(ApiModel):
    """All fields optional — PATCH semantics."""
    ticker: str | None = None
    exchange: str | None = None
    trading_currency: str | None = Field(default=None, min_length=3, max_length=3)
    price_scale: PriceScale | None = None
    is_primary: bool | None = None


class ListingResponse(BaseModel):
    """
    Derives `price_scale` from the stored DB `quote_scale`:
      - quote_scale == 'GBX'  →  price_scale = MINOR
      - anything else         →  price_scale = MAJOR
    """
    listing_id: uuid.UUID
    instrument_id: uuid.UUID
    ticker: str
    exchange: str
    trading_currency: str
    price_scale: PriceScale
    is_primary: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _derive_price_scale(cls, data: object) -> object:
        """
        When constructing from an ORM object (from_attributes path), Pydantic
        calls this validator with the raw ORM instance.  We need `quote_scale`
        (DB column) to derive `price_scale` (API field), so we convert the ORM
        object to a plain dict here and inject the computed field.
        """
        if hasattr(data, "quote_scale"):
            # ORM object path
            price_scale = (
                PriceScale.MINOR if data.quote_scale == "GBX" else PriceScale.MAJOR
            )
            return {
                "listing_id": data.listing_id,
                "instrument_id": data.instrument_id,
                "ticker": data.ticker,
                "exchange": data.exchange,
                "trading_currency": data.trading_currency,
                "price_scale": price_scale,
                "is_primary": data.is_primary,
                "created_at": data.created_at,
            }
        # dict / JSON path (e.g. unit tests)
        if isinstance(data, dict) and "price_scale" not in data and "quote_scale" in data:
            data = dict(data)
            data["price_scale"] = (
                PriceScale.MINOR if data.pop("quote_scale") == "GBX" else PriceScale.MAJOR
            )
        return data


class ListingsPage(BaseModel):
    """Paginated listing list."""
    items: list[ListingResponse]
    limit: int
    offset: int
    total: int
