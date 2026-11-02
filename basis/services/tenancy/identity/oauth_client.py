"""OAuth2 / OIDC token and userinfo helpers (Authlib + httpx)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode, urljoin

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client


async def fetch_oidc_metadata(issuer: str) -> dict[str, Any]:
    issuer = issuer.rstrip("/") + "/"
    url = urljoin(issuer, ".well-known/openid-configuration")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict):
        raise ValueError("invalid OIDC metadata")
    return data


async def exchange_oidc_code(
    metadata: dict[str, Any],
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    token_endpoint = metadata["token_endpoint"]
    async with AsyncOAuth2Client(
        client_id=client_id,
        client_secret=client_secret,
    ) as client:
        token = await client.fetch_token(
            token_endpoint,
            code=code,
            redirect_uri=redirect_uri,
        )
    if not isinstance(token, dict):
        raise ValueError("invalid token response")
    return token


async def fetch_oidc_userinfo(metadata: dict[str, Any], access_token: str) -> dict[str, Any]:
    userinfo = metadata.get("userinfo_endpoint")
    if not userinfo:
        raise ValueError("no userinfo_endpoint")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            userinfo,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict):
        raise ValueError("invalid userinfo")
    return data


def build_oidc_authorize_url(
    metadata: dict[str, Any],
    *,
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
) -> str:
    endpoint = metadata["authorization_endpoint"]
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope,
            "state": state,
        }
    )
    separator = "&" if "?" in endpoint else "?"
    return f"{endpoint}{separator}{query}"


async def fetch_github_user(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        user = (
            await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
        ).json()
        emails = (
            await client.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
        ).json()
    if not isinstance(user, dict):
        raise ValueError("invalid github user")
    primary = None
    if isinstance(emails, list):
        for row in emails:
            if isinstance(row, dict) and row.get("primary") and row.get("verified"):
                primary = row.get("email")
                break
        if primary is None:
            for row in emails:
                if isinstance(row, dict) and row.get("email"):
                    primary = row["email"]
                    break
    user["email"] = primary or user.get("email")
    return user


async def exchange_github_code(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict) or "access_token" not in data:
        raise ValueError("github token exchange failed")
    return data


async def exchange_google_code(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict) or "access_token" not in data:
        raise ValueError("google token exchange failed")
    return data


async def fetch_google_userinfo(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict):
        raise ValueError("invalid google userinfo")
    return data
