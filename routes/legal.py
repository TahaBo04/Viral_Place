from datetime import datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db

legal_bp = Blueprint("legal", __name__)
POLICY_DETAILS = ("BUSINESS_LEGAL_NAME", "BUSINESS_ADDRESS", "BUSINESS_REGISTRATION", "PRIVACY_REGISTRATION", "SUPPORT_EMAIL", "POLICY_VERSION")


def validate_policy_config(app):
    if app.config.get("POLICIES_PUBLISHED") and any(not app.config.get(key, "").strip() for key in POLICY_DETAILS):
        raise RuntimeError("Reviewed legal, contact and privacy registration details are required to publish policies.")


@legal_bp.get("/legal/<page>")
def policy(page):
    if page not in ("terms", "privacy", "cancellations"):
        abort(404)
    if not current_app.config.get("POLICIES_PUBLISHED") and not (current_user.is_authenticated and current_user.role == "admin"):
        abort(404)
    return render_template("legal.html", policy=page)


@legal_bp.route("/legal/accept", methods=["GET", "POST"])
@login_required
def accept():
    if not current_app.config.get("POLICIES_PUBLISHED"):
        abort(404)
    if request.method == "POST":
        if request.form.get("accept_terms") != "on":
            flash("Confirm your agreement to the terms before continuing.", "warning")
            return render_template("legal_accept.html"), 400
        current_user.terms_version = current_app.config["POLICY_VERSION"]
        current_user.terms_accepted_at = datetime.utcnow()
        db.session.commit()
        return redirect(url_for("home"))
    return render_template("legal_accept.html")


def require_accepted_terms():
    if not current_app.config.get("POLICIES_PUBLISHED") or not current_user.is_authenticated or current_user.role == "admin":
        return
    if current_user.terms_version == current_app.config["POLICY_VERSION"]:
        return
    endpoint = request.endpoint or ""
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and endpoint and not endpoint.startswith(("legal.", "account.", "auth.")):
        flash("Review and accept the terms before continuing.", "warning")
        return redirect(url_for("legal.accept"), code=303)
