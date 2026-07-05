# services/logging_service.py
from __future__ import annotations

from datetime import datetime
import json
from flask import request
from extensions import db

from models.logs import UserLoginLog, CreatorViewLog, AuditLog


def log_login(user, success: bool, failure_reason: str | None = None):
    log = UserLoginLog(
        user_id=user.id,
        success=success,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        failure_reason=failure_reason,
        created_at=datetime.utcnow(),
    )
    db.session.add(log)
    db.session.commit()


def log_creator_view(creator_profile_id: int, action: str, viewer_id: int | None = None):
    log = CreatorViewLog(
        user_id=viewer_id,
        creator_profile_id=creator_profile_id,
        action=action,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        created_at=datetime.utcnow(),
    )
    db.session.add(log)
    db.session.commit()


def log_audit_event(
    event_type: str,
    description: str,
    actor_user_id: int | None = None,
    target_user_id: int | None = None,
    campaign_id: int | None = None,
    creator_profile_id: int | None = None,
    order_id: int | None = None,
    metadata: dict | None = None,
):
    log = AuditLog(
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        campaign_id=campaign_id,
        creator_profile_id=creator_profile_id,
        order_id=order_id,
        event_type=event_type,
        description=description,
        metadata_json=json.dumps(metadata or {}),
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        created_at=datetime.utcnow(),
    )
    db.session.add(log)
    db.session.commit()
