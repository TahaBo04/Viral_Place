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
            WTF_CSRF_ENABLED = False
            MAX_OFFER_USD = 1_000_000

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
