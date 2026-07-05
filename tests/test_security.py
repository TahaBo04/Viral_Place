import os
import unittest

from werkzeug.security import generate_password_hash

from app import create_app, initialize_database
from extensions import db
from models.user import User


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.previous_admin_code = os.environ.get("ADMIN_ACCESS_CODE")
        os.environ["ADMIN_ACCESS_CODE"] = "test-operations-code"

        class TestConfig:
            TESTING = True
            SECRET_KEY = "security-test"
            SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            SQLALCHEMY_ENGINE_OPTIONS = {}
            SESSION_COOKIE_SECURE = False
            WTF_CSRF_ENABLED = False

        self.app = create_app(TestConfig)
        initialize_database(self.app)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.session.add_all(
                [
                    User(
                        first_name="Brand",
                        last_name="Owner",
                        email="brand@security.test",
                        password_hash=generate_password_hash("BrandPass123!"),
                        role="business",
                        company_name="Security Brand",
                        phone_number="+212612345601",
                    ),
                    User(
                        first_name="Operations",
                        last_name="Admin",
                        email="admin@security.test",
                        password_hash=generate_password_hash("AdminPass123!"),
                        role="admin",
                    ),
                ]
            )
            db.session.commit()

    def tearDown(self):
        if self.previous_admin_code is None:
            os.environ.pop("ADMIN_ACCESS_CODE", None)
        else:
            os.environ["ADMIN_ACCESS_CODE"] = self.previous_admin_code

    def test_security_headers_and_private_html_cache(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["Cache-Control"], "no-store, max-age=0")

    def test_csrf_rejects_missing_token(self):
        class CsrfConfig:
            TESTING = True
            SECRET_KEY = "csrf-test"
            SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            SQLALCHEMY_ENGINE_OPTIONS = {}
            SESSION_COOKIE_SECURE = False
            WTF_CSRF_ENABLED = True

        csrf_client = create_app(CsrfConfig).test_client()
        response = csrf_client.post(
            "/auth/login/business",
            data={"email": "someone@example.com", "password": "Password123!"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"not submitted securely", response.data)

    def test_admin_requires_admin_portal_and_access_code(self):
        brand_on_admin_portal = self.client.post(
            "/auth/login/admin",
            data={
                "email": "brand@security.test",
                "password": "BrandPass123!",
                "admin_access_code": "test-operations-code",
            },
        )
        self.assertEqual(brand_on_admin_portal.status_code, 403)

        admin_on_brand_portal = self.client.post(
            "/auth/login/business",
            data={"email": "admin@security.test", "password": "AdminPass123!"},
        )
        self.assertEqual(admin_on_brand_portal.status_code, 401)

        wrong_code = self.client.post(
            "/auth/login/admin",
            data={
                "email": "admin@security.test",
                "password": "AdminPass123!",
                "admin_access_code": "wrong-code",
            },
        )
        self.assertEqual(wrong_code.status_code, 401)

        valid = self.client.post(
            "/auth/login/admin",
            data={
                "email": "admin@security.test",
                "password": "AdminPass123!",
                "admin_access_code": "test-operations-code",
            },
        )
        self.assertEqual(valid.status_code, 302)
        self.assertTrue(valid.headers["Location"].endswith("/admin/"))

    def test_repeated_failures_are_throttled(self):
        for _ in range(5):
            response = self.client.post(
                "/auth/login/business",
                data={"email": "victim@example.com", "password": "wrong-password"},
            )
            self.assertEqual(response.status_code, 401)
        blocked = self.client.post(
            "/auth/login/business",
            data={"email": "victim@example.com", "password": "wrong-password"},
        )
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("Retry-After", blocked.headers)


if __name__ == "__main__":
    unittest.main()
