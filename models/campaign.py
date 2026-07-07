from datetime import datetime
from extensions import db


class Campaign(db.Model):
    __tablename__ = "campaigns"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    flow_type = db.Column(db.String(20), default="marketplace", nullable=False)
    visibility = db.Column(db.String(20), default="public", nullable=False, index=True)

    title = db.Column(db.String(140), nullable=False)
    industry = db.Column(db.String(80), nullable=False)
    target_niche = db.Column(db.String(80), nullable=False)
    target_platforms = db.Column(db.String(160), nullable=False)
    target_country = db.Column(db.String(80), nullable=False)
    budget_min = db.Column(db.Integer, default=0, nullable=False)
    budget_max = db.Column(db.Integer, default=0, nullable=False)
    goal = db.Column(db.String(120), nullable=False)
    brief = db.Column(db.Text, nullable=False)
    deliverables = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default="open", nullable=False, index=True)
    closed_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    business = db.relationship("User", back_populates="campaigns")
    applications = db.relationship("Application", back_populates="campaign", cascade="all, delete-orphan")
    orders = db.relationship("Order", back_populates="campaign", cascade="all, delete-orphan")
    offers = db.relationship("CollaborationOffer", back_populates="campaign", cascade="all, delete-orphan")

    @property
    def platform_list(self) -> list[str]:
        return [item.strip() for item in (self.target_platforms or "").split(",") if item.strip()]

    @property
    def is_open(self) -> bool:
        return self.status == "open" and self.closed_at is None
