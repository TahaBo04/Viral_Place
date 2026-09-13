import re

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, logout_user
from sqlalchemy import update
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models.user import User
from services.account_security_service import consume_action, email_ready, queue_email, request_email, wake_mail_worker
from services.auth_security_service import consume_limit

account_bp = Blueprint("account", __name__, url_prefix="/auth")


@account_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    available = email_ready()
    if request.method == "POST" and available:
        email = request.form.get("email", "").strip().lower()
        if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            user = User.query.filter_by(email=email).first()
            request_email(email, "reset", user)
        flash("If this address has an account, a reset link will arrive shortly. Check your spam folder too.", "success")
        return render_template("account_action.html", mode="forgot", available=True), 202
    return render_template("account_action.html", mode="forgot", available=available), 200 if available else 503


@account_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        password = request.form.get("new_password", "")
        if not 12 <= len(password) <= 128 or password != request.form.get("confirm_password"):
            flash("Use 12 to 128 characters and enter the same password twice.", "danger")
        elif consume_action(request.form.get("token", ""), "reset", password):
            logout_user()
            session.clear()
            flash("Password updated. All previous sessions have been revoked. Log in with your new password.", "success")
            return redirect(url_for("auth.login"))
        else:
            flash("This link is invalid or expired. Request a new reset link.", "danger")
        return render_template("account_action.html", mode="reset"), 400
    return render_template("account_action.html", mode="reset")


@account_bp.route("/verify-email", methods=["GET", "POST"])
def verify_email():
    if request.method == "POST":
        if consume_action(request.form.get("token", ""), "verify"):
            flash("Your email address is verified.", "success")
            return redirect(url_for("account.security") if current_user.is_authenticated else url_for("auth.login"))
        flash("This link is invalid or expired. Request a new verification email.", "danger")
        return render_template("account_action.html", mode="verify"), 400
    return render_template("account_action.html", mode="verify")


@account_bp.post("/resend-verification")
@login_required
def resend_verification():
    if not email_ready():
        abort(503, "Email delivery is not yet configured.")
    if not current_user.email_verified_at:
        request_email(current_user.email, "verify", current_user)
    flash("Verification requested. Check your inbox and spam folder.", "success")
    return redirect(url_for("account.security"))


@account_bp.route("/security", methods=["GET", "POST"])
@login_required
def security():
    if request.method == "POST":
        if consume_limit("password-change", str(current_user.id), 5, 900):
            abort(429, "Too many password-change attempts. Please wait.")
        password = request.form.get("new_password", "")
        old_hash = current_user.password_hash
        if not check_password_hash(old_hash, request.form.get("current_password", "")):
            flash("Your current password is incorrect.", "danger")
        elif not 12 <= len(password) <= 128 or password != request.form.get("confirm_password"):
            flash("Use 12 to 128 characters and enter the same password twice.", "danger")
        else:
            changed = db.session.execute(update(User).where(User.id == current_user.id, User.password_hash == old_hash).values(
                password_hash=generate_password_hash(password), auth_version=User.auth_version + 1,
            )).rowcount
            if not changed:
                db.session.rollback()
                abort(409, "The password changed in another session. Log in again.")
            queue_email(current_user.email, "changed", current_user)
            db.session.commit()
            wake_mail_worker()
            logout_user()
            session.clear()
            flash("Password updated. All previous sessions have been revoked. Log in again.", "success")
            return redirect(url_for("auth.login"))
        return render_template("account_security.html", email_available=email_ready()), 400
    return render_template("account_security.html", email_available=email_ready())


def require_verified_email():
    if not current_app.config.get("EMAIL_VERIFICATION_REQUIRED") or not current_user.is_authenticated or current_user.role == "admin" or current_user.email_verified_at:
        return
    allowed = {"auth.logout", "account.security", "account.resend_verification", "account.verify_email", "account.reset_password", "account.forgot_password"}
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.endpoint and request.endpoint not in allowed:
        abort(403, "Verify your email address in Account security before continuing.")
