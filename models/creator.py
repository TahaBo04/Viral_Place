from datetime import datetime
from extensions import db


class CreatorProfile(db.Model):
    __tablename__ = "creator_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    display_name = db.Column(db.String(120), nullable=False)
    niche = db.Column(db.String(80), nullable=False)
    platforms = db.Column(db.String(160), nullable=False)
    audience_country = db.Column(db.String(80), nullable=False)
    followers = db.Column(db.Integer, default=0, nullable=False)
    engagement_rate = db.Column(db.Float, default=0.0, nullable=False)
    starting_rate = db.Column(db.Integer, default=0, nullable=False)
    media_kit_summary = db.Column(db.Text, nullable=False)
    portfolio_url = db.Column(db.String(255))
    availability = db.Column(db.String(30), default="available", nullable=False)
    social_proof_url = db.Column(db.String(255))
    verification_code = db.Column(db.String(24), nullable=False)
    verification_status = db.Column(db.String(24), default="pending", nullable=False, index=True)
    verification_notes = db.Column(db.Text)
    verified_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="creator_profile")
    applications = db.relationship("Application", back_populates="creator_profile", cascade="all, delete-orphan")

    @property
    def platform_list(self) -> list[str]:
        return [item.strip() for item in (self.platforms or "").split(",") if item.strip()]
