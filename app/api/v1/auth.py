"""Authentication endpoints — register, login, Google OAuth, forgot/reset password, logout."""
from __future__ import annotations

import urllib.parse
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.auth.jwt_handler import create_access_token, decode_access_token, oauth2_scheme
from app.auth.password import hash_password, verify_password
from app.config import get_settings
from app.db.password_reset_store import PasswordResetStore
from app.db.token_blocklist import TokenBlocklist
from app.db.user_store import UserStore
from app.dependencies import get_current_user, get_token_blocklist, get_user_store
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserMeResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


def _get_reset_store(request: Request) -> PasswordResetStore:
    return request.app.state.password_reset_store


# ---------------------------------------------------------------------------
# Email / password
# ---------------------------------------------------------------------------

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    body: RegisterRequest,
    store: UserStore = Depends(get_user_store),
):
    existing = await store.get_by_email(body.email)
    if existing:
        if existing.auth_provider == "google":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is linked to a Google account. Please sign in with Google.",
            )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")
    user = await store.create_user(body.email, hash_password(body.password))
    token = create_access_token(user.user_id, user.email)
    return TokenResponse(access_token=token, user_id=user.user_id, email=user.email, name=user.name)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    store: UserStore = Depends(get_user_store),
):
    user = await store.get_by_email(body.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.auth_provider == "google" and not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account uses Google sign-in. Please click 'Sign in with Google'.",
        )
    if not verify_password(body.password, user.hashed_password or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(user.user_id, user.email)
    return TokenResponse(access_token=token, user_id=user.user_id, email=user.email, name=user.name)


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------

@router.get("/google")
async def google_login():
    """Redirect the browser to Google's OAuth consent screen."""
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(status_code=501, detail="Google OAuth is not configured on this server.")

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    url = _GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params)
    return RedirectResponse(url=url)


@router.get("/google/callback")
async def google_callback(
    code: str | None = None,
    error: str | None = None,
    store: UserStore = Depends(get_user_store),
):
    """Receive the auth code from Google, exchange it for user info, issue JWT."""
    settings = get_settings()
    base_url = settings.app_base_url

    if error or not code:
        return RedirectResponse(url=f"{base_url}/?auth_error={error or 'cancelled'}")

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
        if token_resp.status_code != 200:
            return RedirectResponse(url=f"{base_url}/?auth_error=token_exchange_failed")
        access_token = token_resp.json().get("access_token")

        # Fetch user profile
        userinfo_resp = await client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code != 200:
            return RedirectResponse(url=f"{base_url}/?auth_error=userinfo_failed")
        info = userinfo_resp.json()

    google_id: str = info["id"]
    email: str = info.get("email", "")
    name: str | None = info.get("name")

    # Find or create user
    user = await store.get_by_google_id(google_id)
    if user is None:
        # Check if an email/password account already exists
        user = await store.get_by_email(email)
        if user:
            # Link Google to existing account
            await store.link_google_id(user.user_id, google_id, name)
            user.google_id = google_id
        else:
            user = await store.create_google_user(email, google_id, name)

    jwt = create_access_token(user.user_id, user.email)
    params = urllib.parse.urlencode({
        "access_token": jwt,
        "token_type": "bearer",
        "user_id": user.user_id,
        "email": user.email,
        "name": user.name or "",
    })
    return RedirectResponse(url=f"{base_url}/?{params}")


# ---------------------------------------------------------------------------
# Forgot / reset password
# ---------------------------------------------------------------------------

@router.post("/forgot-password", status_code=200)
async def forgot_password(
    body: ForgotPasswordRequest,
    store: UserStore = Depends(get_user_store),
    request: Request = None,  # type: ignore[assignment]
):
    """Send a password-reset email. Always returns 200 to prevent email enumeration."""
    settings = get_settings()
    if not settings.smtp_host:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service is not configured on this server.",
        )

    reset_store: PasswordResetStore = _get_reset_store(request)
    user = await store.get_by_email(body.email)

    if user and user.hashed_password:  # only email/password accounts can reset
        token = await reset_store.create_token(user.user_id)
        reset_link = f"{settings.app_base_url}/reset-password?token={token}"
        try:
            from app.auth.email_sender import send_password_reset_email
            await send_password_reset_email(
                to_email=user.email,
                reset_link=reset_link,
                from_email=settings.smtp_from_email,
                from_name=settings.smtp_from_name,
                smtp_host=settings.smtp_host,
                smtp_port=settings.smtp_port,
                smtp_username=settings.smtp_username,
                smtp_password=settings.smtp_password,
                use_tls=settings.smtp_use_tls,
            )
        except Exception as exc:
            from app.utils.logging import get_logger
            get_logger(__name__).error("Failed to send reset email to %s: %s", body.email, exc)

    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password", response_model=TokenResponse)
async def reset_password(
    body: ResetPasswordRequest,
    store: UserStore = Depends(get_user_store),
    request: Request = None,  # type: ignore[assignment]
):
    reset_store: PasswordResetStore = _get_reset_store(request)
    user_id = await reset_store.consume_token(body.token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset link is invalid or has expired.",
        )

    hashed = hash_password(body.new_password)
    await store.update_password(user_id, hashed)

    user = await store.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=500, detail="User not found after password reset.")

    token = create_access_token(user.user_id, user.email)
    return TokenResponse(access_token=token, user_id=user.user_id, email=user.email, name=user.name)


# ---------------------------------------------------------------------------
# Current user / logout
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserMeResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UserMeResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        name=current_user.name,
        auth_provider=current_user.auth_provider,
    )


@router.post("/logout", status_code=204)
async def logout(
    token: str = Depends(oauth2_scheme),
    blocklist: TokenBlocklist = Depends(get_token_blocklist),
):
    """Revoke the current JWT so it can no longer be used even before it expires."""
    from jose import JWTError
    try:
        payload = decode_access_token(token)
        jti: str = payload.get("jti", "")
        exp: int | None = payload.get("exp")
        if jti and exp:
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
            await blocklist.block(jti, expires_at)
    except JWTError:
        pass
