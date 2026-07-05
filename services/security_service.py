from flask_login import current_user


def is_business() -> bool:
    return current_user.is_authenticated and current_user.role == "business"


def is_influencer() -> bool:
    return current_user.is_authenticated and current_user.role == "influencer"


def is_admin() -> bool:
    return current_user.is_authenticated and current_user.role == "admin"
