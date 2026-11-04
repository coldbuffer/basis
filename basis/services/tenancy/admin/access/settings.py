"""Platform settings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from basis.services.tenancy.admin.admin_types import User, require_system_admin
from basis.services.tenancy.admin.persistence import audit as audit_persist

if TYPE_CHECKING:
    from basis.services.tenancy.admin.store import AdminStore


class SettingsAccess:
    def __init__(self, store: AdminStore) -> None:
        self._store = store

    def get_settings(self) -> dict[str, Any]:
        with self._store._lock:
            chat_key = self._store._setting("chat_api_key")
            embed_key = self._store._setting("embed_api_key")
            return {
                "open_registration": self._store._setting("open_registration") == "true",
                "chat_provider": self._store._setting("chat_provider") or "",
                "chat_base_url": self._store._setting("chat_base_url") or "",
                "chat_model": self._store._setting("chat_model") or "",
                "has_chat_key": bool(chat_key),
                "embed_provider": self._store._setting("embed_provider") or "",
                "embed_base_url": self._store._setting("embed_base_url") or "",
                "embed_model": self._store._setting("embed_model") or "",
                "has_embed_key": bool(embed_key),
            }

    def update_settings(self, actor: User, values: dict[str, Any]) -> dict[str, Any]:
        require_system_admin(actor)
        with self._store._lock:
            conn = self._store._conn
            if "open_registration" in values and values["open_registration"] is not None:
                self._store._put_setting(
                    "open_registration", "true" if values["open_registration"] else "false"
                )
            for key in (
                "chat_provider",
                "chat_base_url",
                "chat_model",
                "embed_provider",
                "embed_base_url",
                "embed_model",
            ):
                if key in values and values[key] is not None:
                    self._store._put_setting(key, str(values[key]).strip())
            for key in ("chat_api_key", "embed_api_key"):
                secret = values.get(key)
                if isinstance(secret, str) and secret.strip():
                    self._store._put_setting(key, secret.strip())
            audit_persist.insert_audit(
                conn,
                actor_id=actor.id,
                action="settings.updated",
                target_type="settings",
                target_id=None,
                detail={"keys": sorted(values)},
            )
            conn.commit()
            chat_key = self._store._setting("chat_api_key")
            embed_key = self._store._setting("embed_api_key")
            view = {
                "open_registration": self._store._setting("open_registration") == "true",
                "chat_provider": self._store._setting("chat_provider") or "",
                "chat_base_url": self._store._setting("chat_base_url") or "",
                "chat_model": self._store._setting("chat_model") or "",
                "has_chat_key": bool(chat_key),
                "embed_provider": self._store._setting("embed_provider") or "",
                "embed_base_url": self._store._setting("embed_base_url") or "",
                "embed_model": self._store._setting("embed_model") or "",
                "has_embed_key": bool(embed_key),
            }
        return view
