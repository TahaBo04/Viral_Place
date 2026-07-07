from datetime import datetime

from extensions import db


class CreatorSocialAccount(db.Model):
    __tablename__ = "creator_social_accounts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    platform = db.Column(db.String(30), nullable=False)
    other_name = db.Column(db.String(60))
    profile_url = db.Column(db.String(500), nullable=False)
    audience_count = db.Column(db.Integer, default=0, nullable=False)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="social_accounts")

    __table_args__ = (
        db.UniqueConstraint("user_id", "platform", name="uq_user_social_platform"),
        db.CheckConstraint("audience_count >= 0", name="ck_social_audience_nonnegative"),
    )

    @property
    def display_name(self) -> str:
        labels = {
            "tiktok": "TikTok",
            "youtube": "YouTube",
            "linkedin": "LinkedIn",
            "x": "X",
        }
        if self.platform == "other" and self.other_name:
            return self.other_name
        return labels.get(self.platform, self.platform.replace("_", " ").title())
