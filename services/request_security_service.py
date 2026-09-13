import re

from flask import abort, request
from werkzeug.exceptions import TooManyRequests

from services.auth_security_service import consume_limit, _client_ip


MAX_PASSWORD_LENGTH = 128
MAX_TOKEN_LENGTH = 512
FIELD_LIMITS = {
    "first_name": 80, "last_name": 80, "email": 120, "password": MAX_PASSWORD_LENGTH,
    "current_password": MAX_PASSWORD_LENGTH, "new_password": MAX_PASSWORD_LENGTH,
    "confirm_password": MAX_PASSWORD_LENGTH, "token": MAX_TOKEN_LENGTH,
    "admin_access_code": 128, "company_name": 140, "company_website": 255,
    "profile_picture": 255, "phone_region": 2, "phone_number": 32,
    "phone_national_number": 32, "display_name": 120, "niche": 80,
    "audience_country": 80, "portfolio_url": 255, "title": 140,
    "industry": 80, "target_niche": 80, "target_country": 80,
    "goal": 120, "reference": 120, "refund_reference": 120,
    "bio": 2000, "notes": 2000, "review_notes": 2000,
    "message": 2000, "comment": 2000, "video_url": 1000,
    "brief": 10000, "deliverables": 4000, "media_kit_summary": 4000,
}
MULTI_FIELDS = {"platforms", "target_platforms"}


def protect_request():
    if len(request.query_string) > 2048:
        abort(400, "The query is too long.")
    if request.method not in ("POST", "PUT", "PATCH", "DELETE") or request.endpoint is None:
        return
    if request.mimetype not in ("application/x-www-form-urlencoded", "multipart/form-data", ""):
        abort(415, "Use a supported form submission.")
    if request.files:
        abort(400, "File uploads are not accepted.")
    for key, values in request.form.lists():
        limit = 500 if key.startswith("social_url_") else 16 if key.startswith("audience_count_") else FIELD_LIMITS.get(key, 120)
        if len(values) > (11 if key in MULTI_FIELDS else 1):
            abort(400, "Duplicate form fields are not accepted.")
        if len(key) > 64 or any(len(value) > limit or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", value) for value in values):
            abort(400, "A form value is invalid or too long.")
    if request.endpoint == "auth.register":
        scope, maximum, seconds = "register", 10, 3600
    elif request.endpoint == "auth.login":
        scope, maximum, seconds = "login-requests", 40, 900
    elif request.endpoint in ("account.forgot_password", "account.resend_verification", "account.reset_password", "account.verify_email", "account.security"):
        scope, maximum, seconds = "account-security", 15, 900
    else:
        scope, maximum, seconds = "write-requests", 120, 60
    retry_after = consume_limit(scope, _client_ip(), maximum, seconds)
    if not retry_after and request.endpoint == "auth.login":
        retry_after = consume_limit("login-account-requests", request.form.get("email", "").strip().lower(), 10, 900)
    if retry_after:
        raise TooManyRequests("Too many requests. Please wait before trying again.", retry_after=retry_after)
