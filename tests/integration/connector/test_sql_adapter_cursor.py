"""SQL adapter incremental cursor watermark typing (PostgreSQL timestamptz)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Column, Date, DateTime, MetaData, Table

from basis.services.connector.adapters.sql import SqlAlchemyStreamAdapter


def test_coerce_cursor_watermark_parses_iso_for_datetime_column() -> None:
    meta = MetaData()
    table = Table("t", meta, Column("updated_at", DateTime(timezone=True)))
    col = table.c.updated_at
    parsed = SqlAlchemyStreamAdapter._coerce_cursor_watermark(col, "2026-01-02T00:00:00Z")
    assert isinstance(parsed, datetime)
    assert parsed.tzinfo is not None
    assert parsed.year == 2026 and parsed.month == 1 and parsed.day == 2


def test_coerce_cursor_watermark_parses_iso_for_date_column() -> None:
    meta = MetaData()
    table = Table("t", meta, Column("day", Date()))
    col = table.c.day
    parsed = SqlAlchemyStreamAdapter._coerce_cursor_watermark(col, "2026-01-02T00:00:00+00:00")
    assert parsed == date(2026, 1, 2)


def test_coerce_cursor_watermark_passes_through_datetime() -> None:
    meta = MetaData()
    table = Table("t", meta, Column("updated_at", DateTime(timezone=True)))
    col = table.c.updated_at
    dt = datetime(2026, 6, 1, tzinfo=timezone.utc)
    assert SqlAlchemyStreamAdapter._coerce_cursor_watermark(col, dt) is dt
