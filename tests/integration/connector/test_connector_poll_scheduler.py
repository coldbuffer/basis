"""BOCP table mapping poll schedule."""

from datetime import datetime, timezone

from basis.services.knowledge.schedulers.connector_mapping_poll_due import (
    is_connector_mapping_poll_due,
    poll_interval_minutes_for_mapping,
)
from basis.services.knowledge.services.connector_sync import SourceTableMappingRecord


def _mapping(**overrides: object) -> SourceTableMappingRecord:
    base = {
        "id": "stm_test",
        "workspace_id": "kb1",
        "source_id": "src1",
        "stream_name": "records",
        "external_table": "t",
        "stream_params": {},
        "primary_key_column": "id",
        "cursor_column": None,
        "label_column": "name",
        "target_class_uri": "urn:test",
        "column_mappings": [],
        "checkpoint": {},
    }
    base.update(overrides)
    return SourceTableMappingRecord(**base)  # type: ignore[arg-type]


def test_poll_interval_from_checkpoint() -> None:
    rec = _mapping(checkpoint={"poll_interval_minutes": 15})
    assert poll_interval_minutes_for_mapping(rec) == 15


def test_mapping_poll_due_first_run() -> None:
    rec = _mapping(checkpoint={"poll_interval_minutes": 5})
    assert is_connector_mapping_poll_due(rec, datetime.now(timezone.utc)) is True


def test_mapping_poll_not_due_when_manual() -> None:
    rec = _mapping(checkpoint={})
    assert is_connector_mapping_poll_due(rec, datetime.now(timezone.utc)) is False


def test_mapping_poll_respects_last_synced_at() -> None:
    now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    rec = _mapping(
        checkpoint={
            "poll_interval_minutes": 10,
            "last_synced_at": "2025-01-01T11:55:00+00:00",
        },
    )
    assert is_connector_mapping_poll_due(rec, now) is False
