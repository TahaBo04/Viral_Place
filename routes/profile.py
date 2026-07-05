from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models.user import User
from services.contact_service import normalize_phone

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
        phone_number = normalize_phone(request.form.get("phone_number", ""))
        if not phone_number or request.form.get("phone_active_confirmed") != "on":
            flash("Enter an active phone number in international format and confirm it is reachable.", "danger")
            return render_template("profile_edit.html")
        current_user.phone_number = phone_number
        current_user.phone_confirmed_at = datetime.utcnow()
        if current_user.role == "business":
            current_user.company_name = request.form.get("company_name", current_user.company_name or "").strip()
            current_user.company_website = request.form.get("company_website", "").strip()
        if current_user.role == "influencer":
            current_user.social_profile_url = request.form.get("social_profile_url", "").strip()
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("profile.public_profile", user_id=current_user.id))
    return render_template("profile_edit.html")
