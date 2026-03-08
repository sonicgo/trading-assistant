from typing import Annotated
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from app.api import deps
from app.services import notifications
from app.schemas.notification import NotificationResponse

router = APIRouter()


@router.get("", response_model=list[NotificationResponse])
def list_notifications(
    db: deps.SessionDep,
    user: deps.CurrentUser,
    since: Annotated[datetime | None, Query()] = None,
):
    """List notifications for the current user, optionally filtered by 'since' timestamp."""
    return notifications.get_notifications(db, str(user.user_id), since=since)
