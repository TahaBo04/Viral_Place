from datetime import datetime

from extensions import db


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaigns.id"), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), unique=True)
    offer_id = db.Column(db.Integer, db.ForeignKey("collaboration_offers.id"), unique=True)
    business_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    influencer_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    creator_profile_id = db.Column(db.Integer, db.ForeignKey("creator_profiles.id"))

    amount_cents = db.Column(db.Integer, nullable=False)
    influencer_payout_cents = db.Column(db.Integer, default=0, nullable=False)
    currency = db.Column(db.String(3), default="usd", nullable=False)
    status = db.Column(db.String(30), default="awaiting_payment", nullable=False, index=True)
    payment_status = db.Column(db.String(30), default="unpaid", nullable=False)
    payout_status = db.Column(db.String(30), default="not_due", nullable=False)

    stripe_checkout_session_id = db.Column(db.String(255), unique=True)
    stripe_payment_intent_id = db.Column(db.String(255))
    refund_reference = db.Column(db.String(255))
    customer_notes = db.Column(db.Text)
    admin_notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    paid_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    refunded_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    campaign = db.relationship("Campaign", back_populates="orders")
    application = db.relationship("Application", back_populates="order")
    offer = db.relationship("CollaborationOffer", back_populates="order")
    business = db.relationship("User", foreign_keys=[business_id], backref="business_orders")
    influencer = db.relationship("User", foreign_keys=[influencer_id], backref="influencer_orders")
    creator_profile = db.relationship("CreatorProfile", backref="orders")
    submissions = db.relationship("Submission", back_populates="order", cascade="all, delete-orphan")
    events = db.relationship("OrderEvent", back_populates="order", cascade="all, delete-orphan")
    reviews = db.relationship("DealReview", back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint("campaign_id", "creator_profile_id", name="uq_campaign_creator_order"),
    )

    @property
    def amount(self) -> str:
        return f"{self.amount_cents / 100:,.2f}"

    @property
    def payout(self) -> str:
        return f"{self.influencer_payout_cents / 100:,.2f}"


class Submission(db.Model):
    __tablename__ = "submissions"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    influencer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    version = db.Column(db.Integer, default=1, nullable=False)
    video_url = db.Column(db.String(1000), nullable=False)
    notes = db.Column(db.Text)
    status = db.Column(db.String(30), default="under_review", nullable=False)
    review_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = db.Column(db.DateTime)

    order = db.relationship("Order", back_populates="submissions")
    influencer = db.relationship("User", backref="submissions")


class OrderEvent(db.Model):
    __tablename__ = "order_events"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    event_type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    order = db.relationship("Order", back_populates="events")
    actor = db.relationship("User", backref="order_events")
