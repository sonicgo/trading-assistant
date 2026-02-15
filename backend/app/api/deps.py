from typing import Generator, Annotated
from jose import jwt, JWTError

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.config import settings
from app.db.session import SessionLocal
from app.domain import models

# OAuth2 scheme
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)

def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]

def get_current_user(session: SessionDep, token: TokenDep) -> models.User:
    try:
        # 1. Decode the JWT Access Token
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalid: missing subject",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalid: could not decode",
        )
    
    # 2. Fetch User from the correct table
    # NOTE: Changed models.User.user_id to handle string/UUID conversion
    user = session.query(models.User).filter(models.User.user_id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if is_enabled exists on your model (if not, use is_bootstrap_admin)
    # user.is_enabled might be missing from your earlier SQL force-create
    return user

CurrentUser = Annotated[models.User, Depends(get_current_user)]

def get_current_active_superuser(current_user: CurrentUser) -> models.User:
    if not current_user.is_bootstrap_admin:
        raise HTTPException(
            status_code=400, detail="The user doesn't have enough privileges"
        )
    return current_user
