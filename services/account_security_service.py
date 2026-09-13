from datetime import datetime, timedelta
import hashlib
import http.client
import json
import re
import secrets
import threading
from urllib.parse import urlsplit

from flask import current_app
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import or_, update
from werkzeug.security import generate_password_hash

from extensions import db
from models.account_email import AccountEmail
from models.user import User
from services.auth_security_service import consume_limit


def email_ready():
    return bool(current_app.config.get("RESEND_API_KEY") and current_app.config.get("MAIL_FROM") and current_app.config.get("SUPPORT_EMAIL"))


def validate_email_config(app):
    with app.app_context():
        if app.config.get("EMAIL_VERIFICATION_REQUIRED") and not email_ready():
            raise RuntimeError("Email verification requires a configured sender and support email.")
        if not email_ready():
            return
        for key in ("MAIL_FROM", "SUPPORT_EMAIL"):
            if not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", app.config[key]):
                raise RuntimeError(f"{key} must be a plain email address.")
        base = urlsplit(app.config.get("PUBLIC_BASE_URL", ""))
        if not base.hostname or base.username or base.password or base.query or base.fragment or base.path not in ("", "/"):
            raise RuntimeError("PUBLIC_BASE_URL must be a fixed origin without credentials or a path.")
        if base.scheme != "https" and not (not app.config.get("PRODUCTION") and base.scheme == "http" and base.hostname in ("localhost", "127.0.0.1")):
            raise RuntimeError("Account emails require a trusted HTTPS origin.")


def action_token(job):
    serializer = URLSafeSerializer(current_app.config["SECRET_KEY"], salt="briefvora-account-v1", signer_kwargs={"digest_method": hashlib.sha256})
    return serializer.dumps({"id": job.id, "purpose": job.purpose})


def queue_email(recipient, purpose, user=None):
    if not email_ready():
        return None
    if purpose not in ("reset", "verify", "changed"):
        raise ValueError("Unsupported account email.")
    now = datetime.utcnow()
    job = AccountEmail(
        id=secrets.token_urlsafe(32), recipient=recipient, purpose=purpose,
        user_id=user.id if user else None, auth_version=user.auth_version if user else 0,
        expires_at=now + timedelta(minutes=30 if purpose == "reset" else 120),
    )
    job.token_hash = hashlib.sha256(action_token(job).encode()).hexdigest()
    db.session.add(job)
    return job


def request_email(recipient, purpose, user=None):
    if not email_ready():
        return
    # Apply quotas before adding rows: the shared limiter commits its transaction.
    if consume_limit("account-email", recipient, 3, 3600):
        return
    queue_email(recipient, purpose, user)
    db.session.commit()
    wake_mail_worker()


