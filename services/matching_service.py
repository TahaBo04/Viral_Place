from __future__ import annotations

from models.campaign import Campaign
from models.creator import CreatorProfile


def _tokens(value: str) -> set[str]:
    return {
        token.strip().lower()
        for token in (value or "").replace("/", ",").replace("|", ",").split(",")
        if token.strip()
    }


def calculate_match_score(campaign: Campaign, creator: CreatorProfile) -> int:
    score = 0

    campaign_niche = (campaign.target_niche or "").strip().lower()
    creator_niche = (creator.niche or "").strip().lower()
    if campaign_niche and creator_niche:
        if campaign_niche == creator_niche:
            score += 28
        elif campaign_niche in creator_niche or creator_niche in campaign_niche:
            score += 18

    campaign_platforms = _tokens(campaign.target_platforms)
    creator_platforms = _tokens(creator.platforms)
    if campaign_platforms and creator_platforms:
        overlap = len(campaign_platforms & creator_platforms)
        score += min(24, overlap * 12)

    if (campaign.target_country or "").strip().lower() == (creator.audience_country or "").strip().lower():
        score += 18

    if campaign.budget_min <= creator.starting_rate <= campaign.budget_max:
        score += 16
    elif creator.starting_rate <= campaign.budget_max:
        score += 9

    if creator.engagement_rate >= 5:
        score += 8
    elif creator.engagement_rate >= 3:
        score += 5

    if creator.followers >= 100000:
        score += 6
    elif creator.followers >= 25000:
        score += 4

    return max(0, min(100, score))


def score_creators_for_campaign(campaign: Campaign, creators: list[CreatorProfile]) -> list[tuple[CreatorProfile, int]]:
    scored = [(creator, calculate_match_score(campaign, creator)) for creator in creators]
    return sorted(scored, key=lambda item: item[1], reverse=True)
