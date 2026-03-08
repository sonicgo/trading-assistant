from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import ConfigDict

from app.schemas.common import ApiModel


class AlertResponse(ApiModel):
    alert_id: uuid.UUID
    portfolio_id: uuid.UUID
    listing_id: uuid.UUID | None
    severity: str
    rule_code: str
    title: str
    message: str | None
    details: dict | None
    created_at: datetime
    resolved_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
