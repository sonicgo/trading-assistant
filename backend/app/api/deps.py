from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core import security
from app.db.session import get_db
from app.domain import models

SessionDep = Annotated[Session, Depends(get_db)]


def get_current_user(request: Request, db: SessionDep) -> models.User:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    try:
        payload = security.decode_access_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token missing subject",
        )

    try:
        parsed_user_id = UUID(str(user_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token subject is not a valid UUID",
        )

    user = db.query(models.User).filter(models.User.user_id == parsed_user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

    return user


CurrentUser = Annotated[models.User, Depends(get_current_user)]


def require_bootstrap_admin(current_user: CurrentUser) -> models.User:
    if not current_user.is_bootstrap_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bootstrap admin privileges required",
        )
    return current_user


def require_portfolio_access(
    portfolio_id: UUID,
    current_user: CurrentUser,
    db: SessionDep,
) -> models.Portfolio:
    portfolio = db.query(models.Portfolio).filter(models.Portfolio.portfolio_id == portfolio_id).first()
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    if portfolio.owner_user_id == current_user.user_id:
        return portfolio

    membership_model = getattr(models, "PortfolioMembership", None)
    if membership_model is not None:
        membership = (
            db.query(membership_model)
            .filter(
                membership_model.portfolio_id == portfolio_id,
                membership_model.user_id == current_user.user_id,
            )
            .first()
        )
        if membership is not None:
            return portfolio

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Portfolio access denied")


CurrentActiveSuperuser = Annotated[models.User, Depends(require_bootstrap_admin)]
