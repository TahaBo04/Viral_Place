from __future__ import annotations

from models.social import CreatorSocialAccount
from services.url_service import safe_https_url


PLATFORMS = (
    ("tiktok", "TikTok"),
    ("instagram", "Instagram"),
    ("youtube", "YouTube"),
    ("facebook", "Facebook"),
    ("x", "X"),
    ("twitch", "Twitch"),
    ("snapchat", "Snapchat"),
    ("linkedin", "LinkedIn"),
    ("pinterest", "Pinterest"),
    ("threads", "Threads"),
    ("other", "Other"),
)
PLATFORM_KEYS = {key for key, _label in PLATFORMS}
PLATFORM_LABELS = dict(PLATFORMS)
PLATFORM_HOSTS = {
    "tiktok": {"tiktok.com"},
    "instagram": {"instagram.com"},
    "youtube": {"youtube.com", "youtu.be"},
    "facebook": {"facebook.com", "fb.com"},
    "x": {"x.com", "twitter.com"},
    "twitch": {"twitch.tv"},
    "snapchat": {"snapchat.com"},
    "linkedin": {"linkedin.com"},
    "pinterest": {"pinterest.com", "pin.it"},
    "threads": {"threads.net"},
}
PLATFORM_ICON_SLUGS = {
    "tiktok": "tiktok",
    "instagram": "instagram",
    "youtube": "youtube",
    "facebook": "facebook",
    "x": "x",
    "twitch": "twitch",
    "snapchat": "snapchat",
    "linkedin": "linkedin",
    "pinterest": "pinterest",
    "threads": "threads",
}


def platform_label(key: str, other_name: str | None = None) -> str:
    return other_name if key == "other" and other_name else PLATFORM_LABELS.get(key, key.title())


def platform_icon_url(key: str) -> str | None:
    slug = PLATFORM_ICON_SLUGS.get(key)
    return f"https://cdn.simpleicons.org/{slug}/9CFF00" if slug else None


def campaign_platform_labels(value: str) -> list[str]:
    labels = []
    for token in (value or "").split(","):
        token = token.strip()
        if token.startswith("other:"):
            labels.append(token.split(":", 1)[1])
        elif token:
            labels.append(platform_label(token))
    return labels


def infer_platform(url: str) -> str:
    for key, hosts in PLATFORM_HOSTS.items():
        if safe_https_url(url, hosts):
            return key
    return "other"


def parse_social_accounts(form) -> list[dict]:
    selected = list(dict.fromkeys(form.getlist("platforms")))
    if not selected or any(key not in PLATFORM_KEYS for key in selected):
        raise ValueError("Select at least one supported social platform.")
    accounts = []
    primary = form.get("primary_platform")
    for key in selected:
        url = form.get(f"social_url_{key}", "").strip()
        count = form.get(f"audience_count_{key}", type=int)
        other_name = form.get("other_platform_name", "").strip() if key == "other" else None
        if count is None or count < 0:
            raise ValueError(f"Enter a valid audience count for {platform_label(key, other_name)}.")
        if key == "other" and not 2 <= len(other_name or "") <= 60:
            raise ValueError("Name the platform selected as Other.")
        safe_url = safe_https_url(url, PLATFORM_HOSTS.get(key))
        if not safe_url:
            raise ValueError(f"Enter a safe official HTTPS profile link for {platform_label(key, other_name)}.")
        accounts.append(
            {
                "platform": key,
                "other_name": other_name,
                "profile_url": safe_url,
                "audience_count": count,
                "is_primary": key == primary,
            }
        )
    if not any(account["is_primary"] for account in accounts):
        accounts[0]["is_primary"] = True
    return accounts


def replace_social_accounts(user, account_data: list[dict]) -> bool:
    old_links = {(account.platform, account.other_name or "", account.profile_url) for account in user.social_accounts}
    new_links = {(item["platform"], item["other_name"] or "", item["profile_url"]) for item in account_data}
    changed_links = old_links != new_links
    existing = {account.platform: account for account in user.social_accounts}
    selected = {item["platform"] for item in account_data}
    for platform, account in list(existing.items()):
        if platform not in selected:
            user.social_accounts.remove(account)
    for item in account_data:
        account = existing.get(item["platform"])
        if account is None:
            user.social_accounts.append(CreatorSocialAccount(**item))
            continue
        account.other_name = item["other_name"]
        account.profile_url = item["profile_url"]
        account.audience_count = item["audience_count"]
        account.is_primary = item["is_primary"]
    user.social_profile_url = next(item["profile_url"] for item in account_data if item["is_primary"])
    return changed_links


def sync_creator_social_summary(profile) -> None:
    accounts = profile.user.social_accounts
    profile.platforms = ", ".join(platform_label(account.platform, account.other_name) for account in accounts)
    profile.followers = max((account.audience_count for account in accounts), default=0)
    primary = next((account for account in accounts if account.is_primary), accounts[0] if accounts else None)
    profile.social_proof_url = primary.profile_url if primary else None
