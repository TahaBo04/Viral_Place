from __future__ import annotations

import os

import stripe

from extensions import db
from services.order_service import mark_order_paid, mark_refunded


def stripe_configured() -> bool:
    return bool(os.environ.get("STRIPE_SECRET_KEY"))


def _configure() -> None:
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")


def stripe_object_dict(value) -> dict:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return dict(value or {})


def create_checkout(order, base_url: str) -> str:
    if not stripe_configured():
        raise RuntimeError("Stripe is not configured")
    _configure()
    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": order.currency,
                    "unit_amount": order.amount_cents,
                    "product_data": {
                        "name": f"Viral Place campaign #{order.campaign_id}",
                        "description": order.campaign.title,
                    },
                },
                "quantity": 1,
            }
        ],
        client_reference_id=str(order.id),
        metadata={"order_id": str(order.id), "campaign_id": str(order.campaign_id)},
        success_url=f"{base_url}/orders/{order.id}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/orders/{order.id}",
    )
    order.stripe_checkout_session_id = session.id
    db.session.commit()
    return session.url


def sync_checkout(order, session_id: str) -> bool:
    if not stripe_configured():
        return False
    _configure()
    session = stripe.checkout.Session.retrieve(session_id)
    session_data = stripe_object_dict(session)
    if str(session_data.get("metadata", {}).get("order_id")) != str(order.id):
        return False
    if session_data.get("payment_status") == "paid":
        mark_order_paid(order, str(session_data.get("payment_intent") or ""))
        return True
    return False


def construct_webhook_event(payload: bytes, signature: str):
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise RuntimeError("Stripe webhook is not configured")
    return stripe.Webhook.construct_event(payload, signature, secret)


def refund_order(order, actor_id: int | None = None) -> None:
    reference = None
    if stripe_configured() and order.stripe_payment_intent_id:
        _configure()
        refund = stripe.Refund.create(payment_intent=order.stripe_payment_intent_id)
        reference = refund.id
    mark_refunded(order, reference=reference, actor_id=actor_id)
