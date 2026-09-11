import re

from flask import current_app

from services.order_service import mark_refunded


def bank_details() -> dict | None:
    rib = re.sub(r"\s+", "", current_app.config.get("COMPANY_RIB", ""))
    bank = current_app.config.get("COMPANY_BANK_NAME", "").strip()
    holder = current_app.config.get("COMPANY_ACCOUNT_HOLDER", "").strip()
    if not re.fullmatch(r"[0-9]{24}", rib) or not bank or not holder:
        return None
    return {"rib": rib, "bank": bank, "holder": holder}


def refund_order(order, actor_id: int | None = None, reference: str = "") -> None:
    if order.payment_status != "paid" or order.payout_status == "paid":
        raise ValueError("Only a paid order without a completed creator payout can be refunded.")
    if not 3 <= len(reference) <= 120:
        raise ValueError("Complete the bank refund, then enter its transaction reference.")
    mark_refunded(order, reference=reference, actor_id=actor_id)
