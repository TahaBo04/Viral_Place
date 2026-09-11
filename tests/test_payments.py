import unittest

from app import create_app
from services.payment_service import bank_details


class BankConfigurationTests(unittest.TestCase):
    def setUp(self):
        class TestConfig:
            TESTING = True
            SECRET_KEY = "test"
            SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            WTF_CSRF_ENABLED = False
        self.app = create_app(TestConfig)

    def test_incomplete_or_malformed_rib_disables_transfers(self):
        with self.app.app_context():
            self.assertIsNone(bank_details())
            self.app.config.update(COMPANY_RIB="<script>alert(1)</script>", COMPANY_BANK_NAME="Example Bank", COMPANY_ACCOUNT_HOLDER="Example Company")
            self.assertIsNone(bank_details())

    def test_bank_details_are_server_configured(self):
        with self.app.app_context():
            self.app.config.update(COMPANY_RIB="123 456 789012345678901234", COMPANY_BANK_NAME="Example Bank", COMPANY_ACCOUNT_HOLDER="Example Company")
            self.assertEqual(bank_details()["rib"], "123456789012345678901234")

    def test_legacy_payment_webhook_is_removed(self):
        response = self.app.test_client().post("/payments/stripe/webhook", json={"type": "checkout.session.completed"})
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
