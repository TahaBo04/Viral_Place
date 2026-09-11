from datetime import datetime, timedelta
import hashlib
import hmac
import math
from ipaddress import ip_address
from sqlalchemy import case

from flask import current_app, request

from extensions import db
from models.security import AuthThrottle


WINDOW = timedelta(minutes=15)
BLOCK_DURATION = timedelta(minutes=15)
MAX_FAILURES = 5
MAX_IP_FAILURES = 30


def _client_ip() -> str:
    value = request.remote_addr or "unknown"
    if current_app.config.get("TRUST_PROXY_HEADERS"):
        # The trusted hosting edge appends the real client after any supplied prefix.
        value = request.headers.get("X-Forwarded-For", value).rsplit(",", 1)[-1].strip()
    try:
        return str(ip_address(value))
    except ValueError:
        return "unknown"


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
    limits = dict(_login_keys(email))
    remaining = [max(1, math.ceil((row.blocked_until - now).total_seconds())) for row in rows if row.attempts >= limits[row.key_hash] and row.blocked_until and row.blocked_until > now]
    return max(remaining, default=0)


def record_login_failure(email: str) -> None:
    for namespace, value in (("login-ip", _client_ip()), ("login-email", email.lower())):
        _increment(namespace, value, int(WINDOW.total_seconds()))


def _increment(namespace: str, value: str, seconds: int):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    now = datetime.utcnow()
    end = now + timedelta(seconds=seconds)
    insert = pg_insert if db.engine.dialect.name == "postgresql" else sqlite_insert
    expired = (AuthThrottle.blocked_until <= now) | AuthThrottle.blocked_until.is_(None)
    statement = insert(AuthThrottle).values(key_hash=_key(namespace, value), attempts=1, window_started_at=now, blocked_until=end, updated_at=now)
    # Atomic upserts keep limits consistent across workers and concurrent requests.
    statement = statement.on_conflict_do_update(index_elements=[AuthThrottle.key_hash], set_={
        "attempts": case((expired, 1), else_=AuthThrottle.attempts + 1),
        "window_started_at": case((expired, now), else_=AuthThrottle.window_started_at),
        "blocked_until": case((expired, end), else_=AuthThrottle.blocked_until),
        "updated_at": now,
    }).returning(AuthThrottle.attempts, AuthThrottle.blocked_until)
    attempts, deadline = db.session.execute(statement).one()
    db.session.commit()
    return attempts, max(1, math.ceil((deadline - now).total_seconds()))


def consume_limit(namespace: str, value: str, maximum: int, seconds: int) -> int:
    attempts, remaining = _increment(namespace, value, seconds)
    return remaining if attempts > maximum else 0


def clear_account_throttle(email: str) -> None:
    AuthThrottle.query.filter_by(key_hash=_key("login-email", email.lower())).delete()
    db.session.commit()
