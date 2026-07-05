from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.campaign import Campaign
from models.collaboration import Application
from models.creator import CreatorProfile
from services.matching_service import calculate_match_score, score_creators_for_campaign
from services.order_service import create_order, select_application
from services.security_service import is_business, is_influencer

campaigns_bp = Blueprint("campaigns", __name__, url_prefix="/campaigns")


@campaigns_bp.route("/")
def list_campaigns():
    campaigns = Campaign.query.filter(Campaign.status.in_(["open", "awaiting_selection"])).order_by(Campaign.created_at.desc()).all()
    profile = current_user.creator_profile if current_user.is_authenticated and current_user.role == "influencer" else None
    scores = {campaign.id: calculate_match_score(campaign, profile) for campaign in campaigns} if profile else {}
    return render_template("campaigns_list.html", campaigns=campaigns, scores=scores)


@campaigns_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_campaign():
    if not is_business():
        flash("Use a business account to create a campaign.", "danger")
        return redirect(url_for("campaigns.list_campaigns"))

    if request.method == "POST":
        flow_type = request.form.get("flow_type", "marketplace")
        campaign = Campaign(
            business_id=current_user.id,
            flow_type=flow_type if flow_type in ("managed", "marketplace") else "marketplace",
            title=request.form.get("title", "").strip(),
            industry=request.form.get("industry", "").strip(),
            target_niche=request.form.get("target_niche", "").strip(),
            target_platforms=request.form.get("target_platforms", "").strip(),
            target_country=request.form.get("target_country", "").strip(),
            budget_min=request.form.get("budget_min", type=int) or 0,
            budget_max=request.form.get("budget_max", type=int) or 0,
            goal=request.form.get("goal", "").strip(),
            brief=request.form.get("brief", "").strip(),
            deliverables=request.form.get("deliverables", "").strip(),
            status="awaiting_payment" if flow_type == "managed" else "open",
        )
        required = [campaign.title, campaign.industry, campaign.target_niche, campaign.target_platforms, campaign.target_country, campaign.goal, campaign.brief, campaign.deliverables]
        if not all(required) or campaign.budget_max <= 0:
            flash("Complete the campaign details and enter a valid budget.", "danger")
            return render_template("campaign_new.html")
        if campaign.budget_min > campaign.budget_max:
            flash("Minimum budget cannot exceed maximum budget.", "danger")
            return render_template("campaign_new.html")

        db.session.add(campaign)
        db.session.flush()
        if campaign.flow_type == "managed":
            order = create_order(campaign, campaign.budget_max * 100, customer_notes="Managed creator sourcing by Viral Place")
            db.session.commit()
            flash("Brief created. Secure payment to start Viral Place sourcing.", "success")
            return redirect(url_for("orders.order_detail", order_id=order.id))

        db.session.commit()
        flash("Campaign is live. Creators can now apply.", "success")
        return redirect(url_for("campaigns.campaign_detail", campaign_id=campaign.id))

    return render_template("campaign_new.html")


@campaigns_bp.route("/<int:campaign_id>")
def campaign_detail(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    scored_creators = []
    my_application = None
    if current_user.is_authenticated and current_user.id == campaign.business_id:
        scored_creators = score_creators_for_campaign(campaign, CreatorProfile.query.order_by(CreatorProfile.followers.desc()).all())
    elif current_user.is_authenticated and current_user.role == "influencer" and current_user.creator_profile:
        my_application = Application.query.filter_by(campaign_id=campaign.id, creator_profile_id=current_user.creator_profile.id).first()
        scored_creators = [(current_user.creator_profile, calculate_match_score(campaign, current_user.creator_profile))]
    return render_template("campaign_detail.html", campaign=campaign, scored_creators=scored_creators, my_application=my_application)


@campaigns_bp.route("/<int:campaign_id>/apply", methods=["GET", "POST"])
@login_required
def apply(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if not is_influencer():
        flash("Use an influencer account to apply.", "danger")
        return redirect(url_for("campaigns.campaign_detail", campaign_id=campaign.id))
    if campaign.flow_type != "marketplace" or campaign.status not in ("open", "awaiting_selection"):
        flash("This campaign is not accepting applications.", "warning")
        return redirect(url_for("campaigns.campaign_detail", campaign_id=campaign.id))
    if current_user.creator_profile is None:
        flash("Complete your creator profile before applying.", "warning")
        return redirect(url_for("creators.onboarding"))
    if current_user.creator_profile.verification_status != "verified":
        flash("Viral Place must confirm control of your social account before you can apply.", "warning")
        return redirect(url_for("creators.onboarding"))

    profile = current_user.creator_profile
    score = calculate_match_score(campaign, profile)
    if request.method == "POST":
        application = Application(
            campaign_id=campaign.id,
            creator_profile_id=profile.id,
            sender_id=current_user.id,
            direction="influencer_application",
            message=request.form.get("message", "").strip(),
            match_score=score,
        )
        db.session.add(application)
        campaign.status = "awaiting_selection"
        try:
            db.session.commit()
            flash("Application sent. The company can now shortlist or select you.", "success")
        except IntegrityError:
            db.session.rollback()
            flash("You already applied to this campaign.", "info")
        return redirect(url_for("campaigns.campaign_detail", campaign_id=campaign.id))
    return render_template("campaign_apply.html", campaign=campaign, profile=profile, score=score)


@campaigns_bp.route("/<int:campaign_id>/applications/<int:application_id>/select", methods=["POST"])
@login_required
def select_creator(campaign_id, application_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if current_user.id != campaign.business_id:
        return "Access denied", 403
    application = Application.query.filter_by(id=application_id, campaign_id=campaign.id).first_or_404()
    if application.order:
        return redirect(url_for("orders.order_detail", order_id=application.order.id))
    order = select_application(application, campaign.budget_max * 100, current_user.id)
    campaign.status = "awaiting_payment"
    db.session.commit()
    flash("Creator selected. Complete payment to notify them to begin production.", "success")
    return redirect(url_for("orders.order_detail", order_id=order.id))
