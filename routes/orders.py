from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models.order import Order, Submission
from services.notification_service import notify, notify_admins
from services.order_service import add_order_event
from services.payment_service import create_checkout, stripe_configured, sync_checkout

orders_bp = Blueprint("orders", __name__, url_prefix="/orders")


def _can_view(order: Order) -> bool:
    return current_user.is_authenticated and (current_user.role == "admin" or current_user.id in (order.business_id, order.influencer_id))


@orders_bp.route("/<int:order_id>")
@login_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    if not _can_view(order):
        return "Access denied", 403
    return render_template("order_detail.html", order=order, stripe_ready=stripe_configured())


@orders_bp.route("/<int:order_id>/checkout", methods=["POST"])
@login_required
def checkout(order_id):
    order = Order.query.get_or_404(order_id)
    if current_user.id != order.business_id:
        return "Access denied", 403
    if order.payment_status == "paid":
        return redirect(url_for("orders.order_detail", order_id=order.id))
    try:
        checkout_url = create_checkout(order, request.url_root.rstrip("/"))
    except Exception:
        flash("Online checkout is temporarily unavailable. Viral Place can confirm a manual payment from the operations panel.", "warning")
        return redirect(url_for("orders.order_detail", order_id=order.id))
    return redirect(checkout_url)


@orders_bp.route("/<int:order_id>/payment/success")
@login_required
def payment_success(order_id):
    order = Order.query.get_or_404(order_id)
    if current_user.id != order.business_id:
        return "Access denied", 403
    session_id = request.args.get("session_id", "")
    if session_id and sync_checkout(order, session_id):
        flash("Payment confirmed. Viral Place has activated the order.", "success")
    else:
        flash("Payment is still being confirmed. Refresh this page shortly.", "info")
    return redirect(url_for("orders.order_detail", order_id=order.id))


@orders_bp.route("/<int:order_id>/submit", methods=["POST"])
@login_required
def submit_content(order_id):
    order = Order.query.get_or_404(order_id)
    if current_user.id != order.influencer_id:
        return "Access denied", 403
    if order.payment_status != "paid" or order.status not in ("in_production", "revision_requested"):
        flash("This order is not ready for content submission.", "warning")
        return redirect(url_for("orders.order_detail", order_id=order.id))
    video_url = request.form.get("video_url", "").strip()
    notes = request.form.get("notes", "").strip()
    if not video_url.startswith(("https://", "http://")):
        flash("Provide a valid secure video delivery link.", "danger")
        return redirect(url_for("orders.order_detail", order_id=order.id))
    version = len(order.submissions) + 1
    submission = Submission(order_id=order.id, influencer_id=current_user.id, version=version, video_url=video_url, notes=notes)
    db.session.add(submission)
    order.status = "under_review"
    order.campaign.status = "under_review"
    add_order_event(order, "content_submitted", f"Version {version} submitted for Viral Place review.", current_user.id)
    notify_admins("Content ready for review", f"Order #{order.id} has a new creator submission.", f"/admin/orders/{order.id}")
    notify(order.business_id, "Content under agency review", f"Viral Place is reviewing the creator submission for {order.campaign.title}.", f"/orders/{order.id}")
    db.session.commit()
    flash("Submission received. Viral Place will review it before customer delivery.", "success")
    return redirect(url_for("orders.order_detail", order_id=order.id))
