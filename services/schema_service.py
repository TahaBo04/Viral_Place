from sqlalchemy import inspect, text

from extensions import db


def apply_compatible_schema_updates() -> None:
    inspector = inspect(db.engine)
    if "users" not in inspector.get_table_names():
        return
    statements = []
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "phone_number" not in user_columns:
        statements.append("ALTER TABLE users ADD COLUMN phone_number VARCHAR(32)")
    if "phone_region" not in user_columns:
        statements.append("ALTER TABLE users ADD COLUMN phone_region VARCHAR(2)")
    if "phone_confirmed_at" not in user_columns:
        statements.append("ALTER TABLE users ADD COLUMN phone_confirmed_at TIMESTAMP")
    if "campaigns" in inspector.get_table_names():
        campaign_columns = {column["name"] for column in inspector.get_columns("campaigns")}
        if "visibility" not in campaign_columns:
            statements.append("ALTER TABLE campaigns ADD COLUMN visibility VARCHAR(20) DEFAULT 'public'")
        if "closed_at" not in campaign_columns:
            statements.append("ALTER TABLE campaigns ADD COLUMN closed_at TIMESTAMP")
    if "orders" in inspector.get_table_names():
        order_columns = {column["name"] for column in inspector.get_columns("orders")}
        if "offer_id" not in order_columns:
            statements.append("ALTER TABLE orders ADD COLUMN offer_id INTEGER REFERENCES collaboration_offers(id)")
    for statement in statements:
        db.session.execute(text(statement))
    if statements:
        db.session.commit()
    if "orders" in inspector.get_table_names():
        db.session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_offer_id ON orders (offer_id)"))
        db.session.commit()
    _backfill_profile_data()


def _backfill_profile_data() -> None:
    from models.campaign import Campaign
    from models.offer import CollaborationOffer
    from models.order import Order
    from models.social import CreatorSocialAccount
    from models.user import User
    from services.contact_service import phone_region
    from services.platform_service import infer_platform, platform_label
    from services.url_service import safe_https_url

    for user in User.query.all():
        if user.phone_number and not user.phone_region:
            user.phone_region = phone_region(user.phone_number)
        if user.role != "influencer" or user.social_accounts or not user.social_profile_url:
            continue
        url = safe_https_url(user.social_profile_url)
        if not url:
            continue
        platform = infer_platform(url)
        followers = user.creator_profile.followers if user.creator_profile else 0
        db.session.add(
            CreatorSocialAccount(
                user_id=user.id,
                platform=platform,
                other_name="Other" if platform == "other" else None,
                profile_url=url,
                audience_count=followers,
                is_primary=True,
            )
        )
        if user.creator_profile:
            user.creator_profile.platforms = platform_label(platform, "Other" if platform == "other" else None)

    for campaign in Campaign.query.all():
        campaign.visibility = "private" if campaign.flow_type == "managed" else (campaign.visibility or "public")
        if campaign.status == "awaiting_selection":
            campaign.status = "open"

    for order in Order.query.filter_by(offer_id=None).all():
        if not order.application or not order.creator_profile:
            continue
        offer = CollaborationOffer(
            application_id=order.application.id,
            campaign_id=order.campaign_id,
            business_id=order.business_id,
            creator_profile_id=order.creator_profile_id,
            amount_cents=order.amount_cents,
            minimum_rate_cents=order.creator_profile.starting_rate * 100,
            creator_payout_cents=order.influencer_payout_cents,
            status="accepted",
            message="Migrated accepted collaboration",
            responded_at=order.created_at,
        )
        db.session.add(offer)
        db.session.flush()
        order.offer_id = offer.id
    db.session.commit()
