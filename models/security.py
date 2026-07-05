from datetime import datetime

from extensions import db


class AuthThrottle(db.Model):
    __tablename__ = "auth_throttles"

    key_hash = db.Column(db.String(64), primary_key=True)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    window_started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    blocked_until = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
