from datetime import datetime, timedelta
import hashlib
import hmac

from flask import current_app, request

from extensions import db
from models.security import AuthThrottle


WINDOW = timedelta(minutes=15)
BLOCK_DURATION = timedelta(minutes=15)
MAX_FAILURES = 5
MAX_IP_FAILURES = 30


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    return (forwarded.split(",", 1)[0].strip() or request.remote_addr or "unknown")[:64]


def _key(namespace: str, value: str) -> str:
    secret = str(current_app.config["SECRET_KEY"]).encode()
    return hmac.new(secret, f"{namespace}:{value}".encode(), hashlib.sha256).hexdigest()


def _login_keys(email: str) -> tuple[tuple[str, int], tuple[str, int]]:
    return (
        (_key("login-ip", _client_ip()), MAX_IP_FAILURES),
        (_key("login-email", email.lower()), MAX_FAILURES),
    )


def login_retry_after(email: str) -> int:
    now = datetime.utcnow()
    key_hashes = [key_hash for key_hash, _limit in _login_keys(email)]
    rows = AuthThrottle.query.filter(AuthThrottle.key_hash.in_(key_hashes)).all()
    remaining = [int((row.blocked_until - now).total_seconds()) for row in rows if row.blocked_until and row.blocked_until > now]
    return max(remaining, default=0)


def record_login_failure(email: str) -> None:
    now = datetime.utcnow()
    for key_hash, failure_limit in _login_keys(email):
        row = db.session.get(AuthThrottle, key_hash)
        if row is None:
            row = AuthThrottle(key_hash=key_hash, attempts=0, window_started_at=now)
            db.session.add(row)
        if now - row.window_started_at > WINDOW:
            row.attempts = 0
            row.window_started_at = now
            row.blocked_until = None
        row.attempts += 1
        if row.attempts >= failure_limit:
            row.blocked_until = now + BLOCK_DURATION
    db.session.commit()


def clear_account_throttle(email: str) -> None:
    AuthThrottle.query.filter_by(key_hash=_key("login-email", email.lower())).delete()
    db.session.commit()
