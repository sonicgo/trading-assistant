from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, PlainSerializer


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

# Standard Decimal string serialization for the API.
# Emits a plain decimal string (no scientific notation) in JSON responses.
DecimalStr = Annotated[
    Decimal,
    PlainSerializer(lambda v: format(v, "f"), return_type=str, when_used="json"),
]


# ---------------------------------------------------------------------------
# Base model
# ---------------------------------------------------------------------------

class ApiModel(BaseModel):
    """All request/response models inherit from this to enforce strict parsing."""
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

ItemT = TypeVar("ItemT")


class OffsetPage(BaseModel, Generic[ItemT]):
    """Generic offset-pagination envelope returned by list endpoints."""
    items: list[ItemT]
    limit: int
    offset: int
    total: int


# ---------------------------------------------------------------------------
# Error envelope
# ---------------------------------------------------------------------------

class ErrorEnvelope(BaseModel):
    """Standard error body returned on 4xx/5xx responses."""
    code: str
    message: str
