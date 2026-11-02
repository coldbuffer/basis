"""BOCP table mappings, ledger sync, and outbox — canonical DB SQL."""

from __future__ import annotations

import json
import uuid
from typing import Any

from basis.services.knowledge.ports.connector import LockedCanonicalConn
from basis.services.knowledge.models import StructuredImportProvenance


def _in_clause(ids: list[str]) -> str:
    return ",".join("?" * len(ids))


def purge_entity_connector_sync_data(conn: Any, workspace_id: str, entity_id: str) -> None:
    """Remove outbox + external refs for an entity (no commit; caller owns transaction)."""
    outbox_ids = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM entity_sync_outbox WHERE workspace_id = ? AND entity_id = ?",
            (workspace_id, entity_id),
        ).fetchall()
    ]
    if outbox_ids:
        conn.execute(
            f"""
            DELETE FROM review_items
            WHERE workspace_id = ? AND subject_type = 'entity_sync_outbox'
              AND subject_id IN ({_in_clause(outbox_ids)})
            """,
            (workspace_id, *outbox_ids),
        )
    conn.execute(
        "DELETE FROM entity_sync_outbox WHERE workspace_id = ? AND entity_id = ?",
        (workspace_id, entity_id),
    )
    conn.execute(
        "DELETE FROM entity_external_refs WHERE workspace_id = ? AND entity_id = ?",
        (workspace_id, entity_id),
    )


