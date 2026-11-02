"""Platform login / registration settings (Console Access-style, stored in settings table)."""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from basis.services.tenancy.admin.passwords import new_token

if TYPE_CHECKING:
    from basis.services.tenancy.admin.store import AdminStore, User

LOCAL_PROVIDERS = frozenset({"password", "email"})
OAUTH_PROVIDERS = frozenset({"github", "google"})
ALL_PROVIDERS = LOCAL_PROVIDERS | OAUTH_PROVIDERS


def _parse_providers(raw: str | None) -> list[str]:
    if not raw:
        return ["password"]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ["password"]
    if not isinstance(data, list):
        return ["password"]
    out: list[str] = []
    for item in data:
        pid = str(item).strip().lower()
        if pid in ALL_PROVIDERS and pid not in out:
            out.append(pid)
    return out or ["password"]


def _serialize_providers(providers: list[str]) -> str:
    clean = _parse_providers(json.dumps(providers))
    return json.dumps(clean, ensure_ascii=False)


def ensure_oauth_state_secret(store: "AdminStore") -> str:
    return store.ensure_oauth_state_secret()


def build_auth_settings_raw(
    store: "AdminStore",
    *,
    default_public_url: str,
    default_web_origin: str,
) -> dict[str, Any]:
    providers = _parse_providers(store._setting("auth_providers_json"))
    state_secret = store.ensure_oauth_state_secret()
    magic_log = store._setting("auth_magic_link_dev_log") == "true"
    smtp_password = store._setting("auth_smtp_password")
    smtp_host = (store._setting("auth_smtp_host") or "").strip() or None
    from_email = (store._setting("auth_magic_link_from") or "").strip() or None
    gh_id = (store._setting("auth_github_client_id") or "").strip() or None
    gh_secret = store._setting("auth_github_client_secret")
    go_id = (store._setting("auth_google_client_id") or "").strip() or None
    go_secret = store._setting("auth_google_client_secret")
    public = (store._setting("auth_public_url") or "").strip() or default_public_url
    web = (store._setting("auth_web_origin") or "").strip() or default_web_origin
    mail_transport = (store._setting("auth_mail_transport") or "").strip() or (
        "smtp" if smtp_host else "resend"
    )
    resend_key = (store._setting("auth_resend_api_key") or "").strip() or None
    if mail_transport == "resend" and resend_key and not smtp_host:
        smtp_host = "smtp.resend.com"
    if mail_transport == "resend" and resend_key and not smtp_password:
        smtp_password = resend_key
    if mail_transport == "resend" and resend_key:
        smtp_user = (store._setting("auth_smtp_user") or "").strip() or "resend"
    else:
        smtp_user = (store._setting("auth_smtp_user") or "").strip() or None
    return {
        "public_url": public.rstrip("/"),
        "web_origin": web.rstrip("/"),
        "state_secret": state_secret,
        "password_login_enabled": "password" in providers,
        "magic_link_enabled": "email" in providers,
        "oauth_github_enabled": "github" in providers,
        "oauth_google_enabled": "google" in providers,
        "github_client_id": gh_id,
        "github_client_secret": gh_secret.strip() if gh_secret else None,
        "google_client_id": go_id,
        "google_client_secret": go_secret.strip() if go_secret else None,
        "magic_link_from_email": from_email,
        "smtp_host": smtp_host,
        "smtp_port": int(store._setting("auth_smtp_port") or "587"),
        "smtp_user": smtp_user,
        "smtp_password": smtp_password.strip() if smtp_password else None,
        "magic_link_log": magic_log,
        "mail_transport": mail_transport,
        "resend_api_key": resend_key,
    }


