from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

from werkzeug.security import check_password_hash, generate_password_hash

from app import create_app, initialize_database
from extensions import db
from models.account_email import AccountEmail
from models.user import User
from services.account_security_service import action_token, consume_action, dispatch_mail, queue_email


class AccountSecurityTests(unittest.TestCase):
    def setUp(self):
        class TestConfig:
            TESTING = True
            SECRET_KEY = "account-test-secret-not-for-production"
            SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            WTF_CSRF_ENABLED = False
            SESSION_PROTECTION = None
            RESEND_API_KEY = "test-provider-key"
            MAIL_FROM = "accounts@briefvora.test"
            SUPPORT_EMAIL = "support@briefvora.test"
            PUBLIC_BASE_URL = "https://briefvora.test"

        self.app = create_app(TestConfig)
        initialize_database(self.app)
        self.client = self.app.test_client()
        with self.app.app_context():
            user = User(first_name="Test", last_name="Account", role="business", email="owner@example.test", password_hash=generate_password_hash("OriginalPassword123!"))
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()

    def make_token(self, purpose="reset"):
        user = db.session.get(User, self.user_id)
        job = queue_email(user.email, purpose, user)
        db.session.commit()
        return job, action_token(job)

    def login(self, client=None):
        with (client or self.client).session_transaction() as session:
            session["_user_id"] = f"{self.user_id}:0"
            session["_fresh"] = True

    def test_reset_does_not_enumerate_accounts_or_send_synchronously(self):
        with patch("services.account_security_service.send_email") as send:
            known = self.client.post("/auth/forgot-password", data={"email": "owner@example.test"})
            unknown = self.client.post("/auth/forgot-password", data={"email": "missing@example.test"})
            self.assertEqual(known.status_code, 202)
            self.assertEqual(unknown.status_code, 202)
            self.assertEqual(known.data, unknown.data)
            send.assert_not_called()
        with self.app.app_context():
            self.assertEqual(AccountEmail.query.count(), 2)

    def test_tokens_expire_are_single_use_and_bound_to_purpose(self):
        with self.app.app_context():
            job, token = self.make_token()
            self.assertNotEqual(job.token_hash, token)
            self.assertFalse(consume_action(token, "verify"))
            self.assertFalse(consume_action(token + "x", "reset", "ChangedPassword123!"))
            self.assertTrue(consume_action(token, "reset", "ChangedPassword123!"))
            self.assertFalse(consume_action(token, "reset", "AttackerPassword123!"))
            user = db.session.get(User, self.user_id)
            self.assertTrue(check_password_hash(user.password_hash, "ChangedPassword123!"))
            self.assertEqual(user.auth_version, 1)
            job, token = self.make_token()
            job.expires_at = datetime.utcnow() - timedelta(seconds=1)
            db.session.commit()
            self.assertFalse(consume_action(token, "reset", "AnotherPassword123!"))

    def test_reset_revokes_sessions_remember_cookie_and_other_reset_links(self):
        other = self.app.test_client()
        other.post("/auth/login/business", data={"email": "owner@example.test", "password": "OriginalPassword123!", "remember": "on"})
        self.login()
        with self.app.app_context():
            _, token = self.make_token()
            _, second = self.make_token()
        response = self.client.post("/auth/reset-password", data={"token": token, "new_password": "NewLongPassword123!", "confirm_password": "NewLongPassword123!"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(other.get("/auth/security").status_code, 302)
        with other.session_transaction() as session:
            session.clear()
        self.assertEqual(other.get("/auth/security").status_code, 302)
        with self.app.app_context():
            self.assertFalse(consume_action(second, "reset", "DifferentPassword123!"))

    def test_password_change_requires_current_password_and_revokes_all_sessions(self):
        other = self.app.test_client()
        self.login()
        self.login(other)
        form = {"current_password": "wrong", "new_password": "NewLongPassword123!", "confirm_password": "NewLongPassword123!"}
        self.assertEqual(self.client.post("/auth/security", data=form).status_code, 400)
        form["current_password"] = "OriginalPassword123!"
        self.assertEqual(self.client.post("/auth/security", data=form).status_code, 302)
        self.assertEqual(other.get("/auth/security").status_code, 302)

    def test_verification_does_not_consume_on_get_or_log_in_the_visitor(self):
        with self.app.app_context():
            _, token = self.make_token("verify")
        self.assertEqual(self.client.get("/auth/verify-email").status_code, 200)
        with self.app.app_context():
            self.assertIsNone(db.session.get(User, self.user_id).email_verified_at)
        self.assertEqual(self.client.post("/auth/verify-email", data={"token": token}).status_code, 302)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(User, self.user_id).email_verified_at)
        with self.client.session_transaction() as session:
            self.assertNotIn("_user_id", session)

    def test_required_verification_blocks_marketplace_writes_not_logout(self):
        self.app.config["EMAIL_VERIFICATION_REQUIRED"] = True
        self.login()
        self.assertEqual(self.client.post("/profile/edit", data={}).status_code, 403)
        self.assertEqual(self.client.get("/auth/security").status_code, 200)
        self.assertEqual(self.client.post("/auth/logout").status_code, 302)

    def test_email_not_configured_is_honest_and_required_mode_fails_closed(self):
        self.app.config["RESEND_API_KEY"] = ""
        self.assertEqual(self.client.get("/auth/forgot-password").status_code, 503)
        from services.account_security_service import validate_email_config
        self.app.config["EMAIL_VERIFICATION_REQUIRED"] = True
        with self.assertRaises(RuntimeError):
            validate_email_config(self.app)

    def test_per_account_quota_and_unknown_recipients_never_sent(self):
        for _ in range(4):
            self.client.post("/auth/forgot-password", data={"email": "owner@example.test"})
        self.client.post("/auth/forgot-password", data={"email": "missing@example.test"})
        with self.app.app_context(), patch("services.account_security_service.send_email") as send:
            self.assertEqual(AccountEmail.query.filter_by(user_id=self.user_id).count(), 3)
            self.assertEqual(dispatch_mail(), 3)
            self.assertEqual(send.call_count, 3)
            self.assertEqual(dispatch_mail(), 0)

    def test_delivery_retry_keeps_same_token_and_does_not_expose_failure_details(self):
        with self.app.app_context():
            job, token = self.make_token()
            with patch("services.account_security_service.send_email", side_effect=RuntimeError("sensitive-provider-error")):
                self.assertEqual(dispatch_mail(), 0)
            self.assertEqual(job.attempts, 1)
            self.assertIsNone(job.sent_at)
            self.assertEqual(action_token(job), token)
            self.assertGreater(job.next_attempt_at, datetime.utcnow())

    def test_fixed_email_origin_and_fragment_token(self):
        from services.account_security_service import send_email, validate_email_config
        import json
        with self.app.app_context(), patch("services.account_security_service.http.client.HTTPSConnection") as connection:
            job, token = self.make_token()
            response = connection.return_value.getresponse.return_value
            response.status = 200
            response.read.return_value = b'{"id":"accepted"}'
            send_email(job)
            body = json.loads(connection.return_value.request.call_args.args[2])
            self.assertIn("https://briefvora.test/auth/reset-password#token=" + token, body["text"])
            self.assertEqual(connection.call_args.args, ("api.resend.com",))
        self.app.config["PUBLIC_BASE_URL"] = "https://attacker.test@briefvora.test"
        with self.assertRaises(RuntimeError):
            validate_email_config(self.app)

    def test_reset_post_requires_csrf(self):
        self.app.config["WTF_CSRF_ENABLED"] = True
        self.assertEqual(self.client.post("/auth/reset-password", data={"token": "invalid"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
