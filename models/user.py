from datetime import datetime

from flask_login import UserMixin

from extensions import db


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="influencer", index=True)

    company_name = db.Column(db.String(140))
    company_website = db.Column(db.String(255))
    social_profile_url = db.Column(db.String(255))
    profile_picture = db.Column(db.String(255))
    bio = db.Column(db.Text)
    phone_number = db.Column(db.String(32))
    phone_confirmed_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime)

    creator_profile = db.relationship(
        "CreatorProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    campaigns = db.relationship("Campaign", back_populates="business", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    deal_reviews = db.relationship("DealReview", back_populates="reviewer", cascade="all, delete-orphan")

    @property
    def display_name(self) -> str:
        if self.role == "business" and self.company_name:
            return self.company_name
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
