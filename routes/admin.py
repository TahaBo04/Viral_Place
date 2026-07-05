from datetime import datetime
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models.creator import CreatorProfile
from models.order import Order, Submission
from services.notification_service import notify
from services.order_service import add_order_event, assign_creator, mark_order_paid
from services.payment_service import refund_order

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            return "Access denied", 403
        return func(*args, **kwargs)
    return wrapper


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    orders = Order.query.order_by(Order.updated_at.desc()).all()
    pending_creators = CreatorProfile.query.filter_by(verification_status="pending").order_by(CreatorProfile.updated_at.asc()).all()
    counts = {
        "awaiting_payment": sum(o.payment_status == "unpaid" for o in orders),
        "paid_unassigned": sum(o.status == "paid_unassigned" for o in orders),
        "under_review": sum(o.status == "under_review" for o in orders),
        "ready_payout": sum(o.payout_status == "ready" for o in orders),
    }
    return render_template("admin_dashboard.html", orders=orders, counts=counts, pending_creators=pending_creators)


@admin_bp.route("/creators/<int:creator_id>/verification", methods=["POST"])
@login_required
@admin_required
def review_creator(creator_id):
    creator = CreatorProfile.query.get_or_404(creator_id)
    action = request.form.get("action")
    notes = request.form.get("notes", "").strip()
    if action == "approve":
        creator.verification_status = "verified"
        creator.verified_at = datetime.utcnow()
        creator.verification_notes = notes or "Social account ownership confirmed by Viral Place."
        notify(creator.user_id, "Creator profile approved", "Your social account ownership is confirmed. You can now appear in discovery and apply to campaigns.", "/influencer/dashboard")
        flash("Creator approved and notified.", "success")
    elif action == "reject":
        creator.verification_status = "rejected"
        creator.verified_at = None
        creator.verification_notes = notes or "We could not confirm social account ownership. Add the supplied code to your social bio and resubmit."
        notify(creator.user_id, "Creator review needs attention", creator.verification_notes, "/creators/onboarding")
        flash("Creator review returned with instructions.", "warning")
    else:
        flash("Choose approve or return for correction.", "danger")
        return redirect(url_for("admin.dashboard"))
    db.session.commit()
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/orders/<int:order_id>")
@login_required
@admin_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    creators = CreatorProfile.query.filter_by(availability="available", verification_status="verified").order_by(CreatorProfile.followers.desc()).all()
    return render_template("admin_order.html", order=order, creators=creators)


@admin_bp.route("/orders/<int:order_id>/assign", methods=["POST"])
@login_required
@admin_required
def assign(order_id):
    order = Order.query.get_or_404(order_id)
    creator = CreatorProfile.query.get_or_404(request.form.get("creator_profile_id", type=int))
    try:
        assign_creator(order, creator, current_user.id)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("admin.order_detail", order_id=order.id))
    flash("Creator assigned. If payment is secured, they were notified immediately.", "success")
    return redirect(url_for("admin.order_detail", order_id=order.id))


@admin_bp.route("/orders/<int:order_id>/mark-paid", methods=["POST"])
@login_required
@admin_required
def mark_paid(order_id):
    order = Order.query.get_or_404(order_id)
    mark_order_paid(order, payment_intent_id=request.form.get("reference", "manual"), actor_id=current_user.id)
    flash("Payment marked as received and workflow activated.", "success")
    return redirect(url_for("admin.order_detail", order_id=order.id))


@admin_bp.route("/orders/<int:order_id>/submissions/<int:submission_id>/review", methods=["POST"])
@login_required
@admin_required
def review_submission(order_id, submission_id):
    order = Order.query.get_or_404(order_id)
    submission = Submission.query.filter_by(id=submission_id, order_id=order.id).first_or_404()
    action = request.form.get("action")
    notes = request.form.get("review_notes", "").strip()
    submission.review_notes = notes
    submission.reviewed_at = datetime.utcnow()

    if action == "approve":
        submission.status = "approved"
        order.status = "delivered"
        order.campaign.status = "delivered"
        order.payout_status = "ready"
        order.completed_at = datetime.utcnow()
        add_order_event(order, "approved", "Viral Place approved the content and released it to the customer.", current_user.id)
        notify(order.business_id, "Content approved and delivered", f"Your final content for {order.campaign.title} is ready in the order workspace.", f"/orders/{order.id}")
        notify(order.influencer_id, "Content approved", f"Viral Place approved your submission. Your payout is now ready for processing.", f"/orders/{order.id}")
        flash("Content approved, delivered to the customer, and queued for payout.", "success")
    elif action == "revision":
        submission.status = "revision_requested"
        order.status = "revision_requested"
        order.campaign.status = "revision_requested"
        add_order_event(order, "revision_requested", notes or "Viral Place requested a more efficient revision.", current_user.id)
        notify(order.influencer_id, "Revision requested", notes or "Viral Place requested a revision before customer delivery.", f"/orders/{order.id}")
        notify(order.business_id, "Creator revision in progress", "Viral Place requested improvements before delivering your content.", f"/orders/{order.id}")
        flash("Revision request sent to the influencer.", "success")
    elif action == "refund":
        submission.status = "rejected"
        order.admin_notes = notes
        db.session.flush()
        try:
            refund_order(order, actor_id=current_user.id)
            flash("Order refunded and both parties notified.", "success")
        except Exception as exc:
            db.session.rollback()
            flash(f"Refund could not be completed: {exc}", "danger")
            return redirect(url_for("admin.order_detail", order_id=order.id))
    else:
        flash("Choose approve, request revision, or refund.", "danger")
        return redirect(url_for("admin.order_detail", order_id=order.id))

    db.session.commit()
    return redirect(url_for("admin.order_detail", order_id=order.id))


@admin_bp.route("/orders/<int:order_id>/mark-payout", methods=["POST"])
@login_required
@admin_required
def mark_payout(order_id):
    order = Order.query.get_or_404(order_id)
    if order.payout_status != "ready":
        flash("This payout is not ready yet.", "warning")
        return redirect(url_for("admin.order_detail", order_id=order.id))
    order.payout_status = "paid"
    order.status = "complete"
    order.campaign.status = "complete"
    add_order_event(order, "payout_sent", "Influencer payout marked as sent by Viral Place.", current_user.id)
    if order.influencer_id:
        notify(order.influencer_id, "Payout sent", f"Your ${order.payout} payout for {order.campaign.title} was sent.", f"/orders/{order.id}")
    db.session.commit()
    flash("Influencer payout marked as paid.", "success")
    return redirect(url_for("admin.order_detail", order_id=order.id))
