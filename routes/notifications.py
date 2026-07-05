from datetime import datetime

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models.notification import Notification

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.route("/")
@login_required
def list_notifications():
    items = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(100).all()
    return render_template("notifications.html", notifications=items)


@notifications_bp.route("/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id):
    item = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first_or_404()
    item.read_at = item.read_at or datetime.utcnow()
    db.session.commit()
    return redirect(item.link or request.referrer or url_for("notifications.list_notifications"))


@notifications_bp.route("/read-all", methods=["POST"])
@login_required
def read_all():
    Notification.query.filter_by(user_id=current_user.id, read_at=None).update({"read_at": datetime.utcnow()})
    db.session.commit()
    return redirect(url_for("notifications.list_notifications"))
