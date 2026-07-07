from flask import Blueprint, render_template
from flask_login import current_user, login_required

from models.campaign import Campaign
from models.collaboration import Application
from models.order import Order
from models.offer import CollaborationOffer

business_bp = Blueprint("business", __name__, url_prefix="/business")


@business_bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role != "business":
        return "Access denied", 403
    campaigns = Campaign.query.filter_by(business_id=current_user.id).order_by(Campaign.created_at.desc()).all()
    applications = Application.query.join(Campaign).filter(Campaign.business_id == current_user.id).order_by(Application.created_at.desc()).all()
    orders = Order.query.filter_by(business_id=current_user.id).order_by(Order.created_at.desc()).all()
    offers = CollaborationOffer.query.filter_by(business_id=current_user.id).order_by(CollaborationOffer.created_at.desc()).all()
    return render_template("business_dashboard.html", campaigns=campaigns, applications=applications, orders=orders, offers=offers)
