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

    def test_oversized_and_duplicate_sensitive_inputs_are_rejected(self):
        from werkzeug.datastructures import MultiDict
        oversized = self.client.post("/auth/login/business", data={"email": "brand@security.test", "password": "x" * 129})
        self.assertEqual(oversized.status_code, 400)
        duplicate = self.client.post("/auth/login/business", data=MultiDict([("email", "one@example.com"), ("email", "two@example.com"), ("password", "test")]))
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(self.client.post("/auth/login/business", json={"email": "bad"}).status_code, 415)

    def test_forwarded_header_cannot_bypass_ip_throttling(self):
        for index in range(30):
            response = self.client.post("/auth/login/business", headers={"X-Forwarded-For": f"192.0.2.{index + 1}"}, data={"email": f"attempt{index}@example.com", "password": "incorrect"})
            self.assertEqual(response.status_code, 401)
        response = self.client.post("/auth/login/business", headers={"X-Forwarded-For": "198.51.100.1"}, data={"email": "another@example.com", "password": "incorrect"})
        self.assertEqual(response.status_code, 429)

    def test_trusted_proxy_uses_appended_ip(self):
        from services.auth_security_service import _client_ip
        self.app.config["TRUST_PROXY_HEADERS"] = True
        with self.app.test_request_context(headers={"X-Forwarded-For": "192.0.2.99, 198.51.100.10"}):
            self.assertEqual(_client_ip(), "198.51.100.10")

    def test_login_injection_does_not_authenticate(self):
        response = self.client.post("/auth/login/business", data={"email": "' OR 1=1 --", "password": "incorrect"})
        self.assertEqual(response.status_code, 401)
        with self.client.session_transaction() as session:
            self.assertNotIn("_user_id", session)

    def test_registration_is_rate_limited_before_password_hashing(self):
        for _ in range(10):
            self.assertEqual(self.client.post("/auth/register/business", data={}).status_code, 200)
        response = self.client.post("/auth/register/business", data={})
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)

    def test_rate_limit_expires(self):
        from datetime import datetime, timedelta
        from models.security import AuthThrottle
        from services.auth_security_service import consume_limit
        with self.app.test_request_context():
            self.assertEqual(consume_limit("test", "key", 1, 60), 0)
            self.assertGreater(consume_limit("test", "key", 1, 60), 0)
            AuthThrottle.query.update({"blocked_until": datetime.utcnow() - timedelta(seconds=1)})
            db.session.commit()
            self.assertEqual(consume_limit("test", "key", 1, 60), 0)

    def test_untrusted_host_and_oversized_body_are_rejected(self):
        self.app.config.update(TRUSTED_HOSTS=["localhost"], MAX_CONTENT_LENGTH=65536)
        self.assertEqual(self.client.get("/", headers={"Host": "attacker.example"}).status_code, 400)
        self.assertEqual(self.client.post("/auth/login/business", data={"password": "x" * 70000}).status_code, 413)

    def test_production_refuses_default_secret_and_ephemeral_storage(self):
        from config import Config
        from unittest.mock import patch
        with patch.object(Config, "PRODUCTION", True), patch.object(Config, "SECRET_KEY", "weak"):
            with self.assertRaises(RuntimeError):
                create_app(Config)
        with patch.object(Config, "PRODUCTION", True), patch.object(Config, "SECRET_KEY", "x" * 64), patch.object(Config, "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"):
            with self.assertRaises(RuntimeError):
                create_app(Config)

    def test_admin_profile_is_not_public(self):
        with self.app.app_context():
            admin_id = User.query.filter_by(role="admin").one().id
        self.assertEqual(self.client.get(f"/profile/{admin_id}").status_code, 404)

    def test_parallel_rate_limit_updates_do_not_lose_attempts(self):
        from concurrent.futures import ThreadPoolExecutor
        from tempfile import TemporaryDirectory
        from services.auth_security_service import consume_limit
        with TemporaryDirectory() as directory:
            class ConcurrentConfig:
                TESTING = True
                SECRET_KEY = "concurrent-test"
                SQLALCHEMY_DATABASE_URI = f"sqlite:///{directory}/rate-limit.db"
                SQLALCHEMY_TRACK_MODIFICATIONS = False
            app = create_app(ConcurrentConfig)
            with app.app_context():
                db.create_all()
            def attempt(_index):
                with app.test_request_context():
                    return consume_limit("parallel", "same-account", 5, 60)
            with ThreadPoolExecutor(max_workers=8) as executor:
                results = list(executor.map(attempt, range(20)))
            self.assertEqual(results.count(0), 5)
            self.assertEqual(sum(value > 0 for value in results), 15)

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