class ConnectorSyncPersistence:
    def __init__(self, db: LockedCanonicalConn) -> None:
        self._db = db

    def execute(self, sql: str, params: Any = ()) -> Any:
        return self._db.execute(sql, params)

    def commit(self) -> None:
        self._db.commit()

    def insert_table_mapping(
        self,
        *,
        mapping_id: str,
        workspace_id: str,
        source_id: str,
        stream_name: str,
        external_table: str,
        stream_params_json: str,
        primary_key_column: str,
        cursor_column: str | None,
        label_column: str,
        target_class_uri: str,
        column_mappings_json: str,
        sync_mode: str,
        track_deletes: int,
        checkpoint_json: str,
        sync_direction: str,
        writeback_mode: str,
        max_rows: int,
        created_at: str,
        updated_at: str,
    ) -> None:
        self._db.execute(
            """
            INSERT INTO source_table_mappings (
                id, workspace_id, source_id, stream_name, external_table,
                stream_params_json, primary_key_column, cursor_column,
                label_column, target_class_uri, column_mappings_json,
                sync_mode, track_deletes, checkpoint_json,
                sync_direction, writeback_mode, max_rows, status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                mapping_id,
                workspace_id,
                source_id,
                stream_name,
                external_table,
                stream_params_json,
                primary_key_column,
                cursor_column,
                label_column,
                target_class_uri,
                column_mappings_json,
                sync_mode,
                track_deletes,
                checkpoint_json,
                sync_direction,
                writeback_mode,
                max_rows,
                created_at,
                updated_at,
            ),
        )
        self._db.commit()

    def update_ingest_source_config(
        self,
        workspace_id: str,
        source_id: str,
        config_json: str,
        updated_at: str,
    ) -> None:
        self._db.execute(
            """
            UPDATE ingest_sources
            SET config_json = ?, updated_at = ?
            WHERE workspace_id = ? AND id = ? AND deleted_at IS NULL
            """,
            (config_json, updated_at, workspace_id, source_id),
        )

    def update_table_mapping(
        self,
        *,
        stream_name: str,
        external_table: str,
        stream_params_json: str,
        primary_key_column: str,
        cursor_column: str | None,
        label_column: str,
        target_class_uri: str,
        column_mappings_json: str,
        sync_mode: str,
        track_deletes: int,
        checkpoint_json: str,
        sync_direction: str,
        writeback_mode: str,
        max_rows: int,
        updated_at: str,
        workspace_id: str,
        mapping_id: str,
    ) -> None:
        self._db.execute(
            """
            UPDATE source_table_mappings SET
                stream_name = ?,
                external_table = ?,
                stream_params_json = ?,
                primary_key_column = ?,
                cursor_column = ?,
                label_column = ?,
                target_class_uri = ?,
                column_mappings_json = ?,
                sync_mode = ?,
                track_deletes = ?,
                checkpoint_json = ?,
                sync_direction = ?,
                writeback_mode = ?,
                max_rows = ?,
                updated_at = ?
            WHERE workspace_id = ? AND id = ?
            """,
            (
                stream_name,
                external_table,
                stream_params_json,
                primary_key_column,
                cursor_column,
                label_column,
                target_class_uri,
                column_mappings_json,
                sync_mode,
                track_deletes,
                checkpoint_json,
                sync_direction,
                writeback_mode,
                max_rows,
                updated_at,
                workspace_id,
                mapping_id,
            ),
        )
        self._db.commit()

    def delete_table_mapping(self, workspace_id: str, mapping_id: str) -> int:
        cur = self._db.execute(
            "DELETE FROM source_table_mappings WHERE workspace_id = ? AND id = ?",
            (workspace_id, mapping_id),
        )
        self._db.commit()
        return int(cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0)

    def fetch_table_mapping_row(self, workspace_id: str, mapping_id: str) -> Any:
        return self._db.execute(
            """
            SELECT id, workspace_id, source_id, stream_name, external_table,
                   stream_params_json, primary_key_column, cursor_column,
                   label_column, target_class_uri, column_mappings_json,
                   sync_mode, track_deletes, checkpoint_json,
                   sync_direction, writeback_mode, max_rows, status,
                   created_at, updated_at
            FROM source_table_mappings
            WHERE workspace_id = ? AND id = ?
            """,
            (workspace_id, mapping_id),
        ).fetchone()

    def fetch_ingest_source_row(self, workspace_id: str, source_id: str) -> Any:
        return self._db.execute(
            "SELECT kind, config_json FROM ingest_sources WHERE workspace_id = ? AND id = ? AND deleted_at IS NULL",
            (workspace_id, source_id),
        ).fetchone()

    def fetch_external_ref_by_pk(
        self,
        workspace_id: str,
        source_id: str,
        external_table: str,
        external_pk: str,
    ) -> Any:
        return self.execute(
            """
            SELECT id, entity_id, row_hash, deleted_upstream_at
            FROM entity_external_refs
            WHERE workspace_id = ? AND source_id = ? AND external_table = ? AND external_pk = ?
            """,
            (workspace_id, source_id, external_table, external_pk),
        ).fetchone()

    def insert_sync_entity(
        self,
        entity_id: str,
        workspace_id: str,
        label: str,
        description: str,
        created_at: str,
    ) -> None:
        self.execute(
            """
            INSERT INTO entities (
                id, workspace_id, canonical_label, description, entity_kind, created_at, invalidated_at
            ) VALUES (?, ?, ?, ?, 'named', ?, NULL)
            """,
            (entity_id, workspace_id, label, description, created_at),
        )

    def insert_external_ref(
        self,
        *,
        ref_id: str,
        workspace_id: str,
        entity_id: str,
        source_id: str,
        mapping_id: str,
        external_table: str,
        external_pk: str,
        row_hash: str,
        last_synced_at: str,
    ) -> None:
        self.execute(
            """
            INSERT INTO entity_external_refs (
                id, workspace_id, entity_id, source_id, mapping_id,
                external_table, external_pk, row_hash, last_synced_at, deleted_upstream_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                ref_id,
                workspace_id,
                entity_id,
                source_id,
                mapping_id,
                external_table,
                external_pk,
                row_hash,
                last_synced_at,
            ),
        )

    def touch_external_ref(self, ref_id: str, last_synced_at: str) -> None:
        self.execute(
            "UPDATE entity_external_refs SET last_synced_at = ? WHERE id = ?",
            (last_synced_at, ref_id),
        )

    def update_entity_label(self, label: str, entity_id: str, workspace_id: str) -> None:
        self.execute(
            "UPDATE entities SET canonical_label = ?, invalidated_at = NULL WHERE id = ? AND workspace_id = ?",
            (label, entity_id, workspace_id),
        )

    def refresh_external_ref_hash(
        self,
        ref_id: str,
        row_hash: str,
        last_synced_at: str,
    ) -> None:
        self.execute(
            """
            UPDATE entity_external_refs
            SET row_hash = ?, last_synced_at = ?, deleted_upstream_at = NULL
            WHERE id = ?
            """,
            (row_hash, last_synced_at, ref_id),
        )

    def list_active_external_refs_for_mapping(self, workspace_id: str, mapping_id: str) -> list[Any]:
        return self.execute(
            """
            SELECT id, entity_id, external_pk
            FROM entity_external_refs
            WHERE workspace_id = ? AND mapping_id = ? AND deleted_upstream_at IS NULL
            """,
            (workspace_id, mapping_id),
        ).fetchall()

    def mark_external_ref_deleted_upstream(self, ref_id: str, deleted_at: str) -> None:
        self.execute(
            "UPDATE entity_external_refs SET deleted_upstream_at = ? WHERE id = ?",
            (deleted_at, ref_id),
        )

    def invalidate_connector_subject_statements(
        self,
        invalidated_at: str,
        workspace_id: str,
        entity_id: str,
        proposed_by: str,
    ) -> None:
        self.execute(
            """
            UPDATE statements
            SET status = 'invalidated', invalidated_at = ?
            WHERE workspace_id = ? AND subject_id = ? AND proposed_by = ? AND invalidated_at IS NULL
            """,
            (invalidated_at, workspace_id, entity_id, proposed_by),
        )

    def invalidate_connector_subject_typed_facts(
        self,
        invalidated_at: str,
        workspace_id: str,
        entity_id: str,
    ) -> None:
        self.execute(
            """
            UPDATE typed_facts
            SET invalidated_at = ?
            WHERE workspace_id = ? AND subject_id = ? AND import_provenance_json IS NOT NULL AND invalidated_at IS NULL
            """,
            (invalidated_at, workspace_id, entity_id),
        )

    def update_mapping_checkpoint(
        self,
        checkpoint_json: str,
        updated_at: str,
        mapping_id: str,
        workspace_id: str,
    ) -> None:
        self.execute(
            """
            UPDATE source_table_mappings
            SET checkpoint_json = ?, updated_at = ?
            WHERE id = ? AND workspace_id = ?
            """,
            (checkpoint_json, updated_at, mapping_id, workspace_id),
        )

    def fetch_outbox_row(self, workspace_id: str, outbox_id: str) -> Any:
        return self.execute(
            """
            SELECT id, workspace_id, entity_id, external_ref_id, statement_id, typed_fact_id,
                   action_kind, patch_json, status, review_item_id, decision_id,
                   job_id, error_code, error_detail_json, created_by, created_at, synced_at
            FROM entity_sync_outbox
            WHERE workspace_id = ? AND id = ?
            """,
            (workspace_id, outbox_id),
        ).fetchone()

    def fetch_outbox_execution_row(self, workspace_id: str, outbox_id: str) -> Any:
        return self.execute(
            """
            SELECT o.entity_id, o.external_ref_id, o.patch_json, o.status,
                   r.source_id, r.mapping_id, r.external_table, r.external_pk
            FROM entity_sync_outbox o
            JOIN entity_external_refs r ON r.id = o.external_ref_id
            WHERE o.workspace_id = ? AND o.id = ?
            """,
            (workspace_id, outbox_id),
        ).fetchone()

    def fetch_fk_entity_id(
        self, workspace_id: str, external_table: str, external_pk: str
    ) -> Any:
        return self.execute(
            """
            SELECT entity_id FROM entity_external_refs
            WHERE workspace_id = ? AND external_table = ? AND external_pk = ?
            LIMIT 1
            """,
            (workspace_id, external_table, external_pk),
        ).fetchone()

    def list_active_typed_facts_for_predicate(
        self, workspace_id: str, entity_id: str, predicate_uri: str
    ) -> list[Any]:
        return self.execute(
            """
            SELECT id, object_entity_id, object_value, from_statement_id, import_provenance_json
            FROM typed_facts
            WHERE workspace_id = ? AND subject_id = ? AND predicate_uri = ? AND invalidated_at IS NULL
            """,
            (workspace_id, entity_id, predicate_uri),
        ).fetchall()

    def invalidate_typed_fact_by_id(self, fact_id: str, invalidated_at: str) -> None:
        self.execute(
            "UPDATE typed_facts SET invalidated_at = ? WHERE id = ?",
            (invalidated_at, fact_id),
        )

    def invalidate_statement_by_id(self, statement_id: str, invalidated_at: str) -> None:
        self.execute(
            "UPDATE statements SET status = 'invalidated', invalidated_at = ? WHERE id = ?",
            (invalidated_at, statement_id),
        )

    def supersede_statement_by_id(self, statement_id: str, invalidated_at: str) -> None:
        self.execute(
            "UPDATE statements SET status = 'superseded', invalidated_at = ? WHERE id = ?",
            (invalidated_at, statement_id),
        )

    def insert_connector_statement(
        self,
        *,
        statement_id: str,
        workspace_id: str,
        entity_id: str,
        surface_phrase: str,
        object_entity_id: str | None,
        object_value: str | None,
        object_datatype: str | None,
        proposed_by: str,
        recorded_at: str,
        supersedes_id: str | None,
    ) -> None:
        self.execute(
            """
            INSERT INTO statements (
                id, workspace_id, subject_id, surface_phrase, object_entity_id, object_value,
                object_datatype, confidence, status, proposed_by, recorded_at,
                invalidated_at, supersedes_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1.0, 'confirmed', ?, ?, NULL, ?)
            """,
            (
                statement_id,
                workspace_id,
                entity_id,
                surface_phrase,
                object_entity_id,
                object_value,
                object_datatype,
                proposed_by,
                recorded_at,
                supersedes_id,
            ),
        )

    def insert_connector_typed_fact(
        self,
        *,
        fact_id: str,
        workspace_id: str,
        entity_id: str,
        predicate_uri: str,
        object_entity_id: str | None,
        object_value: str | None,
        object_datatype: str | None,
        from_statement_id: str,
        import_provenance_json: str,
        recorded_at: str,
        supersedes_id: str | None,
    ) -> None:
        self.execute(
            """
            INSERT INTO typed_facts (
                id, workspace_id, subject_id, predicate_uri,
                object_entity_id, object_value, object_datatype,
                from_statement_id, import_provenance_json, confidence,
                recorded_at, invalidated_at, supersedes_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0, ?, NULL, ?)
            """,
            (
                fact_id,
                workspace_id,
                entity_id,
                predicate_uri,
                object_entity_id,
                object_value,
                object_datatype,
                from_statement_id,
                import_provenance_json,
                recorded_at,
                supersedes_id,
            ),
        )

    def upsert_entity_column_facts(
        self,
        *,
        workspace_id: str,
        provider: str,
        mapping: Any,
        ref_id: str,
        entity_id: str,
        ext_pk: str,
        row: dict[str, Any],
        now: str,
    ) -> None:
        proposed_by = f"connector:{provider}"
        for col_spec in mapping.column_mappings:
            raw_val = row.get(col_spec.column)
            str_val = None if raw_val is None else str(raw_val)
            pred_uri = col_spec.predicate_uri or f"urn:basis:prop:{col_spec.column}"

            obj_entity_id: str | None = None
            obj_value: str | None = str_val
            if col_spec.kind == "relation" and col_spec.fk_target_table and str_val:
                fk_row = self.fetch_fk_entity_id(workspace_id, col_spec.fk_target_table, str_val)
                if fk_row:
                    obj_entity_id = fk_row[0]
                    obj_value = None

            existing_facts = self.list_active_typed_facts_for_predicate(
                workspace_id, entity_id, pred_uri
            )
            matched_fact = None
            for fact_row in existing_facts:
                if not fact_row[4]:
                    continue
                try:
                    prov_data = json.loads(fact_row[4])
                    if (
                        prov_data.get("external_ref_id") == ref_id
                        and prov_data.get("column") == col_spec.column
                    ):
                        matched_fact = fact_row
                        break
                except Exception:
                    continue

            if obj_entity_id is None and obj_value is None:
                if matched_fact:
                    self.invalidate_typed_fact_by_id(matched_fact[0], now)
                    if matched_fact[3]:
                        self.invalidate_statement_by_id(matched_fact[3], now)
                continue

            if matched_fact:
                _old_fact_id, old_obj_ent, old_obj_val, _old_stmt_id, _ = matched_fact
                if old_obj_ent == obj_entity_id and old_obj_val == obj_value:
                    continue

            new_stmt_id = f"stmt_{uuid.uuid4().hex[:16]}"
            new_fact_id = f"tf_{uuid.uuid4().hex[:16]}"

            if matched_fact:
                old_fact_id, _, _, old_stmt_id, _ = matched_fact
                self.invalidate_typed_fact_by_id(old_fact_id, now)
                if old_stmt_id:
                    self.supersede_statement_by_id(old_stmt_id, now)
            else:
                old_fact_id = None
                old_stmt_id = None

            self.insert_connector_statement(
                statement_id=new_stmt_id,
                workspace_id=workspace_id,
                entity_id=entity_id,
                surface_phrase=col_spec.surface_phrase,
                object_entity_id=obj_entity_id,
                object_value=obj_value,
                object_datatype=col_spec.datatype if obj_value is not None else None,
                proposed_by=proposed_by,
                recorded_at=now,
                supersedes_id=old_stmt_id,
            )
            prov = StructuredImportProvenance(
                provider=provider,
                stream=mapping.stream_name,
                source_id=mapping.source_id,
                mapping_id=mapping.id,
                external_ref_id=ref_id,
                external_table=mapping.external_table,
                external_pk=ext_pk,
                column=col_spec.column,
            )
            self.insert_connector_typed_fact(
                fact_id=new_fact_id,
                workspace_id=workspace_id,
                entity_id=entity_id,
                predicate_uri=pred_uri,
                object_entity_id=obj_entity_id,
                object_value=obj_value,
                object_datatype=col_spec.datatype if obj_value is not None else None,
                from_statement_id=new_stmt_id,
                import_provenance_json=json.dumps(prov.model_dump(mode="json"), ensure_ascii=False),
                recorded_at=now,
                supersedes_id=old_fact_id,
            )

    def fetch_external_ref_context_row(self, workspace_id: str, entity_id: str) -> Any:
        return self.execute(
            """
            SELECT id, source_id, mapping_id, external_table, external_pk, last_synced_at, deleted_upstream_at
            FROM entity_external_refs
            WHERE workspace_id = ? AND entity_id = ?
            ORDER BY last_synced_at DESC
            LIMIT 1
            """,
            (workspace_id, entity_id),
        ).fetchone()

    def fetch_typed_fact_object_value(
        self, workspace_id: str, entity_id: str, predicate_uri: str
    ) -> Any:
        return self.execute(
            """
            SELECT object_value
            FROM typed_facts
            WHERE workspace_id = ? AND subject_id = ? AND predicate_uri = ? AND invalidated_at IS NULL
            ORDER BY recorded_at DESC
            LIMIT 1
            """,
            (workspace_id, entity_id, predicate_uri),
        ).fetchone()

    def fetch_active_external_ref_for_writeback(self, workspace_id: str, entity_id: str) -> Any:
        return self.execute(
            """
            SELECT id, source_id, mapping_id, external_table, external_pk, row_hash
            FROM entity_external_refs
            WHERE workspace_id = ? AND entity_id = ? AND deleted_upstream_at IS NULL
            LIMIT 1
            """,
            (workspace_id, entity_id),
        ).fetchone()

    def fetch_typed_fact_writeback_baseline(
        self, workspace_id: str, entity_id: str, predicate_uri: str
    ) -> Any:
        return self.execute(
            """
            SELECT object_value, from_statement_id
            FROM typed_facts
            WHERE workspace_id = ? AND subject_id = ? AND predicate_uri = ? AND invalidated_at IS NULL
            ORDER BY recorded_at DESC
            LIMIT 1
            """,
            (workspace_id, entity_id, predicate_uri),
        ).fetchone()

    def insert_connector_writeback_review(
        self,
        *,
        review_item_id: str,
        workspace_id: str,
        outbox_id: str,
        payload_json: str,
        created_at: str,
    ) -> None:
        self.execute(
            """
            INSERT INTO review_items (
                id, workspace_id, kind, subject_type, subject_id, status,
                priority, payload_json, version, created_at
            ) VALUES (?, ?, 'connector_writeback', 'entity_sync_outbox', ?, 'open', 10, ?, 1, ?)
            """,
            (review_item_id, workspace_id, outbox_id, payload_json, created_at),
        )

    def insert_sync_outbox_item(
        self,
        *,
        outbox_id: str,
        workspace_id: str,
        entity_id: str,
        external_ref_id: str,
        statement_id: str | None,
        typed_fact_id: str | None,
        patch_json: str,
        status: str,
        review_item_id: str | None,
        created_by: str | None,
        created_at: str,
    ) -> None:
        self.execute(
            """
            INSERT INTO entity_sync_outbox (
                id, workspace_id, entity_id, external_ref_id, statement_id, typed_fact_id,
                action_kind, patch_json, status, review_item_id, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'update_fields', ?, ?, ?, ?, ?)
            """,
            (
                outbox_id,
                workspace_id,
                entity_id,
                external_ref_id,
                statement_id,
                typed_fact_id,
                patch_json,
                status,
                review_item_id,
                created_by,
                created_at,
            ),
        )

    def approve_writeback_review_item(
        self,
        *,
        resolved_at: str,
        resolved_by: str | None,
        rationale: str,
        review_item_id: str,
        workspace_id: str,
    ) -> None:
        self.execute(
            """
            UPDATE review_items
            SET status = 'approved', resolved_at = ?, resolved_by = ?, rationale = ?
            WHERE id = ? AND workspace_id = ?
            """,
            (resolved_at, resolved_by, rationale, review_item_id, workspace_id),
        )

    def insert_writeback_agent_decision(
        self,
        *,
        decision_id: str,
        workspace_id: str,
        review_item_id: str | None,
        rationale: str,
        trace_json: str,
        created_at: str,
        applied_at: str,
    ) -> None:
        self.execute(
            """
            INSERT INTO agent_decisions (
                id, workspace_id, review_item_id, action, status, confidence,
                rationale, trace_json, created_at, applied_at
            ) VALUES (?, ?, ?, 'approve_connector_writeback', 'applied', 1.0, ?, ?, ?, ?)
            """,
            (
                decision_id,
                workspace_id,
                review_item_id,
                rationale,
                trace_json,
                created_at,
                applied_at,
            ),
        )

    def queue_outbox_after_approval(
        self, decision_id: str, outbox_id: str, workspace_id: str
    ) -> None:
        self.execute(
            """
            UPDATE entity_sync_outbox
            SET status = 'queued', decision_id = ?
            WHERE id = ? AND workspace_id = ?
            """,
            (decision_id, outbox_id, workspace_id),
        )

    def update_external_ref_row_hash(
        self, ref_id: str, row_hash: str, last_synced_at: str
    ) -> None:
        self.execute(
            """
            UPDATE entity_external_refs
            SET row_hash = ?, last_synced_at = ?
            WHERE id = ?
            """,
            (row_hash, last_synced_at, ref_id),
        )

    def mark_outbox_synced(self, synced_at: str, outbox_id: str, workspace_id: str) -> None:
        self.execute(
            """
            UPDATE entity_sync_outbox
            SET status = 'synced', synced_at = ?, error_code = NULL, error_detail_json = NULL
            WHERE id = ? AND workspace_id = ?
            """,
            (synced_at, outbox_id, workspace_id),
        )

    def mark_outbox_writeback_failed(
        self, error_detail_json: str, outbox_id: str, workspace_id: str
    ) -> None:
        self.execute(
            """
            UPDATE entity_sync_outbox
            SET status = 'failed', error_code = 'writeback_failed', error_detail_json = ?
            WHERE id = ? AND workspace_id = ?
            """,
            (error_detail_json, outbox_id, workspace_id),
        )

    def fetch_entity_canonical_label(self, entity_id: str, workspace_id: str) -> Any:
        return self.execute(
            "SELECT canonical_label FROM entities WHERE id = ? AND workspace_id = ?",
            (entity_id, workspace_id),
        ).fetchone()

    def list_mapping_ids(self, workspace_id: str, *, limit: int | None = None) -> list[str]:
        if limit is not None:
            rows = self.execute(
                """
                SELECT id FROM source_table_mappings
                WHERE workspace_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (workspace_id, limit),
            ).fetchall()
        else:
            rows = self.execute(
                """
                SELECT id FROM source_table_mappings
                WHERE workspace_id = ?
                ORDER BY created_at DESC
                """,
                (workspace_id,),
            ).fetchall()
        return [str(row[0]) for row in rows]

    def list_outbox_ids(
        self, workspace_id: str, *, status: str | None = None, limit: int = 50
    ) -> list[str]:
        if status:
            rows = self.execute(
                """
                SELECT id FROM entity_sync_outbox
                WHERE workspace_id = ? AND status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (workspace_id, status, limit),
            ).fetchall()
        else:
            rows = self.execute(
                """
                SELECT id FROM entity_sync_outbox
                WHERE workspace_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (workspace_id, limit),
            ).fetchall()
        return [str(row[0]) for row in rows]

    def reject_outbox(self, workspace_id: str, outbox_id: str) -> None:
        self.execute(
            """
            UPDATE entity_sync_outbox
            SET status = 'rejected'
            WHERE id = ? AND workspace_id = ?
            """,
            (outbox_id, workspace_id),
        )
        self.commit()

    def list_active_inbound_mapping_pairs(self) -> list[tuple[str, str]]:
        """(workspace_id, mapping_id) for scheduler — active inbound/bidirectional mappings."""
        rows = self.execute(
            """
            SELECT workspace_id, id
            FROM source_table_mappings
            WHERE status = 'active'
              AND sync_direction IN ('inbound', 'bidirectional')
            ORDER BY workspace_id, created_at ASC
            """,
        ).fetchall()
        return [(str(row[0]), str(row[1])) for row in rows]
