from datetime import datetime
from extensions import db


class UserLoginLog(db.Model):
    __tablename__ = "user_login_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    success = db.Column(db.Boolean, nullable=False)

    ip_address = db.Column(db.String(64))
    user_agent = db.Column(db.Text)
    failure_reason = db.Column(db.String(120))

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class CreatorViewLog(db.Model):
    __tablename__ = "creator_view_logs"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    creator_profile_id = db.Column(db.Integer, db.ForeignKey("creator_profiles.id"), nullable=False)

    action = db.Column(db.String(40), default="view", nullable=False)

    ip_address = db.Column(db.String(64))
    user_agent = db.Column(db.Text)
    extra = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)

    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaigns.id"))
    creator_profile_id = db.Column(db.Integer, db.ForeignKey("creator_profiles.id"))
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"))

    event_type = db.Column(db.String(60), nullable=False)
    description = db.Column(db.Text)
    metadata_json = db.Column(db.Text)

    ip_address = db.Column(db.String(64))
    user_agent = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
