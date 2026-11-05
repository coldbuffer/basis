"""Ontology RDF fetch (SSRF-hardened), parse, and ingest→graph (no Explorer routes)."""

from __future__ import annotations

import ipaddress
import socket
import uuid
from typing import Any
from urllib.parse import urljoin, urlparse

from fastapi import HTTPException

from basis.services.ontology.hub.catalog import _humanize_rdf_label, uri_to_prefixed
from basis.services.ontology.io.admin_errors import admin_error_from_http_status

_MAX_FETCH_BYTES = 20 * 1024 * 1024


def _as_uri_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if item is None or item == "":
                continue
            if isinstance(item, dict):
                uri = item.get("uri") or item.get("id") or item.get("@id")
                if uri:
                    result.append(str(uri))
            else:
                result.append(str(item))
        return result
    if isinstance(value, dict):
        uri = value.get("uri") or value.get("id") or value.get("@id")
        return [str(uri)] if uri else []
    return [str(value)]


def _convert_ontology_to_graph_impl(ontology_dict: dict[str, Any]) -> Tuple[List[dict[str, Any]], List[dict[str, Any]]]:
    """Convert OntologyIngestor ontology dict to graph nodes and edges."""
    nodes = []
    edges = []
    
    # Add ontology node
    ontology_uri = ontology_dict.get("uri", f"temp:{uuid.uuid4().hex[:12]}")
    onto_display = _humanize_rdf_label(ontology_dict.get("name", "Ontology"), ontology_uri)
    nodes.append({
        "id": ontology_uri,
        "type": "owl:Ontology",
        "content": onto_display,
        "properties": {
            "rdfs:label": onto_display,
            "rdfs:comment": ontology_dict.get("description", ""),
            "uri": ontology_uri,
        },
    })
    
    # Add class nodes
    for cls in ontology_dict.get("classes", []):
        cls_uri = cls.get("uri", f"temp:class:{uuid.uuid4().hex[:12]}")
        cls_display = _humanize_rdf_label(cls.get("label") or cls.get("name", ""), cls_uri)
        node = {
            "id": cls_uri,
            "type": "owl:Class",
            "content": cls_display,
            "properties": {
                "rdfs:label": cls_display,
                "rdfs:comment": cls.get("description", ""),
                "uri": cls_uri,
                "scheme_uri": ontology_uri,
            },
        }
        nodes.append(node)
        
        # Add subclass edges
        for parent in cls.get("parents", []):
            edges.append({
                "source": cls_uri,
                "target": parent,
                "type": "rdfs:subClassOf",
                "weight": 1.0,
            })
    
    # Add property nodes and edges
    for prop in ontology_dict.get("properties", []):
        prop_uri = prop.get("uri", f"temp:prop:{uuid.uuid4().hex[:12]}")
        property_type = {
            "object": "owl:ObjectProperty",
            "data": "owl:DatatypeProperty",
            "datatype": "owl:DatatypeProperty",
            "annotation": "owl:AnnotationProperty",
        }.get(str(prop.get("type", "object")).lower(), "owl:ObjectProperty")
        prop_display = _humanize_rdf_label(prop.get("label") or prop.get("name", ""), prop_uri)
        node = {
            "id": prop_uri,
            "type": property_type,
            "content": prop_display,
            "properties": {
                "rdfs:label": prop_display,
                "rdfs:comment": prop.get("description", ""),
                "uri": prop_uri,
                "scheme_uri": ontology_uri,
            },
        }
        nodes.append(node)
        
        # Add domain and range edges
        for domain_uri in _as_uri_list(prop.get("domain")):
            edges.append({
                "source": prop_uri,
                "target": domain_uri,
                "type": "rdfs:domain",
                "weight": 1.0,
            })
        for range_uri in _as_uri_list(prop.get("range")):
            edges.append({
                "source": prop_uri,
                "target": range_uri,
                "type": "rdfs:range",
                "weight": 1.0,
            })
    
    return nodes, edges

