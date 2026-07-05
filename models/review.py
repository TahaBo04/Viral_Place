from datetime import datetime

from extensions import db


class DealReview(db.Model):
    __tablename__ = "deal_reviews"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    reviewer_role = db.Column(db.String(20), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(30), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    order = db.relationship("Order", back_populates="reviews")
    reviewer = db.relationship("User", back_populates="deal_reviews")

    __table_args__ = (
        db.UniqueConstraint("order_id", "reviewer_id", name="uq_order_reviewer"),
        db.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating"),
    )
