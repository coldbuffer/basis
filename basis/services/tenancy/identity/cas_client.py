"""CAS 2.0 client: login redirect and service ticket validation."""

from __future__ import annotations

from urllib.parse import urlencode
from xml.etree.ElementTree import Element

import httpx
from defusedxml.ElementTree import fromstring

_CAS_NS = {"cas": "http://www.yale.edu/tp/cas"}


def cas_service_url(public_url: str, callback_path: str, org_slug: str) -> str:
    """Service URL registered with CAS. Login and ticket validation must use the same string."""
    base = f"{public_url.rstrip('/')}{callback_path}"
    return f"{base}?{urlencode({'org': org_slug})}"


DEFAULT_CAS_LOGIN_PATH = "/login"
DEFAULT_CAS_VALIDATE_PATH = "/serviceValidate"


def _cas_endpoint(server_url: str, path: str) -> str:
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{server_url.rstrip('/')}{suffix}"


def cas_login_url(
    server_url: str,
    service: str,
    login_path: str = DEFAULT_CAS_LOGIN_PATH,
) -> str:
    return f"{_cas_endpoint(server_url, login_path)}?{urlencode({'service': service})}"


def cas_validate_url(
    server_url: str,
    service: str,
    ticket: str,
    validate_path: str = DEFAULT_CAS_VALIDATE_PATH,
) -> str:
    query = urlencode({"service": service, "ticket": ticket})
    return f"{_cas_endpoint(server_url, validate_path)}?{query}"


async def validate_cas_ticket(
    server_url: str,
    service: str,
    ticket: str,
    validate_path: str = DEFAULT_CAS_VALIDATE_PATH,
) -> str:
    url = cas_validate_url(server_url, service, ticket, validate_path)
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


def parse_cas_success(xml_text: str, email_attribute: str) -> tuple[str, str | None, str | None]:
    """Return (subject, email, display_name) from a CAS serviceValidate body."""
    root = fromstring(xml_text)
    failure = root.find("cas:authenticationFailure", _CAS_NS)
    if failure is not None:
        code = (failure.attrib.get("code") or "INVALID_TICKET").strip()
        raise ValueError(code)
    success = root.find("cas:authenticationSuccess", _CAS_NS)
    if success is None:
        raise ValueError("INVALID_RESPONSE")
    user_el = success.find("cas:user", _CAS_NS)
    subject = (user_el.text or "").strip() if user_el is not None else ""
    if not subject:
        raise ValueError("MISSING_USER")
    attributes = _cas_attributes(success)
    email = attributes.get(email_attribute.strip() or "email")
    if not email and "@" in subject:
        email = subject
    display_name = attributes.get("name") or attributes.get("displayName") or attributes.get("cn")
    return subject, email, display_name


def _cas_attributes(success: Element) -> dict[str, str]:
    found: dict[str, str] = {}
    container = success.find("cas:attributes", _CAS_NS)
    if container is None:
        return found
    for child in list(container):
        local = child.tag.rsplit("}", 1)[-1]
        text = (child.text or "").strip()
        name = (child.attrib.get("name") or "").strip()
        value = (child.attrib.get("value") or text).strip()
        if name and value:
            found.setdefault(name, value)
        if local and local != "attribute" and text:
            found.setdefault(local, text)
    return found