def _validate_fetch_url(url: str) -> list[str]:
    """Reject non-HTTP(S) schemes and private/loopback/link-local targets.

    Returns every resolved, validated IP address (deduplicated, in
    resolution order) so the caller can pin the actual connection to them
    (see _make_pinned_session) with fallback across all of them — not just
    the first — since a hostname can have multiple A/AAAA records and the
    first one isn't guaranteed reachable. Resolving the hostname again at
    connect time would open a DNS check-then-use window (a low-TTL or
    rebinding DNS answer could differ between this check and the client's
    own lookup), which is what pinning to these specific addresses avoids.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=422, detail="Only http and https URLs are allowed.")
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=422, detail="Invalid URL: missing hostname.")
    try:
        addrinfos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise HTTPException(status_code=422, detail=f"Cannot resolve hostname '{hostname}': {exc}") from exc
    validated_ips: list[str] = []
    for _family, _type, _proto, _canonname, sockaddr in addrinfos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise HTTPException(
                status_code=422,
                detail="Fetching from private, loopback, or reserved network addresses is not allowed.",
            )
        if sockaddr[0] not in validated_ips:
            validated_ips.append(sockaddr[0])
    if not validated_ips:
        raise HTTPException(status_code=422, detail=f"Cannot resolve hostname '{hostname}' to a usable address.")
    return validated_ips

def _make_pinned_session(pinned_ips: list[str], url: str):
    """Build a requests.Session whose connection is pinned to pinned_ips
    (tried in order, falling back on connection failure), regardless of
    what url's hostname resolves to at connect time.

    _validate_fetch_url() resolves and validates the hostname once; letting
    the HTTP client resolve it again independently at connect time reopens
    the exact gap that validation exists to close — a low-TTL or rebinding
    DNS answer can differ between the two lookups. This pins the pool's
    connect target to the already-validated addresses directly (bypassing
    DNS resolution for the connection entirely), while keeping the original
    hostname as the outgoing HTTP Host header and, for HTTPS, the TLS SNI
    server_hostname / assert_hostname — otherwise the connection would
    reach the right IP but present the wrong identity, breaking name-based
    virtual hosting and (for HTTPS) certificate hostname verification.

    Falls back across every validated address (not just the first) so a
    hostname with multiple A/AAAA records doesn't fail outright just
    because the first-returned address happens to be unreachable.

    Note: urllib3's Connection.host is a property that reads/writes the
    same underlying value as `_dns_host` in this version — it is NOT the
    separate "presented identity" field it is in some older releases, so
    overriding just `_dns_host` post-construction (as an earlier version of
    this fix did) actually changes the Host header too. Pinning the pool's
    `host` directly and restoring the real hostname via an explicit Host
    header (+ SNI params for HTTPS) is the correct mechanism here.
    """
    import requests as _req
    import urllib3.util.connection as _u3_connection
    from urllib3.exceptions import NewConnectionError

    parsed = urlparse(url)
    hostname = parsed.hostname
    port = parsed.port
    default_port = 443 if parsed.scheme == "https" else 80
    host_header = hostname if port in (None, default_port) else f"{hostname}:{port}"

    class _MultiIPConnectionMixin:
        """Overrides _new_conn to fall back across every pinned IP in
        order, instead of urllib3's default single-host connect."""

        def _new_conn(self):
            last_exc: BaseException | None = None
            for ip in pinned_ips:
                try:
                    return _u3_connection.create_connection(
                        (ip, self.port),
                        self.timeout,
                        source_address=self.source_address,
                        socket_options=self.socket_options,
                    )
                except OSError as exc:
                    last_exc = exc
                    continue
            raise NewConnectionError(
                self, f"Failed to establish a connection to any of {pinned_ips}: {last_exc}"
            )

    class _PinnedIPHTTPAdapter(_req.adapters.HTTPAdapter):
        def get_connection_with_tls_context(self, request, verify, proxies=None, cert=None):
            # A proxy would perform its own DNS resolution of the target
            # host on this process's behalf — a resolution outside this
            # process's visibility or control, so there is no client-side
            # pin that closes that race. Proxies are disabled outright for
            # this SSRF-sensitive fetcher (session.trust_env=False below),
            # so this should be unreachable via environment proxies; fail
            # closed rather than silently skip pinning if a proxy is
            # somehow still configured (e.g. passed explicitly in the
            # future). _validate_fetch_url's destination classification is
            # a separate, always-enforced check — this only guards the
            # secondary DNS-pinning hardening.
            if _req.utils.select_proxy(request.url, proxies):
                raise HTTPException(
                    status_code=502,
                    detail="Proxied requests are not supported for ontology URL fetching.",
                )
            host_params, pool_kwargs = self.build_connection_pool_key_attributes(request, verify, cert)
            if host_params.get("scheme") == "https":
                pool_kwargs.setdefault("assert_hostname", hostname)
                pool_kwargs.setdefault("server_hostname", hostname)
            host_params["host"] = pinned_ips[0]
            pool = self.poolmanager.connection_from_host(**host_params, pool_kwargs=pool_kwargs)
            base_connection_cls = pool.ConnectionCls
            if not issubclass(base_connection_cls, _MultiIPConnectionMixin):
                pool.ConnectionCls = type(
                    "_PinnedConnection", (_MultiIPConnectionMixin, base_connection_cls), {}
                )
            return pool

    session = _req.Session()
    # Never honor HTTP_PROXY/HTTPS_PROXY/NO_PROXY env vars for this
    # SSRF-sensitive fetcher: a configured proxy would perform its own DNS
    # resolution of the target host outside this process's control,
    # silently reopening the DNS check-then-use race pinning exists to
    # close. See _PinnedIPHTTPAdapter.get_connection_with_tls_context for
    # the fail-closed backstop if a proxy is somehow still configured.
    session.trust_env = False
    session.headers["Host"] = host_header
    adapter = _PinnedIPHTTPAdapter()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def _fetch_url_sync(url: str) -> bytes:
    pinned_ips = _validate_fetch_url(url)
    _MAX_REDIRECTS = 5
    current_url = url
    try:
        for _ in range(_MAX_REDIRECTS + 1):
            session = _make_pinned_session(pinned_ips, current_url)
            try:
                resp = session.get(
                    current_url,
                    headers={"Accept": "text/turtle, application/rdf+xml, application/ld+json, */*;q=0.1"},
                    timeout=30,
                    stream=True,
                    allow_redirects=False,  # SECURITY: follow redirects manually
                )
                if resp.is_redirect or resp.is_permanent_redirect:
                    redirect_url = resp.headers.get("Location")
                    resp.close()  # Release the streamed connection before following the redirect
                    if not redirect_url:
                        raise HTTPException(status_code=502, detail="Redirect without Location header.")
                    # Resolve relative redirects (e.g. /ontology.ttl) against the current URL
                    redirect_url = urljoin(current_url, redirect_url)
                    # Re-validate the redirect target to prevent SSRF via
                    # open-redirect to internal/cloud-metadata endpoints, and
                    # get fresh pins for the new host.
                    pinned_ips = _validate_fetch_url(redirect_url)
                    current_url = redirect_url
                    continue
                try:
                    resp.raise_for_status()
                    chunks: list[bytes] = []
                    total = 0
                    for chunk in resp.iter_content(65536):
                        total += len(chunk)
                        if total > _MAX_FETCH_BYTES:
                            raise HTTPException(status_code=413, detail="Remote resource exceeds 20 MB limit.")
                        chunks.append(chunk)
                    return b"".join(chunks)
                finally:
                    resp.close()  # Release the streamed connection once fully read (or on error)
            finally:
                session.close()
        raise HTTPException(status_code=502, detail=f"Too many redirects (max {_MAX_REDIRECTS}).")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not fetch {url}: {exc}") from exc

