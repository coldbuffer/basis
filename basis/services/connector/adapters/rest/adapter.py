"""Declarative REST stream adapter for BOCP (Airbyte DeclarativeSource style)."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

import httpx

from basis.services.connector.vault.auth_vault import (
    ConnectorAuthVault,
    StoredConnection,
    extract_dot_path,
    interpolate_placeholders,
)
from basis.services.connector.manifest.manifest_schema import (
    ConnectorManifest,
    StreamFieldSpec,
    StreamSpec,
    ToolSpec,
)


@dataclass
class RestBatchResult:
    records: list[dict[str, Any]]
    next_cursor_value: Any | None = None
    pages_fetched: int = 0
    has_more: bool = False


def _extract_records_by_path(
    payload: Any, path_parts: list[str], unwrap_path: str | None = None
) -> list[dict[str, Any]]:
    """Extract a list of record dicts using Airbyte DpathExtractor style path parts."""
    cur = payload
    for part in path_parts:
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            next_items: list[Any] = []
            for elem in cur:
                if isinstance(elem, dict) and part in elem:
                    val = elem[part]
                    if isinstance(val, list):
                        next_items.extend(val)
                    else:
                        next_items.append(val)
            cur = next_items
        else:
            return []

    if isinstance(cur, dict):
        # Some APIs (like Notion properties) return a dict keyed by field/record name
        raw_list = [
            {"id": k, **(v if isinstance(v, dict) else {"value": v})}
            for k, v in cur.items()
        ]
    elif isinstance(cur, list):
        raw_list = [r for r in cur if isinstance(r, dict)]
    else:
        return []

    if not unwrap_path:
        return raw_list

    unwrapped: list[dict[str, Any]] = []
    for rec in raw_list:
        nested = extract_dot_path(rec, unwrap_path)
        if isinstance(nested, dict):
            merged = {k: v for k, v in rec.items() if k != unwrap_path}
            merged.update(nested)
            unwrapped.append(merged)
        else:
            unwrapped.append(rec)
    return unwrapped


def _parse_link_header(link_header: str | None, rel: str = "next") -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        segments = [s.strip() for s in part.split(";")]
        if len(segments) < 2:
            continue
        url_part = segments[0]
        if url_part.startswith("<") and url_part.endswith(">"):
            url_val = url_part[1:-1]
            for seg in segments[1:]:
                if re.match(rf'rel=["\']?{re.escape(rel)}["\']?', seg):
                    return url_val
    return None


def _render_body_template(
    template: Any,
    *,
    patch: dict[str, Any],
    external_id: str | None = None,
    stream_params: dict[str, Any] | None = None,
    connection_config: dict[str, Any] | None = None,
    credentials: dict[str, Any] | None = None,
) -> Any:
    if isinstance(template, str):
        if template == "{{patch}}":
            return patch
        if template == "{{external_id}}":
            return external_id
        return interpolate_placeholders(
            template,
            connection_config=connection_config,
            credentials=credentials,
            stream_params=stream_params,
            extra={"external_id": external_id or ""},
        )
    if isinstance(template, dict):
        # Special case: {"patch": "{{patch}}"} where top-level body IS the patch dict
        if len(template) == 1 and template.get("patch") == "{{patch}}":
            return dict(patch)
        return {
            k: _render_body_template(
                v,
                patch=patch,
                external_id=external_id,
                stream_params=stream_params,
                connection_config=connection_config,
                credentials=credentials,
            )
            for k, v in template.items()
        }
    if isinstance(template, list):
        return [
            _render_body_template(
                v,
                patch=patch,
                external_id=external_id,
                stream_params=stream_params,
                connection_config=connection_config,
                credentials=credentials,
            )
            for v in template
        ]
    return template


class RestDeclarativeStreamAdapter:
    """Executes CHECK, DISCOVER, READ, MUTATE, and RPC TOOLS against REST APIs."""

    def __init__(
        self,
        vault: ConnectorAuthVault,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._vault = vault
        self._client = http_client or httpx.Client(timeout=30.0, follow_redirects=True)
        self._owns_client = http_client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def check_connection(
        self, manifest: ConnectorManifest, connection: StoredConnection
    ) -> dict[str, Any]:
        """Execute declarative `CHECK` endpoint and extract account profile."""
        auth_spec = self._vault._match_auth_spec(manifest, connection.auth_type)
        if not auth_spec or not auth_spec.check:
            return {"ok": True, "account_id": connection.service}

        base_url, headers, query_params = self._vault.build_request_auth(
            manifest, connection
        )
        for key, value in auth_spec.check.headers.items():
            headers[key] = interpolate_placeholders(
                value,
                connection_config=connection.connection_config,
                credentials=connection.credentials,
            )
        check_path = interpolate_placeholders(
            auth_spec.check.path,
            connection_config=connection.connection_config,
            credentials=connection.credentials,
            url_encode_values=True,
        )
        url = f"{base_url}/{check_path.lstrip('/')}"
        resp = self._client.request(
            auth_spec.check.method,
            url,
            headers=headers,
            params=query_params,
        )
        resp.raise_for_status()
        body = resp.json() if resp.content else {}
        account_id = extract_dot_path(body, auth_spec.check.account_id_path)
        display_name = extract_dot_path(body, auth_spec.check.display_name_path)
        return {
            "ok": True,
            "account_id": str(account_id) if account_id is not None else None,
            "display_name": str(display_name) if display_name is not None else None,
            "raw": body,
        }

    def discover_stream_schema(
        self,
        manifest: ConnectorManifest,
        connection: StoredConnection,
        stream: StreamSpec,
        *,
        stream_params: dict[str, Any] | None = None,
    ) -> list[StreamFieldSpec]:
        """Return static stream fields or dynamically introspect remote metadata (`DISCOVER`)."""
        loader = stream.dynamic_schema_loader
        if not loader or loader.type != "rest_metadata" or not loader.metadata_path:
            return list(stream.fields)

        base_url, headers, query_params = self._vault.build_request_auth(
            manifest, connection
        )
        rel_path = interpolate_placeholders(
            loader.metadata_path,
            connection_config=connection.connection_config,
            credentials=connection.credentials,
            stream_params=stream_params,
            url_encode_values=True,
        )
        url = f"{base_url}/{rel_path.lstrip('/')}"
        resp = self._client.get(url, headers=headers, params=query_params)
        resp.raise_for_status()
        payload = resp.json()

        raw_fields = _extract_records_by_path(payload, loader.fields_field_path)
        discovered: list[StreamFieldSpec] = list(stream.fields)
        seen_names = {f.name for f in discovered}

        # Ensure primary key is always present first
        for pk in stream.primary_key:
            if pk not in seen_names:
                discovered.append(
                    StreamFieldSpec(
                        name=pk,
                        data_type="string",
                        nullable=False,
                        primary_key=True,
                    )
                )
                seen_names.add(pk)

        for rf in raw_fields:
            fname = str(rf.get(loader.field_name_key) or rf.get("id") or "")
            if not fname or fname in seen_names:
                continue
            raw_type = str(rf.get(loader.field_type_key) or "string").lower()
            mapped_type = loader.types_map.get(raw_type)
            if not mapped_type:
                if raw_type in ("number", "currency", "percent", "rating", "float", "decimal"):
                    mapped_type = "number"
                elif raw_type in ("integer", "int", "autonumber", "count"):
                    mapped_type = "integer"
                elif raw_type in ("checkbox", "boolean", "bool"):
                    mapped_type = "boolean"
                elif raw_type in ("date",):
                    mapped_type = "date"
                elif raw_type in ("datetime", "createdtime", "lastmodifiedtime", "date_time"):
                    mapped_type = "datetime"
                else:
                    mapped_type = "string"
            discovered.append(
                StreamFieldSpec(
                    name=fname,
                    data_type=mapped_type,  # type: ignore[arg-type]
                    nullable=True,
                    primary_key=fname in stream.primary_key,
                )
            )
            seen_names.add(fname)

        return discovered

    def read_stream_records(
        self,
        manifest: ConnectorManifest,
        connection: StoredConnection,
        stream: StreamSpec,
        *,
        stream_params: dict[str, Any] | None = None,
        cursor_watermark: Any | None = None,
        max_records: int = 1000,
        max_pages: int = 20,
    ) -> RestBatchResult:
        """Fetch and paginate records from a declarative REST stream (`READ` primitive)."""
        retriever = stream.retriever
        paginator = retriever.paginator
        base_url, base_headers, base_query = self._vault.build_request_auth(
            manifest, connection
        )

        headers = dict(base_headers)
        for key, value in retriever.request_headers.items():
            headers[key] = interpolate_placeholders(
                value,
                connection_config=connection.connection_config,
                credentials=connection.credentials,
                stream_params=stream_params,
            )
        rel_path = interpolate_placeholders(
            retriever.path,
            connection_config=connection.connection_config,
            credentials=connection.credentials,
            stream_params=stream_params,
            url_encode_values=True,
        )
        next_url: str | None = f"{base_url}/{rel_path.lstrip('/')}"

        query_params: dict[str, Any] = {**base_query}
        for k, v in retriever.request_params.items():
            query_params[k] = interpolate_placeholders(
                v,
                connection_config=connection.connection_config,
                credentials=connection.credentials,
                stream_params=stream_params,
            )

        body_json: dict[str, Any] = dict(retriever.request_body_json or {})
        if cursor_watermark is not None and retriever.incremental_cursor_param:
            cursor_value = str(cursor_watermark)
            if retriever.incremental_cursor_inject == "body":
                body_json[retriever.incremental_cursor_param] = cursor_value
            elif retriever.incremental_cursor_inject == "header":
                headers[retriever.incremental_cursor_param] = cursor_value
            else:
                query_params[retriever.incremental_cursor_param] = cursor_value
        if paginator.limit_param and paginator.page_size:
            if paginator.inject_into == "body":
                body_json[paginator.limit_param] = paginator.page_size
            else:
                query_params[paginator.limit_param] = paginator.page_size

        all_records: list[dict[str, Any]] = []
        pages_fetched = 0
        has_more = False
        current_offset = 0
        current_page = 1
        current_cursor: Any | None = None

        while next_url and pages_fetched < max_pages and len(all_records) < max_records:
            req_query = dict(query_params)
            req_body = dict(body_json) if body_json else None

            if paginator.type == "cursor" and current_cursor is not None and paginator.cursor_request_param:
                if paginator.inject_into == "body":
                    req_body = dict(req_body or {})
                    req_body[paginator.cursor_request_param] = current_cursor
                else:
                    req_query[paginator.cursor_request_param] = current_cursor
            elif paginator.type == "offset" and paginator.offset_request_param and pages_fetched > 0:
                req_query[paginator.offset_request_param] = current_offset
            elif paginator.type == "page" and paginator.page_request_param:
                req_query[paginator.page_request_param] = current_page

            resp = self._client.request(
                retriever.http_method,
                next_url,
                headers=headers,
                params=req_query,
                json=req_body if retriever.http_method == "POST" else None,
            )
            resp.raise_for_status()
            pages_fetched += 1
            payload = resp.json() if resp.content else {}

            batch = _extract_records_by_path(
                payload,
                retriever.records_field_path,
                unwrap_path=retriever.record_fields_unwrap_path,
            )
            if not batch:
                break

            all_records.extend(batch)
            if len(all_records) >= max_records:
                has_more = len(all_records) > max_records or bool(batch)
                all_records = all_records[:max_records]
                break

            # Advance pagination
            if paginator.type == "none":
                break
            elif paginator.type == "cursor":
                current_cursor = extract_dot_path(payload, paginator.cursor_response_path)
                if not current_cursor:
                    break
            elif paginator.type == "offset":
                page_sz = paginator.page_size or len(batch)
                if len(batch) < page_sz:
                    break
                current_offset += len(batch)
            elif paginator.type == "page":
                page_sz = paginator.page_size or len(batch)
                if len(batch) < page_sz:
                    break
                current_page += 1
            elif paginator.type == "link":
                link_next = (
                    extract_dot_path(payload, paginator.link_response_path)
                    if paginator.link_response_path
                    else _parse_link_header(
                        resp.headers.get("Link"), rel=paginator.link_header_rel or "next"
                    )
                )
                if not link_next:
                    break
                next_url = str(link_next)
                query_params = {}  # Link URLs already include query string

        if next_url and pages_fetched >= max_pages:
            has_more = True

        next_watermark = cursor_watermark
        if all_records and stream.cursor_field:
            for rec in all_records:
                val = extract_dot_path(rec, stream.cursor_field) or rec.get(
                    stream.cursor_field
                )
                if val is not None and (
                    next_watermark is None or str(val) > str(next_watermark)
                ):
                    next_watermark = val

        return RestBatchResult(
            records=all_records,
            next_cursor_value=next_watermark,
            pages_fetched=pages_fetched,
            has_more=has_more,
        )

    def mutate_stream_record(
        self,
        manifest: ConnectorManifest,
        connection: StoredConnection,
        stream: StreamSpec,
        *,
        operation: str = "update",
        external_id: str | None = None,
        patch: dict[str, Any],
        stream_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a declarative write-back mutation (`MUTATE` primitive) against a REST stream."""
        mutation = stream.mutations.get(operation)  # type: ignore[arg-type]
        if not mutation:
            raise ValueError(
                f"Stream '{stream.name}' on service '{manifest.service}' does not support '{operation}' mutation"
            )

        base_url, headers, query_params = self._vault.build_request_auth(
            manifest, connection
        )
        for key, value in mutation.request_headers.items():
            headers[key] = interpolate_placeholders(
                value,
                connection_config=connection.connection_config,
                credentials=connection.credentials,
                stream_params=stream_params,
            )
        for key, value in mutation.request_params.items():
            query_params[key] = interpolate_placeholders(
                value,
                connection_config=connection.connection_config,
                credentials=connection.credentials,
                stream_params=stream_params,
            )
        rel_path = interpolate_placeholders(
            mutation.path_template,
            connection_config=connection.connection_config,
            credentials=connection.credentials,
            stream_params=stream_params,
            extra={"external_id": external_id or ""},
            url_encode_values=True,
        )
        url = f"{base_url}/{rel_path.lstrip('/')}"
        body = _render_body_template(
            mutation.body_template,
            patch=patch,
            external_id=external_id,
            stream_params=stream_params,
            connection_config=connection.connection_config,
            credentials=connection.credentials,
        )

        resp = self._client.request(
            mutation.http_method,
            url,
            headers=headers,
            params=query_params,
            json=body,
        )
        resp.raise_for_status()
        return resp.json() if resp.content else {"ok": True}

    def execute_tool(
        self,
        manifest: ConnectorManifest,
        connection: StoredConnection,
        tool: ToolSpec,
        *,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a standalone declarative RPC tool (`TOOL` primitive) against a REST API."""
        base_url, headers, query_params = self._vault.build_request_auth(
            manifest, connection
        )
        args = dict(arguments or {})
        method = tool.http_method or (
            "GET" if tool.annotations.read_only_hint else "POST"
        )
        raw_path = tool.path_template or f"/{tool.id}"
        rel_path = interpolate_placeholders(
            raw_path,
            connection_config=connection.connection_config,
            credentials=connection.credentials,
            extra=args,
            url_encode_values=True,
        )
        url = f"{base_url}/{rel_path.lstrip('/')}"

        req_params = dict(query_params)
        req_json: dict[str, Any] | None = None
        if method == "GET":
            for k, v in args.items():
                if f"{{{{{k}}}}}" not in raw_path and v is not None:
                    req_params[k] = str(v)
        else:
            req_json = {
                k: v for k, v in args.items() if f"{{{{{k}}}}}" not in raw_path
            }

        encoding = getattr(tool, "body_encoding", "json") or "json"
        request_kwargs: dict[str, Any] = {
            "method": method,
            "url": url,
            "headers": headers,
            "params": req_params,
        }
        if method != "GET":
            if encoding == "form":
                request_kwargs["data"] = {
                    k: str(v) for k, v in req_json.items() if v is not None
                }
            else:
                request_kwargs["json"] = req_json

        resp = self._client.request(**request_kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {"ok": True}
