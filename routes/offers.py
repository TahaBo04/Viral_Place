from flask import Blueprint, flash, redirect, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from models.offer import CollaborationOffer
from services.logging_service import log_audit_event
from services.offer_service import accept_offer, decline_offer, withdraw_offer


offers_bp = Blueprint("offers", __name__, url_prefix="/offers")


@offers_bp.route("/<int:offer_id>/accept", methods=["POST"])
@login_required
def accept(offer_id):
    offer = CollaborationOffer.query.get_or_404(offer_id)
    try:
        order = accept_offer(offer, current_user)
    except IntegrityError:
        from extensions import db
        db.session.rollback()
        flash("This offer was already processed.", "info")
        return redirect(url_for("influencer.dashboard"))
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("influencer.dashboard"))
    log_audit_event(
        "offer_accepted",
        "Creator accepted a collaboration offer.",
        actor_user_id=current_user.id,
        campaign_id=offer.campaign_id,
        creator_profile_id=offer.creator_profile_id,
        order_id=order.id,
        metadata={"offer_id": offer.id, "amount_cents": offer.amount_cents},
    )
    flash("Offer accepted. The brand can now secure payment.", "success")
    return redirect(url_for("orders.order_detail", order_id=order.id))


@offers_bp.route("/<int:offer_id>/decline", methods=["POST"])
@login_required
def decline(offer_id):
    offer = CollaborationOffer.query.get_or_404(offer_id)
    try:
        decline_offer(offer, current_user)
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("influencer.dashboard"))
    log_audit_event(
        "offer_declined",
        "Creator declined a collaboration offer.",
        actor_user_id=current_user.id,
        campaign_id=offer.campaign_id,
        creator_profile_id=offer.creator_profile_id,
        metadata={"offer_id": offer.id},
    )
    flash("Offer declined. No order or payment was created.", "info")
    return redirect(url_for("influencer.dashboard"))


@offers_bp.route("/<int:offer_id>/withdraw", methods=["POST"])
@login_required
def withdraw(offer_id):
    offer = CollaborationOffer.query.get_or_404(offer_id)
    try:
        withdraw_offer(offer, current_user)
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("business.dashboard"))
    log_audit_event(
        "offer_withdrawn",
        "Brand withdrew a pending collaboration offer.",
        actor_user_id=current_user.id,
        campaign_id=offer.campaign_id,
        creator_profile_id=offer.creator_profile_id,
        metadata={"offer_id": offer.id},
    )
    flash("Pending offer withdrawn.", "success")
    return redirect(url_for("campaigns.campaign_detail", campaign_id=offer.campaign_id))
