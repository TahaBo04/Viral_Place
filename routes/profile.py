from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models.user import User
from services.contact_service import normalize_phone
from services.url_service import safe_https_url

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")


@profile_bp.route("/<int:user_id>")
def public_profile(user_id):
    user = User.query.get_or_404(user_id)
    return render_template("profile_public.html", profile_user=user)


@profile_bp.route("/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        current_user.first_name = request.form.get("first_name", current_user.first_name).strip()
        current_user.last_name = request.form.get("last_name", current_user.last_name).strip()
        current_user.bio = request.form.get("bio", "").strip()
        region = request.form.get("phone_region", "").upper()
        phone_number = normalize_phone(request.form.get("phone_national_number", ""), region or None)
        if not phone_number or request.form.get("phone_active_confirmed") != "on":
            flash("Enter an active phone number in international format and confirm it is reachable.", "danger")
            return render_template("profile_edit.html")
        current_user.phone_number = phone_number
        current_user.phone_region = region
        current_user.phone_confirmed_at = datetime.utcnow()
        picture_input = request.form.get("profile_picture", "").strip()
        profile_picture = safe_https_url(picture_input) if picture_input else None
        if picture_input and (not profile_picture or len(profile_picture) > 255):
            flash("Profile pictures must use a safe public HTTPS URL.", "danger")
            return render_template("profile_edit.html")
        current_user.profile_picture = profile_picture
        if current_user.role == "business":
            current_user.company_name = request.form.get("company_name", current_user.company_name or "").strip()
            current_user.company_website = request.form.get("company_website", "").strip()
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("profile.public_profile", user_id=current_user.id))
    return render_template("profile_edit.html")
