from __future__ import annotations

import secrets

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.campaign import Campaign
from models.collaboration import Application
from models.creator import CreatorProfile
from models.social import CreatorSocialAccount
from services.matching_service import calculate_match_score
from services.offer_service import create_offer
from services.logging_service import log_audit_event
from services.platform_service import PLATFORM_KEYS, parse_social_accounts, replace_social_accounts, sync_creator_social_summary
from services.url_service import safe_https_url
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
        platform = platform.lower()
        if platform in PLATFORM_KEYS:
            query = query.join(CreatorProfile.user).join(CreatorSocialAccount).filter(CreatorSocialAccount.platform == platform)
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
                platforms="",
                verification_code=f"VP-{secrets.token_hex(3).upper()}",
            )
            db.session.add(profile)
        profile.display_name = request.form.get("display_name", current_user.display_name).strip()
        profile.niche = request.form.get("niche", "").strip()
        profile.audience_country = request.form.get("audience_country", "").strip()
        profile.engagement_rate = request.form.get("engagement_rate", type=float) or 0.0
        profile.starting_rate = request.form.get("starting_rate", type=int) or 0
        profile.media_kit_summary = request.form.get("media_kit_summary", "").strip()
        portfolio_input = request.form.get("portfolio_url", "").strip()
        profile.portfolio_url = safe_https_url(portfolio_input) if portfolio_input else None
        if portfolio_input and not profile.portfolio_url:
            flash("Portfolio links must use a safe public HTTPS URL.", "danger")
            return render_template("creator_onboarding.html", profile=profile)
        try:
            social_accounts = parse_social_accounts(request.form)
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template("creator_onboarding.html", profile=profile)
        social_links_changed = replace_social_accounts(current_user, social_accounts)
        if social_links_changed and profile.verification_status == "verified":
            profile.verification_status = "pending"
            profile.verification_notes = None
            profile.verified_at = None
        sync_creator_social_summary(profile)
        required = [profile.display_name, profile.niche, profile.platforms, profile.audience_country, profile.media_kit_summary, profile.social_proof_url]
        if not all(required):
            flash("Complete the profile and add the social account used for ownership review.", "danger")
            return render_template("creator_onboarding.html", profile=profile)
        if profile.starting_rate <= 0:
            flash("Enter a starting rate of at least $1 USD.", "danger")
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
        campaigns = Campaign.query.filter_by(business_id=current_user.id, status="open").all()
        scores = {campaign.id: calculate_match_score(campaign, creator) for campaign in campaigns}
    return render_template("creator_detail.html", creator=creator, campaigns=campaigns, scores=scores)


@creators_bp.route("/<int:creator_id>/invite", methods=["POST"])
@login_required
def invite_creator(creator_id):
    if not is_business():
        return "Access denied", 403
    creator = CreatorProfile.query.get_or_404(creator_id)
    if not current_user.phone_number:
        flash("Add your active brand phone number before selecting a creator.", "warning")
        return redirect(url_for("profile.edit_profile"))
    if not creator.user.phone_number:
        flash("This creator must add an active phone number before selection.", "warning")
        return redirect(url_for("creators.creator_detail", creator_id=creator.id))
    if creator.verification_status != "verified":
        flash("This creator is still completing social ownership review.", "warning")
        return redirect(url_for("creators.creator_detail", creator_id=creator.id))
    campaign = Campaign.query.filter_by(id=request.form.get("campaign_id", type=int), business_id=current_user.id).first_or_404()
    try:
        offer = create_offer(
            campaign,
            creator,
            current_user,
            request.form.get("offer_amount", type=int) or 0,
            request.form.get("message", "").strip(),
        )
        offer.application.match_score = calculate_match_score(campaign, creator)
        db.session.commit()
    except (IntegrityError, ValueError) as exc:
        db.session.rollback()
        flash(str(exc) or "This creator is already connected to that campaign.", "warning")
        return redirect(url_for("creators.creator_detail", creator_id=creator.id))
    flash("Offer sent. Payment unlocks only after the creator accepts.", "success")
    log_audit_event("offer_created", "Brand created a direct creator offer.", actor_user_id=current_user.id, target_user_id=creator.user_id, campaign_id=campaign.id, creator_profile_id=creator.id, metadata={"offer_id": offer.id, "amount_cents": offer.amount_cents})
    return redirect(url_for("campaigns.campaign_detail", campaign_id=campaign.id))
