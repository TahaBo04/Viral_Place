from ipaddress import ip_address
import re
from urllib.parse import urlsplit, urlunsplit


BLOCKED_HOST_SUFFIXES = (".local", ".internal", ".localhost", ".test")


def safe_https_url(value: str, allowed_hosts: set[str] | None = None) -> str | None:
    raw = (value or "").strip()
    if not raw or len(raw) > 1000 or "\\" in raw or re.search(r"[\x00-\x20\x7f]", raw):
        return None
    try:
        parsed = urlsplit(raw)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme.lower() != "https" or not hostname or parsed.username or parsed.password:
        return None
    if port not in (None, 443) or hostname == "localhost" or hostname.endswith(BLOCKED_HOST_SUFFIXES):
        return None
    try:
        ip_address(hostname)
        return None
    except ValueError:
        pass
    if "." not in hostname or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", hostname) or hostname.replace(".", "").isdigit():
        return None
    if allowed_hosts and not any(hostname == host or hostname.endswith(f".{host}") for host in allowed_hosts):
        return None
    return urlunsplit(("https", parsed.netloc, parsed.path or "/", parsed.query, ""))
