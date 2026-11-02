"""Derived fact rows — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

from typing import Any


def find_active_derived_fact_duplicate(
    conn: Any,
    workspace_id: str,
    subject_id: str,
    predicate_uri: str,
    object_entity_id: str | None,
    object_value: str | None,
) -> Any:
    return conn.execute(
        """
        SELECT id FROM derived_facts
        WHERE workspace_id = ? AND subject_id = ? AND predicate_uri = ?
          AND COALESCE(object_entity_id, '') = COALESCE(?, '')
          AND COALESCE(object_value, '') = COALESCE(?, '')
          AND invalidated_at IS NULL
        LIMIT 1
        """,
        (workspace_id, subject_id, predicate_uri, object_entity_id, object_value),
    ).fetchone()


def insert_derived_fact_row(
    conn: Any,
    *,
    fact_id: str,
    workspace_id: str,
    subject_id: str,
    predicate_uri: str,
    object_entity_id: str | None,
    object_value: str | None,
    rule_id: str | None,
    recorded_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO derived_facts (
            id, workspace_id, subject_id, predicate_uri,
            object_entity_id, object_value, object_datatype,
            rule_id, recorded_at, invalidated_at
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL)
        """,
        (
            fact_id,
            workspace_id,
            subject_id,
            predicate_uri,
            object_entity_id,
            object_value,
            rule_id,
            recorded_at,
        ),
    )


def insert_fact_derivation(
    conn: Any,
    derived_fact_id: str,
    premise_kind: str,
    premise_id: str,
    ordinal: int,
) -> None:
    conn.execute(
        """
        INSERT INTO fact_derivations (
            derived_fact_id, premise_kind, premise_id, ordinal
        ) VALUES (?, ?, ?, ?)
        """,
        (derived_fact_id, premise_kind[:64], premise_id[:240], ordinal),
    )


def fetch_derivations_for_fact(conn: Any, derived_fact_id: str) -> list[Any]:
    return conn.execute(
        """
        SELECT premise_kind, premise_id, ordinal
        FROM fact_derivations
        WHERE derived_fact_id = ?
        ORDER BY ordinal
        """,
        (derived_fact_id,),
    ).fetchall()


def _derived_fact_dict(row: Any, deriv_rows: list[Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "subject_id": row["subject_id"],
        "predicate_uri": row["predicate_uri"],
        "object_entity_id": row["object_entity_id"],
        "object_value": row["object_value"],
        "rule_id": row["rule_id"],
        "recorded_at": row["recorded_at"],
        "derivations": [
            {
                "premise_kind": d["premise_kind"],
                "premise_id": d["premise_id"],
                "ordinal": d["ordinal"],
            }
            for d in deriv_rows
        ],
    }


def list_derived_facts_limited(conn: Any, workspace_id: str, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, workspace_id, subject_id, predicate_uri,
               object_entity_id, object_value, rule_id, recorded_at
        FROM derived_facts
        WHERE workspace_id = ? AND invalidated_at IS NULL
        ORDER BY recorded_at DESC
        LIMIT ?
        """,
        (workspace_id, limit),
    ).fetchall()
    facts: list[dict[str, Any]] = []
    for row in rows:
        deriv_rows = fetch_derivations_for_fact(conn, row["id"])
        facts.append(_derived_fact_dict(row, deriv_rows))
    return facts


def list_derived_facts_for_entity(
    conn: Any, workspace_id: str, entity_id: str, limit: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, workspace_id, subject_id, predicate_uri,
               object_entity_id, object_value, rule_id, recorded_at
        FROM derived_facts
        WHERE workspace_id = ? AND invalidated_at IS NULL
          AND (subject_id = ? OR object_entity_id = ?)
        ORDER BY recorded_at DESC
        LIMIT ?
        """,
        (workspace_id, entity_id, entity_id, limit),
    ).fetchall()
    facts: list[dict[str, Any]] = []
    for row in rows:
        deriv_rows = fetch_derivations_for_fact(conn, row["id"])
        facts.append(_derived_fact_dict(row, deriv_rows))
    return facts
