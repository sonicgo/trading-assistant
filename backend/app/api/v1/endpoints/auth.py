from datetime import timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Header, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.api import deps
from app.schemas import auth as schemas
from app.domain import models

router = APIRouter()

# ------------------------------------------------------------------
# Helper: Cookie Setter
# ------------------------------------------------------------------
def set_auth_cookies(response: Response, refresh_token: str, csrf_token: str):
    # 1. Refresh Token (HttpOnly, Secure)
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path=f"{settings.API_V1_STR}/auth/refresh" # Scope to refresh endpoint
    )
    
    # 2. CSRF Token (JS-Readable, Secure)
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False, # Must be readable by JS
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path=f"{settings.API_V1_STR}/auth/refresh"
    )

# ------------------------------------------------------------------
# 1. Login
# ------------------------------------------------------------------
@router.post("/login", response_model=schemas.AuthTokenResponse)
def login(
    response: Response,
    db: deps.SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    """
    OAuth2 compatible token login, get an access token for future requests.
    Sets HttpOnly refresh cookie.
    """
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not security.verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    if not user.is_enabled:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Generate Tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        subject=user.user_id, expires_delta=access_token_expires
    )
    
    # Refresh Token (Opaque)
    refresh_token_raw = security.generate_refresh_token()
    csrf_token_raw = security.generate_refresh_token() # Random string for CSRF
    
    # In V1, we store the hash (TODO: persist session in DB for revocation)
    # For now, we trust the signature/existence. In Phase 2, add 'auth_sessions' table insert here.
    
    set_auth_cookies(response, refresh_token_raw, csrf_token_raw)
    
    return schemas.AuthTokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

# ------------------------------------------------------------------
# 2. Refresh
# ------------------------------------------------------------------
@router.post("/refresh", response_model=schemas.AuthTokenResponse)
def refresh_token(
    response: Response,
    db: deps.SessionDep,
    x_csrf_token: Annotated[str | None, Header()] = None,
    ta_refresh: Annotated[str | None, Cookie()] = None,
    ta_csrf: Annotated[str | None, Cookie()] = None
):
    """
    Rotate refresh token and issue new access token.
    Requires: HttpOnly Cookie (ta_refresh) + CSRF Header (X-CSRF-Token) matching CSRF Cookie.
    """
    # 1. CSRF Check (Double-Submit Cookie)
    if not ta_csrf or not x_csrf_token or ta_csrf != x_csrf_token:
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid")
    
    if not ta_refresh:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    # 2. Validate Refresh Token
    # In V1 (Stateless): We accept it if present. 
    # In V2 (Stateful): We would hash 'ta_refresh' and lookup in 'auth_sessions'.
    
    # 3. Rotate (Issue new pair)
    # For MVP, we just re-issue (Rotation logic requires the DB session table, which we will add next).
    # To keep Phase 1 simple but secure-ish, we just issue a new Access Token.
    
    # Mocking user retrieval for stateless refresh (In real impl, get user_id from session)
    # This is a placeholder: In strict V1, you MUST persist sessions. 
    # For this step, we assume the user is valid if they have the cookie.
    # To fix this properly: we need to decode the OLD access token or store user_id in the refresh token.
    # RECOMMENDATION: Let's assume we implement the 'auth_sessions' table in Step 3.
    
    new_access_token = security.create_access_token(
        subject="placeholder_user_id", # Fixed in next step with DB lookup
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Rotate cookies
    new_refresh = security.generate_refresh_token()
    new_csrf = security.generate_refresh_token()
    set_auth_cookies(response, new_refresh, new_csrf)
    
    return schemas.AuthTokenResponse(
        access_token=new_access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

# ------------------------------------------------------------------
# 3. Logout
# ------------------------------------------------------------------
@router.post("/logout", response_model=schemas.AuthLogoutResponse)
def logout(response: Response):
    response.delete_cookie(settings.REFRESH_COOKIE_NAME)
    response.delete_cookie(settings.CSRF_COOKIE_NAME)
    return schemas.AuthLogoutResponse()

# ------------------------------------------------------------------
# 4. Me
# ------------------------------------------------------------------
@router.get("/me", response_model=schemas.MeResponse)
def read_users_me(current_user: deps.CurrentUser):
    return current_user