def _parse_rdf_sync_impl(content: bytes, fmt: str) -> tuple:
    """Return (nodes, edges, metadata). Raises HTTPException on failure."""
    try:
        import rdflib
    except ImportError:
        raise HTTPException(status_code=501, detail="rdflib is not installed.")

    fmt_map = {
        "turtle": "turtle", "xml": "xml", "nt": "nt",
        "json-ld": "json-ld", "n3": "n3",
    }
    parse_fmt = fmt_map.get(fmt, "turtle")

    g = rdflib.Graph()
    try:
        from basis.services.ontology.io.rdf_parse import safe_parse_rdf

        safe_parse_rdf(g, content, parse_fmt)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"RDF parse error: {exc}") from exc

    OWL = rdflib.Namespace("http://www.w3.org/2002/07/owl#")
    RDF = rdflib.RDF
    RDFS = rdflib.RDFS
    SKOS = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")
    DCT = rdflib.Namespace("http://purl.org/dc/terms/")
    DC = rdflib.Namespace("http://purl.org/dc/elements/1.1/")

    metadata: dict[str, Any] = {}

    for subj in g.subjects(RDF.type, OWL.Ontology):
        metadata["uri"] = str(subj)
        for pred, obj in g.predicate_objects(subj):
            p = str(pred)
            if p in {str(RDFS.label), str(DCT.title), str(DC.title)}:
                metadata.setdefault("name", str(obj))
            elif p in {str(RDFS.comment), str(DCT.description), str(DC.description)}:
                metadata.setdefault("description", str(obj))
            elif p == str(OWL.versionInfo):
                metadata.setdefault("version", str(obj))
            elif p in {str(DCT.license), str(DC.rights)}:
                metadata.setdefault("license", str(obj))
        break

    if "uri" not in metadata:
        for subj in g.subjects(RDF.type, SKOS.ConceptScheme):
            metadata["uri"] = str(subj)
            for pred, obj in g.predicate_objects(subj):
                p = str(pred)
                if p in {str(SKOS.prefLabel), str(DCT.title), str(DC.title)}:
                    metadata.setdefault("name", str(obj))
                elif p in {str(SKOS.definition), str(DCT.description)}:
                    metadata.setdefault("description", str(obj))
            break

    synthetic_uri = "uri" not in metadata
    if synthetic_uri:
        metadata["uri"] = f"urn:semantica:onto:{uuid.uuid4().hex[:8]}"
    metadata.setdefault("name", metadata["uri"].rsplit("/", 1)[-1].rsplit("#", 1)[-1] or "Unnamed")
    metadata["triple_count"] = len(g)

    # Collect literal properties per subject
    literal_props: dict[str, dict[str, str]] = {}
    for subj, pred, obj in g:
        if isinstance(subj, rdflib.BNode) or not isinstance(obj, rdflib.Literal):
            continue
        sid = str(subj)
        pk = uri_to_prefixed(str(pred))
        literal_props.setdefault(sid, {})[pk] = str(obj)

    # Build nodes from rdf:type statements
    seen_ids: set = set()
    nodes: List[dict[str, Any]] = []
    for subj, _, type_obj in g.triples((None, RDF.type, None)):
        if isinstance(subj, rdflib.BNode):
            continue
        sid = str(subj)
        ntype = uri_to_prefixed(str(type_obj))
        if sid in seen_ids:
            continue
        seen_ids.add(sid)
        props = dict(literal_props.get(sid, {}))
        props["uri"] = sid
        label = _humanize_rdf_label(
            props.get("rdfs:label")
            or props.get("skos:prefLabel")
            or props.get("dcterms:title"),
            sid,
        )
        props.setdefault("rdfs:label", label)
        nodes.append({"id": sid, "type": ntype, "content": label, "properties": props})

    # Build edges from non-literal object statements
    edges: List[dict[str, Any]] = []
    for subj, pred, obj in g:
        if isinstance(subj, rdflib.BNode) or isinstance(obj, (rdflib.Literal, rdflib.BNode)):
            continue
        edges.append({
            "source": str(subj),
            "target": str(obj),
            "type": uri_to_prefixed(str(pred)),
            "weight": 1.0,
        })

    if synthetic_uri:
        # No owl:Ontology / skos:ConceptScheme declaration exists, so the
        # synthetic registry URI shares no namespace with any node. Ownership
        # must be recorded explicitly, and the editor needs a matching graph
        # node, or the registered ontology resolves to an empty core and 404s.
        for node in nodes:
            node["properties"].setdefault("scheme_uri", metadata["uri"])
        nodes.append({
            "id": metadata["uri"],
            "type": "owl:Ontology",
            "content": metadata["name"],
            "properties": {"rdfs:label": metadata["name"], "uri": metadata["uri"]},
        })

    return nodes, edges, metadata


def convert_ontology_to_graph(ontology_data: dict[str, Any]) -> tuple[list[Any], list[Any]]:
    return _convert_ontology_to_graph_impl(ontology_data)


def parse_rdf_sync_for_basis(content: bytes, fmt: str) -> tuple[Any, Any, dict[str, Any]]:
    try:
        return _parse_rdf_sync_impl(content, fmt)
    except HTTPException as exc:
        raise admin_error_from_http_status(
            exc.status_code, exc.detail, context="ontology"
        ) from exc


def fetch_ontology_url_bytes(url: str) -> bytes:
    try:
        return _fetch_url_sync(url)
    except HTTPException as exc:
        raise admin_error_from_http_status(
            exc.status_code, exc.detail, context="ontology"
        ) from exc
