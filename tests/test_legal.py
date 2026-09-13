import unittest

from app import create_app, initialize_database
from extensions import db
from models.user import User
from routes.legal import POLICY_DETAILS, validate_policy_config


class LegalPolicyTests(unittest.TestCase):
    def setUp(self):
        class TestConfig:
            TESTING = True
            SECRET_KEY = "legal-test-key"
            SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            WTF_CSRF_ENABLED = False
            SESSION_PROTECTION = None
            POLICY_VERSION = "2026-09-13"

        self.app = create_app(TestConfig)
        initialize_database(self.app)
        self.client = self.app.test_client()
        with self.app.app_context():
            user = User(first_name="Test", last_name="Operator", email="operator@example.test", password_hash="unused-in-test", role="admin")
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

    def login(self):
        with self.client.session_transaction() as session:
            session["_user_id"] = f"{self.user_id}:0"
            session["_fresh"] = True

    def test_drafts_are_not_public_and_include_result_deliverable_distinction(self):
        for page in ("terms", "privacy", "cancellations"):
            self.assertEqual(self.client.get("/legal/" + page).status_code, 404)
        self.login()
        response = self.client.get("/legal/terms")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Not published or in force", response.data)
        self.assertIn(b"No guaranteed marketing results", response.data)
        self.assertIn(b"does not excuse missing agreed deliverables", response.data)
        self.assertIn(b"No business address provided yet", response.data)

    def test_publication_requires_factual_details(self):
        self.app.config["POLICIES_PUBLISHED"] = True
        with self.assertRaises(RuntimeError):
            validate_policy_config(self.app)
        for key in POLICY_DETAILS:
            self.app.config[key] = "synthetic-test-value"
        validate_policy_config(self.app)

    def test_terms_acceptance_is_required_and_recorded_for_existing_users(self):
        self.app.config["POLICIES_PUBLISHED"] = True
        with self.app.app_context():
            db.session.get(User, self.user_id).role = "business"
            db.session.commit()
        self.login()
        blocked = self.client.post("/profile/edit")
        self.assertEqual(blocked.status_code, 303)
        self.assertTrue(blocked.location.endswith("/legal/accept"))
        self.assertEqual(self.client.post("/legal/accept").status_code, 400)
        self.assertEqual(self.client.post("/legal/accept", data={"accept_terms": "on"}).status_code, 302)
        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            self.assertEqual(user.terms_version, "2026-09-13")
            self.assertIsNotNone(user.terms_accepted_at)

    def test_published_registration_requires_explicit_agreement(self):
        self.app.config["POLICIES_PUBLISHED"] = True
        response = self.client.post("/auth/register/business", data={})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Review and accept the terms", response.data)


if __name__ == "__main__":
    unittest.main()
