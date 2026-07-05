import os

from flask import Flask, render_template
from flask_login import current_user

from config import Config
from extensions import db, login_manager


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    from models.user import User
    from models import campaign, collaboration, creator, logs, notification, order, user  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return db.session.get(User, int(user_id))
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
    from routes.payments import payments_bp
    from routes.profile import profile_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(creators_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(business_bp)
    app.register_blueprint(influencer_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(profile_bp)

    @app.context_processor
    def inject_navigation_state():
        if not current_user.is_authenticated:
            return {"unread_notification_count": 0}
        from services.notification_service import unread_count
        return {"unread_notification_count": unread_count(current_user.id)}

    @app.route("/")
    def home():
        from models.campaign import Campaign
        from models.creator import CreatorProfile
        creators = CreatorProfile.query.filter_by(verification_status="verified", availability="available").order_by(CreatorProfile.followers.desc()).limit(3).all()
        campaigns = Campaign.query.filter(Campaign.status.in_(["open", "awaiting_selection"])).order_by(Campaign.created_at.desc()).limit(3).all()
        return render_template("home.html", creators=creators, campaigns=campaigns)

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="That page does not exist."), 404

    @app.errorhandler(500)
    def server_error(_error):
        db.session.rollback()
        return render_template("error.html", code=500, message="Viral Place hit an unexpected error. Please try again."), 500

    return app


def initialize_database(app):
    with app.app_context():
        db.create_all()
        from services.bootstrap_service import ensure_admin_account
        ensure_admin_account()
        if os.environ.get("VIRAL_PLACE_DEMO") == "1":
            from services.demo_seed import seed_demo_data
            seed_demo_data()


if __name__ == "__main__":
    app = create_app()
    initialize_database(app)
    app.run(debug=True, use_reloader=False)
