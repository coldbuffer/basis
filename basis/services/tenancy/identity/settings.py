"""Auth settings loaded from platform settings (AdminStore), not environment."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from basis.services.tenancy.admin.store import AdminStore


@dataclass(frozen=True)
class AuthSettings:
    public_url: str
    web_origin: str
    state_secret: str
    password_login_enabled: bool
    magic_link_enabled: bool
    github_client_id: str | None
    github_client_secret: str | None
    google_client_id: str | None
    google_client_secret: str | None
    magic_link_from_email: str | None
    smtp_host: str | None
    smtp_port: int
    smtp_user: str | None
    smtp_password: str | None
    magic_link_log: bool
    oauth_github_enabled: bool
    oauth_google_enabled: bool
    mail_transport: str
    resend_api_key: str | None

    @property
    def github_enabled(self) -> bool:
        return (
            self.oauth_github_enabled
            and bool(self.github_client_id and self.github_client_secret)
        )

    @property
    def google_enabled(self) -> bool:
        return (
            self.oauth_google_enabled
            and bool(self.google_client_id and self.google_client_secret)
        )

    @property
    def smtp_enabled(self) -> bool:
        return bool(
            self.magic_link_enabled
            and self.smtp_host
            and self.magic_link_from_email
            and self.smtp_password
        )

    @property
    def magic_link_available(self) -> bool:
        if not self.magic_link_enabled:
            return False
        return self.smtp_enabled or self.magic_link_log

    def oauth_callback_url(self, path: str) -> str:
        base = self.public_url.rstrip("/")
        return f"{base}{path}"


def load_auth_settings_from_store(
    store: "AdminStore",
    *,
    default_public_url: str = "http://127.0.0.1:8090",
    default_web_origin: str = "http://localhost:5173",
) -> AuthSettings:
    raw: dict[str, Any] = store.build_auth_settings_raw(
        default_public_url=default_public_url,
        default_web_origin=default_web_origin,
    )
    allowed = {f.name for f in fields(AuthSettings)}
    return AuthSettings(**{k: v for k, v in raw.items() if k in allowed})


def invalidate_app_auth_settings(request: Any) -> None:
    if hasattr(request, "app") and hasattr(request.app, "state"):
        request.app.state.auth_settings = None
