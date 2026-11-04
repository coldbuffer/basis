"""Map a SQL catalog snapshot onto OWL classes and properties."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote


def catalog_namespace(source_id: str) -> str:
    return f"https://basis.local/sql-catalog/{quote(source_id, safe='')}"


def catalog_ontology_uri(source_id: str) -> str:
    return f"{catalog_namespace(source_id)}#ontology"


def _segment(value: Any, *, fallback: str) -> str:
    text = str(value or "").strip()
    return quote(text or fallback, safe="")


def _text(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if value is None:
        return ""
    return str(value).strip()


def _class_uri(namespace: str, schema: str, table: str) -> str:
    return f"{namespace}/{_segment(schema, fallback='main')}/{_segment(table, fallback='table')}"


def catalog_to_graph(
    source_id: str,
    display_name: str,
    catalog: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    """Build ontology nodes and edges. Identifiers stay stable across re-applies."""
    namespace = catalog_namespace(source_id)
    ontology_uri = catalog_ontology_uri(source_id)
    label = display_name.strip() or source_id
    nodes: list[dict[str, Any]] = [
        {
            "id": ontology_uri,
            "type": "owl:Ontology",
            "content": label,
            "properties": {
                "rdfs:label": label,
                "rdfs:comment": "Generated from a SQL catalog snapshot.",
                "scheme_uri": ontology_uri,
                "basis:sqlCatalogSource": source_id,
            },
        }
    ]
    edges: list[dict[str, Any]] = []
    classes: dict[tuple[str, str], str] = {}

    for table in catalog.get("tables") or []:
        if not isinstance(table, dict):
            continue
        table_name = _text(table, "table_name")
        if not table_name:
            continue
        schema = _text(table, "table_schema") or "main"
        class_uri = _class_uri(namespace, schema, table_name)
        classes[(schema, table_name)] = class_uri
        table_type = _text(table, "table_type") or "base table"
        nodes.append(
            {
                "id": class_uri,
                "type": "owl:Class",
                "content": table_name,
                "properties": {
                    "rdfs:label": table_name,
                    "rdfs:comment": f"{schema}.{table_name} ({table_type})",
                    "scheme_uri": ontology_uri,
                    "basis:sqlSchema": schema,
                    "basis:sqlTable": table_name,
                    "basis:sqlTableType": table_type,
                },
            }
        )

    primary_keys = {
        (
            _text(row, "table_schema") or "main",
            _text(row, "table_name"),
            _text(row, "column_name"),
        )
        for row in catalog.get("primary_keys") or []
        if isinstance(row, dict) and _text(row, "column_name")
    }

    datatype_properties = 0
    for column in catalog.get("columns") or []:
        if not isinstance(column, dict):
            continue
        table_name = _text(column, "table_name")
        column_name = _text(column, "column_name")
        if not table_name or not column_name:
            continue
        schema = _text(column, "table_schema") or "main"
        class_uri = classes.get((schema, table_name))
        if class_uri is None:
            continue
        data_type = _text(column, "data_type") or "text"
        nullable = column.get("is_nullable")
        required = nullable in (False, 0, "NO", "no", "false")
        prop_uri = f"{class_uri}/{_segment(column_name, fallback='column')}"
        is_pk = (schema, table_name, column_name) in primary_keys
        comment = data_type
        if is_pk:
            comment = f"{comment}, primary key"
        if required:
            comment = f"{comment}, required"
        nodes.append(
            {
                "id": prop_uri,
                "type": "owl:DatatypeProperty",
                "content": column_name,
                "properties": {
                    "rdfs:label": column_name,
                    "rdfs:comment": comment,
                    "scheme_uri": ontology_uri,
                    "basis:sqlDataType": data_type,
                    "basis:primaryKey": "true" if is_pk else "false",
                },
            }
        )
        edges.append(
            {
                "source": prop_uri,
                "target": class_uri,
                "type": "rdfs:domain",
                "weight": 1.0,
            }
        )
        datatype_properties += 1

    object_properties = 0
    for foreign_key in catalog.get("foreign_keys") or []:
        if not isinstance(foreign_key, dict):
            continue
        table_name = _text(foreign_key, "table_name")
        column_name = _text(foreign_key, "column_name")
        referenced_table = _text(foreign_key, "referenced_table")
        if not table_name or not column_name or not referenced_table:
            continue
        schema = _text(foreign_key, "table_schema") or "main"
        referenced_schema = _text(foreign_key, "referenced_schema") or schema
        source_uri = classes.get((schema, table_name))
        target_uri = classes.get((referenced_schema, referenced_table))
        if source_uri is None or target_uri is None:
            continue
        prop_uri = f"{source_uri}/{_segment(column_name, fallback='column')}/fk"
        referenced_column = _text(foreign_key, "referenced_column")
        nodes.append(
            {
                "id": prop_uri,
                "type": "owl:ObjectProperty",
                "content": column_name,
                "properties": {
                    "rdfs:label": column_name,
                    "rdfs:comment": (
                        f"{schema}.{table_name}.{column_name} references "
                        f"{referenced_schema}.{referenced_table}.{referenced_column}"
                    ),
                    "scheme_uri": ontology_uri,
                },
            }
        )
        edges.append(
            {"source": prop_uri, "target": source_uri, "type": "rdfs:domain", "weight": 1.0}
        )
        edges.append(
            {"source": prop_uri, "target": target_uri, "type": "rdfs:range", "weight": 1.0}
        )
        object_properties += 1

    summary = {
        "classes": len(classes),
        "datatype_properties": datatype_properties,
        "object_properties": object_properties,
    }
    return nodes, edges, summary


def apply_catalog_ontology(
    session: Any,
    registry: dict[str, Any],
    *,
    source_id: str,
    display_name: str,
    catalog: dict[str, Any],
) -> dict[str, Any]:
    """Write the snapshot into the workspace graph and ontology registry."""
    nodes, edges, summary = catalog_to_graph(source_id, display_name, catalog)
    nodes_added, edges_added = session.add_nodes_and_edges(nodes, edges)
    ontology_uri = catalog_ontology_uri(source_id)
    label = display_name.strip() or source_id
    registry[ontology_uri] = {
        "uri": ontology_uri,
        "name": label,
        "description": f"SQL catalog snapshot for {label}.",
        "format": "sql-catalog",
        "status": "draft",
        "version": "0.1.0",
        "class_count": summary["classes"],
        "property_count": summary["datatype_properties"] + summary["object_properties"],
        "loaded_at": datetime.now(timezone.utc).isoformat(),
        "enabled": True,
        "tags": ["sql-catalog", source_id],
        "source_id": source_id,
    }
    return {
        "status": "success",
        "uri": ontology_uri,
        "name": label,
        "source_id": source_id,
        "nodes_added": nodes_added,
        "edges_added": edges_added,
        **summary,
    }
