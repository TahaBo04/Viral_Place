from datetime import datetime

from flask import current_app

from extensions import db
from models.collaboration import Application
from models.offer import CollaborationOffer
from services.notification_service import notify, notify_admins
from services.order_service import add_order_event, create_order, payout_percent


def create_offer(campaign, creator_profile, business, amount_usd: int, message: str = "", application=None):
    if campaign.business_id != business.id or business.role != "business":
        raise ValueError("Only the campaign owner can make this offer.")
    if not campaign.is_open:
        raise ValueError("This campaign is closed.")
    if creator_profile.verification_status != "verified":
        raise ValueError("Only verified creators can receive offers.")
    if not business.phone_number or not creator_profile.user.phone_number:
        raise ValueError("Both parties need active phone contacts before an offer.")
    maximum = int(current_app.config.get("MAX_OFFER_USD", 1_000_000))
    if amount_usd < creator_profile.starting_rate or amount_usd > maximum:
        raise ValueError(f"Offer must be between ${creator_profile.starting_rate:,} and ${maximum:,} USD.")
    if application is None:
        application = Application.query.filter_by(campaign_id=campaign.id, creator_profile_id=creator_profile.id).first()
    if application is None:
        application = Application(
            campaign_id=campaign.id,
            creator_profile_id=creator_profile.id,
            sender_id=business.id,
            direction="business_invite",
            status="invited",
            message=message,
        )
        db.session.add(application)
        db.session.flush()
    active = CollaborationOffer.query.filter_by(application_id=application.id).filter(
        CollaborationOffer.status.in_(("pending", "accepted"))
    ).first()
    if active:
        raise ValueError("This creator already has an active offer for the campaign.")
    amount_cents = amount_usd * 100
    offer = CollaborationOffer(
        application_id=application.id,
        campaign_id=campaign.id,
        business_id=business.id,
        creator_profile_id=creator_profile.id,
        amount_cents=amount_cents,
        minimum_rate_cents=creator_profile.starting_rate * 100,
        creator_payout_cents=int(amount_cents * payout_percent() / 100),
        message=message or application.message,
    )
    application.status = "offer_pending"
    db.session.add(offer)
    db.session.flush()
    notify(
        creator_profile.user_id,
        "New creator offer",
        f"{business.display_name} offered ${offer.amount} for {campaign.title}. Review and accept or decline.",
        f"/campaigns/{campaign.id}",
    )
    notify_admins("Creator offer sent", f"Offer #{offer.id} is awaiting creator acceptance.", f"/campaigns/{campaign.id}")
    db.session.commit()
    return offer


def accept_offer(offer, creator_user):
    if offer.creator_profile.user_id != creator_user.id or offer.status != "pending":
        raise ValueError("This offer cannot be accepted.")
    if not offer.campaign.is_open:
        raise ValueError("This campaign is closed.")
    offer.status = "accepted"
    offer.responded_at = datetime.utcnow()
    offer.application.status = "accepted_pending_payment"
    order = create_order(
        offer.campaign,
        offer.amount_cents,
        creator_profile=offer.creator_profile,
        application=offer.application,
        payout_cents=offer.creator_payout_cents,
        offer=offer,
    )
    add_order_event(order, "offer_accepted", "Creator accepted the offer. Customer payment is now available.", creator_user.id)
    notify(offer.business_id, "Offer accepted", f"{offer.creator_profile.display_name} accepted your offer for {offer.campaign.title}. Payment is now available.", f"/orders/{order.id}")
    notify_admins("Offer accepted", f"Order #{order.id} is ready for customer payment.", f"/admin/orders/{order.id}")
    db.session.commit()
    return order


def decline_offer(offer, creator_user):
    if offer.creator_profile.user_id != creator_user.id or offer.status != "pending":
        raise ValueError("This offer cannot be declined.")
    offer.status = "declined"
    offer.responded_at = datetime.utcnow()
    offer.application.status = "declined"
    notify(offer.business_id, "Offer declined", f"{offer.creator_profile.display_name} declined the offer for {offer.campaign.title}.", f"/campaigns/{offer.campaign_id}")
    db.session.commit()


def withdraw_offer(offer, business):
    if offer.business_id != business.id or offer.status != "pending":
        raise ValueError("This offer cannot be withdrawn.")
    offer.status = "withdrawn"
    offer.withdrawn_at = datetime.utcnow()
    offer.application.status = "withdrawn"
    notify(offer.creator_profile.user_id, "Offer withdrawn", f"The offer for {offer.campaign.title} was withdrawn by the brand.", f"/influencer/dashboard")
    db.session.commit()


def close_campaign(campaign, business):
    if campaign.business_id != business.id or not campaign.is_open:
        raise ValueError("This campaign cannot be closed.")
    campaign.status = "closed"
    campaign.closed_at = datetime.utcnow()
    pending = CollaborationOffer.query.filter_by(campaign_id=campaign.id, status="pending").all()
    for offer in pending:
        offer.status = "withdrawn"
        offer.withdrawn_at = datetime.utcnow()
        offer.application.status = "withdrawn"
        notify(offer.creator_profile.user_id, "Campaign closed", f"The pending offer for {campaign.title} was withdrawn when the campaign closed.", "/influencer/dashboard")
    db.session.commit()
