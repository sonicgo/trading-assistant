"""
Portfolio + Constituent schemas.

Constituents bulk-upsert semantics (PUT /portfolios/{id}/constituents):
  - Transactional.
  - Upsert each item (PK = portfolio_id + listing_id).
  - Enforce one listing per sleeve per portfolio: if another listing already
    occupies the same sleeve, the old occupant is evicted first.
  - If replace_missing=true, rows NOT present in the payload are deleted.
"""
import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ApiModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TaxProfile(str, Enum):
    SIPP = "SIPP"
    ISA = "ISA"
    GIA = "GIA"


# ---------------------------------------------------------------------------
# Portfolio schemas
# ---------------------------------------------------------------------------

class PortfolioCreate(ApiModel):
    name: str
    base_currency: str = Field(
        default="GBP",
        min_length=3,
        max_length=3,
        description="ISO-4217 base currency, default GBP",
    )
    tax_profile: TaxProfile = Field(description="SIPP / ISA / GIA")
    broker: str = Field(default="Manual", description="Broker name, e.g. AJ Bell")


class PortfolioUpdate(ApiModel):
    """All fields optional — PATCH semantics."""
    name: str | None = None
    base_currency: str | None = Field(default=None, min_length=3, max_length=3)
    tax_profile: TaxProfile | None = None
    broker: str | None = None
    is_enabled: bool | None = None


class PortfolioResponse(BaseModel):
    portfolio_id: uuid.UUID
    owner_user_id: uuid.UUID
    name: str
    base_currency: str
    tax_profile: str
    broker: str
    is_enabled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Constituent schemas
# ---------------------------------------------------------------------------

class ConstituentItem(ApiModel):
    listing_id: uuid.UUID
    sleeve_code: str = Field(
        description="Must match a sleeve_code in the sleeves reference table"
    )
    is_monitored: bool = True


class ConstituentBulkUpsert(ApiModel):
    items: list[ConstituentItem] = Field(
        description="Complete or partial set of (listing, sleeve) mappings"
    )
    replace_missing: bool = Field(
        default=False,
        description=(
            "If true, any existing constituent NOT present in `items` is deleted. "
            "Use this to atomically replace the full constituent set."
        ),
    )


class ConstituentBulkUpsertResponse(BaseModel):
    status: str = "success"
    updated_count: int


class PortfolioConstituentResponse(BaseModel):
    portfolio_id: uuid.UUID
    listing_id: uuid.UUID
    sleeve_code: str
    is_monitored: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
