from datetime import datetime
import unittest

from werkzeug.security import generate_password_hash

from app import create_app, initialize_database
from extensions import db
from models.campaign import Campaign
from models.creator import CreatorProfile
from models.offer import CollaborationOffer
from models.order import Order
from models.social import CreatorSocialAccount
from models.user import User


class MarketplaceWorkflowTests(unittest.TestCase):
    def setUp(self):
        class TestConfig:
            TESTING = True
            SECRET_KEY = "marketplace-test"
            SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            SQLALCHEMY_ENGINE_OPTIONS = {}
            SESSION_COOKIE_SECURE = False
            SESSION_PROTECTION = None
            WTF_CSRF_ENABLED = False
            MAX_OFFER_AMOUNT = 1_000_000

        self.app = create_app(TestConfig)
        initialize_database(self.app)
        self.client = self.app.test_client()
        with self.app.app_context():
            self.brand = self._user("brand@flow.test", "business", "+12025550101", company_name="Flow Brand")
            self.admin = self._user("admin@flow.test", "admin", None)
            self.creators = []
            for index in range(3):
                user = self._user(f"creator{index}@flow.test", "influencer", f"+3361234567{index}")
                social = CreatorSocialAccount(
                    user_id=user.id,
                    platform="instagram",
                    profile_url=f"https://instagram.com/creator{index}",
                    audience_count=20000 + index * 1000,
                    is_primary=True,
                )
                profile = CreatorProfile(
                    user_id=user.id,
                    display_name=f"Creator {index}",
                    niche="Technology",
                    platforms="Instagram",
                    audience_country="France",
                    followers=social.audience_count,
                    engagement_rate=4.5,
                    starting_rate=500 + index * 100,
                    media_kit_summary="Technology creator profile.",
                    social_proof_url=social.profile_url,
                    verification_code=f"VP-FLOW{index}",
                    verification_status="verified",
                )
                db.session.add_all([social, profile])
                self.creators.append((user, profile))
            self.private_campaign = self._campaign("Private launch", "private")
            self.public_campaign = self._campaign("Public launch", "public")
            db.session.commit()
            self.brand_id = self.brand.id
            self.admin_id = self.admin.id
            self.creator_ids = [(user.id, profile.id) for user, profile in self.creators]
            self.private_id = self.private_campaign.id
            self.public_id = self.public_campaign.id

    def _user(self, email, role, phone, **kwargs):
        user = User(
            first_name=role.title(),
            last_name="User",
            email=email,
            password_hash=generate_password_hash("Password123!"),
            role=role,
            phone_number=phone,
            phone_region="US" if phone and phone.startswith("+1") else "FR" if phone else None,
            phone_confirmed_at=datetime.utcnow() if phone else None,
            **kwargs,
        )
        db.session.add(user)
        db.session.flush()
        return user

    def _campaign(self, title, visibility, flow_type="marketplace"):
        campaign = Campaign(
            business_id=self.brand.id,
            flow_type=flow_type,
            visibility=visibility,
            title=title,
            industry="Technology",
            target_niche="Technology",
            target_platforms="instagram,youtube",
            target_country="France",
            budget_min=500,
            budget_max=2000,
            goal="Awareness",
            brief="A confidential creator campaign brief.",
            deliverables="One vertical video.",
            status="open",
        )
        db.session.add(campaign)
        db.session.flush()
        return campaign

    def login_as(self, user_id):
        with self.client.session_transaction() as session:
            session.clear()
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

    def send_offer(self, creator_profile_id, amount=700):
        return self.client.post(
            f"/creators/{creator_profile_id}/invite",
            data={"campaign_id": self.private_id, "offer_amount": str(amount), "message": "Private launch offer."},
        )

    def accepted_order(self):
        creator_id, profile_id = self.creator_ids[0]
        self.login_as(self.brand_id)
        self.send_offer(profile_id, amount=800)
        with self.app.app_context():
            offer_id = CollaborationOffer.query.one().id
        self.login_as(creator_id)
        self.client.post(f"/offers/{offer_id}/accept")
        with self.app.app_context():
            return Order.query.one().id

    def test_bank_details_wait_for_configuration_and_only_reach_buyer(self):
        order_id = self.accepted_order()
        self.login_as(self.brand_id)
        response = self.client.get(f"/orders/{order_id}")
        self.assertIn(b"Awaiting company bank details", response.data)
        self.app.config.update(COMPANY_RIB="123456789012345678901234", COMPANY_BANK_NAME="Bank Example", COMPANY_ACCOUNT_HOLDER="Example Company")
        response = self.client.get(f"/orders/{order_id}")
        self.assertIn(b"123456789012345678901234", response.data)
        self.assertNotIn(b"STRIPE", response.data)
        self.login_as(self.creator_ids[0][0])
        self.assertNotIn(b"123456789012345678901234", self.client.get(f"/orders/{order_id}").data)
        self.login_as(self.creator_ids[1][0])
        self.assertEqual(self.client.get(f"/orders/{order_id}").status_code, 403)

    def test_buyer_cannot_fake_payment_using_url_or_post(self):
        order_id = self.accepted_order()
        self.login_as(self.brand_id)
        self.client.get(f"/orders/{order_id}/payment/success?session_id=fake&payment_status=paid")
        self.client.post(f"/orders/{order_id}/checkout", data={"amount": "1", "payment_status": "paid", "COMPANY_RIB": "ATTACKER"})
        self.assertEqual(self.client.post(f"/admin/orders/{order_id}/mark-paid", data={"reference": "FAKE"}).status_code, 403)
        with self.app.app_context():
            order = db.session.get(Order, order_id)
            self.assertEqual(order.payment_status, "unpaid")
            self.assertEqual(order.amount_cents, 80000)

    def test_transfer_report_alerts_admin_once_without_confirming_payment(self):
        from models.notification import Notification

        order_id = self.accepted_order()
        self.app.config.update(COMPANY_RIB="123456789012345678901234", COMPANY_BANK_NAME="Bank Example", COMPANY_ACCOUNT_HOLDER="Example Company")
        self.login_as(self.brand_id)
        for _ in range(2):
            response = self.client.post(f"/orders/{order_id}/report-transfer", data={"payment_status": "paid", "amount": "1"})
            self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            order = db.session.get(Order, order_id)
            self.assertEqual(order.payment_status, "unpaid")
            self.assertEqual(order.status, "awaiting_payment")
            self.assertEqual(order.amount_cents, 80000)
            self.assertEqual(sum(e.event_type == "transfer_reported" for e in order.events), 1)
            self.assertEqual(Notification.query.filter_by(title="Transfer awaiting verification", user_id=self.admin_id).count(), 1)
        page = self.client.get(f"/orders/{order_id}").data
        self.assertIn(b"Awaiting bank verification", page)
        self.assertNotIn(b"I sent the transfer", page)
        self.login_as(self.admin_id)
        self.assertIn(b"Customer reported a transfer", self.client.get(f"/admin/orders/{order_id}").data)
        self.client.post(f"/admin/orders/{order_id}/mark-paid", data={"reference": "BANK-VERIFIED-123"})
        with self.app.app_context():
            self.assertEqual(db.session.get(Order, order_id).status, "in_production")
            self.assertEqual(Notification.query.filter_by(title="Start production", user_id=self.creator_ids[0][0]).count(), 1)
            self.assertEqual(Notification.query.filter_by(title="Payment confirmed", user_id=self.brand_id).count(), 1)

    def test_transfer_actions_require_buyer_and_complete_bank_details(self):
        order_id = self.accepted_order()
        self.login_as(self.brand_id)
        self.assertEqual(self.client.post(f"/orders/{order_id}/report-transfer").status_code, 409)
        self.assertEqual(self.client.get(f"/orders/{order_id}/transfer-instructions").status_code, 409)
        self.app.config.update(COMPANY_RIB="123456789012345678901234", COMPANY_BANK_NAME="Bank Example", COMPANY_ACCOUNT_HOLDER="Example Company")
        for user_id in [self.creator_ids[0][0], self.creator_ids[1][0], self.admin_id]:
            self.login_as(user_id)
            self.assertEqual(self.client.post(f"/orders/{order_id}/report-transfer").status_code, 403)
            self.assertEqual(self.client.get(f"/orders/{order_id}/transfer-instructions").status_code, 403)
        self.login_as(self.brand_id)
        self.assertEqual(self.client.get(f"/orders/{order_id}/report-transfer").status_code, 405)
        self.app.config["WTF_CSRF_ENABLED"] = True
        self.assertEqual(self.client.post(f"/orders/{order_id}/report-transfer").status_code, 400)

    def test_transfer_download_uses_server_values_and_is_not_cached(self):
        order_id = self.accepted_order()
        self.app.config.update(COMPANY_RIB="123456789012345678901234", COMPANY_BANK_NAME="Bank Example", COMPANY_ACCOUNT_HOLDER="Example Company")
        self.login_as(self.brand_id)
        response = self.client.get(f"/orders/{order_id}/transfer-instructions?amount=1&rib=ATTACKER")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/plain")
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertIn(f'briefvora-transfer-{order_id}.txt', response.headers["Content-Disposition"])
        for value in [b"123456789012345678901234", b"800.00 USD", f"BRIEFVORA-{order_id}".encode(), b"not a payment receipt"]:
            self.assertIn(value, response.data)
        self.assertNotIn(b"ATTACKER", response.data)

    def test_transfer_actions_reject_ineligible_orders(self):
        order_id = self.accepted_order()
        self.app.config.update(COMPANY_RIB="123456789012345678901234", COMPANY_BANK_NAME="Bank Example", COMPANY_ACCOUNT_HOLDER="Example Company")
        self.login_as(self.brand_id)
        for status, payment, offer in [("awaiting_payment", "unpaid", "pending"), ("in_production", "paid", "accepted"), ("refunded", "refunded", "accepted"), ("cancelled", "unpaid", "accepted")]:
            with self.app.app_context():
                order = db.session.get(Order, order_id)
                order.status, order.payment_status, order.offer.status = status, payment, offer
                db.session.commit()
            self.assertEqual(self.client.post(f"/orders/{order_id}/report-transfer").status_code, 409)
            self.assertEqual(self.client.get(f"/orders/{order_id}/transfer-instructions").status_code, 409)
            self.assertNotIn(b"I sent the transfer", self.client.get(f"/orders/{order_id}").data)

    def test_admin_confirmation_is_fresh_referenced_and_idempotent(self):
        order_id = self.accepted_order()
        self.login_as(self.admin_id)
        with self.client.session_transaction() as session:
            session["_fresh"] = False
        self.assertEqual(self.client.post(f"/admin/orders/{order_id}/mark-paid", data={"reference": "BANK-123"}).status_code, 403)
        self.login_as(self.admin_id)
        self.client.post(f"/admin/orders/{order_id}/mark-paid", data={})
        with self.app.app_context():
            self.assertEqual(db.session.get(Order, order_id).payment_status, "unpaid")
        for _ in range(2):
            self.client.post(f"/admin/orders/{order_id}/mark-paid", data={"reference": "BANK-123"})
        with self.app.app_context():
            order = db.session.get(Order, order_id)
            self.assertEqual(order.payment_status, "paid")
            self.assertEqual(order.status, "in_production")
            self.assertEqual(sum(event.event_type == "payment_confirmed" for event in order.events), 1)

    def test_delivery_links_reject_active_content_and_private_hosts(self):
        from models.order import Submission
        order_id = self.accepted_order()
        self.login_as(self.admin_id)
        self.client.post(f"/admin/orders/{order_id}/mark-paid", data={"reference": "BANK-123"})
        self.login_as(self.creator_ids[0][0])
        for url in ("javascript:alert(1)", "https://localhost/secret", "http://example.com/video", "https://127.0.0.1/admin"):
            self.client.post(f"/orders/{order_id}/submit", data={"video_url": url})
        with self.app.app_context():
            self.assertEqual(Submission.query.count(), 0)
        self.client.post(f"/orders/{order_id}/submit", data={"video_url": "https://example.com/video", "notes": "<script>alert(1)</script>"})
        response = self.client.get(f"/orders/{order_id}")
        self.assertIn(b"&lt;script&gt;", response.data)
        self.assertNotIn(b"<script>alert(1)</script>", response.data)

    def test_private_campaign_is_hidden_until_invited(self):
        self.assertEqual(self.client.get(f"/campaigns/{self.private_id}").status_code, 404)
        listing = self.client.get("/campaigns/")
        self.assertNotIn(b"Private launch", listing.data)
        self.assertIn(b"Public launch", listing.data)
        self.assertNotIn(b"Private launch", self.client.get("/").data)

        creator_user_id, creator_profile_id = self.creator_ids[0]
        self.login_as(creator_user_id)
        self.assertEqual(self.client.get(f"/campaigns/{self.private_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/campaigns/{self.private_id}/apply").status_code, 404)

        self.login_as(self.brand_id)
        self.assertEqual(self.send_offer(creator_profile_id).status_code, 302)
        self.login_as(creator_user_id)
        response = self.client.get(f"/campaigns/{self.private_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"confidential creator campaign", response.data.lower())

        self.login_as(self.admin_id)
        self.assertEqual(self.client.get(f"/campaigns/{self.private_id}").status_code, 200)

    def test_offer_requires_minimum_and_acceptance_before_order(self):
        creator_user_id, creator_profile_id = self.creator_ids[0]
        self.login_as(self.brand_id)
        below_minimum = self.send_offer(creator_profile_id, amount=499)
        self.assertEqual(below_minimum.status_code, 302)
        with self.app.app_context():
            self.assertEqual(CollaborationOffer.query.count(), 0)
            self.assertEqual(Order.query.count(), 0)

        self.send_offer(creator_profile_id, amount=800)
        with self.app.app_context():
            offer = CollaborationOffer.query.one()
            offer_id = offer.id
            self.assertEqual(offer.status, "pending")
            self.assertEqual(offer.creator_payout_cents, 56000)
            self.assertEqual(Order.query.count(), 0)

        self.login_as(creator_user_id)
        accepted = self.client.post(f"/offers/{offer_id}/accept")
        self.assertEqual(accepted.status_code, 302)
        with self.app.app_context():
            order = Order.query.one()
            self.assertEqual(order.amount_cents, 80000)
            self.assertEqual(order.offer.status, "accepted")
            self.assertEqual(order.payment_status, "unpaid")

    def test_checkout_and_manual_payment_reject_pending_offer(self):
        _creator_user_id, creator_profile_id = self.creator_ids[0]
        self.login_as(self.brand_id)
        self.send_offer(creator_profile_id, amount=800)
        with self.app.app_context():
            from services.order_service import create_order

            offer = CollaborationOffer.query.one()
            order = create_order(
                offer.campaign,
                offer.amount_cents,
                creator_profile=offer.creator_profile,
                application=offer.application,
                offer=offer,
            )
            db.session.commit()
            order_id = order.id
        checkout = self.client.post(f"/orders/{order_id}/checkout")
        self.assertEqual(checkout.status_code, 302)
        self.login_as(self.admin_id)
        manual = self.client.post(f"/admin/orders/{order_id}/mark-paid", data={"reference": "TEST"})
        self.assertEqual(manual.status_code, 302)
        with self.app.app_context():
            self.assertEqual(db.session.get(Order, order_id).payment_status, "unpaid")

    def test_multiple_creators_and_campaign_closure(self):
        offer_ids = []
        self.login_as(self.brand_id)
        for _user_id, profile_id in self.creator_ids:
            self.send_offer(profile_id, amount=900)
        with self.app.app_context():
            offer_ids = [offer.id for offer in CollaborationOffer.query.order_by(CollaborationOffer.id).all()]

        for (user_id, _profile_id), offer_id in zip(self.creator_ids[:2], offer_ids[:2]):
            self.login_as(user_id)
            self.client.post(f"/offers/{offer_id}/accept")

        self.login_as(self.brand_id)
        closed = self.client.post(f"/campaigns/{self.private_id}/close")
        self.assertEqual(closed.status_code, 302)
        with self.app.app_context():
            self.assertEqual(Order.query.count(), 2)
            statuses = [offer.status for offer in CollaborationOffer.query.order_by(CollaborationOffer.id).all()]
            self.assertEqual(statuses, ["accepted", "accepted", "withdrawn"])
            campaign = db.session.get(Campaign, self.private_id)
            self.assertEqual(campaign.status, "closed")

        self.login_as(self.creator_ids[0][0])
        self.assertEqual(self.client.get(f"/campaigns/{self.private_id}").status_code, 200)
        self.login_as(self.creator_ids[2][0])
        self.assertEqual(self.client.get(f"/campaigns/{self.private_id}").status_code, 404)

    def test_managed_recommendation_waits_for_brand_offer_and_creator_acceptance(self):
        with self.app.app_context():
            managed = self._campaign("Managed private launch", "private", flow_type="managed")
            db.session.commit()
            managed_id = managed.id
        creator_user_id, creator_profile_id = self.creator_ids[0]

        self.login_as(self.admin_id)
        recommended = self.client.post(
            f"/admin/campaigns/{managed_id}/recommend",
            data={"creator_profile_id": str(creator_profile_id)},
        )
        self.assertEqual(recommended.status_code, 302)
        with self.app.app_context():
            campaign = db.session.get(Campaign, managed_id)
            application = campaign.applications[0]
            application_id = application.id
            self.assertEqual(application.status, "recommended")
            self.assertEqual(Order.query.count(), 0)

        self.login_as(self.brand_id)
        self.client.post(
            f"/campaigns/{managed_id}/applications/{application_id}/select",
            data={"offer_amount": "750"},
        )
        with self.app.app_context():
            offer = CollaborationOffer.query.filter_by(campaign_id=managed_id).one()
            offer_id = offer.id
            self.assertEqual(Order.query.count(), 0)

        self.login_as(creator_user_id)
        self.assertEqual(self.client.get(f"/campaigns/{managed_id}").status_code, 200)
        self.client.post(f"/offers/{offer_id}/accept")
        with self.app.app_context():
            self.assertEqual(Order.query.filter_by(campaign_id=managed_id).count(), 1)


if __name__ == "__main__":
    unittest.main()
