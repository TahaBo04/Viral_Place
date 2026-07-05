from datetime import datetime

from extensions import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(255))
    read_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="notifications")

    @property
    def is_read(self) -> bool:
        return self.read_at is not None
