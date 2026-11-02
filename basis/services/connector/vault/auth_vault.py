"""AES-256-GCM credential encryption & BOCP connection/OAuth/policy vault."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from typing import Any
from urllib.parse import quote, urlencode
import uuid

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import httpx

from basis.services.connector.vault.allowlist import (
    assert_allowed_providers_in_catalog,
    assert_workspace_allowlist_within_platform,
    effective_allowed_providers,
    is_provider_allowed,
    provider_blocked_layer,
)
from basis.services.connector.vault.connection_scope import (
    SCOPE_END_USER,
    SCOPE_WORKSPACE,
    assert_end_user_allowed_for_service,
    WORKSPACE_SUBJECT_ID,
    ConnectionScope,
    normalize_connection_scope,
    normalize_subject_id,
)
from basis.services.connector.registry import get_connector_catalog
from basis.services.connector.manifest.manifest_schema import AuthSpec, ConnectorManifest, ToolSpec
from basis.services.connector.canonical_db import LockedCanonicalConn, is_knowledge_store
from basis.services.knowledge.sql import ConnectorVaultPersistence


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_vault_key(explicit_secret: str | None = None) -> bytes:
    """Derive a 32-byte AES-256 key from explicit secret, env var, or local dev fallback."""
    raw = (
        explicit_secret
        or os.environ.get("BASIS_CONNECTOR_VAULT_SECRET")
        or os.environ.get("BASIS_SECRET_KEY")
        or "basis-dev-connector-vault-secret-do-not-use-in-prod"
    )
    return hashlib.sha256(raw.encode("utf-8")).digest()


def encrypt_vault_payload(
    payload: dict[str, Any], *, secret: str | None = None
) -> str:
    """Encrypt a JSON dictionary with AES-256-GCM into a versioned base64 string."""
    key = _resolve_vault_key(secret)
    nonce = os.urandom(12)
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    token = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return f"v1:{token}"


def decrypt_vault_payload(
    encrypted: str, *, secret: str | None = None
) -> dict[str, Any]:
    """Decrypt a versioned AES-256-GCM string back into a JSON dictionary."""
    if not encrypted.startswith("v1:"):
        raise ValueError("Unsupported vault ciphertext version")
    raw_b64 = encrypted[3:]
    blob = base64.urlsafe_b64decode(raw_b64.encode("ascii"))
    if len(blob) < 13:
        raise ValueError("Invalid vault ciphertext payload")
    nonce, ciphertext = blob[:12], blob[12:]
    key = _resolve_vault_key(secret)
    plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
    parsed = json.loads(plaintext.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("Vault payload must decode to a JSON object")
    return parsed


_UNRESOLVED_PLACEHOLDER = re.compile(r"\$\{[^}]+\}|\{\{[^}]+\}\}")


def interpolate_placeholders(
    template: str,
    *,
    connection_config: dict[str, Any] | None = None,
    credentials: dict[str, Any] | None = None,
    stream_params: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
    url_encode_values: bool = False,
    strict: bool = True,
) -> str:
    """Resolve BOCP placeholders in a template.

    Connection config wins over per-call ``action_params``/``stream_params`` for
    ``{{config.KEY}}`` (a connection-bound scope cannot be overridden by a caller).
    ``url_encode_values`` percent-encodes every substituted value for URL path use.
    """
    if not template:
        return ""

    cfg = connection_config or {}
    creds = credentials or {}
    params = stream_params or {}
    ext = extra or {}

    def render(value: Any) -> str:
        raw = str(value)
        if not url_encode_values:
            return raw
        # Percent-encoding cannot make a bare "." / ".." segment inert: URL
        # parsers normalize it after decoding. Reject it instead.
        if raw in (".", ".."):
            raise ValueError(f"Unsafe URL path placeholder value: {raw!r}")
        return quote(raw, safe="")

    # Caller params may fill missing scope keys, but never override the connection.
    merged = dict(params)
    merged.update(cfg)

    result = template
    for key, value in merged.items():
        result = result.replace(f"{{{{config.{key}}}}}", render(value))
    for key, value in creds.items():
        result = result.replace(f"${{credentials.{key}}}", render(value))
    # Legacy bare aliases. Normative templates use ``{{config.KEY}}``.
    for key, value in merged.items():
        result = result.replace(f"{{{{{key}}}}}", render(value))
    for key, value in ext.items():
        result = result.replace(f"{{{{{key}}}}}", render(value))

    if strict:
        unresolved = _UNRESOLVED_PLACEHOLDER.findall(result)
        if unresolved:
            raise ValueError(
                "Unresolved connector placeholder(s): "
                + ", ".join(sorted(set(unresolved)))
            )
    return result


def extract_dot_path(data: Any, path: str | None) -> Any:
    """Extract a nested value from a dict/list using dot notation (e.g. 'paging.next.after')."""
    if not path or data is None:
        return None
    cur = data
    for part in path.split("."):
        if not part:
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit():
            idx = int(part)
            cur = cur[idx] if 0 <= idx < len(cur) else None
        else:
            return None
    return cur


@dataclass
class StoredConnection:
    workspace_id: str
    service: str
    auth_type: str
    connection_config: dict[str, Any]
    credentials: dict[str, Any]
    account_profile: dict[str, Any] = field(default_factory=dict)
    revision: int = 1
    updated_at: str = ""
    connection_scope: ConnectionScope = SCOPE_WORKSPACE
    subject_id: str = WORKSPACE_SUBJECT_ID

    def to_public_dict(self) -> dict[str, Any]:
        """Return safe connection metadata without exposing decrypted credentials."""
        return {
            "workspace_id": self.workspace_id,
            "service": self.service,
            "connection_scope": self.connection_scope,
            "subject_id": self.subject_id if self.connection_scope != SCOPE_WORKSPACE else None,
            "auth_type": self.auth_type,
            "connection_config": self.connection_config,
            "account_profile": self.account_profile,
            "revision": self.revision,
            "updated_at": self.updated_at,
            "has_credentials": bool(self.credentials),
        }


@dataclass
class ConnectorPolicy:
    workspace_id: str
    allowed_providers: list[str] | str = "*"
    action_policy: dict[str, Any] = field(default_factory=dict)
    updated_at: str = ""

    def is_provider_allowed(self, service: str) -> bool:
        if self.allowed_providers == "*":
            return True
        if isinstance(self.allowed_providers, list):
            return "*" in self.allowed_providers or service in self.allowed_providers
        return False

    def is_provider_allowed_with_platform(
        self,
        service: str,
        platform_allowed: list[str] | str,
    ) -> bool:
        return is_provider_allowed(service, platform_allowed, self.allowed_providers)

    def resolve_tool_execution_mode(
        self, service: str, tool: ToolSpec
    ) -> str:
        """Resolve execution governance mode ('auto', 'review', or 'disabled') for a BOCP tool."""
        tools_map = self.action_policy.get("tools")
        if isinstance(tools_map, dict):
            explicit = tools_map.get(f"{service}:{tool.id}") or tools_map.get(tool.id)
            if explicit in ("auto", "review", "disabled"):
                return str(explicit)
        if tool.annotations.read_only_hint:
            mode = self.action_policy.get("default_read_mode", "auto")
        else:
            mode = self.action_policy.get("default_write_mode", "auto")
        return str(mode) if mode in ("auto", "review", "disabled") else "auto"

    def resolve_primitive_execution_mode(
        self,
        service: str,
        action_id: str,
        primitive: str,
        *,
        operation: str | None = None,
    ) -> str:
        """Governance for entity/procedure primitives (discover, list, mutate, invoke)."""
        entities_map = self.action_policy.get("entities")
        if isinstance(entities_map, dict):
            candidates = [
                f"{service}:{action_id}.{primitive}",
                f"{action_id}.{primitive}",
                f"{service}:{action_id}",
                action_id,
            ]
            if operation:
                candidates[:0] = [
                    f"{service}:{action_id}.{operation}",
                    f"{action_id}.{operation}",
                    f"{service}:{action_id}.mutate.{operation}",
                    f"{action_id}.mutate.{operation}",
                ]
            for key in candidates:
                explicit = entities_map.get(key)
                if explicit in ("auto", "review", "disabled"):
                    return str(explicit)
        if primitive in ("discover", "list"):
            mode = self.action_policy.get(
                "default_entity_read_mode",
                self.action_policy.get("default_read_mode", "auto"),
            )
        else:
            mode = self.action_policy.get(
                "default_entity_write_mode",
                self.action_policy.get("default_write_mode", "auto"),
            )
        return str(mode) if mode in ("auto", "review", "disabled") else "auto"


def _connection_row_field(row: Any, name: str, index: int, default: Any) -> Any:
    """Read a column from sqlite3.Row, CompatRow, or positional tuple."""
    if hasattr(row, "keys"):
        keys = row.keys()
        if name in keys:
            val = row[name]
            return default if val is None and default is not None else val
    try:
        return row[index]
    except (IndexError, KeyError, TypeError):
        return default


class ConnectorAuthVault:
    """SQLite/PostgreSQL persistence & authentication engine for BOCP connections."""

    def __init__(self, knowledge_or_conn: Any, *, vault_secret: str | None = None) -> None:
        self._store = knowledge_or_conn if is_knowledge_store(knowledge_or_conn) else None
        self._db = LockedCanonicalConn(knowledge_or_conn)
        self._vault_secret = vault_secret
        self._persist = (
            knowledge_or_conn.connector_vault_persistence()
            if self._store is not None
            else ConnectorVaultPersistence(self._db)
        )

    # ── Policies ─────────────────────────────────────────────────────────────

    def get_policy(self, workspace_id: str) -> ConnectorPolicy:
        row = self._persist.fetch_policy_row(workspace_id)
        if not row:
            return ConnectorPolicy(workspace_id=workspace_id, allowed_providers="*", action_policy={})
        allowed = json.loads(row[0]) if row[0] else "*"
        action_policy = json.loads(row[1]) if row[1] else {}
        return ConnectorPolicy(
            workspace_id=workspace_id,
            allowed_providers=allowed,
            action_policy=action_policy,
            updated_at=row[2] or "",
        )

    def upsert_policy(
        self,
        workspace_id: str,
        *,
        allowed_providers: list[str] | str = "*",
        action_policy: dict[str, Any] | None = None,
    ) -> ConnectorPolicy:
        platform_allowed = self.get_platform_allowed_providers()
        try:
            assert_allowed_providers_in_catalog(
                allowed_providers,
                get_connector_catalog().service_ids(),
            )
            assert_workspace_allowlist_within_platform(allowed_providers, platform_allowed)
        except ValueError as exc:
            raise PermissionError(str(exc)) from exc
        now = _now_iso()
        allowed_json = json.dumps(allowed_providers, ensure_ascii=False)
        action_json = json.dumps(action_policy or {}, ensure_ascii=False)
        self._persist.upsert_policy(workspace_id, allowed_json, action_json, now)
        return self.get_policy(workspace_id)

    def get_platform_allowed_providers(self) -> list[str] | str:
        if self._store is not None:
            return self._store.get_platform_allowed_providers()
        return self._db.get_platform_allowed_providers()

    def effective_allowed_providers(self, workspace_id: str) -> list[str] | str:
        from basis.services.connector.workspace_apps import effective_active_providers

        platform = self.get_platform_allowed_providers()
        workspace_policy = self.get_policy(workspace_id)
        return effective_active_providers(
            platform,
            workspace_policy.allowed_providers,
            workspace_policy.action_policy,
        )

    def assert_service_allowed(self, workspace_id: str, service: str) -> None:
        from basis.services.connector.workspace_apps import is_workspace_app_active

        platform = self.get_platform_allowed_providers()
        workspace_policy = self.get_policy(workspace_id)
        layer = provider_blocked_layer(service, platform, workspace_policy.allowed_providers)
        if layer == "platform":
            raise PermissionError(
                f"Connector service '{service}' is blocked by platform connector policy"
            )
        if layer == "workspace":
            raise PermissionError(
                f"Connector service '{service}' is blocked by workspace connector policy"
            )
        if not is_workspace_app_active(
            service,
            workspace_policy.allowed_providers,
            workspace_policy.action_policy,
        ):
            raise PermissionError(
                f"Connector service '{service}' is not installed or is disabled for this workspace"
            )

    # ── OAuth App Configs ────────────────────────────────────────────────────

    def upsert_oauth_config(
        self,
        workspace_id: str,
        service: str,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = _now_iso()
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            **(extra or {}),
        }
        encrypted = encrypt_vault_payload(payload, secret=self._vault_secret)
        self._persist.upsert_oauth_config(workspace_id, service, encrypted, now)
        return {"workspace_id": workspace_id, "service": service, "client_id": client_id, "updated_at": now}

    def get_oauth_config(self, workspace_id: str, service: str) -> dict[str, Any] | None:
        row = self._persist.fetch_oauth_config_row(workspace_id, service)
        if not row:
            return None
        decrypted = decrypt_vault_payload(row[0], secret=self._vault_secret)
        decrypted["updated_at"] = row[1]
        return decrypted

    def get_oauth_config_public(
        self, workspace_id: str, service: str
    ) -> dict[str, Any] | None:
        """OAuth app metadata for editors (no client_secret)."""
        cfg = self.get_oauth_config(workspace_id, service)
        if not cfg:
            return None
        return {
            "workspace_id": workspace_id,
            "service": service,
            "client_id": str(cfg.get("client_id") or ""),
            "redirect_uri": cfg.get("redirect_uri"),
            "has_client_secret": bool(str(cfg.get("client_secret") or "").strip()),
            "updated_at": str(cfg.get("updated_at") or ""),
        }

    # ── Connections CRUD ─────────────────────────────────────────────────────

    def upsert_connection(
        self,
        workspace_id: str,
        service: str,
        *,
        connection_scope: ConnectionScope | str = SCOPE_WORKSPACE,
        subject_id: str | None = None,
        auth_type: str,
        connection_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        account_profile: dict[str, Any] | None = None,
    ) -> StoredConnection:
        scope = normalize_connection_scope(
            connection_scope if isinstance(connection_scope, str) else connection_scope
        )
        sid = normalize_subject_id(subject_id, scope=scope)
        if scope == SCOPE_END_USER:
            workspace_rows = self.list_connections(
                workspace_id,
                service=service,
                connection_scope=SCOPE_WORKSPACE,
            )
            assert_end_user_allowed_for_service(
                scope=scope,
                has_workspace_connection=bool(workspace_rows),
                service=service,
            )
        now = _now_iso()
        existing = self.get_connection(
            workspace_id,
            service,
            connection_scope=scope,
            subject_id=sid,
        )
        rev = (existing.revision + 1) if existing else 1
        merged_cfg = (
            dict(existing.connection_config, **(connection_config or {}))
            if existing and connection_config is not None
            else (connection_config or (existing.connection_config if existing else {}))
        )
        merged_creds = (
            dict(existing.credentials, **(credentials or {}))
            if existing and credentials is not None
            else (credentials or (existing.credentials if existing else {}))
        )
        merged_profile = (
            account_profile
            if account_profile is not None
            else (existing.account_profile if existing else {})
        )

        encrypted = encrypt_vault_payload(merged_creds, secret=self._vault_secret)
        self._persist.upsert_connection(
            workspace_id=workspace_id,
            service=service,
            connection_scope=scope,
            subject_id=sid,
            auth_type=auth_type,
            connection_config_json=json.dumps(merged_cfg, ensure_ascii=False),
            value_encrypted=encrypted,
            account_profile_json=json.dumps(merged_profile, ensure_ascii=False),
            revision=rev,
            updated_at=now,
        )
        res = self.get_connection(
            workspace_id,
            service,
            connection_scope=scope,
            subject_id=sid,
        )
        assert res is not None
        return res

    @staticmethod
    def _row_to_stored_connection(
        workspace_id: str,
        service: str,
        row: Any,
        *,
        vault_secret: str | None,
    ) -> StoredConnection:
        return StoredConnection(
            workspace_id=workspace_id,
            service=service,
            auth_type=row[0],
            connection_config=json.loads(row[1]) if row[1] else {},
            credentials=decrypt_vault_payload(row[2], secret=vault_secret),
            account_profile=json.loads(row[3]) if row[3] else {},
            revision=int(row[4]),
            updated_at=row[5] or "",
            connection_scope=normalize_connection_scope(
                _connection_row_field(row, "connection_scope", 6, SCOPE_WORKSPACE)
            ),
            subject_id=str(
                _connection_row_field(row, "subject_id", 7, WORKSPACE_SUBJECT_ID) or WORKSPACE_SUBJECT_ID
            ),
        )

    def get_connection(
        self,
        workspace_id: str,
        service: str,
        *,
        connection_scope: ConnectionScope | str = SCOPE_WORKSPACE,
        subject_id: str | None = None,
    ) -> StoredConnection | None:
        scope = normalize_connection_scope(
            connection_scope if isinstance(connection_scope, str) else connection_scope
        )
        sid = normalize_subject_id(subject_id, scope=scope)
        row = self._persist.fetch_connection_row(
            workspace_id,
            service,
            connection_scope=scope,
            subject_id=sid,
        )
        if not row:
            return None
        return self._row_to_stored_connection(
            workspace_id,
            service,
            row,
            vault_secret=self._vault_secret,
        )

    def list_connections(
        self,
        workspace_id: str,
        *,
        service: str | None = None,
        connection_scope: ConnectionScope | str | None = None,
        subject_id: str | None = None,
    ) -> list[StoredConnection]:
        scope_filter: str | None = None
        if connection_scope is not None:
            scope_filter = normalize_connection_scope(
                connection_scope if isinstance(connection_scope, str) else connection_scope
            )
        sid_filter: str | None = None
        if subject_id is not None:
            sid_filter = subject_id.strip()
        rows = self._persist.list_connection_rows(
            workspace_id,
            service=service,
            connection_scope=scope_filter,
            subject_id=sid_filter,
        )
        return [
            StoredConnection(
                workspace_id=workspace_id,
                service=r[0],
                auth_type=r[1],
                connection_config=json.loads(r[2]) if r[2] else {},
                credentials=decrypt_vault_payload(r[3], secret=self._vault_secret),
                account_profile=json.loads(r[4]) if r[4] else {},
                revision=int(r[5]),
                updated_at=r[6] or "",
                connection_scope=normalize_connection_scope(r[7]),
                subject_id=str(r[8]),
            )
            for r in rows
        ]

    def delete_connection(
        self,
        workspace_id: str,
        service: str,
        *,
        connection_scope: ConnectionScope | str = SCOPE_WORKSPACE,
        subject_id: str | None = None,
    ) -> bool:
        scope = normalize_connection_scope(
            connection_scope if isinstance(connection_scope, str) else connection_scope
        )
        sid = normalize_subject_id(subject_id, scope=scope)
        return (
            self._persist.delete_connection(
                workspace_id,
                service,
                connection_scope=scope,
                subject_id=sid,
            )
            > 0
        )

    # ── Audit Runs ───────────────────────────────────────────────────────────

    def record_run(
        self,
        workspace_id: str,
        *,
        service: str,
        operation_kind: str,
        target_id: str,
        started_at: str,
        completed_at: str | None = None,
        ok: bool = True,
        value: dict[str, Any] | None = None,
    ) -> str:
        run_id = f"crun_{uuid.uuid4().hex[:16]}"
        done_at = completed_at or _now_iso()
        self._persist.insert_connector_run(
            run_id=run_id,
            workspace_id=workspace_id,
            service=service,
            operation_kind=operation_kind,
            target_id=target_id,
            started_at=started_at,
            completed_at=done_at,
            ok=1 if ok else 0,
            value_json=json.dumps(value or {}, ensure_ascii=False),
        )
        return run_id

    # ── Request Auth Headers / Params Builder ────────────────────────────────

    def build_request_auth(
        self,
        manifest: ConnectorManifest,
        connection: StoredConnection,
    ) -> tuple[str, dict[str, str], dict[str, str]]:
        """Resolve base_url, HTTP headers, and query params for a StoredConnection."""
        auth_spec = self._match_auth_spec(manifest, connection.auth_type)
        raw_base = (auth_spec.base_url if auth_spec else None) or ""
        base_url = interpolate_placeholders(
            raw_base,
            connection_config=connection.connection_config,
            credentials=connection.credentials,
        ).rstrip("/")

        headers: dict[str, str] = {}
        query_params: dict[str, str] = {}

        if auth_spec:
            for hk, hv in auth_spec.headers.items():
                headers[hk] = interpolate_placeholders(
                    hv,
                    connection_config=connection.connection_config,
                    credentials=connection.credentials,
                )
            for qk, qv in auth_spec.query_params.items():
                query_params[qk] = interpolate_placeholders(
                    qv,
                    connection_config=connection.connection_config,
                    credentials=connection.credentials,
                )

        mode = connection.auth_type
        creds = connection.credentials
        if mode in ("oauth2", "oauth2_cc", "two_step", "jwt"):
            token = creds.get("access_token") or creds.get("token")
            if token and "Authorization" not in headers:
                headers["Authorization"] = f"Bearer {token}"
        elif mode == "api_key":
            # BOCP requires api_key placement to be declared in auth.headers or
            # auth.query_params. Guessing a header/credential is not conformant.
            if not headers and not query_params:
                raise ValueError(
                    f"api_key auth for service '{connection.service}' must declare "
                    "an explicit auth.headers or auth.query_params entry"
                )
        elif mode == "basic":
            if "Authorization" not in headers:
                username = str(creds.get("username") or "")
                password = str(creds.get("password") or "")
                b64 = base64.b64encode(
                    f"{username}:{password}".encode("utf-8")
                ).decode("ascii")
                headers["Authorization"] = f"Basic {b64}"

        return base_url, headers, query_params

    def build_oauth2_authorize_url(
        self,
        workspace_id: str,
        service: str,
        *,
        state: str,
        redirect_uri: str | None = None,
        connection_config: dict[str, Any] | None = None,
        code_challenge: str | None = None,
    ) -> str:
        manifest = get_connector_catalog().get(service)
        if not manifest:
            raise ValueError(f"Unknown connector service: {service}")
        auth_spec = self._match_auth_spec(manifest, "oauth2")
        if not auth_spec or not auth_spec.oauth2 or not auth_spec.oauth2.authorization_url:
            raise ValueError(f"Service {service} does not support OAuth2 authorization URL")
        oauth_cfg = self.get_oauth_config(workspace_id, service)
        if not oauth_cfg:
            raise ValueError(f"OAuth2 client config not configured for {service}")
        self.assert_service_allowed(workspace_id, service)

        oauth2 = auth_spec.oauth2
        auth_url = interpolate_placeholders(
            oauth2.authorization_url,
            connection_config=connection_config,
        )
        params: dict[str, str] = {
            "response_type": "code",
            "client_id": str(oauth_cfg["client_id"]),
            "state": state,
            **oauth2.authorization_params,
        }
        final_redirect = redirect_uri or oauth_cfg.get("redirect_uri")
        if final_redirect:
            params["redirect_uri"] = str(final_redirect)
        if oauth2.scopes:
            params["scope"] = oauth2.scope_separator.join(oauth2.scopes)
        if oauth2.pkce_s256 and code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        elif oauth2.pkce_s256 and not code_challenge:
            raise ValueError(
                f"OAuth2 PKCE (code_challenge) is required for service '{service}'"
            )

        sep = "&" if "?" in auth_url else "?"
        return f"{auth_url}{sep}{urlencode(params)}"

    @staticmethod
    def _oauth2_token_error_message(
        token_payload: Any,
        *,
        http_status: int | None = None,
    ) -> str:
        if isinstance(token_payload, dict):
            err = token_payload.get("error")
            desc = token_payload.get("error_description") or token_payload.get("error_uri")
            if err:
                msg = str(err)
                if desc:
                    msg = f"{msg}: {desc}"
                return msg
        if http_status:
            return f"OAuth2 token request failed (HTTP {http_status})"
        return "OAuth2 token endpoint did not return an access_token"

    def exchange_oauth2_code(
        self,
        workspace_id: str,
        service: str,
        *,
        code: str,
        redirect_uri: str | None = None,
        code_verifier: str | None = None,
        connection_scope: ConnectionScope | str = SCOPE_WORKSPACE,
        subject_id: str | None = None,
        connection_config: dict[str, Any] | None = None,
        http_client: httpx.Client | None = None,
    ) -> StoredConnection:
        """Exchange an OAuth2 authorization code for tokens and persist the encrypted connection."""
        manifest = get_connector_catalog().get(service)
        if not manifest:
            raise ValueError(f"Unknown connector service: {service}")
        auth_spec = self._match_auth_spec(manifest, "oauth2")
        if not auth_spec or not auth_spec.oauth2 or not auth_spec.oauth2.token_url:
            raise ValueError(f"Service {service} does not support OAuth2 token exchange")
        oauth_cfg = self.get_oauth_config(workspace_id, service)
        if not oauth_cfg:
            raise ValueError(f"OAuth2 client config not configured for {service}")
        self.assert_service_allowed(workspace_id, service)

        oauth2 = auth_spec.oauth2
        token_url = interpolate_placeholders(
            oauth2.token_url,
            connection_config=connection_config,
        )
        form_data: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": str(oauth_cfg["client_id"]),
            "client_secret": str(oauth_cfg["client_secret"]),
            **oauth2.token_params,
        }
        final_redirect = redirect_uri or oauth_cfg.get("redirect_uri")
        if final_redirect:
            form_data["redirect_uri"] = str(final_redirect)
        if oauth2.pkce_s256 and not code_verifier:
            raise ValueError(
                f"OAuth2 PKCE (code_verifier) is required for service '{service}'"
            )
        if code_verifier:
            form_data["code_verifier"] = code_verifier

        client = http_client or httpx.Client(timeout=30.0)
        owns_client = http_client is None
        try:
            resp = client.post(
                token_url,
                data=form_data,
                headers={"Accept": "application/json"},
            )
            token_payload: Any = {}
            if resp.content:
                try:
                    token_payload = resp.json()
                except json.JSONDecodeError:
                    token_payload = {}
            if not resp.is_success:
                raise ValueError(
                    self._oauth2_token_error_message(
                        token_payload,
                        http_status=resp.status_code,
                    )
                )
        finally:
            if owns_client:
                client.close()

        if not isinstance(token_payload, dict) or not (
            token_payload.get("access_token") or token_payload.get("token")
        ):
            raise ValueError(
                self._oauth2_token_error_message(
                    token_payload,
                    http_status=resp.status_code,
                )
            )

        return self.upsert_connection(
            workspace_id,
            service,
            connection_scope=connection_scope,
            subject_id=subject_id,
            auth_type="oauth2",
            connection_config=connection_config or {},
            credentials=token_payload,
        )

    @staticmethod
    def _match_auth_spec(
        manifest: ConnectorManifest, auth_type: str
    ) -> AuthSpec | None:
        for spec in manifest.auth:
            if spec.auth_mode == auth_type:
                return spec
        return manifest.auth[0] if manifest.auth else None
