from datetime import datetime
import unittest

from werkzeug.security import generate_password_hash

from app import create_app, initialize_database
from extensions import db
from models.campaign import Campaign
from models.creator import CreatorProfile
from models.order import Order
from models.review import DealReview
from models.user import User


class ReviewAndContactTests(unittest.TestCase):
    def setUp(self):
        class TestConfig:
            TESTING = True
            SECRET_KEY = "review-test"
            SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            SQLALCHEMY_ENGINE_OPTIONS = {}
            SESSION_COOKIE_SECURE = False
            WTF_CSRF_ENABLED = False

        self.app = create_app(TestConfig)
        initialize_database(self.app)
        self.client = self.app.test_client()
        with self.app.app_context():
            business = User(
                first_name="Brand",
                last_name="Owner",
                email="brand@reviews.test",
                password_hash=generate_password_hash("Password123!"),
                role="business",
                company_name="Review Brand",
                phone_number="+212612345621",
                phone_confirmed_at=datetime.utcnow(),
            )
            influencer = User(
                first_name="Creator",
                last_name="Partner",
                email="creator@reviews.test",
                password_hash=generate_password_hash("Password123!"),
                role="influencer",
                phone_number="+212612345622",
                phone_confirmed_at=datetime.utcnow(),
            )
            outsider = User(
                first_name="Outside",
                last_name="User",
                email="outside@reviews.test",
                password_hash=generate_password_hash("Password123!"),
                role="business",
                company_name="Outside Brand",
                phone_number="+212612345623",
            )
            admin = User(
                first_name="Operations",
                last_name="Admin",
                email="admin@reviews.test",
                password_hash=generate_password_hash("Password123!"),
                role="admin",
            )
            db.session.add_all([business, influencer, outsider, admin])
            db.session.flush()
            creator = CreatorProfile(
                user_id=influencer.id,
                display_name="Creator Partner",
                niche="Beauty",
                platforms="TikTok",
                audience_country="Morocco",
                followers=50000,
                engagement_rate=5.2,
                starting_rate=500,
                media_kit_summary="Short-form beauty campaigns.",
                verification_code="VP-TEST",
                verification_status="verified",
            )
            db.session.add(creator)
            db.session.flush()
            campaign = Campaign(
                business_id=business.id,
                title="Review campaign",
                industry="Beauty",
                target_niche="Beauty",
                target_platforms="TikTok",
                target_country="Morocco",
                budget_min=500,
                budget_max=1000,
                goal="Conversions",
                brief="Create a polished product demonstration.",
                deliverables="One vertical video.",
                status="complete",
            )
            db.session.add(campaign)
            db.session.flush()
            order = Order(
                campaign_id=campaign.id,
                business_id=business.id,
                influencer_id=influencer.id,
                creator_profile_id=creator.id,
                amount_cents=100000,
                influencer_payout_cents=70000,
                status="complete",
                payment_status="paid",
                payout_status="paid",
            )
            db.session.add(order)
            db.session.commit()
            self.business_id = business.id
            self.influencer_id = influencer.id
            self.outsider_id = outsider.id
            self.admin_id = admin.id
            self.order_id = order.id

    def login_as(self, user_id):
        with self.client.session_transaction() as session:
            session.clear()
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

    def test_both_parties_can_submit_one_private_review_after_completion(self):
        self.login_as(self.business_id)
        response = self.client.post(
            f"/orders/{self.order_id}/review",
            data={"rating": "4", "category": "suggestion", "comment": "Communication was good; faster updates would help."},
        )
        self.assertEqual(response.status_code, 302)

        duplicate = self.client.post(
            f"/orders/{self.order_id}/review",
            data={"rating": "5", "category": "praise", "comment": "This duplicate must not be stored."},
        )
        self.assertEqual(duplicate.status_code, 302)

        self.login_as(self.influencer_id)
        response = self.client.post(
            f"/orders/{self.order_id}/review",
            data={"rating": "5", "category": "praise", "comment": "Clear brief and a smooth payout process."},
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            self.assertEqual(DealReview.query.filter_by(order_id=self.order_id).count(), 2)

    def test_outsider_cannot_review_or_view_the_order(self):
        self.login_as(self.outsider_id)
        self.assertEqual(self.client.get(f"/orders/{self.order_id}").status_code, 403)
        response = self.client.post(
            f"/orders/{self.order_id}/review",
            data={"rating": "1", "category": "inconvenience", "comment": "I am not part of this deal."},
        )
        self.assertEqual(response.status_code, 403)

    def test_review_is_not_accepted_before_terminal_status(self):
        with self.app.app_context():
            order = db.session.get(Order, self.order_id)
            order.status = "in_production"
            db.session.commit()
        self.login_as(self.business_id)
        response = self.client.post(
            f"/orders/{self.order_id}/review",
            data={"rating": "3", "category": "suggestion", "comment": "This deal is not finished yet."},
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(DealReview.query.count(), 0)

    def test_phone_numbers_are_private_and_available_to_admin(self):
        public_profile = self.client.get(f"/profile/{self.business_id}")
        self.assertNotIn(b"+212612345621", public_profile.data)

        self.login_as(self.business_id)
        self.assertEqual(self.client.get("/admin/contacts").status_code, 403)

        self.login_as(self.admin_id)
        directory = self.client.get("/admin/contacts")
        self.assertEqual(directory.status_code, 200)
        self.assertIn(b"+212612345621", directory.data)
        self.assertIn(b"+212612345622", directory.data)


if __name__ == "__main__":
    unittest.main()
