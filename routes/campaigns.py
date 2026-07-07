from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.campaign import Campaign
from models.collaboration import Application
from models.creator import CreatorProfile
from services.campaign_access_service import can_apply_to_campaign, can_view_campaign
from services.matching_service import calculate_match_score, score_creators_for_campaign
from services.offer_service import close_campaign, create_offer
from services.platform_service import PLATFORM_KEYS
from services.logging_service import log_audit_event
from services.security_service import is_business, is_influencer

campaigns_bp = Blueprint("campaigns", __name__, url_prefix="/campaigns")


@campaigns_bp.route("/")
def list_campaigns():
    campaigns = Campaign.query.filter_by(status="open", visibility="public").order_by(Campaign.created_at.desc()).all()
    profile = current_user.creator_profile if current_user.is_authenticated and current_user.role == "influencer" else None
    scores = {campaign.id: calculate_match_score(campaign, profile) for campaign in campaigns} if profile else {}
    return render_template("campaigns_list.html", campaigns=campaigns, scores=scores)


@campaigns_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_campaign():
    if not is_business():
        flash("Use a business account to create a campaign.", "danger")
        return redirect(url_for("campaigns.list_campaigns"))
    if not current_user.phone_number:
        flash("Add an active phone number before starting a campaign.", "warning")
        return redirect(url_for("profile.edit_profile"))

    if request.method == "POST":
        campaign_mode = request.form.get("campaign_mode", "public")
        flow_type = "managed" if campaign_mode == "managed" else "marketplace"
        visibility = "public" if campaign_mode == "public" else "private"
        selected_platforms = list(dict.fromkeys(request.form.getlist("target_platforms")))
        if not selected_platforms or any(key not in PLATFORM_KEYS for key in selected_platforms):
            flash("Select at least one supported target platform.", "danger")
            return render_template("campaign_new.html")
        other_target = request.form.get("target_platform_other", "").strip()
        if "other" in selected_platforms and not 2 <= len(other_target) <= 60:
            flash("Name the target platform selected as Other.", "danger")
            return render_template("campaign_new.html")
        platform_tokens = [f"other:{other_target}" if key == "other" else key for key in selected_platforms]
        campaign = Campaign(
            business_id=current_user.id,
            flow_type=flow_type,
            visibility=visibility,
            title=request.form.get("title", "").strip(),
            industry=request.form.get("industry", "").strip(),
            target_niche=request.form.get("target_niche", "").strip(),
            target_platforms=",".join(platform_tokens),
            target_country=request.form.get("target_country", "").strip(),
            budget_min=request.form.get("budget_min", type=int) or 0,
            budget_max=request.form.get("budget_max", type=int) or 0,
            goal=request.form.get("goal", "").strip(),
            brief=request.form.get("brief", "").strip(),
            deliverables=request.form.get("deliverables", "").strip(),
            status="open",
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
        db.session.commit()
        if campaign.flow_type == "managed":
            flash("Managed brief created. Operations will recommend creators before any offer or payment.", "success")
        elif campaign.visibility == "private":
            flash("Private campaign created. Only invited creators and operations can view it.", "success")
        else:
            flash("Public campaign is live. Creators can now apply.", "success")
        return redirect(url_for("campaigns.campaign_detail", campaign_id=campaign.id))

    return render_template("campaign_new.html")


@campaigns_bp.route("/<int:campaign_id>")
def campaign_detail(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if not can_view_campaign(campaign):
        abort(404)
    scored_creators = []
    my_application = None
    if current_user.is_authenticated and current_user.id == campaign.business_id:
        creators = CreatorProfile.query.filter_by(verification_status="verified", availability="available").order_by(CreatorProfile.followers.desc()).all()
        scored_creators = score_creators_for_campaign(campaign, creators)
    elif current_user.is_authenticated and current_user.role == "influencer" and current_user.creator_profile:
        my_application = Application.query.filter_by(campaign_id=campaign.id, creator_profile_id=current_user.creator_profile.id).first()
        scored_creators = [(current_user.creator_profile, calculate_match_score(campaign, current_user.creator_profile))]
    return render_template("campaign_detail.html", campaign=campaign, scored_creators=scored_creators, my_application=my_application)


@campaigns_bp.route("/<int:campaign_id>/apply", methods=["GET", "POST"])
@login_required
def apply(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if campaign.visibility == "private" and not can_view_campaign(campaign):
        abort(404)
    if not is_influencer():
        flash("Use an influencer account to apply.", "danger")
        return redirect(url_for("campaigns.campaign_detail", campaign_id=campaign.id))
    if not can_apply_to_campaign(campaign):
        flash("This campaign is not accepting applications.", "warning")
        return redirect(url_for("campaigns.campaign_detail", campaign_id=campaign.id))
    if current_user.creator_profile is None:
        flash("Complete your creator profile before applying.", "warning")
        return redirect(url_for("creators.onboarding"))
    if not current_user.phone_number:
        flash("Add an active phone number before applying to a campaign.", "warning")
        return redirect(url_for("profile.edit_profile"))
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
    if not current_user.phone_number:
        flash("Add your active brand phone number before selecting a creator.", "warning")
        return redirect(url_for("profile.edit_profile"))
    if not application.creator_profile.user.phone_number:
        flash("This creator must add an active phone number before selection.", "warning")
        return redirect(url_for("campaigns.campaign_detail", campaign_id=campaign.id))
    try:
        offer = create_offer(
            campaign,
            application.creator_profile,
            current_user,
            request.form.get("offer_amount", type=int) or 0,
            request.form.get("message", "").strip(),
            application=application,
        )
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("campaigns.campaign_detail", campaign_id=campaign.id))
    flash("Offer sent. Payment unlocks after the creator accepts.", "success")
    log_audit_event("offer_created", "Brand created an offer for a campaign applicant or recommendation.", actor_user_id=current_user.id, target_user_id=application.creator_profile.user_id, campaign_id=campaign.id, creator_profile_id=application.creator_profile_id, metadata={"offer_id": offer.id, "amount_cents": offer.amount_cents})
    return redirect(url_for("campaigns.campaign_detail", campaign_id=campaign.id))


@campaigns_bp.route("/<int:campaign_id>/close", methods=["POST"])
@login_required
def close(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    try:
        close_campaign(campaign, current_user)
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("campaigns.campaign_detail", campaign_id=campaign.id))
    flash("Campaign closed. Pending offers were withdrawn.", "success")
    log_audit_event("campaign_closed", "Brand closed a campaign and withdrew pending offers.", actor_user_id=current_user.id, campaign_id=campaign.id)
    return redirect(url_for("campaigns.campaign_detail", campaign_id=campaign.id))
