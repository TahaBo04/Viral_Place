from datetime import datetime

from extensions import db


class CollaborationOffer(db.Model):
    __tablename__ = "collaboration_offers"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False, index=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaigns.id"), nullable=False, index=True)
    business_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    creator_profile_id = db.Column(db.Integer, db.ForeignKey("creator_profiles.id"), nullable=False, index=True)
    amount_cents = db.Column(db.Integer, nullable=False)
    minimum_rate_cents = db.Column(db.Integer, nullable=False)
    creator_payout_cents = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(30), default="pending", nullable=False, index=True)
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    responded_at = db.Column(db.DateTime)
    withdrawn_at = db.Column(db.DateTime)

    application = db.relationship("Application", back_populates="offers")
    campaign = db.relationship("Campaign", back_populates="offers")
    business = db.relationship("User", foreign_keys=[business_id], backref="sent_offers")
    creator_profile = db.relationship("CreatorProfile", backref="offers")
    order = db.relationship("Order", back_populates="offer", uselist=False)

    @property
    def amount(self) -> str:
        return f"{self.amount_cents / 100:,.2f}"

    @property
    def creator_payout(self) -> str:
        return f"{self.creator_payout_cents / 100:,.2f}"
