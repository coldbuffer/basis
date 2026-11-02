"""Ontology preview (read-only) without calling Explorer route handlers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from basis.services.errors import AdminError

_FORMAT_ALIASES: dict[str, str] = {
    "ttl": "turtle",
    "rdf": "xml",
    "owl": "xml",
    "jsonld": "json-ld",
    "json": "json-ld",
}


def detect_format(content: str) -> str:
    stripped = content.strip()[:500]
    if stripped.startswith("{") or stripped.startswith("["):
        return "json-ld"
    if stripped.startswith("<"):
        return "xml"
    if "@prefix" in stripped or "@base" in stripped:
        return "turtle"
    if stripped.startswith("_:") and " <" in stripped:
        return "nt"
    return "turtle"


def normalize_format(fmt: str | None) -> str:
    if not fmt:
        return "turtle"
    lower = fmt.strip().lower()
    return _FORMAT_ALIASES.get(lower, lower)


def extract_namespace(uri: str) -> str | None:
    if "#" in uri:
        return uri.rsplit("#", 1)[0] + "#"
    if "/" in uri:
        return uri.rsplit("/", 1)[0] + "/"
    return None


def preview_ontology(
    *,
    url: str | None,
    content: str | None,
    format: str | None,
    fetch_url_bytes: Callable[[str], bytes],
    parse_rdf_sync: Callable[[bytes, str], tuple[Any, Any, dict[str, Any]]],
) -> dict[str, Any]:
    if not url and not content:
        raise AdminError(422, "validation_error", "Provide either url or content.")

    if url:
        raw = fetch_url_bytes(url)
        content_str = raw.decode("utf-8", errors="replace")
        source_url = url
    else:
        content_str = content or ""
        source_url = None

    fmt = normalize_format(format) if format else detect_format(content_str)

    try:
        _nodes, _edges, metadata = parse_rdf_sync(content_str.encode("utf-8"), fmt)
    except AdminError:
        raise
    except Exception as exc:
        raise AdminError(422, "validation_error", f"Could not parse ontology: {exc}") from exc

    uri = metadata.get("uri", "")
    return {
        "uri": uri,
        "name": metadata.get("name", ""),
        "description": metadata.get("description"),
        "namespace": extract_namespace(uri),
        "version": metadata.get("version"),
        "license": metadata.get("license"),
        "format": fmt,
        "estimated_triples": metadata.get("triple_count", 0),
        "source_url": source_url,
    }
