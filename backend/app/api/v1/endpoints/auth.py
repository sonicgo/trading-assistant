from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Header, HTTPException, Response, status

from app.api import deps
from app.core.config import settings
from app.core import security
from app.schemas import auth as schemas
from app.domain import models

router = APIRouter()

_session_lock = Lock()
_refresh_sessions: dict[str, dict[str, object]] = {}


def _set_auth_cookies(response: Response, refresh_token: str, csrf_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path=f"{settings.api_v1_str}/auth/refresh",
    )

    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path=f"{settings.api_v1_str}/auth/refresh",
    )


def _register_refresh_session(user_id: UUID, session_id: UUID, refresh_token: str) -> None:
    token_hash = security.hash_refresh_token(refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    with _session_lock:
        _refresh_sessions[token_hash] = {
            "user_id": user_id,
            "session_id": session_id,
            "expires_at": expires_at,
            "revoked": False,
            "last_seen_at": datetime.now(timezone.utc),
        }


def _resolve_refresh_session(refresh_token: str) -> tuple[UUID, UUID, str]:
    token_hash = security.hash_refresh_token(refresh_token)
    with _session_lock:
        session_state = _refresh_sessions.get(token_hash)

    if session_state is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if bool(session_state.get("revoked")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session revoked")

    expires_at = session_state.get("expires_at")
    if not isinstance(expires_at, datetime) or datetime.now(timezone.utc) >= expires_at:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user_id = session_state.get("user_id")
    session_id = session_state.get("session_id")
    if not isinstance(user_id, UUID) or not isinstance(session_id, UUID):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh session")

    return user_id, session_id, token_hash


def _rotate_refresh_session(token_hash: str, refresh_token: str) -> None:
    with _session_lock:
        session_state = _refresh_sessions.pop(token_hash, None)
        if session_state is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        session_state["last_seen_at"] = datetime.now(timezone.utc)
        _refresh_sessions[security.hash_refresh_token(refresh_token)] = session_state


def _revoke_refresh_session(refresh_token: str | None) -> None:
    if not refresh_token:
        return
    token_hash = security.hash_refresh_token(refresh_token)
    with _session_lock:
        session_state = _refresh_sessions.get(token_hash)
        if session_state is not None:
            session_state["revoked"] = True


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(settings.refresh_cookie_name, path=f"{settings.api_v1_str}/auth/refresh")
    response.delete_cookie(settings.csrf_cookie_name, path=f"{settings.api_v1_str}/auth/refresh")


@router.post("/login", response_model=schemas.AuthTokenResponse)
def login(response: Response, payload: schemas.AuthLoginRequest, db: deps.SessionDep):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not security.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if not user.is_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

    session_id = uuid4()
    access_token = security.create_access_token(user_id=user.user_id, session_id=session_id)
    refresh_token = security.generate_refresh_token()
    csrf_token = security.generate_refresh_token()

    _register_refresh_session(user.user_id, session_id, refresh_token)
    _set_auth_cookies(response, refresh_token, csrf_token)

    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()

    return schemas.AuthTokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )

@router.post("/refresh", response_model=schemas.AuthTokenResponse)
def refresh_token(
    response: Response,
    db: deps.SessionDep,
    x_csrf_token: Annotated[str | None, Header()] = None,
    ta_refresh: Annotated[str | None, Cookie()] = None,
    ta_csrf: Annotated[str | None, Cookie()] = None,
):
    if not ta_csrf or not x_csrf_token or ta_csrf != x_csrf_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing or invalid")
    if not ta_refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")

    user_id, session_id, token_hash = _resolve_refresh_session(ta_refresh)
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user or not user.is_enabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not active")

    new_access_token = security.create_access_token(user_id=user_id, session_id=session_id)
    new_refresh = security.generate_refresh_token()
    new_csrf = security.generate_refresh_token()

    _rotate_refresh_session(token_hash, new_refresh)
    _set_auth_cookies(response, new_refresh, new_csrf)

    return schemas.AuthTokenResponse(
        access_token=new_access_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/logout", response_model=schemas.AuthLogoutResponse)
def logout(response: Response, ta_refresh: Annotated[str | None, Cookie()] = None):
    _revoke_refresh_session(ta_refresh)
    _clear_auth_cookies(response)
    return schemas.AuthLogoutResponse()


@router.get("/me", response_model=schemas.MeResponse)
def read_users_me(current_user: deps.CurrentUser):
    return schemas.MeResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        is_bootstrap_admin=current_user.is_bootstrap_admin,
    )
