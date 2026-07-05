from __future__ import annotations

import os
from datetime import datetime

from extensions import db
from models.collaboration import Application
from models.creator import CreatorProfile
from models.order import Order, OrderEvent
from services.notification_service import notify, notify_admins


def payout_percent() -> int:
    try:
        value = int(os.environ.get("INFLUENCER_PAYOUT_PERCENT", "70"))
    except ValueError:
        value = 70
    return max(1, min(95, value))


def add_order_event(order: Order, event_type: str, message: str, actor_id: int | None = None) -> OrderEvent:
    event = OrderEvent(order_id=order.id, actor_id=actor_id, event_type=event_type, message=message)
    db.session.add(event)
    return event


def create_order(
    campaign,
    amount_cents: int,
    creator_profile: CreatorProfile | None = None,
    application: Application | None = None,
    customer_notes: str | None = None,
) -> Order:
    payout_cents = int(amount_cents * payout_percent() / 100)
    order = Order(
        campaign_id=campaign.id,
        application_id=application.id if application else None,
        business_id=campaign.business_id,
        influencer_id=creator_profile.user_id if creator_profile else None,
        creator_profile_id=creator_profile.id if creator_profile else None,
        amount_cents=amount_cents,
        influencer_payout_cents=payout_cents,
        customer_notes=customer_notes,
    )
    db.session.add(order)
    db.session.flush()
    add_order_event(order, "order_created", "Order created and awaiting customer payment.", campaign.business_id)
    return order


def select_application(application: Application, amount_cents: int, actor_id: int) -> Order:
    application.status = "selected_pending_payment"
    for other in application.campaign.applications:
        if other.id != application.id and other.status == "pending":
            other.status = "not_selected"
    order = create_order(
        application.campaign,
        amount_cents,
        creator_profile=application.creator_profile,
        application=application,
    )
    notify_admins(
        "Creator selected, payment pending",
        f"{application.creator_profile.display_name} was selected for {application.campaign.title}; activation waits for payment.",
        f"/admin/orders/{order.id}",
    )
    add_order_event(order, "creator_selected", f"{application.creator_profile.display_name} selected by the customer.", actor_id)
    db.session.commit()
    return order


def assign_creator(order: Order, creator_profile: CreatorProfile, actor_id: int) -> None:
    if creator_profile.verification_status != "verified":
        raise ValueError("Only verified creators can be assigned")
    if not creator_profile.user.phone_number:
        raise ValueError("The creator must add an active phone number before assignment")
    if not order.business.phone_number:
        raise ValueError("The brand must add an active phone number before assignment")
    order.creator_profile_id = creator_profile.id
    order.influencer_id = creator_profile.user_id
    if order.payment_status == "paid":
        order.status = "in_production"
        order.payout_status = "held"
        notify(
            creator_profile.user_id,
            "New paid assignment",
            f"Viral Place assigned you to {order.campaign.title}. The customer payment is secured; production can start.",
            f"/orders/{order.id}",
        )
    add_order_event(order, "creator_assigned", f"{creator_profile.display_name} assigned by Viral Place.", actor_id)
    db.session.commit()


def mark_order_paid(order: Order, payment_intent_id: str | None = None, actor_id: int | None = None) -> None:
    if order.payment_status == "paid":
        return
    order.payment_status = "paid"
    order.paid_at = datetime.utcnow()
    order.payout_status = "held"
    order.stripe_payment_intent_id = payment_intent_id or order.stripe_payment_intent_id
    order.status = "in_production" if order.influencer_id else "paid_unassigned"
    order.campaign.status = "in_production" if order.influencer_id else "paid_unassigned"
    if order.application:
        order.application.status = "selected"
    add_order_event(order, "payment_confirmed", "Customer payment confirmed and held by Viral Place.", actor_id)
    notify(order.business_id, "Payment confirmed", f"Payment for {order.campaign.title} is secured by Viral Place.", f"/orders/{order.id}")
    if order.influencer_id:
        notify(
            order.influencer_id,
            "Start production",
            f"Payment is secured for {order.campaign.title}. Submit your content through the order workspace.",
            f"/orders/{order.id}",
        )
    notify_admins("Payment received", f"Order #{order.id} is paid and ready for operations.", f"/admin/orders/{order.id}")
    db.session.commit()


def mark_refunded(order: Order, reference: str | None = None, actor_id: int | None = None) -> None:
    order.status = "refunded"
    order.payment_status = "refunded"
    order.payout_status = "cancelled"
    order.refund_reference = reference
    order.refunded_at = datetime.utcnow()
    order.campaign.status = "refunded"
    add_order_event(order, "refunded", "Customer payment refunded after agency review.", actor_id)
    notify(order.business_id, "Refund issued", f"Order #{order.id} was refunded after Viral Place review.", f"/orders/{order.id}")
    if order.influencer_id:
        notify(order.influencer_id, "Order closed after review", "The content was not approved and the customer was refunded. Review the agency notes before future submissions.", f"/orders/{order.id}")
    db.session.commit()
