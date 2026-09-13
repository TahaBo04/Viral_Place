from datetime import datetime

from extensions import db


class AccountEmail(db.Model):
    __tablename__ = "account_emails"

    id = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recipient = db.Column(db.String(120), nullable=False)
    purpose = db.Column(db.String(20), nullable=False)
    auth_version = db.Column(db.Integer, nullable=False)
    token_hash = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    consumed_at = db.Column(db.DateTime)
    sent_at = db.Column(db.DateTime)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    next_attempt_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    lease_until = db.Column(db.DateTime)
