"""SHACL generation helpers from ontology subgraph nodes (no Explorer routes)."""

from __future__ import annotations

from typing import Any

from basis.services.ontology.hub.catalog import _classify_node_type, _node_label
from basis.services.ontology.browse.preview_read import extract_namespace


def _entity_description(node: dict[str, Any]) -> str:
    props = node.get("properties", {})
    return str(
        props.get("rdfs:comment")
        or props.get("skos:definition")
        or props.get("definition")
        or props.get("description")
        or ""
    )


def _ontology_namespace(uri: str) -> str:
    extracted = extract_namespace(uri)
    if extracted:
        return extracted if extracted.endswith(("#", "/")) else extracted + "#"
    if uri.endswith("/"):
        return uri
    return uri.rstrip("#/") + "#"


def ontology_dict_from_nodes(
    uri: str,
    name: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    classes: list[dict[str, Any]] = []
    properties: list[dict[str, Any]] = []
    for node in nodes:
        entity_type = _classify_node_type(node.get("type", ""))
        label = _node_label(node) or node.get("id", "")
        item: dict[str, Any] = {
            "name": label,
            "uri": node.get("id", ""),
            "label": label,
            "description": _entity_description(node),
        }
        if entity_type == "class":
            classes.append(item)
        elif entity_type == "property":
            domain = [
                edge.get("target", "")
                for edge in edges
                if edge.get("source") == node.get("id") and edge.get("type") == "rdfs:domain"
            ]
            range_ = [
                edge.get("target", "")
                for edge in edges
                if edge.get("source") == node.get("id") and edge.get("type") == "rdfs:range"
            ]
            item.update({
                "type": "object" if "ObjectProperty" in node.get("type", "") else "datatype",
                "domain": domain,
                "range": range_,
                "required": False,
            })
            properties.append(item)

    return {
        "name": name,
        "namespace": _ontology_namespace(uri),
        "classes": classes,
        "properties": properties,
    }


def basic_shacl_turtle(uri: str, name: str, nodes: list[dict[str, Any]]) -> str:
    namespace = _ontology_namespace(uri)
    lines = [
        "@prefix sh: <http://www.w3.org/ns/shacl#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        f"@prefix onto: <{namespace}> .",
        "",
    ]
    class_nodes = [n for n in nodes if _classify_node_type(n.get("type", "")) == "class"]
    for index, node in enumerate(class_nodes or nodes[:1], start=1):
        label = (_node_label(node) or f"{name}Shape").replace(" ", "")
        target = node.get("id") or uri
        lines.extend([
            f"onto:{label}Shape a sh:NodeShape ;",
            f"  sh:targetClass <{target}> ;",
            "  sh:severity sh:Violation .",
            "",
        ])
    return "\n".join(lines)


def summarize_shacl_shapes(shacl_turtle: str) -> list[dict[str, Any]]:
    normalised = shacl_turtle.replace("\r\n", "\n").replace("\r", "\n")
    blocks = [block.strip() for block in normalised.split(".\n") if "sh:NodeShape" in block]
    summaries: list[dict[str, Any]] = []
    for index, block in enumerate(blocks, start=1):
        first = block.splitlines()[0].strip()
        shape_id = first.split()[0] if first else f"shape-{index}"
        target_class = None
        constraints: list[str] = []
        for token in ("sh:targetClass", "sh:path", "sh:minCount", "sh:maxCount", "sh:datatype", "sh:class"):
            if token in block:
                constraints.append(token.replace("sh:", ""))
        if "sh:targetClass" in block:
            after = block.split("sh:targetClass", 1)[1].strip()
            target_class = after.split()[0].strip(" ;")
        summaries.append({
            "id": shape_id,
            "target_class": target_class,
            "constraint_count": max(0, len(constraints) - 1),
            "constraints": constraints,
            "violation_count": 0,
        })
    return summaries
