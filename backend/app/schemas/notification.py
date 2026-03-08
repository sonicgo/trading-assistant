from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import ConfigDict

from app.schemas.common import ApiModel


class NotificationResponse(ApiModel):
    notification_id: uuid.UUID
    owner_user_id: uuid.UUID
    severity: str
    title: str
    body: str | None
    created_at: datetime
    read_at: datetime | None
    meta: dict | None

    model_config = ConfigDict(from_attributes=True)