def consume_action(token, purpose, password=None):
    if not token or len(token) > 512:
        return False
    try:
        payload = URLSafeSerializer(current_app.config["SECRET_KEY"], salt="briefvora-account-v1", signer_kwargs={"digest_method": hashlib.sha256}).loads(token)
    except BadSignature:
        return False
    if not isinstance(payload, dict) or payload.get("purpose") != purpose or not isinstance(payload.get("id"), str):
        return False
    now = datetime.utcnow()
    job = db.session.get(AccountEmail, payload["id"])
    if not job or not job.user_id or job.purpose != purpose or job.consumed_at or job.expires_at <= now:
        return False
    if not secrets.compare_digest(job.token_hash, hashlib.sha256(token.encode()).hexdigest()):
        return False
    user = db.session.execute(db.select(User).where(User.id == job.user_id).with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
    if not user or user.email != job.recipient or user.auth_version != job.auth_version:
        db.session.rollback()
        return False
    claimed = db.session.execute(update(AccountEmail).where(
        AccountEmail.id == job.id, AccountEmail.consumed_at.is_(None), AccountEmail.expires_at > now,
    ).values(consumed_at=now)).rowcount
    if not claimed:
        db.session.rollback()
        return False
    if purpose == "reset":
        if not password or not 12 <= len(password) <= 128:
            db.session.rollback()
            return False
        user.password_hash = generate_password_hash(password)
        user.auth_version += 1
        queue_email(user.email, "changed", user)
    elif purpose == "verify":
        user.email_verified_at = now
    else:
        db.session.rollback()
        return False
    db.session.commit()
    wake_mail_worker()
    return True


def send_email(job):
    if job.purpose == "changed":
        subject = "Your Briefvora password changed"
        body = "Your password was changed and all previous sessions were revoked. If this was not you, reset your password immediately and contact " + current_app.config["SUPPORT_EMAIL"] + "."
    else:
        path = "reset-password" if job.purpose == "reset" else "verify-email"
        subject = "Reset your Briefvora password" if job.purpose == "reset" else "Verify your Briefvora email"
        link = current_app.config["PUBLIC_BASE_URL"].rstrip("/") + "/auth/" + path + "#token=" + action_token(job)
        body = subject + ":\n\n" + link + "\n\nThis single-use link expires at " + job.expires_at.isoformat(timespec="seconds") + " UTC. If you did not request it, ignore this email.\nSupport: " + current_app.config["SUPPORT_EMAIL"]
    payload = {"from": current_app.config["MAIL_FROM"], "to": [job.recipient], "subject": subject, "text": body}
    # A fixed HTTPS API avoids SMTP restrictions and never follows redirects with credentials.
    connection = http.client.HTTPSConnection("api.resend.com", timeout=8)
    try:
        connection.request("POST", "/emails", json.dumps(payload), {
            "Authorization": "Bearer " + current_app.config["RESEND_API_KEY"],
            "Content-Type": "application/json", "Idempotency-Key": "account-" + job.id,
        })
        response = connection.getresponse()
        content = response.read(16384)
        if response.status != 200 or not json.loads(content).get("id"):
            raise RuntimeError("Email provider did not accept the message.")
    finally:
        connection.close()


def dispatch_mail(limit=10):
    if not email_ready():
        return 0
    now = datetime.utcnow()
    AccountEmail.query.filter(AccountEmail.expires_at < now - timedelta(days=7)).delete()
    db.session.commit()
    eligible = (AccountEmail.sent_at.is_(None), AccountEmail.consumed_at.is_(None),
                AccountEmail.expires_at > now, AccountEmail.next_attempt_at <= now,
                AccountEmail.attempts < 5, or_(AccountEmail.lease_until.is_(None), AccountEmail.lease_until <= now))
    ids = db.session.execute(db.select(AccountEmail.id).where(*eligible).order_by(AccountEmail.created_at).limit(limit)).scalars().all()
    sent = 0
    for job_id in ids:
        claimed = db.session.execute(update(AccountEmail).where(AccountEmail.id == job_id, *eligible).values(lease_until=now + timedelta(minutes=2))).rowcount
        db.session.commit()
        if not claimed:
            continue
        job = db.session.get(AccountEmail, job_id)
        user = db.session.get(User, job.user_id) if job.user_id else None
        if not user or user.email != job.recipient or (job.purpose != "changed" and user.auth_version != job.auth_version):
            job.consumed_at = now
            db.session.commit()
            continue
        # Conservative shared quotas also count retries; they cannot upgrade the provider plan.
        day = consume_limit("mail-daily", "all", 80, 86400)
        month = consume_limit("mail-monthly", "all", 2400, 31 * 86400)
        if day or month:
            job.next_attempt_at = now + timedelta(seconds=max(day, month))
            job.lease_until = None
            db.session.commit()
            break
        job.attempts += 1
        db.session.commit()
        try:
            send_email(job)
            job.sent_at = datetime.utcnow()
            sent += 1
        except Exception:
            # Provider responses, addresses and reset links must not enter application logs.
            current_app.logger.warning("Account email delivery failed; retry scheduled.")
            job.next_attempt_at = datetime.utcnow() + timedelta(seconds=60 * 2 ** job.attempts)
        job.lease_until = None
        db.session.commit()
    return sent


def wake_mail_worker():
    event = current_app.extensions.get("account_mail_event")
    if event:
        event.set()


def start_mail_worker(app):
    with app.app_context():
        if app.testing or not email_ready() or "account_mail_event" in app.extensions:
            return
    event = threading.Event()
    app.extensions["account_mail_event"] = event

    def run():
        while True:
            event.clear()
            with app.app_context():
                try:
                    dispatch_mail()
                except Exception:
                    db.session.rollback()
                    app.logger.warning("Account email queue temporarily unavailable.")
            event.wait(600)

    threading.Thread(target=run, name="account-mail", daemon=True).start()
