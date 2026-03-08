from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import ConfigDict

from app.schemas.common import ApiModel


class FreezeStateResponse(ApiModel):
    freeze_id: uuid.UUID
    portfolio_id: uuid.UUID
    is_frozen: bool
    reason_alert_id: uuid.UUID | None
    created_at: datetime
    cleared_at: datetime | None
    cleared_by_user_id: uuid.UUID | None

    model_config = ConfigDict(from_attributes=True)


class FreezeStatusResponse(ApiModel):
    is_frozen: bool
    freeze: FreezeStateResponse | None

    model_config = ConfigDict(from_attributes=True)
