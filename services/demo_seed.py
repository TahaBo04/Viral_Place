from werkzeug.security import generate_password_hash

from extensions import db
from models.campaign import Campaign
from models.collaboration import Application
from models.creator import CreatorProfile
from models.user import User
from services.matching_service import calculate_match_score


def _user(email: str, first_name: str, last_name: str, role: str, **kwargs) -> User:
    user = User.query.filter_by(email=email).first()
    if user:
        return user
    user = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=role,
        password_hash=generate_password_hash("viralplace123"),
        **kwargs,
    )
    db.session.add(user)
    db.session.flush()
    return user


def seed_demo_data() -> None:
    if User.query.filter_by(email="brand@viralplace.local").first():
        return

    brand = _user("brand@viralplace.local", "Maya", "Brands", "business", company_name="Northstar Labs", company_website="https://example.com")
    lina = _user("lina@viralplace.local", "Lina", "Reels", "influencer", social_profile_url="https://instagram.com/lina.reels")
    samir = _user("samir@viralplace.local", "Samir", "Fit", "influencer", social_profile_url="https://instagram.com/samir.fit")

    profiles = [
        CreatorProfile(user_id=lina.id, display_name="Lina Reels", niche="Beauty", platforms="TikTok, Instagram", audience_country="Morocco", followers=184000, engagement_rate=6.8, starting_rate=900, media_kit_summary="Fast product education, before-and-after routines, and high-save beauty tutorials.", portfolio_url="https://instagram.com/lina.reels", social_proof_url="https://instagram.com/lina.reels", verification_code="VP-DEMO01", verification_status="verified"),
        CreatorProfile(user_id=samir.id, display_name="Samir Fit", niche="Fitness", platforms="Instagram, YouTube Shorts", audience_country="France", followers=92000, engagement_rate=4.4, starting_rate=700, media_kit_summary="Practical fitness, supplement, apparel, and app-install content for a male 18-34 audience.", portfolio_url="https://instagram.com/samir.fit", social_proof_url="https://instagram.com/samir.fit", verification_code="VP-DEMO02", verification_status="verified"),
    ]
    db.session.add_all(profiles)
    db.session.flush()

    campaign = Campaign(
        business_id=brand.id,
        flow_type="marketplace",
        title="Launch a Gen Z skincare routine",
        industry="Beauty",
        target_niche="Beauty",
        target_platforms="TikTok, Instagram",
        target_country="Morocco",
        budget_min=600,
        budget_max=1600,
        goal="Drive creator-led awareness and trackable visits.",
        brief="Create authentic short-form videos showing the morning routine, texture, and product benefit.",
        deliverables="2 TikToks, 1 Instagram Reel, 3 story frames, 30-day paid usage rights.",
        status="awaiting_selection",
    )
    db.session.add(campaign)
    db.session.flush()
    db.session.add(Application(campaign_id=campaign.id, creator_profile_id=profiles[0].id, sender_id=lina.id, message="I can build this around a humid-weather morning routine.", match_score=calculate_match_score(campaign, profiles[0])))
    db.session.commit()
