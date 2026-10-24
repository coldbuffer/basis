"""Model catalog and legacy chat/embed settings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from basis.domain.tenancy.admin.admin_types import User, require_system_admin
from basis.domain.tenancy.admin.errors import AdminError
from basis.domain.tenancy.admin.persistence import audit as audit_persist
from basis.domain.tenancy.admin.persistence import settings as settings_persist
from basis.domain.tenancy.catalog.catalog import (
    CATALOG_SETTINGS_KEY,
    ModelKind,
    find_entry,
    model_secret_key,
    new_entry,
    parse_catalog,
    serialize_catalog,
)

if TYPE_CHECKING:
    from basis.domain.tenancy.admin.store import AdminStore


class ModelsAccess:
    def __init__(self, store: AdminStore) -> None:
        self._store = store

    def _read_model_catalog(self) -> dict[str, list[dict[str, Any]]]:
        catalog = parse_catalog(self._store._setting(CATALOG_SETTINGS_KEY))
        self._migrate_legacy_models_into_catalog(catalog)
        return catalog

    def _write_model_catalog(self, catalog: dict[str, list[dict[str, Any]]]) -> None:
        self._store._put_setting(CATALOG_SETTINGS_KEY, serialize_catalog(catalog))

    def _migrate_legacy_models_into_catalog(self, catalog: dict[str, list[dict[str, Any]]]) -> None:
        if self._store._setting("model_catalog_legacy_imported") == "true":
            return
        if not catalog["llm"] and (self._store._setting("chat_model") or "").strip():
            entry = new_entry(
                "llm",
                provider=self._store._setting("chat_provider") or "custom",
                api_base=self._store._setting("chat_base_url") or "",
                model=self._store._setting("chat_model") or "",
                enabled=True,
            )
            catalog["llm"].append(entry)
            legacy_key = self._store._setting("chat_api_key")
            if legacy_key:
                self._store._put_setting(model_secret_key(entry["id"]), legacy_key)
            self._write_model_catalog(catalog)
        migrated = bool(catalog["llm"] or catalog["embed"])
        if not catalog["embed"] and (self._store._setting("embed_model") or "").strip():
            entry = new_entry(
                "embed",
                provider=self._store._setting("embed_provider") or "custom",
                api_base=self._store._setting("embed_base_url") or "",
                model=self._store._setting("embed_model") or "",
                enabled=True,
            )
            catalog["embed"].append(entry)
            legacy_key = self._store._setting("embed_api_key")
            if legacy_key:
                self._store._put_setting(model_secret_key(entry["id"]), legacy_key)
            self._write_model_catalog(catalog)
            migrated = True
        if migrated or self._store._setting(CATALOG_SETTINGS_KEY):
            self._store._put_setting("model_catalog_legacy_imported", "true")

    def _model_entry_configured(self, entry_id: str) -> bool:
        return bool(self._store._setting(model_secret_key(entry_id)))

    def _model_entry_public(self, entry: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": entry["id"],
            "kind": entry["kind"],
            "provider": entry.get("provider") or "",
            "api_base": entry.get("api_base") or "",
            "model": entry.get("model") or "",
            "display_name": entry.get("display_name") or entry.get("model") or "",
            "enabled": entry.get("enabled", True) is not False,
            "configured": self._model_entry_configured(entry["id"]),
        }

    def _primary_catalog_entry(self, kind: ModelKind) -> dict[str, Any] | None:
        catalog = self._read_model_catalog()
        items = catalog.get(kind, [])
        for entry in items:
            if entry.get("enabled", True) is False:
                continue
            if self._model_entry_configured(entry["id"]):
                return entry
        for entry in items:
            if entry.get("enabled", True) is not False:
                return entry
        return items[0] if items else None

    def _sync_legacy_model_fields(self, kind: ModelKind) -> None:
        entry = self._primary_catalog_entry(kind)
        if not entry:
            if kind == "llm":
                self._store._put_setting("chat_provider", "")
                self._store._put_setting("chat_base_url", "")
                self._store._put_setting("chat_model", "")
                self._store._put_setting("chat_api_key", "")
            else:
                self._store._put_setting("embed_provider", "")
                self._store._put_setting("embed_base_url", "")
                self._store._put_setting("embed_model", "")
                self._store._put_setting("embed_api_key", "")
            return
        secret = self._store._setting(model_secret_key(entry["id"])) or ""
        if kind == "llm":
            self._store._put_setting("chat_provider", entry.get("provider") or "")
            self._store._put_setting("chat_base_url", entry.get("api_base") or "")
            self._store._put_setting("chat_model", entry.get("model") or "")
            if secret:
                self._store._put_setting("chat_api_key", secret)
        else:
            self._store._put_setting("embed_provider", entry.get("provider") or "")
            self._store._put_setting("embed_base_url", entry.get("api_base") or "")
            self._store._put_setting("embed_model", entry.get("model") or "")
            if secret:
                self._store._put_setting("embed_api_key", secret)

    def upsert_kind_endpoint(
        self,
        actor: User,
        kind: ModelKind,
        *,
        provider: str,
        api_base: str,
        api_key: str = "",
    ) -> dict[str, Any]:
        """Add or update endpoint credentials for ``kind`` (matched by provider + api_base)."""
        require_system_admin(actor)
        base = api_base.strip().rstrip("/")
        if not base:
            raise AdminError(400, "api_base_required", "请填写 Base URL")
        provider_norm = provider.strip()
        base_norm = base.lower()
        with self._store._lock:
            conn = self._store._conn
            catalog = self._read_model_catalog()
            bucket = catalog.setdefault(kind, [])
            entry: dict[str, Any] | None = None
            for item in bucket:
                item_provider = (item.get("provider") or "").strip()
                item_base = (item.get("api_base") or "").strip().rstrip("/").lower()
                if item_provider == provider_norm and item_base == base_norm:
                    entry = item
                    break
            preserved_key = ""
            if entry:
                preserved_key = (self._store._setting(model_secret_key(entry["id"])) or "").strip()
                entry["provider"] = provider_norm
                entry["api_base"] = base
                entry["enabled"] = True
            else:
                entry = new_entry(
                    kind,
                    provider=provider_norm,
                    api_base=base,
                    model="",
                    display_name="",
                    enabled=True,
                )
                bucket.append(entry)
            key = api_key.strip() or preserved_key
            if key:
                self._store._put_setting(model_secret_key(entry["id"]), key)
            self._write_model_catalog(catalog)
            self._sync_legacy_model_fields(kind)
            audit_persist.insert_audit(
                conn,
                actor_id=actor.id,
                action="model.endpoint_upserted",
                target_type="model",
                target_id=entry["id"],
                detail={"kind": kind, "provider": provider.strip()},
            )
            conn.commit()
            return self._model_entry_public(entry)

    def list_configured_models(self, kind: ModelKind | None = None) -> list[dict[str, Any]]:
        with self._store._lock:
            catalog = self._read_model_catalog()
            if kind:
                return [self._model_entry_public(e) for e in catalog.get(kind, [])]
            out: list[dict[str, Any]] = []
            for bucket in ("llm", "embed"):
                out.extend(self._model_entry_public(e) for e in catalog.get(bucket, []))
            return out

    def _catalog_has_model(
        self,
        catalog: dict[str, list[dict[str, Any]]],
        kind: ModelKind,
        provider: str,
        api_base: str,
        model: str,
    ) -> bool:
        base_norm = api_base.strip().rstrip("/").lower()
        provider_norm = provider.strip()
        model_norm = model.strip()
        for entry in catalog.get(kind, []):
            if (entry.get("model") or "").strip() != model_norm:
                continue
            if (entry.get("provider") or "").strip() != provider_norm:
                continue
            entry_base = (entry.get("api_base") or "").strip().rstrip("/").lower()
            if entry_base == base_norm:
                return True
        return False

    def add_configured_models_batch(
        self,
        actor: User,
        kind: ModelKind,
        *,
        provider: str,
        api_base: str,
        models: list[str],
        api_key: str = "",
    ) -> dict[str, Any]:
        require_system_admin(actor)
        base = api_base.strip()
        if not base:
            raise AdminError(400, "api_base_required", "请填写 Base URL")
        unique_models: list[str] = []
        seen: set[str] = set()
        for raw in models:
            model_id = raw.strip()
            if not model_id or model_id in seen:
                continue
            seen.add(model_id)
            unique_models.append(model_id)
        if not unique_models:
            raise AdminError(400, "model_required", "请至少选择一个模型 ID")

        with self._store._lock:
            conn = self._store._conn
            catalog = self._read_model_catalog()
            added: list[dict[str, Any]] = []
            skipped: list[str] = []
            key = api_key.strip()
            for model_id in unique_models:
                if self._catalog_has_model(catalog, kind, provider, base, model_id):
                    skipped.append(model_id)
                    continue
                entry = new_entry(
                    kind,
                    provider=provider,
                    api_base=base,
                    model=model_id,
                    enabled=True,
                )
                catalog[kind].append(entry)
                if key:
                    self._store._put_setting(model_secret_key(entry["id"]), key)
                added.append(self._model_entry_public(entry))
            if not added:
                raise AdminError(409, "models_already_configured", "所选模型均已存在")
            self._write_model_catalog(catalog)
            self._sync_legacy_model_fields(kind)
            audit_persist.insert_audit(
                conn,
                actor_id=actor.id,
                action="model.batch_added",
                target_type="model",
                target_id=added[0]["id"],
                detail={
                    "kind": kind,
                    "provider": provider.strip(),
                    "added": [e["model"] for e in added],
                    "skipped": skipped,
                },
            )
            conn.commit()
            return {"models": added, "skipped": skipped}

    def add_configured_model(
        self,
        actor: User,
        kind: ModelKind,
        *,
        provider: str,
        api_base: str,
        model: str,
        api_key: str = "",
        display_name: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        require_system_admin(actor)
        model_id = model.strip()
        if not model_id:
            raise AdminError(400, "model_required", "请填写模型 ID")
        base = api_base.strip()
        if not base:
            raise AdminError(400, "api_base_required", "请填写 Base URL")
        with self._store._lock:
            conn = self._store._conn
            catalog = self._read_model_catalog()
            entry = new_entry(
                kind,
                provider=provider,
                api_base=base,
                model=model_id,
                display_name=display_name,
                enabled=enabled,
            )
            catalog[kind].append(entry)
            key = api_key.strip()
            if key:
                self._store._put_setting(model_secret_key(entry["id"]), key)
            self._write_model_catalog(catalog)
            self._sync_legacy_model_fields(kind)
            audit_persist.insert_audit(
                conn,
                actor_id=actor.id,
                action="model.added",
                target_type="model",
                target_id=entry["id"],
                detail={"kind": kind, "model": model_id},
            )
            conn.commit()
            return self._model_entry_public(entry)

    def delete_configured_model(self, actor: User, entry_id: str) -> None:
        require_system_admin(actor)
        with self._store._lock:
            conn = self._store._conn
            catalog = self._read_model_catalog()
            found = find_entry(catalog, entry_id)
            if not found:
                raise AdminError(404, "model_not_found", "模型不存在")
            kind, index, _entry = found
            catalog[kind].pop(index)
            settings_persist.delete_setting(conn, model_secret_key(entry_id))
            self._write_model_catalog(catalog)
            self._sync_legacy_model_fields(kind)
            audit_persist.insert_audit(
                conn,
                actor_id=actor.id,
                action="model.removed",
                target_type="model",
                target_id=entry_id,
                detail={"kind": kind},
            )
            conn.commit()

    def patch_configured_model(
        self,
        actor: User,
        entry_id: str,
        *,
        enabled: bool | None = None,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        require_system_admin(actor)
        with self._store._lock:
            conn = self._store._conn
            catalog = self._read_model_catalog()
            found = find_entry(catalog, entry_id)
            if not found:
                raise AdminError(404, "model_not_found", "模型不存在")
            kind, index, entry = found
            if enabled is not None:
                entry["enabled"] = enabled
            if api_key is not None and api_key.strip():
                self._store._put_setting(model_secret_key(entry_id), api_key.strip())
            catalog[kind][index] = entry
            self._write_model_catalog(catalog)
            self._sync_legacy_model_fields(kind)
            audit_persist.insert_audit(
                conn,
                actor_id=actor.id,
                action="model.updated",
                target_type="model",
                target_id=entry_id,
                detail={"kind": kind},
            )
            conn.commit()
            return self._model_entry_public(entry)

    def list_public_llm_endpoints(self) -> list[dict[str, Any]]:
        with self._store._lock:
            catalog = self._read_model_catalog()
            out: list[dict[str, Any]] = []
            for entry in catalog.get("llm", []):
                if entry.get("enabled", True) is False:
                    continue
                if not self._model_entry_configured(entry["id"]):
                    continue
                out.append(
                    {
                        "id": entry["id"],
                        "provider": entry.get("provider") or "",
                        "api_base": entry.get("api_base") or "",
                    }
                )
            return out

    def get_chat_llm_settings_for_entry(self, entry_id: str) -> dict[str, str | None]:
        with self._store._lock:
            found = find_entry(self._read_model_catalog(), entry_id.strip())
            if not found or found[0] != "llm":
                raise AdminError(404, "llm_endpoint_not_found", "对话模型服务商不存在")
            entry = found[2]
            secret = self._store._setting(model_secret_key(entry["id"])) or ""
            return {
                "id": entry["id"],
                "provider": entry.get("provider") or "",
                "base_url": entry.get("api_base") or "",
                "model": entry.get("model") or "",
                "api_key": secret,
            }

    def get_chat_llm_settings(self) -> dict[str, str | None]:
        with self._store._lock:
            entry = self._primary_catalog_entry("llm")
            if entry:
                secret = self._store._setting(model_secret_key(entry["id"])) or ""
                return {
                    "base_url": entry.get("api_base") or "",
                    "model": entry.get("model") or "",
                    "api_key": secret,
                }
            return {
                "base_url": self._store._setting("chat_base_url") or "",
                "model": self._store._setting("chat_model") or "",
                "api_key": self._store._setting("chat_api_key") or "",
            }

    def get_embed_settings(self, model_id: str | None = None) -> dict[str, str | None]:
        with self._store._lock:
            entry: dict[str, Any] | None = None
            if model_id:
                found = find_entry(self._read_model_catalog(), model_id)
                if found and found[0] == "embed":
                    entry = found[2]
            else:
                entry = self._primary_catalog_entry("embed")
            if entry:
                secret = self._store._setting(model_secret_key(entry["id"])) or ""
                return {
                    "id": entry["id"],
                    "base_url": entry.get("api_base") or "",
                    "model": entry.get("model") or "",
                    "api_key": secret,
                }
            if model_id:
                raise AdminError(422, "embedding_model_not_found", "指定的嵌入模型不存在")
            return {
                "id": None,
                "base_url": self._store._setting("embed_base_url") or "",
                "model": self._store._setting("embed_model") or "",
                "api_key": self._store._setting("embed_api_key") or "",
            }

    def get_stored_model_api_key(self, kind: str) -> str:
        with self._store._lock:
            entry = self._primary_catalog_entry("llm" if kind != "embed" else "embed")
            if entry:
                return self._store._setting(model_secret_key(entry["id"])) or ""
            if kind == "embed":
                return self._store._setting("embed_api_key") or ""
            return self._store._setting("chat_api_key") or ""

    def get_stored_model_api_key_for_probe(self, kind: str, provider: str, api_base: str) -> str:
        with self._store._lock:
            catalog = self._read_model_catalog()
            base_norm = api_base.strip().rstrip("/").lower()
            for entry in catalog.get(kind, []):
                if (entry.get("provider") or "") != provider:
                    continue
                entry_base = (entry.get("api_base") or "").strip().rstrip("/").lower()
                if entry_base and base_norm and entry_base != base_norm:
                    continue
                secret = self._store._setting(model_secret_key(entry["id"]))
                if secret:
                    return secret
            if kind == "embed":
                return self._store._setting("embed_api_key") or ""
            return self._store._setting("chat_api_key") or ""
