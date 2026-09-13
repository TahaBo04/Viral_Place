import os

from flask import Flask, render_template
from flask_login import current_user
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import SecurityError
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from extensions import csrf, db, login_manager


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    from services.account_security_service import validate_email_config
    validate_email_config(app)
    from routes.legal import legal_bp, require_accepted_terms, validate_policy_config
    validate_policy_config(app)
    for key in ("MARKETPLACE_CURRENCY", "COMPANY_BANK_CURRENCY"):
        if app.config.get(key, "usd") not in ("mad", "usd"):
            raise RuntimeError(f"{key} must be mad or usd.")
    if app.config.get("TRUST_PROXY_HEADERS"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=0, x_proto=1, x_host=0)
    if app.config.get("PRODUCTION"):
        if not app.config.get("SECRET_KEY") or len(app.config["SECRET_KEY"]) < 32 or app.config["SECRET_KEY"].startswith("replace-") or app.config["SECRET_KEY"] == "viral-place-local-development-key":
            raise RuntimeError("A strong SECRET_KEY is required in production.")
        if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgresql://"):
            raise RuntimeError("Production requires persistent PostgreSQL storage.")
        if os.environ.get("VIRAL_PLACE_DEMO") == "1" or os.environ.get("BRIEFVORA_DEMO") == "1":
            raise RuntimeError("Demo accounts must never be enabled in production.")
    from services.request_security_service import protect_request

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    app.before_request(protect_request)

    from models.user import User
    from models import account_email, campaign, collaboration, creator, logs, notification, offer, order, review, security, social, user  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            identifier, _, version = user_id.partition(":")
            user = db.session.get(User, int(identifier))
            return user if user and user.auth_version == int(version or "0") else None
        except (TypeError, ValueError):
            return None

    from routes.admin import admin_bp
    from routes.auth import auth_bp
    from routes.business import business_bp
    from routes.campaigns import campaigns_bp
    from routes.creators import creators_bp
    from routes.influencer import influencer_bp
    from routes.notifications import notifications_bp
    from routes.orders import orders_bp
    from routes.offers import offers_bp
    from routes.profile import profile_bp
    from routes.account import account_bp, require_verified_email

    app.register_blueprint(auth_bp)
    app.register_blueprint(creators_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(offers_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(business_bp)
    app.register_blueprint(influencer_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(legal_bp)
    app.before_request(require_verified_email)
    app.before_request(require_accepted_terms)

    @app.after_request
    def set_security_headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
            "form-action 'self'; script-src 'self'; "
            "style-src 'self' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; connect-src 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if app.config.get("PRODUCTION"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if response.content_type and response.content_type.startswith("text/html"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    @app.context_processor
    def inject_navigation_state():
        from services.contact_service import country_catalog, national_phone
        from services.platform_service import PLATFORMS, campaign_platform_labels, platform_icon_url, platform_label
        shared = {
            "platform_catalog": PLATFORMS,
            "platform_label": platform_label,
            "platform_icon_url": platform_icon_url,
            "campaign_platform_labels": campaign_platform_labels,
            "phone_country_catalog": country_catalog(),
            "national_phone": national_phone,
        }
        if not current_user.is_authenticated:
            return {"unread_notification_count": 0, **shared}
        from services.notification_service import unread_count
        return {"unread_notification_count": unread_count(current_user.id), **shared}

    @app.route("/")
    def home():
        from models.campaign import Campaign
        from models.creator import CreatorProfile
        creators = CreatorProfile.query.filter_by(verification_status="verified", availability="available").order_by(CreatorProfile.followers.desc()).limit(3).all()
        campaigns = Campaign.query.filter_by(status="open", visibility="public").order_by(Campaign.created_at.desc()).limit(3).all()
        return render_template("home.html", creators=creators, campaigns=campaigns)

    @app.route("/healthz")
    def health():
        from sqlalchemy import text
        try:
            db.session.execute(text("SELECT 1"))
        except Exception:
            db.session.rollback()
            return {"status": "unavailable"}, 503
        return {"status": "ok"}

    @app.errorhandler(400)
    @app.errorhandler(413)
    @app.errorhandler(415)
    @app.errorhandler(429)
    def rejected_request(error):
        if isinstance(error, SecurityError):
            return "Invalid request host.", 400, {"Content-Type": "text/plain; charset=utf-8"}
        response = app.make_response((render_template("error.html", code=error.code, message=error.description), error.code))
        if error.code == 429:
            response.headers["Retry-After"] = str(getattr(error, "retry_after", None) or 900)
        return response

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="That page does not exist."), 404

    @app.errorhandler(403)
    @app.errorhandler(409)
    @app.errorhandler(503)
    def unavailable(error):
        return render_template("error.html", code=error.code, message=error.description), error.code

    @app.cli.command("dispatch-mail")
    def dispatch_account_mail():
        from services.account_security_service import dispatch_mail
        print(f"Messages accepted by provider: {dispatch_mail()}")

    @app.errorhandler(500)
    def server_error(_error):
        db.session.rollback()
        return render_template("error.html", code=500, message="Briefvora hit an unexpected error. Please try again."), 500

    @app.errorhandler(CSRFError)
    def csrf_error(_error):
        return render_template("error.html", code=400, message="This form expired or was not submitted securely. Refresh and try again."), 400

    return app


def initialize_database(app):
    with app.app_context():
        db.create_all()
        from services.schema_service import apply_compatible_schema_updates
        apply_compatible_schema_updates()
        from services.bootstrap_service import ensure_admin_account
        ensure_admin_account()
        if os.environ.get("BRIEFVORA_DEMO", os.environ.get("VIRAL_PLACE_DEMO")) == "1":
            from services.demo_seed import seed_demo_data
            seed_demo_data()
    from services.account_security_service import start_mail_worker
    start_mail_worker(app)


if __name__ == "__main__":
    app = create_app()
    initialize_database(app)
    app.run(debug=False, use_reloader=False)
