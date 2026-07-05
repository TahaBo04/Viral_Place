import hashlib
import hmac
import json
import os
import time
import unittest

import stripe

from app import create_app
from services.payment_service import stripe_object_dict


class PaymentWebhookTests(unittest.TestCase):
    def setUp(self):
        self.previous_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
        os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_regression_test"

        class TestConfig:
            TESTING = True
            SECRET_KEY = "test"
            SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            SQLALCHEMY_ENGINE_OPTIONS = {}
            SESSION_COOKIE_SECURE = False

        self.client = create_app(TestConfig).test_client()

    def tearDown(self):
        if self.previous_secret is None:
            os.environ.pop("STRIPE_WEBHOOK_SECRET", None)
        else:
            os.environ["STRIPE_WEBHOOK_SECRET"] = self.previous_secret

    def test_stripe_objects_are_normalized_recursively(self):
        value = stripe.StripeObject.construct_from(
            {"metadata": {"order_id": "42"}, "payment_status": "paid"},
            "test-key",
        )
        self.assertEqual(stripe_object_dict(value)["metadata"]["order_id"], "42")

    def test_signed_checkout_event_is_accepted(self):
        payload = json.dumps(
            {
                "id": "evt_test",
                "object": "event",
                "type": "checkout.session.completed",
                "data": {"object": {"metadata": {}}},
            },
            separators=(",", ":"),
        )
        timestamp = int(time.time())
        digest = hmac.new(
            os.environ["STRIPE_WEBHOOK_SECRET"].encode(),
            f"{timestamp}.{payload}".encode(),
            hashlib.sha256,
        ).hexdigest()
        response = self.client.post(
            "/payments/stripe/webhook",
            data=payload,
            headers={"Stripe-Signature": f"t={timestamp},v1={digest}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"received": True})


if __name__ == "__main__":
    unittest.main()
