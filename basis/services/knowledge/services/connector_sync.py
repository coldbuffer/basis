"""Bidirectional entity synchronization engine between BOCP connectors and the Evidence Ledger."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any, Literal
import uuid

from basis.services.knowledge.ports.connector import (
    ConnectorRuntime,
    LockedCanonicalConn,
    UnifiedReadResult,
    is_knowledge_store,
)
from basis.services.knowledge.sql import ConnectorSyncPersistence
from basis.services.knowledge.models import (
    ColumnMappingSpec,
    ConnectorSourceConfig,
    OutboxFieldChange,
    OutboxPatchSpec,
    compute_canonical_row_hash,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SourceTableMappingRecord:
    id: str
    workspace_id: str
    source_id: str
    stream_name: str
    external_table: str
    stream_params: dict[str, Any]
    primary_key_column: str
    cursor_column: str | None
    label_column: str
    target_class_uri: str
    column_mappings: list[ColumnMappingSpec]
    sync_mode: Literal["full_refresh", "incremental"] = "incremental"
    track_deletes: bool = False
    checkpoint: dict[str, Any] = field(default_factory=dict)
    sync_direction: Literal["inbound", "bidirectional"] = "inbound"
    writeback_mode: Literal["disabled", "review", "auto"] = "review"
    max_rows: int = 10000
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class InboundSyncStats:
    mapping_id: str
    external_table: str
    fetched_rows: int = 0
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0
    new_cursor_watermark: Any | None = None


class ConnectorLedgerSyncService:
    """Orchestrates inbound stream-to-ledger sync and outbound ledger-to-stream writeback."""

    def __init__(self, knowledge_or_conn: Any, runtime: ConnectorRuntime) -> None:
        self._store = knowledge_or_conn if is_knowledge_store(knowledge_or_conn) else None
        locked = LockedCanonicalConn(knowledge_or_conn)
        self.runtime = runtime
        self._persist = (
            knowledge_or_conn.connector_sync_persistence()
            if self._store is not None
            else ConnectorSyncPersistence(locked)
        )

    # ── Mapping CRUD ─────────────────────────────────────────────────────────

    def create_table_mapping(
        self,
        workspace_id: str,
        *,
        source_id: str,
        stream_name: str,
        external_table: str,
        primary_key_column: str,
        label_column: str,
        target_class_uri: str,
        column_mappings: list[ColumnMappingSpec],
        cursor_column: str | None = None,
        stream_params: dict[str, Any] | None = None,
        sync_mode: Literal["full_refresh", "incremental"] = "incremental",
        track_deletes: bool = False,
        sync_direction: Literal["inbound", "bidirectional"] = "inbound",
        writeback_mode: Literal["disabled", "review", "auto"] = "review",
        max_rows: int = 10000,
        poll_interval_minutes: int = 0,
    ) -> SourceTableMappingRecord:
        mapping_id = f"stm_{uuid.uuid4().hex[:16]}"
        now = _now_iso()
        cols_json = json.dumps(
            [m.model_dump(mode="json", exclude_none=True) for m in column_mappings],
            ensure_ascii=False,
        )
        checkpoint: dict[str, Any] = {}
        if poll_interval_minutes > 0:
            checkpoint["poll_interval_minutes"] = int(poll_interval_minutes)
        checkpoint_json = json.dumps(checkpoint, ensure_ascii=False)
        self._persist.insert_table_mapping(
            mapping_id=mapping_id,
            workspace_id=workspace_id,
            source_id=source_id,
            stream_name=stream_name,
            external_table=external_table,
            stream_params_json=json.dumps(stream_params or {}, ensure_ascii=False),
            primary_key_column=primary_key_column,
            cursor_column=cursor_column,
            label_column=label_column,
            target_class_uri=target_class_uri,
            column_mappings_json=cols_json,
            sync_mode=sync_mode,
            track_deletes=1 if track_deletes else 0,
            checkpoint_json=checkpoint_json,
            sync_direction=sync_direction,
            writeback_mode=writeback_mode,
            max_rows=max_rows,
            created_at=now,
            updated_at=now,
        )
        rec = self.get_table_mapping(workspace_id, mapping_id)
        assert rec is not None
        return rec

    def update_table_mapping(
        self,
        workspace_id: str,
        mapping_id: str,
        *,
        provider: str | None = None,
        stream_name: str,
        external_table: str,
        primary_key_column: str,
        label_column: str,
        target_class_uri: str,
        column_mappings: list[ColumnMappingSpec],
        cursor_column: str | None = None,
        stream_params: dict[str, Any] | None = None,
        sync_mode: Literal["full_refresh", "incremental"] = "incremental",
        track_deletes: bool = False,
        sync_direction: Literal["inbound", "bidirectional"] = "inbound",
        writeback_mode: Literal["disabled", "review", "auto"] = "review",
        max_rows: int = 10000,
        poll_interval_minutes: int = 0,
    ) -> SourceTableMappingRecord:
        existing = self.get_table_mapping(workspace_id, mapping_id)
        if not existing:
            raise LookupError(f"Table mapping '{mapping_id}' not found in workspace '{workspace_id}'")

        if provider is not None:
            cfg = self._get_source_config(workspace_id, existing.source_id)
            merged = cfg.model_copy(update={"provider": provider or cfg.provider})
            now = _now_iso()
            self._persist.update_ingest_source_config(
                workspace_id,
                existing.source_id,
                json.dumps(merged.model_dump(mode="json", exclude_none=True)),
                now,
            )

        now = _now_iso()
        cols_json = json.dumps(
            [m.model_dump(mode="json", exclude_none=True) for m in column_mappings],
            ensure_ascii=False,
        )
        new_checkpoint = dict(existing.checkpoint)
        if poll_interval_minutes > 0:
            new_checkpoint["poll_interval_minutes"] = int(poll_interval_minutes)
        else:
            new_checkpoint.pop("poll_interval_minutes", None)
        checkpoint_json = json.dumps(new_checkpoint, ensure_ascii=False)
        self._persist.update_table_mapping(
            stream_name=stream_name,
            external_table=external_table,
            stream_params_json=json.dumps(stream_params or {}, ensure_ascii=False),
            primary_key_column=primary_key_column,
            cursor_column=cursor_column,
            label_column=label_column,
            target_class_uri=target_class_uri,
            column_mappings_json=cols_json,
            sync_mode=sync_mode,
            track_deletes=1 if track_deletes else 0,
            checkpoint_json=checkpoint_json,
            sync_direction=sync_direction,
            writeback_mode=writeback_mode,
            max_rows=max_rows,
            updated_at=now,
            workspace_id=workspace_id,
            mapping_id=mapping_id,
        )
        rec = self.get_table_mapping(workspace_id, mapping_id)
        assert rec is not None
        return rec

    def delete_table_mapping(self, workspace_id: str, mapping_id: str) -> bool:
        return self._persist.delete_table_mapping(workspace_id, mapping_id) > 0

    def get_mapping_connection_binding(
        self, workspace_id: str, source_id: str
    ) -> ConnectorSourceConfig:
        return self._get_source_config(workspace_id, source_id)

    def get_table_mapping(
        self, workspace_id: str, mapping_id: str
    ) -> SourceTableMappingRecord | None:
        row = self._persist.fetch_table_mapping_row(workspace_id, mapping_id)
        if not row:
            return None
        raw_cols = json.loads(row[10]) if row[10] else []
        return SourceTableMappingRecord(
            id=row[0],
            workspace_id=row[1],
            source_id=row[2],
            stream_name=row[3],
            external_table=row[4],
            stream_params=json.loads(row[5]) if row[5] else {},
            primary_key_column=row[6],
            cursor_column=row[7],
            label_column=row[8],
            target_class_uri=row[9],
            column_mappings=[ColumnMappingSpec.model_validate(c) for c in raw_cols],
            sync_mode=row[11],
            track_deletes=bool(row[12]),
            checkpoint=json.loads(row[13]) if row[13] else {},
            sync_direction=row[14],
            writeback_mode=row[15],
            max_rows=int(row[16]),
            status=row[17],
            created_at=row[18] or "",
            updated_at=row[19] or "",
        )

    def _get_source_config(self, workspace_id: str, source_id: str) -> ConnectorSourceConfig:
        row = self._persist.fetch_ingest_source_row(workspace_id, source_id)
        if not row:
            raise LookupError(f"Ingest source '{source_id}' not found in workspace '{workspace_id}'")
        raw_cfg = json.loads(row[1]) if row[1] else {}
        return ConnectorSourceConfig.model_validate(raw_cfg)

    # ── Inbound Sync: Stream READ → Evidence Ledger ──────────────────────────

    def sync_inbound_mapping(
        self, workspace_id: str, mapping_id: str
    ) -> InboundSyncStats:
        """Pull records from BOCP stream and route via 4-way row_hash diff into the Evidence Ledger."""
        mapping = self.get_table_mapping(workspace_id, mapping_id)
        if not mapping:
            raise LookupError(f"Table mapping '{mapping_id}' not found")

        src_cfg = self._get_source_config(workspace_id, mapping.source_id)
        watermark = (
            mapping.checkpoint.get("cursor_watermark")
            if mapping.sync_mode == "incremental" and not mapping.track_deletes
            else None
        )

        read_res: UnifiedReadResult = self.runtime.read_stream(
            workspace_id,
            src_cfg.provider,
            stream_name=mapping.stream_name,
            external_table=mapping.external_table,
            primary_key_column=mapping.primary_key_column,
            cursor_column=mapping.cursor_column,
            cursor_watermark=watermark,
            stream_params=mapping.stream_params,
            limit=mapping.max_rows,
        )

        stats = InboundSyncStats(
            mapping_id=mapping.id,
            external_table=mapping.external_table,
            fetched_rows=len(read_res.records),
            new_cursor_watermark=read_res.next_cursor_value,
        )

        now = _now_iso()
        seen_pks: set[str] = set()

        # Pre-resolve FK target entities by (external_table, external_pk)
        for row in read_res.records:
            raw_pk = row.get(mapping.primary_key_column)
            if raw_pk is None:
                continue
            ext_pk = str(raw_pk)
            seen_pks.add(ext_pk)

            new_hash = compute_canonical_row_hash(
                row,
                label_column=mapping.label_column,
                column_mappings=mapping.column_mappings,
            )

            existing_ref = self._persist.fetch_external_ref_by_pk(
                workspace_id, mapping.source_id, mapping.external_table, ext_pk
            )

            if existing_ref is None:
                # 1. ADDED: create entity + entity_external_ref + statements + typed_facts
                entity_id = f"ent_{uuid.uuid4().hex[:16]}"
                ref_id = f"eref_{uuid.uuid4().hex[:16]}"
                label_val = str(row.get(mapping.label_column) or ext_pk).strip() or ext_pk

                self._persist.insert_sync_entity(
                    entity_id,
                    workspace_id,
                    label_val,
                    f"Synced from {src_cfg.provider}:{mapping.external_table} ({ext_pk})",
                    now,
                )
                self._persist.insert_external_ref(
                    ref_id=ref_id,
                    workspace_id=workspace_id,
                    entity_id=entity_id,
                    source_id=mapping.source_id,
                    mapping_id=mapping.id,
                    external_table=mapping.external_table,
                    external_pk=ext_pk,
                    row_hash=new_hash,
                    last_synced_at=now,
                )
                self._persist.upsert_entity_column_facts(
                    workspace_id=workspace_id,
                    provider=src_cfg.provider,
                    mapping=mapping,
                    ref_id=ref_id,
                    entity_id=entity_id,
                    ext_pk=ext_pk,
                    row=row,
                    now=now,
                )
                stats.added += 1
            else:
                ref_id, entity_id, old_hash, deleted_at = (
                    existing_ref[0],
                    existing_ref[1],
                    existing_ref[2],
                    existing_ref[3],
                )
                if old_hash == new_hash and deleted_at is None:
                    # 2. UNCHANGED: fast path O(1) skip
                    self._persist.touch_external_ref(ref_id, now)
                    stats.unchanged += 1
                else:
                    # 3. UPDATED (or restored): update canonical_label and supersede changed column facts
                    label_val = (
                        str(row.get(mapping.label_column) or ext_pk).strip() or ext_pk
                    )
                    self._persist.update_entity_label(label_val, entity_id, workspace_id)
                    self._persist.upsert_entity_column_facts(
                        workspace_id=workspace_id,
                        provider=src_cfg.provider,
                        mapping=mapping,
                        ref_id=ref_id,
                        entity_id=entity_id,
                        ext_pk=ext_pk,
                        row=row,
                        now=now,
                    )
                    self._persist.refresh_external_ref_hash(ref_id, new_hash, now)
                    stats.updated += 1

        # 4. DELETED: if track_deletes is enabled on full snapshot, mark missing rows as deleted upstream
        if mapping.track_deletes:
            active_refs = self._persist.list_active_external_refs_for_mapping(workspace_id, mapping.id)
            proposed_by = f"connector:{src_cfg.provider}"
            for r_id, ent_id, r_pk in active_refs:
                if r_pk not in seen_pks:
                    self._persist.mark_external_ref_deleted_upstream(r_id, now)
                    self._persist.invalidate_connector_subject_statements(
                        now, workspace_id, ent_id, proposed_by
                    )
                    self._persist.invalidate_connector_subject_typed_facts(now, workspace_id, ent_id)
                    stats.deleted += 1

        # Update mapping checkpoint_json
        new_checkpoint = dict(mapping.checkpoint)
        if read_res.next_cursor_value is not None:
            new_checkpoint["cursor_watermark"] = str(read_res.next_cursor_value)
        new_checkpoint["last_synced_at"] = now
        self._persist.update_mapping_checkpoint(
            json.dumps(new_checkpoint, ensure_ascii=False),
            now,
            mapping.id,
            workspace_id,
        )
        self._persist.commit()
        return stats

    # ── Outbound Sync: Ledger → Outbox → Review → Stream MUTATE ──────────────

    def get_entity_external_sync_context(
        self,
        workspace_id: str,
        entity_id: str,
    ) -> dict[str, Any] | None:
        """Return external connector provenance and writable column values for an entity, if any."""
        ref_row = self._persist.fetch_external_ref_context_row(workspace_id, entity_id)
        if not ref_row:
            return None
        (
            ref_id,
            source_id,
            mapping_id,
            external_table,
            external_pk,
            last_synced_at,
            deleted_upstream_at,
        ) = ref_row
        mapping = self.get_table_mapping(workspace_id, mapping_id)
        if not mapping:
            return None
        try:
            src_cfg = self._get_source_config(workspace_id, source_id)
            provider = src_cfg.provider
        except LookupError:
            provider = "unknown"

        writable_columns: list[dict[str, Any]] = []
        for col_spec in mapping.column_mappings:
            if not col_spec.writable:
                continue
            pred_uri = col_spec.predicate_uri or f"urn:basis:prop:{col_spec.column}"
            val_row = self._persist.fetch_typed_fact_object_value(
                workspace_id, entity_id, pred_uri
            )
            writable_columns.append(
                {
                    "column": col_spec.column,
                    "surface_phrase": col_spec.surface_phrase,
                    "predicate_uri": pred_uri,
                    "current_value": val_row[0] if val_row else None,
                }
            )
        return {
            "ref_id": ref_id,
            "mapping_id": mapping.id,
            "provider": provider,
            "stream_name": mapping.stream_name,
            "external_table": external_table,
            "external_pk": external_pk,
            "sync_direction": mapping.sync_direction,
            "writeback_mode": mapping.writeback_mode,
            "last_synced_at": last_synced_at,
            "deleted_upstream_at": deleted_upstream_at,
            "writable_columns": writable_columns,
        }

    def propose_entity_writeback(
        self,
        workspace_id: str,
        *,
        entity_id: str,
        field_updates: dict[str, Any],
        created_by: str | None = None,
        statement_id: str | None = None,
        typed_fact_id: str | None = None,
    ) -> dict[str, Any]:
        """Stage an outbound mutation in `entity_sync_outbox` and open a `review_items` gate if required."""
        ref_row = self._persist.fetch_active_external_ref_for_writeback(workspace_id, entity_id)
        if not ref_row:
            raise LookupError(
                f"Entity '{entity_id}' has no active external connector reference"
            )
        ref_id, source_id, mapping_id, external_table, external_pk, _ = ref_row

        mapping = self.get_table_mapping(workspace_id, mapping_id)
        if not mapping:
            raise LookupError(f"Mapping '{mapping_id}' not found")
        if mapping.sync_direction != "bidirectional" or mapping.writeback_mode == "disabled":
            raise PermissionError(
                f"Writeback is disabled on mapping '{mapping.id}' ({mapping.external_table})"
            )

        src_cfg = self._get_source_config(workspace_id, source_id)
        writable_cols = {
            c.column: c for c in mapping.column_mappings if c.writable
        }

        changes: dict[str, OutboxFieldChange] = {}
        for col_name, new_val in field_updates.items():
            col_spec = writable_cols.get(col_name)
            if not col_spec:
                raise PermissionError(
                    f"Column '{col_name}' is not marked writable on mapping '{mapping.id}'"
                )
            pred_uri = col_spec.predicate_uri or f"urn:basis:prop:{col_name}"
            old_row = self._persist.fetch_typed_fact_writeback_baseline(
                workspace_id, entity_id, pred_uri
            )
            old_val = old_row[0] if old_row else None
            old_stmt = old_row[1] if old_row else None
            changes[col_name] = OutboxFieldChange(
                old=old_val,
                new=new_val,
                predicate_uri=pred_uri,
                statement_id=statement_id or old_stmt,
            )

        patch = OutboxPatchSpec(
            provider=src_cfg.provider,
            stream_name=mapping.stream_name,
            mutation_operation="update",
            external_table=external_table,
            primary_key_column=mapping.primary_key_column,
            external_pk=external_pk,
            stream_params=mapping.stream_params,
            changes=changes,
        )

        outbox_id = f"out_{uuid.uuid4().hex[:16]}"
        now = _now_iso()
        initial_status = (
            "queued" if mapping.writeback_mode == "auto" else "pending_review"
        )
        review_item_id: str | None = None

        if initial_status == "pending_review":
            review_item_id = f"rev_{uuid.uuid4().hex[:16]}"
            review_payload = {
                "outbox_id": outbox_id,
                "entity_id": entity_id,
                "provider": src_cfg.provider,
                "external_table": external_table,
                "external_pk": external_pk,
                "changes": {
                    k: v.model_dump(mode="json") for k, v in changes.items()
                },
            }
            self._persist.insert_connector_writeback_review(
                review_item_id=review_item_id,
                workspace_id=workspace_id,
                outbox_id=outbox_id,
                payload_json=json.dumps(review_payload, ensure_ascii=False),
                created_at=now,
            )

        self._persist.insert_sync_outbox_item(
            outbox_id=outbox_id,
            workspace_id=workspace_id,
            entity_id=entity_id,
            external_ref_id=ref_id,
            statement_id=statement_id,
            typed_fact_id=typed_fact_id,
            patch_json=json.dumps(patch.model_dump(mode="json"), ensure_ascii=False),
            status=initial_status,
            review_item_id=review_item_id,
            created_by=created_by,
            created_at=now,
        )
        self._persist.commit()

        if mapping.writeback_mode == "auto":
            return self.execute_outbox_item(workspace_id, outbox_id)

        return self.get_outbox_item(workspace_id, outbox_id)

    def approve_and_execute_outbox(
        self,
        workspace_id: str,
        outbox_id: str,
        *,
        actor_id: str | None = None,
        rationale: str = "Approved connector writeback",
    ) -> dict[str, Any]:
        """Resolve the governance review item, record an agent_decision, and execute the remote mutation."""
        item = self.get_outbox_item(workspace_id, outbox_id)
        now = _now_iso()
        decision_id = f"dec_{uuid.uuid4().hex[:16]}"
        review_item_id = item.get("review_item_id")

        if review_item_id:
            self._persist.approve_writeback_review_item(
                resolved_at=now,
                resolved_by=actor_id,
                rationale=rationale,
                review_item_id=review_item_id,
                workspace_id=workspace_id,
            )

        self._persist.insert_writeback_agent_decision(
            decision_id=decision_id,
            workspace_id=workspace_id,
            review_item_id=review_item_id,
            rationale=rationale,
            trace_json=json.dumps({"outbox_id": outbox_id, "actor_id": actor_id}),
            created_at=now,
            applied_at=now,
        )
        self._persist.queue_outbox_after_approval(decision_id, outbox_id, workspace_id)
        self._persist.commit()
        return self.execute_outbox_item(workspace_id, outbox_id)

    def execute_outbox_item(self, workspace_id: str, outbox_id: str) -> dict[str, Any]:
        """Execute a queued outbox item against the upstream connector and update ledger + row_hash."""
        row = self._persist.fetch_outbox_execution_row(workspace_id, outbox_id)
        if not row:
            raise LookupError(f"Outbox item '{outbox_id}' not found")

        (
            entity_id,
            ref_id,
            patch_json,
            status,
            source_id,
            mapping_id,
            external_table,
            external_pk,
        ) = row
        if status not in ("queued", "failed"):
            raise ValueError(
                f"Outbox item '{outbox_id}' cannot be executed from status '{status}'"
            )

        patch = OutboxPatchSpec.model_validate(json.loads(patch_json))
        mapping = self.get_table_mapping(workspace_id, mapping_id)
        assert mapping is not None
        src_cfg = self._get_source_config(workspace_id, source_id)

        raw_changes = {col: chg.new for col, chg in patch.changes.items()}
        now = _now_iso()

        try:
            remote_res = self.runtime.mutate_stream(
                workspace_id,
                src_cfg.provider,
                stream_name=patch.stream_name,
                external_table=external_table,
                operation=patch.mutation_operation,
                primary_key_column=patch.primary_key_column,
                external_pk=external_pk,
                changes=raw_changes,
                stream_params=patch.stream_params,
            )

            # Update local ledger facts for the mutated columns
            merged_row = self._build_current_entity_row(
                workspace_id, entity_id, mapping, overrides=raw_changes
            )
            if isinstance(remote_res, dict) and remote_res:
                # If remote returned updated fields, merge any mapped columns
                remote_fields = (
                    remote_res.get("fields")
                    if isinstance(remote_res.get("fields"), dict)
                    else remote_res
                )
                for col_spec in mapping.column_mappings:
                    if col_spec.column in remote_fields:
                        merged_row[col_spec.column] = remote_fields[col_spec.column]

            self._persist.upsert_entity_column_facts(
                workspace_id=workspace_id,
                provider=src_cfg.provider,
                mapping=mapping,
                ref_id=ref_id,
                entity_id=entity_id,
                ext_pk=external_pk,
                row=merged_row,
                now=now,
            )

            # Anti-echo loop: recompute canonical row_hash and update entity_external_refs
            new_hash = compute_canonical_row_hash(
                merged_row,
                label_column=mapping.label_column,
                column_mappings=mapping.column_mappings,
            )
            self._persist.update_external_ref_row_hash(ref_id, new_hash, now)
            self._persist.mark_outbox_synced(now, outbox_id, workspace_id)
            self._persist.commit()
        except Exception as exc:
            self._persist.mark_outbox_writeback_failed(
                json.dumps({"message": str(exc)}), outbox_id, workspace_id
            )
            self._persist.commit()
            raise

        return self.get_outbox_item(workspace_id, outbox_id)

    def _build_current_entity_row(
        self,
        workspace_id: str,
        entity_id: str,
        mapping: SourceTableMappingRecord,
        *,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ent_row = self._persist.fetch_entity_canonical_label(entity_id, workspace_id)
        row_dict: dict[str, Any] = {
            mapping.label_column: ent_row[0] if ent_row else ""
        }
        for col_spec in mapping.column_mappings:
            pred_uri = col_spec.predicate_uri or f"urn:basis:prop:{col_spec.column}"
            f_row = self._persist.fetch_typed_fact_object_value(
                workspace_id, entity_id, pred_uri
            )
            row_dict[col_spec.column] = f_row[0] if f_row else None
        if overrides:
            row_dict.update(overrides)
        return row_dict

    def get_outbox_item(self, workspace_id: str, outbox_id: str) -> dict[str, Any]:
        row = self._persist.fetch_outbox_row(workspace_id, outbox_id)
        if not row:
            raise LookupError(f"Outbox item '{outbox_id}' not found")
        return {
            "id": row[0],
            "workspace_id": row[1],
            "entity_id": row[2],
            "external_ref_id": row[3],
            "statement_id": row[4],
            "typed_fact_id": row[5],
            "action_kind": row[6],
            "patch": json.loads(row[7]) if row[7] else {},
            "status": row[8],
            "review_item_id": row[9],
            "decision_id": row[10],
            "job_id": row[11],
            "error_code": row[12],
            "error_detail": json.loads(row[13]) if row[13] else None,
            "created_by": row[14],
            "created_at": row[15],
            "synced_at": row[16],
        }
