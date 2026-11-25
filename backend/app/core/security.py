"""Security helpers: URL/SSRF validation, HTML escaping, and upload sanitization."""

import html
import ipaddress
import socket
from typing import Tuple
from urllib.parse import urlparse

from app.core.config import get_settings

_BLOCKED_HOSTNAMES = {
    "metadata.google.internal",
    "169.254.169.254",
}


def validate_target_url(raw_url: str) -> Tuple[bool, str, str]:
    """
    Validate and normalize a target website URL.
    Blocks unsafe schemes and internal/private network destinations (SSRF protection),
    while optionally allowing localhost/127.0.0.1 when ALLOW_LOCALHOST_TESTING=true.

    Returns:
        (is_valid, normalized_url, error_message)
    """
    if not raw_url or not isinstance(raw_url, str):
        return False, "", "URL is required"

    candidate = raw_url.strip()
    if not candidate:
        return False, "", "URL is empty"

    if "://" not in candidate:
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in {"http", "https"}:
        return False, "", f"Unsupported URL scheme: {parsed.scheme}"

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        return False, "", "URL is missing a valid hostname"

    if hostname in _BLOCKED_HOSTNAMES:
        return False, "", f"Blocked destination hostname: {hostname}"

    settings = get_settings()
    is_localhost = hostname in {"localhost", "127.0.0.1", "::1"}

    if is_localhost and not settings.allow_localhost_testing:
        return False, "", "Localhost URLs are disabled in this environment"

    if not is_localhost:
        # Check literal IP addresses
        try:
            ip = ipaddress.ip_address(hostname)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                return False, "", f"Internal or private IP address not allowed: {hostname}"
        except ValueError:
            # Domain name: verify it doesn't resolve to a private/link-local IP if resolvable
            try:
                resolved = socket.getaddrinfo(hostname, None)
                for item in resolved:
                    addr_str = item[4][0]
                    ip = ipaddress.ip_address(addr_str)
                    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                        return False, "", f"Domain resolves to a blocked internal IP: {hostname}"
            except socket.gaierror:
                # DNS may fail offline or for new domains; allow storing URL and handle during scan
                pass

    normalized = parsed.geturl()
    return True, normalized, ""


def extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        return (parsed.hostname or "").lower()
    except Exception:
        return ""


def escape_html(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)
