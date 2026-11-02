"""Desktop profile: fixed local principal (ADR 0004)."""

from __future__ import annotations

from basis.services.tenancy.admin.access.desktop import (
    DESKTOP_DISPLAY_NAME,
    DESKTOP_EMAIL,
    DESKTOP_USER_ID,
)
from basis.services.tenancy.admin.store import AdminStore, User


def ensure_desktop_principal(store: AdminStore) -> User:
    return store.ensure_desktop_principal()


def issue_desktop_session_token(store: AdminStore, user: User) -> str:
    return store.issue_desktop_session_token(user)


__all__ = [
    "DESKTOP_DISPLAY_NAME",
    "DESKTOP_EMAIL",
    "DESKTOP_USER_ID",
    "ensure_desktop_principal",
    "issue_desktop_session_token",
]
