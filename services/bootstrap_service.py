from __future__ import annotations

import os

from werkzeug.security import generate_password_hash

from extensions import db
from models.user import User


def ensure_admin_account() -> None:
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not email or not password:
        return
    admin = User.query.filter_by(email=email).first()
    if admin:
        return
    admin = User(
        first_name="Viral",
        last_name="Place",
        email=email,
        password_hash=generate_password_hash(password),
        role="admin",
        company_name="Viral Place",
    )
    db.session.add(admin)
    db.session.commit()
