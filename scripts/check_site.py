"""Low-frequency, read-only smoke checks for a deployment."""

import argparse
import json
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def check_site(base):
    origin = urlsplit(base)
    if origin.scheme != "https" or not origin.hostname or origin.username or origin.password or origin.query or origin.fragment or origin.path not in ("", "/"):
        raise ValueError("Supply an HTTPS origin without a path or credentials.")
    base = base.rstrip("/")
    for path in ("/healthz", "/", "/auth/login/business", "/.env.local", "/.git/config"):
        request = Request(base + path, headers={"User-Agent": "Briefvora-health-check/1.0"})
        try:
            response = urlopen(request, timeout=90)
        except HTTPError as error:
            response = error
        with response:
            status = response.status
            if path.startswith("/."):
                if status not in (403, 404):
                    raise RuntimeError(f"Unexpected response for protected path: {path}")
            else:
                if status != 200 or urlsplit(response.url).netloc != origin.netloc:
                    raise RuntimeError(f"Deployment unavailable: {path}")
                if response.headers.get("X-Content-Type-Options") != "nosniff" or "frame-ancestors 'none'" not in response.headers.get("Content-Security-Policy", "") or "max-age=" not in response.headers.get("Strict-Transport-Security", ""):
                    raise RuntimeError(f"Missing security headers: {path}")
                content = response.read(512000)
                if path == "/healthz" and json.loads(content).get("status") != "ok":
                    raise RuntimeError("Database health check failed.")
                if path == "/" and b"Briefvora" not in content:
                    raise RuntimeError("Expected brand missing from homepage.")
                if path.startswith("/auth/") and b'name="csrf_token"' not in content:
                    raise RuntimeError("Login form is missing CSRF protection.")
            print(f"PASS {path}: {status}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="https://briefvora.onrender.com")
    check_site(parser.parse_args().url)
