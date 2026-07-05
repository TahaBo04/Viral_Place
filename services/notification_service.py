from __future__ import annotations

from models.notification import Notification
from models.user import User
from extensions import db


def notify(user_id: int, title: str, message: str, link: str | None = None) -> Notification:
    notification = Notification(user_id=user_id, title=title, message=message, link=link)
    db.session.add(notification)
    return notification


def notify_admins(title: str, message: str, link: str | None = None) -> None:
    for admin in User.query.filter_by(role="admin").all():
        notify(admin.id, title, message, link)


def unread_count(user_id: int) -> int:
    return Notification.query.filter_by(user_id=user_id, read_at=None).count()
