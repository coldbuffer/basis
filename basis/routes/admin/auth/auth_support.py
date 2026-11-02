"""Shared helpers for auth HTTP routes."""

from __future__ import annotations

import urllib.parse

from fastapi import Request
from fastapi.responses import RedirectResponse

from basis.services.tenancy.identity.settings import AuthSettings, load_auth_settings_from_store


def default_public_url(request: Request) -> str:
    app_settings = request.app.state.settings
    return f"http://{app_settings.host}:{app_settings.port}".rstrip("/")


def auth_settings(request: Request) -> AuthSettings:
    cached = getattr(request.app.state, "auth_settings", None)
    if cached is not None:
        return cached
    store = request.app.state.store
    settings = load_auth_settings_from_store(
        store,
        default_public_url=default_public_url(request),
    )
    request.app.state.auth_settings = settings
    return settings


def redirect_with_token(settings: AuthSettings, token: str) -> RedirectResponse:
    query = urllib.parse.urlencode({"basis_token": token})
    return RedirectResponse(url=f"{settings.web_origin}/?{query}", status_code=302)
