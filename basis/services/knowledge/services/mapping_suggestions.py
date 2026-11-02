"""Heuristic cross-stream connector table-mapping drafts (Helix ontologyBundle-style grouping)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from basis.services.knowledge.ports.connector import ConnectorRuntime, SqlAlchemyStreamAdapter
from basis.services.knowledge.models import ColumnMappingSpec

Confidence = Literal["high", "medium", "low"]

_STREAM_GROUP_ALIASES: dict[str, str] = {
    "members": "users",
    "people": "users",
    "contacts": "users",
    "organizations": "orgs",
    "companies": "accounts",
    "accounts": "accounts",
    "repositories": "repositories",
    "projects": "projects",
    "issues": "issues",
    "pull_requests": "pull_requests",
    "merge_requests": "pull_requests",
}

_ID_LIKE = frozenset(
    {"id", "uuid", "guid", "pk", "key", "external_id", "record_id", "object_id"}
)
_LABEL_LIKE = frozenset(
    {
        "name",
        "title",
        "label",
        "display_name",
        "full_name",
        "account_name",
        "subject",
        "summary",
    }
)
_CURSOR_LIKE = frozenset(
    {"updated_at", "modified_at", "last_modified", "synced_at", "changed_at", "timestamp"}
)


def _pascal_case(slug: str) -> str:
    parts = re.split(r"[_\-\s]+", slug.strip())
    return "".join(p[:1].upper() + p[1:] for p in parts if p)


def entity_group_key(stream_name: str) -> str:
    normalized = stream_name.strip().lower()
    return _STREAM_GROUP_ALIASES.get(normalized, normalized)


def target_class_uri_for_stream(stream_name: str, display_name: str | None = None) -> str:
    if stream_name == "table_records":
        base = display_name or "Entity"
        # external_table may be schema.table — use table segment
        table = base.split(".")[-1] if "." in base else base
        return f"urn:basis:class:{_pascal_case(table)}"
    group = entity_group_key(stream_name)
    return f"urn:basis:class:{_pascal_case(group)}"


def _pick_primary_key(
    discovered_pk: list[str], field_names: list[str], fallback: str = "id"
) -> str:
    if discovered_pk:
        return discovered_pk[0]
    for candidate in field_names:
        if candidate.lower() in _ID_LIKE or candidate.lower().endswith("_id"):
            return candidate
    return field_names[0] if field_names else fallback


def _pick_label_column(field_names: list[str], pk: str) -> str:
    for candidate in field_names:
        if candidate.lower() in _LABEL_LIKE:
            return candidate
    for candidate in field_names:
        if candidate != pk and not candidate.lower().endswith("_id"):
            return candidate
    return pk


def _pick_cursor_column(field_names: list[str]) -> str | None:
    for candidate in field_names:
        if candidate.lower() in _CURSOR_LIKE:
            return candidate
    return None


def column_mappings_from_fields(
    field_names: list[str],
    *,
    pk: str,
    max_columns: int = 12,
) -> list[ColumnMappingSpec]:
    mappings: list[ColumnMappingSpec] = []
    for name in field_names:
        if name == pk:
            continue
        if len(mappings) >= max_columns:
            break
        writable = name.lower() in _LABEL_LIKE or name.lower() not in _ID_LIKE
        mappings.append(
            ColumnMappingSpec(
                column=name,
                kind="literal",
                surface_phrase=f"has {name}",
                predicate_uri=f"urn:basis:prop:{name}",
                writable=writable,
            )
        )
    return mappings


@dataclass
class SuggestStreamTarget:
    provider: str
    stream_name: str | None = None
    external_table: str | None = None


@dataclass
class MappingDraftSuggestion:
    draft: dict[str, Any]
    entity_group: str
    entity_group_label: str
    confidence: Confidence
    source_label: str


@dataclass
class SkippedSuggestTarget:
    provider: str
    stream_name: str | None
    external_table: str | None
    reason: str


@dataclass
class TableMappingSuggestResult:
    groups: list[dict[str, Any]] = field(default_factory=list)
    drafts: list[MappingDraftSuggestion] = field(default_factory=list)
    skipped: list[SkippedSuggestTarget] = field(default_factory=list)


def expand_auto_targets(
    runtime: ConnectorRuntime,
    workspace_id: str,
    *,
    max_streams_per_connection: int = 8,
    connection_scopes: list[str] | None = None,
) -> list[SuggestStreamTarget]:
    targets: list[SuggestStreamTarget] = []
    connections = runtime.vault.list_connections(workspace_id)
    scope_set: set[str] | None = None
    if connection_scopes:
        scope_set = set(connection_scopes)
    for conn in connections:
        if scope_set is not None and conn.service not in scope_set:
            continue
        manifest = runtime.catalog.get(conn.service)
        if not manifest or not manifest.streams:
            continue
        sql_stream = next(
            (s for s in manifest.streams if runtime._is_sql_stream(s)),
            None,
        )
        if sql_stream is not None:
            try:
                _, connection = runtime._require_manifest_and_connection(
                    workspace_id,
                    conn.service,
                )
                adapter = SqlAlchemyStreamAdapter.from_connection(connection)
                try:
                    tables = adapter.list_tables()[:max_streams_per_connection]
                finally:
                    adapter.close()
                for table in tables:
                    targets.append(
                        SuggestStreamTarget(
                            provider=conn.service,
                            stream_name=sql_stream.name,
                            external_table=table,
                        )
                    )
            except Exception:
                continue
            continue
        streams = manifest.streams[:max_streams_per_connection]
        for stream in streams:
            if runtime._is_sql_stream(stream):
                continue
            targets.append(
                SuggestStreamTarget(
                    provider=conn.service,
                    stream_name=stream.name,
                    external_table=stream.name,
                )
            )
    return targets


def _mapping_fingerprint(
    provider: str,
    stream_name: str,
    external_table: str,
) -> tuple[str, str, str]:
    return (provider, stream_name, external_table)


def suggest_table_mapping_drafts(
    runtime: ConnectorRuntime,
    workspace_id: str,
    targets: list[SuggestStreamTarget],
    *,
    existing_fingerprints: set[tuple[str, str, str]] | None = None,
) -> TableMappingSuggestResult:
    """Discover schemas and emit grouped mapping drafts for REST streams (SQL needs external_table)."""
    existing = existing_fingerprints or set()
    result = TableMappingSuggestResult()
    grouped: dict[str, list[MappingDraftSuggestion]] = {}

    for target in targets:
        manifest = runtime.catalog.get(target.provider)
        if not manifest:
            result.skipped.append(
                SkippedSuggestTarget(
                    target.provider,
                    target.stream_name,
                    target.external_table,
                    "unknown_provider",
                )
            )
            continue
        stream_name = target.stream_name
        if not stream_name and manifest.streams:
            stream_name = manifest.streams[0].name
        if not stream_name:
            result.skipped.append(
                SkippedSuggestTarget(
                    target.provider,
                    None,
                    target.external_table,
                    "no_streams",
                )
            )
            continue
        stream = runtime._find_stream(manifest, stream_name)
        external_table = target.external_table
        if runtime._is_sql_stream(stream):
            if not external_table:
                result.skipped.append(
                    SkippedSuggestTarget(
                        target.provider,
                        stream_name,
                        None,
                        "sql_requires_external_table",
                    )
                )
                continue
        else:
            external_table = external_table or stream_name

        fp = _mapping_fingerprint(target.provider, stream_name, external_table)
        if fp in existing:
            result.skipped.append(
                SkippedSuggestTarget(
                    target.provider,
                    stream_name,
                    external_table,
                    "already_mapped",
                )
            )
            continue

        try:
            info = runtime.discover_schema(
                workspace_id,
                target.provider,
                stream_name=stream_name,
                external_table=external_table if runtime._is_sql_stream(stream) else None,
            )
        except Exception as exc:
            result.skipped.append(
                SkippedSuggestTarget(
                    target.provider,
                    stream_name,
                    external_table,
                    str(exc)[:200],
                )
            )
            continue

        field_names = [f.name for f in info.fields]
        pk = _pick_primary_key(info.primary_key, field_names)
        label = _pick_label_column(field_names, pk)
        cursor = _pick_cursor_column(field_names)
        class_uri = target_class_uri_for_stream(stream_name, info.display_name)
        group_key = entity_group_key(stream_name)
        if stream_name == "table_records":
            group_key = class_uri.split(":")[-1].lower()
        group_label = _pascal_case(group_key)

        draft = {
            "provider": target.provider,
            "stream_name": stream_name,
            "external_table": info.external_table,
            "primary_key_column": pk,
            "cursor_column": cursor,
            "label_column": label,
            "target_class_uri": class_uri,
            "column_mappings": [
                c.model_dump(mode="json")
                for c in column_mappings_from_fields(field_names, pk=pk)
            ],
            "sync_mode": "incremental",
            "track_deletes": False,
            "sync_direction": "inbound",
            "writeback_mode": "review",
            "max_rows": 10000,
            "poll_interval_minutes": 0,
        }
        confidence: Confidence = (
            "high" if info.primary_key and len(field_names) >= 2 else "medium"
        )
        source_label = f"{target.provider} · {stream_name}"
        suggestion = MappingDraftSuggestion(
            draft=draft,
            entity_group=group_key,
            entity_group_label=group_label,
            confidence=confidence,
            source_label=source_label,
        )
        result.drafts.append(suggestion)
        grouped.setdefault(group_key, []).append(suggestion)

    for group_key, items in sorted(grouped.items()):
        result.groups.append(
            {
                "id": group_key,
                "label": items[0].entity_group_label,
                "draft_count": len(items),
                "drafts": [
                    {
                        "entity_group": s.entity_group,
                        "entity_group_label": s.entity_group_label,
                        "confidence": s.confidence,
                        "source_label": s.source_label,
                        "draft": s.draft,
                    }
                    for s in items
                ],
            }
        )
    return result
