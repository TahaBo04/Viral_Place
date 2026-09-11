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
    code = os.environ.get("ADMIN_ACCESS_CODE", "")
    if len(password) < 16 or len(code) < 16 or password.startswith("replace-") or code.startswith("replace-") or password == code:
        raise RuntimeError("Admin password and separate access code must each be at least 16 characters.")
    admin = User.query.filter_by(email=email).first()
    if admin:
        return
    admin = User(
        first_name="Briefvora",
        last_name="Operations",
        email=email,
        password_hash=generate_password_hash(password),
        role="admin",
        company_name="Briefvora",
    )
    db.session.add(admin)
    db.session.commit()
