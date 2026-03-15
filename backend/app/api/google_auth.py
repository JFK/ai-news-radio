"""Google OAuth 2.0 endpoints for Drive authentication."""

from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models.app_setting import AppSetting

router = APIRouter(tags=["google-auth"])

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"


CALLBACK_PATH = "/api/auth/google/drive/callback"
# Default base URL for OAuth callback; override via GOOGLE_DRIVE_REDIRECT_BASE env
DEFAULT_REDIRECT_BASE = "http://localhost:8000"


def _get_redirect_uri() -> str:
    """Build redirect URI for OAuth callback."""
    base = settings.google_drive_redirect_base or DEFAULT_REDIRECT_BASE
    return f"{base}{CALLBACK_PATH}"


@router.get("/auth/google/drive/url")
async def get_auth_url() -> dict:
    """Generate Google OAuth authorization URL."""
    if not settings.google_drive_client_id or not settings.google_drive_client_secret:
        raise HTTPException(
            status_code=400,
            detail="Google Drive Client ID and Client Secret must be configured first.",
        )

    redirect_uri = _get_redirect_uri()
    params = {
        "client_id": settings.google_drive_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{AUTH_URI}?{urlencode(params)}"
    return {"auth_url": auth_url}


@router.get("/auth/google/drive/callback", name="google_drive_callback", response_model=None)
async def google_drive_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse | RedirectResponse:
    """Handle Google OAuth callback, store refresh token."""
    if error:
        return HTMLResponse(
            f"<html><body><h2>Authentication failed</h2><p>{error}</p>"
            "<script>window.close()</script></body></html>",
            status_code=400,
        )

    if not code:
        return HTMLResponse(
            "<html><body><h2>No authorization code received</h2>"
            "<script>window.close()</script></body></html>",
            status_code=400,
        )

    redirect_uri = _get_redirect_uri()

    # Exchange authorization code for tokens
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            TOKEN_URI,
            data={
                "code": code,
                "client_id": settings.google_drive_client_id,
                "client_secret": settings.google_drive_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )

    if token_response.status_code != 200:
        detail = token_response.json().get("error_description", "Token exchange failed")
        return HTMLResponse(
            f"<html><body><h2>Authentication failed</h2><p>{detail}</p>"
            "<script>window.close()</script></body></html>",
            status_code=400,
        )

    token_data = token_response.json()
    refresh_token = token_data.get("refresh_token")

    if not refresh_token:
        return HTMLResponse(
            "<html><body><h2>No refresh token received</h2>"
            "<p>Please revoke access and try again.</p>"
            "<script>window.close()</script></body></html>",
            status_code=400,
        )

    # Persist refresh token to DB
    key = "google_drive_refresh_token"
    result = await session.execute(
        select(AppSetting).where(AppSetting.key == key)
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.value = refresh_token
    else:
        session.add(AppSetting(key=key, value=refresh_token))

    # Update in-memory settings
    object.__setattr__(settings, key, refresh_token)

    await session.commit()

    # Redirect back to frontend settings page
    frontend_url = settings.google_drive_redirect_base.replace(":8000", ":3000") if settings.google_drive_redirect_base else "http://localhost:3000"
    return RedirectResponse(url=f"{frontend_url}/settings?drive_auth=success")


@router.get("/auth/google/drive/status")
async def get_auth_status() -> dict:
    """Check if Google Drive is authenticated."""
    return {
        "authenticated": bool(settings.google_drive_refresh_token),
        "client_id_configured": bool(settings.google_drive_client_id),
    }
