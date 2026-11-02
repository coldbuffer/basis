"""Auth/OAuth HTTP paths (OpenAPI v1; legacy unversioned /api is gated off by default)."""

AUTH_V1_PREFIX = "/api/v1/auth"


def auth_v1_path(subpath: str) -> str:
    segment = subpath.lstrip("/")
    return f"{AUTH_V1_PREFIX}/{segment}" if segment else AUTH_V1_PREFIX
