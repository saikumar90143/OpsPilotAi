"""Outbound URL validation to prevent Server-Side Request Forgery (SSRF)."""

import ipaddress
from urllib.parse import urlparse

BLOCKED_HOSTNAMES = frozenset({"localhost", "localhost.localdomain", "metadata.google.internal"})


def validate_safe_outbound_url(raw_url: str) -> str:
    """Validate that an outbound connector URL is HTTPS and not loopback/private/link-local."""
    cleaned = raw_url.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() != "https":
        raise ValueError("Outbound connector URL must use https://")
    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise ValueError("Outbound connector URL must include a hostname")
    if host in BLOCKED_HOSTNAMES or host.endswith((".local", ".internal", ".localhost")):
        raise ValueError(f"Outbound connector hostname '{host}' is not permitted (SSRF guard)")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return cleaned

    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
        raise ValueError(f"Outbound connector IP '{ip}' is not permitted (SSRF guard)")
    return cleaned
