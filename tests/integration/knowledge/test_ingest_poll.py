"""HTTP poll scheduler helpers."""

from datetime import datetime, timezone

from basis.services.knowledge.services.ingest_source_service import is_http_poll_due


def test_http_poll_due_without_interval() -> None:
    source = {"config": {"poll_interval_minutes": 0}}
    assert is_http_poll_due(source, datetime.now(timezone.utc)) is False


def test_http_poll_due_first_run() -> None:
    source = {"config": {"poll_interval_minutes": 5}}
    assert is_http_poll_due(source, datetime.now(timezone.utc)) is True


def test_http_poll_not_due_yet() -> None:
    now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    source = {
        "config": {
            "poll_interval_minutes": 10,
            "last_sync_at": "2025-01-01T11:55:00+00:00",
        },
    }
    assert is_http_poll_due(source, now) is False


def test_http_poll_due_after_interval() -> None:
    now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    source = {
        "config": {
            "poll_interval_minutes": 10,
            "last_sync_at": "2025-01-01T11:49:00+00:00",
        },
    }
    assert is_http_poll_due(source, now) is True
