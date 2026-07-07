from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from models.collaboration import Application
from models.order import Order
from models.offer import CollaborationOffer

influencer_bp = Blueprint("influencer", __name__, url_prefix="/influencer")


@influencer_bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role != "influencer":
        return "Access denied", 403
    if current_user.creator_profile is None:
        flash("Complete your creator profile to browse and apply to paid briefs.", "info")
        return redirect(url_for("creators.onboarding"))
    applications = Application.query.filter_by(creator_profile_id=current_user.creator_profile.id).order_by(Application.created_at.desc()).all()
    orders = Order.query.filter_by(influencer_id=current_user.id).order_by(Order.created_at.desc()).all()
    offers = CollaborationOffer.query.filter_by(creator_profile_id=current_user.creator_profile.id).order_by(CollaborationOffer.created_at.desc()).all()
    return render_template("influencer_dashboard.html", applications=applications, orders=orders, offers=offers)
