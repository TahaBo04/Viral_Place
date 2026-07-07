from flask_login import current_user

from models.collaboration import Application


def can_view_campaign(campaign, user=None) -> bool:
    viewer = user or current_user
    if campaign.visibility == "public":
        return True
    if not getattr(viewer, "is_authenticated", False):
        return False
    if viewer.role == "admin" or viewer.id == campaign.business_id:
        return True
    if viewer.role != "influencer" or not viewer.creator_profile:
        return False
    application = Application.query.filter_by(
        campaign_id=campaign.id,
        creator_profile_id=viewer.creator_profile.id,
    ).first()
    if application is None:
        return False
    if application.order is not None or application.status in ("accepted", "accepted_pending_payment", "selected"):
        return True
    if not campaign.is_open:
        return False
    return application.status not in ("declined", "rejected", "withdrawn")


def can_apply_to_campaign(campaign) -> bool:
    return campaign.visibility == "public" and campaign.flow_type == "marketplace" and campaign.is_open
