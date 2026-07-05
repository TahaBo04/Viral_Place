from __future__ import annotations

import secrets

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.campaign import Campaign
from models.collaboration import Application
from models.creator import CreatorProfile
from services.matching_service import calculate_match_score
from services.order_service import select_application
from services.security_service import is_business, is_influencer

creators_bp = Blueprint("creators", __name__, url_prefix="/creators")


@creators_bp.route("/")
def list_creators():
    query = CreatorProfile.query.filter_by(verification_status="verified", availability="available")
    niche = request.args.get("niche", "").strip()
    platform = request.args.get("platform", "").strip()
    country = request.args.get("country", "").strip()
    if niche:
        query = query.filter(CreatorProfile.niche.ilike(f"%{niche}%"))
    if platform:
        query = query.filter(CreatorProfile.platforms.ilike(f"%{platform}%"))
    if country:
        query = query.filter(CreatorProfile.audience_country.ilike(f"%{country}%"))
    creators = query.order_by(CreatorProfile.followers.desc()).all()
    campaign = None
    scores = {}
    campaign_id = request.args.get("campaign_id", type=int)
    if campaign_id and current_user.is_authenticated:
        campaign = Campaign.query.filter_by(id=campaign_id, business_id=current_user.id).first()
        if campaign:
            scores = {creator.id: calculate_match_score(campaign, creator) for creator in creators}
    return render_template("creators_list.html", creators=creators, scores=scores, campaign=campaign)


@creators_bp.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    if not is_influencer():
        flash("Only influencer accounts have creator profiles.", "danger")
        return redirect(url_for("home"))
    profile = current_user.creator_profile
    if request.method == "POST":
        if profile is None:
            profile = CreatorProfile(
                user_id=current_user.id,
                display_name=current_user.display_name,
                verification_code=f"VP-{secrets.token_hex(3).upper()}",
            )
            db.session.add(profile)
        profile.display_name = request.form.get("display_name", current_user.display_name).strip()
        profile.niche = request.form.get("niche", "").strip()
        profile.platforms = request.form.get("platforms", "").strip()
        profile.audience_country = request.form.get("audience_country", "").strip()
        profile.followers = request.form.get("followers", type=int) or 0
        profile.engagement_rate = request.form.get("engagement_rate", type=float) or 0.0
        profile.starting_rate = request.form.get("starting_rate", type=int) or 0
        profile.media_kit_summary = request.form.get("media_kit_summary", "").strip()
        profile.portfolio_url = request.form.get("portfolio_url", "").strip()
        social_proof_url = request.form.get("social_proof_url", "").strip()
        if profile.social_proof_url and social_proof_url != profile.social_proof_url:
            profile.verification_status = "pending"
            profile.verification_notes = None
            profile.verified_at = None
        profile.social_proof_url = social_proof_url
        current_user.social_profile_url = social_proof_url
        required = [profile.display_name, profile.niche, profile.platforms, profile.audience_country, profile.media_kit_summary, profile.social_proof_url]
        if not all(required):
            flash("Complete the profile and add the social account used for ownership review.", "danger")
            return render_template("creator_onboarding.html", profile=profile)
        if not profile.social_proof_url.startswith(("https://", "http://")):
            flash("Provide a valid social profile URL for ownership review.", "danger")
            return render_template("creator_onboarding.html", profile=profile)
        db.session.commit()
        if profile.verification_status == "verified":
            flash("Creator profile updated.", "success")
        else:
            flash(f"Profile sent for review. Place {profile.verification_code} in your social bio until Viral Place approves it.", "success")
        return redirect(url_for("influencer.dashboard"))
    return render_template("creator_onboarding.html", profile=profile)


@creators_bp.route("/<int:creator_id>")
def creator_detail(creator_id):
    creator = CreatorProfile.query.get_or_404(creator_id)
    may_preview = current_user.is_authenticated and (
        current_user.id == creator.user_id or current_user.role == "admin"
    )
    if creator.verification_status != "verified" and not may_preview:
        return "Access denied", 403
    campaigns = []
    scores = {}
    if current_user.is_authenticated and current_user.role == "business":
        campaigns = Campaign.query.filter_by(business_id=current_user.id).filter(Campaign.status.in_(["open", "awaiting_selection"])).all()
        scores = {campaign.id: calculate_match_score(campaign, creator) for campaign in campaigns}
    return render_template("creator_detail.html", creator=creator, campaigns=campaigns, scores=scores)


@creators_bp.route("/<int:creator_id>/invite", methods=["POST"])
@login_required
def invite_creator(creator_id):
    if not is_business():
        return "Access denied", 403
    creator = CreatorProfile.query.get_or_404(creator_id)
    if not current_user.phone_number or not creator.user.phone_number:
        flash("Both parties need active phone contacts before selection.", "warning")
        return redirect(url_for("creators.creator_detail", creator_id=creator.id))
    if creator.verification_status != "verified":
        flash("This creator is still completing social ownership review.", "warning")
        return redirect(url_for("creators.creator_detail", creator_id=creator.id))
    campaign = Campaign.query.filter_by(id=request.form.get("campaign_id", type=int), business_id=current_user.id).first_or_404()
    application = Application(
        campaign_id=campaign.id,
        creator_profile_id=creator.id,
        sender_id=current_user.id,
        direction="business_invite",
        message=request.form.get("message", "").strip(),
        match_score=calculate_match_score(campaign, creator),
    )
    db.session.add(application)
    try:
        db.session.flush()
        order = select_application(application, campaign.budget_max * 100, current_user.id)
        campaign.status = "awaiting_payment"
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = Application.query.filter_by(campaign_id=campaign.id, creator_profile_id=creator.id).first()
        if existing and existing.order:
            return redirect(url_for("orders.order_detail", order_id=existing.order.id))
        flash("This creator is already connected to that campaign.", "info")
        return redirect(url_for("creators.creator_detail", creator_id=creator.id))
    flash("Creator selected. Complete payment to activate the assignment.", "success")
    return redirect(url_for("orders.order_detail", order_id=order.id))
