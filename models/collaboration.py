from datetime import datetime

from extensions import db


class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaigns.id"), nullable=False)
    creator_profile_id = db.Column(db.Integer, db.ForeignKey("creator_profiles.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    direction = db.Column(db.String(30), nullable=False, default="influencer_application")
    status = db.Column(db.String(30), default="pending", nullable=False, index=True)
    message = db.Column(db.Text)
    match_score = db.Column(db.Integer, default=0, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    campaign = db.relationship("Campaign", back_populates="applications")
    creator_profile = db.relationship("CreatorProfile", back_populates="applications")
    sender = db.relationship("User", backref="sent_applications")
    order = db.relationship("Order", back_populates="application", uselist=False)

    __table_args__ = (
        db.UniqueConstraint("campaign_id", "creator_profile_id", name="uq_campaign_creator_application"),
    )
