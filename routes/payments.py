from flask import Blueprint, request

from models.order import Order
from services.order_service import mark_order_paid, mark_refunded
from services.payment_service import construct_webhook_event

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")


@payments_bp.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    signature = request.headers.get("Stripe-Signature", "")
    try:
        event = construct_webhook_event(request.get_data(), signature)
    except Exception:
        return {"error": "invalid signature"}, 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("order_id")
        order = Order.query.get(int(order_id)) if order_id else None
        if order:
            mark_order_paid(order, str(session.get("payment_intent") or ""))
    elif event["type"] == "charge.refunded":
        charge = event["data"]["object"]
        payment_intent = charge.get("payment_intent")
        order = Order.query.filter_by(stripe_payment_intent_id=payment_intent).first()
        if order and order.payment_status != "refunded":
            mark_refunded(order, reference=str(charge.get("id") or ""))
    return {"received": True}
