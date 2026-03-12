from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import ConfigDict

from app.schemas.common import ApiModel, DecimalStr


class PricePointResponse(ApiModel):
    price_point_id: uuid.UUID
    listing_id: uuid.UUID
    ticker: str
    as_of: datetime
    price: DecimalStr
    currency: str | None
    is_close: bool
    source_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FxRateResponse(ApiModel):
    fx_rate_id: uuid.UUID
    base_ccy: str
    quote_ccy: str
    as_of: datetime
    rate: DecimalStr
    source_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RefreshResponse(ApiModel):
    job_id: str
    status: str = "enqueued"

    model_config = ConfigDict(from_attributes=True)


class SyncRequest(ApiModel):
    incremental: bool = False

    model_config = ConfigDict(from_attributes=True)


class SyncResponse(ApiModel):
    portfolio_id: str
    total_listings: int
    prices_fetched: int
    prices_inserted: int
    errors: list[str] = []
    status: str = "completed"

    model_config = ConfigDict(from_attributes=True)
