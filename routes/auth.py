from datetime import datetime
import os

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models.user import User
from services.logging_service import log_login

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
ACCOUNT_TYPES = ("business", "influencer")


@auth_bp.route("/register", defaults={"account_type": None}, methods=["GET", "POST"])
@auth_bp.route("/register/<account_type>", methods=["GET", "POST"])
def register(account_type):
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if account_type is None and request.method == "GET":
        return render_template("auth_choice.html", mode="register")
    role = account_type or request.form.get("role", "")
    if role not in ACCOUNT_TYPES:
        flash("Choose the brand or influencer registration portal.", "warning")
        return redirect(url_for("auth.register"))

    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        company_name = request.form.get("company_name", "").strip()
        company_website = request.form.get("company_website", "").strip()
        social_profile_url = request.form.get("social_profile_url", "").strip()

        if not all([first_name, last_name, email, password]):
            flash("Complete your name, email, and password.", "danger")
            return render_template("register.html", portal_role=role)
        if len(password) < 8:
            flash("Use at least 8 characters for your password.", "danger")
            return render_template("register.html", portal_role=role)
        if role == "business" and not company_name:
            flash("Enter your company or brand name.", "danger")
            return render_template("register.html", portal_role=role)
        if role == "influencer" and not social_profile_url:
            flash("Add the social profile you will use for creator ownership review.", "danger")
            return render_template("register.html", portal_role=role)
        if User.query.filter_by(email=email).first():
            flash("An account already exists for this email. Log in instead.", "warning")
            return redirect(url_for("auth.login", account_type=role))

        admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password_hash=generate_password_hash(password),
            role="admin" if email == admin_email and admin_email else role,
            company_name=company_name if role == "business" else None,
            company_website=company_website if role == "business" else None,
            social_profile_url=social_profile_url if role == "influencer" else None,
        )
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("That email is already registered. Log in instead.", "warning")
            return redirect(url_for("auth.login", account_type=role))

        login_user(user)
        flash("Welcome to Viral Place. Your account is ready.", "success")
        if user.role == "business":
            return redirect(url_for("business.dashboard"))
        if user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("creators.onboarding"))

    return render_template("register.html", portal_role=role)


@auth_bp.route("/login", defaults={"account_type": None}, methods=["GET", "POST"])
@auth_bp.route("/login/<account_type>", methods=["GET", "POST"])
def login(account_type):
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if account_type is None and request.method == "GET":
        return render_template("auth_choice.html", mode="login")
    portal_role = account_type or request.form.get("account_type")
    if portal_role not in (*ACCOUNT_TYPES, None, "admin"):
        flash("Choose the brand or influencer login portal.", "warning")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            if user:
                log_login(user, success=False, failure_reason="wrong_password")
            flash("Email or password is incorrect.", "danger")
            return render_template("login.html", portal_role=portal_role), 401

        if portal_role in ACCOUNT_TYPES and user.role not in (portal_role, "admin"):
            log_login(user, success=False, failure_reason="wrong_portal")
            destination = "brand" if user.role == "business" else "influencer"
            flash(f"This account belongs to the {destination} portal. Use its dedicated login.", "warning")
            return render_template("login.html", portal_role=portal_role), 403

        login_user(user, remember=request.form.get("remember") == "on")
        user.last_login_at = datetime.utcnow()
        db.session.commit()
        log_login(user, success=True)

        if user.role == "business":
            return redirect(url_for("business.dashboard"))
        if user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("influencer.dashboard"))

    return render_template("login.html", portal_role=portal_role)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    if current_user.is_authenticated:
        logout_user()
    return redirect(url_for("home"))
