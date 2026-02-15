from decimal import Decimal
from typing import Annotated
from pydantic import BaseModel, PlainSerializer, ConfigDict

# Standard Decimal string serialization for the API
DecimalStr = Annotated[
    Decimal,
    PlainSerializer(lambda v: format(v, "f"), return_type=str, when_used="json")
]

class OffsetPage(BaseModel):
    limit: int
    offset: int
    total: int