def get_access_settings(
    store: "AdminStore",
    *,
    default_public_url: str,
    default_web_origin: str,
) -> dict[str, Any]:
    raw = build_auth_settings_raw(
        store,
        default_public_url=default_public_url,
        default_web_origin=default_web_origin,
    )
    providers = _parse_providers(store._setting("auth_providers_json"))
    signup = (store._setting("auth_signup_policy") or "open").strip().lower()
    public = raw["public_url"]
    from basis.services.tenancy.identity.http_paths import auth_v1_path

    callbacks = {
        "github": f"{public.rstrip('/')}{auth_v1_path('oauth/github/callback')}",
        "google": f"{public.rstrip('/')}{auth_v1_path('oauth/google/callback')}",
        "org_oidc": f"{public.rstrip('/')}{auth_v1_path('oidc/callback')}",
    }
    mail_transport = (store._setting("auth_mail_transport") or "").strip() or (
        "smtp" if raw["smtp_host"] else "resend"
    )
    return {
        "auth_providers": providers,
        "signup_policy": "open" if signup != "closed" else "closed",
        "magic_link_dev_log": store._setting("auth_magic_link_dev_log") == "true",
        "public_url": public,
        "web_origin": raw["web_origin"],
        "callbacks": callbacks,
        "credentials": {
            "email": {
                "transport": mail_transport if mail_transport in ("smtp", "resend") else "smtp",
                "from": raw["magic_link_from_email"],
                "host": raw["smtp_host"],
                "port": raw["smtp_port"],
                "username": raw["smtp_user"],
                "api_key": (store._setting("auth_resend_api_key") or "").strip() or None,
                "password": (
                    (store._setting("auth_smtp_password") or "").strip() or None
                ),
            },
            "oauth": {
                "github": {
                    "client_id": raw["github_client_id"],
                    "client_secret": (
                        (store._setting("auth_github_client_secret") or "").strip() or None
                    ),
                },
                "google": {
                    "client_id": raw["google_client_id"],
                    "client_secret": (
                        (store._setting("auth_google_client_secret") or "").strip() or None
                    ),
                },
            },
        },
    }


def update_access_settings(
    store: "AdminStore",
    actor: "User",
    body: dict[str, Any],
    *,
    default_public_url: str,
    default_web_origin: str,
) -> dict[str, Any]:
    from basis.services.tenancy.admin.store import _require_system_admin

    _require_system_admin(actor)
    with store._lock:
        if "auth_providers" in body and body["auth_providers"] is not None:
            store._put_setting("auth_providers_json", _serialize_providers(body["auth_providers"]))
        if "signup_policy" in body and body["signup_policy"] is not None:
            policy = str(body["signup_policy"]).strip().lower()
            store._put_setting("auth_signup_policy", "closed" if policy == "closed" else "open")
            store._put_setting(
                "open_registration", "false" if policy == "closed" else "true"
            )
        if "public_url" in body and body["public_url"] is not None:
            store._put_setting("auth_public_url", str(body["public_url"]).strip().rstrip("/"))
        if "web_origin" in body and body["web_origin"] is not None:
            store._put_setting("auth_web_origin", str(body["web_origin"]).strip().rstrip("/"))
        if body.get("magic_link_dev_log") is not None:
            store._put_setting(
                "auth_magic_link_dev_log",
                "true" if body["magic_link_dev_log"] else "false",
            )
        creds = body.get("credentials") or {}
        email = creds.get("email") or {}
        if isinstance(email, dict):
            if email.get("transport") in ("smtp", "resend"):
                store._put_setting("auth_mail_transport", email["transport"])
            for key, setting_key in (
                ("from", "auth_magic_link_from"),
                ("host", "auth_smtp_host"),
                ("username", "auth_smtp_user"),
            ):
                if key in email and email[key] is not None:
                    store._put_setting(setting_key, str(email[key]).strip())
            if "port" in email and email["port"] is not None:
                store._put_setting("auth_smtp_port", str(int(email["port"])))
            if isinstance(email.get("api_key"), str) and email["api_key"].strip():
                store._put_setting("auth_resend_api_key", email["api_key"].strip())
            if isinstance(email.get("password"), str) and email["password"].strip():
                store._put_setting("auth_smtp_password", email["password"].strip())
        oauth = creds.get("oauth") or {}
        for provider in ("github", "google"):
            block = oauth.get(provider) or creds.get(provider)
            if not isinstance(block, dict):
                continue
            prefix = f"auth_{provider}_"
            if isinstance(block.get("client_id"), str) and block["client_id"].strip():
                store._put_setting(f"{prefix}client_id", block["client_id"].strip())
            if isinstance(block.get("client_secret"), str) and block["client_secret"].strip():
                store._put_setting(f"{prefix}client_secret", block["client_secret"].strip())
        store._audit(
            actor.id,
            "settings.access_updated",
            "settings",
            None,
            {"keys": sorted(k for k in body if body[k] is not None)},
        )
        store.commit_transaction()
    return get_access_settings(
        store,
        default_public_url=default_public_url,
        default_web_origin=default_web_origin,
    )
