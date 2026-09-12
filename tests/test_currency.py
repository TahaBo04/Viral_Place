import unittest
from unittest.mock import patch

from sqlalchemy import text

from app import create_app
from extensions import db
from models.campaign import Campaign
from models.creator import CreatorProfile
from models.offer import CollaborationOffer
from models.order import Order
from services.payment_service import bank_details
from services.schema_service import apply_compatible_schema_updates
import test_marketplace_workflow as workflow


class CurrencyWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.flow = workflow.MarketplaceWorkflowTests()
        self.flow.setUp()
        self.app = self.flow.app
        self.client = self.flow.client
        self.app.config.update(
            MARKETPLACE_CURRENCY="mad", COMPANY_BANK_CURRENCY="mad",
            COMPANY_RIB="123456789012345678901234", COMPANY_BANK_NAME="Example Bank",
            COMPANY_ACCOUNT_HOLDER="Example Account Holder",
        )

    def make_mad_order(self):
        with self.app.app_context():
            db.session.get(Campaign, self.flow.private_id).currency = "mad"
            db.session.get(CreatorProfile, self.flow.creator_ids[0][1]).currency = "mad"
            db.session.commit()
        return self.flow.accepted_order()

    def test_mad_offer_order_and_transfer_preserve_exact_amount(self):
        order_id = self.make_mad_order()
        with self.app.app_context():
            order = db.session.get(Order, order_id)
            self.assertEqual(order.currency, "mad")
            self.assertEqual(order.offer.currency, "mad")
            self.assertEqual(order.amount_cents, 80000)
            self.assertEqual(order.influencer_payout_cents, 56000)
            self.assertEqual(bank_details()["currency"], "mad")
        self.flow.login_as(self.flow.brand_id)
        page = self.client.get(f"/orders/{order_id}").data
        self.assertIn(b"800.00 MAD", page)
        self.assertIn(b"Moroccan dirham", page)
        self.assertNotIn(b"USD", page)
        self.assertNotIn(b"$", page)
        instructions = self.client.get(f"/orders/{order_id}/transfer-instructions?currency=usd&amount=1").data
        self.assertIn(b"Amount to transfer: 800.00 MAD", instructions)
        self.assertIn(b"Transfer currency: MAD", instructions)
        self.client.post(f"/orders/{order_id}/report-transfer")
        self.flow.login_as(self.flow.admin_id)
        self.client.post(f"/admin/orders/{order_id}/mark-paid", data={"reference": "BANK-MAD-123"})
        with self.app.app_context():
            order = db.session.get(Order, order_id)
            self.assertEqual(order.status, "in_production")
            self.assertEqual(order.currency, "mad")
            self.assertEqual(order.amount_cents, 80000)

    def test_legacy_usd_is_not_relabelled_or_accepted_as_mad(self):
        order_id = self.flow.accepted_order()
        self.flow.login_as(self.flow.brand_id)
        page = self.client.get(f"/orders/{order_id}").data
        self.assertIn(b"800.00 USD", page)
        self.assertIn(b"Currency review required", page)
        self.assertNotIn(b"123456789012345678901234", page)
        self.assertEqual(self.client.get(f"/orders/{order_id}/transfer-instructions").status_code, 409)
        self.assertEqual(self.client.post(f"/orders/{order_id}/report-transfer", data={"currency": "mad"}).status_code, 409)
        self.flow.login_as(self.flow.admin_id)
        self.client.post(f"/admin/orders/{order_id}/mark-paid", data={"reference": "BANK-MAD-123"})
        with self.app.app_context():
            order = db.session.get(Order, order_id)
            self.assertEqual(order.currency, "usd")
            self.assertEqual(order.amount_cents, 80000)
            self.assertEqual(order.payment_status, "unpaid")

    def test_mismatched_campaign_and_creator_cannot_create_offer(self):
        with self.app.app_context():
            db.session.get(Campaign, self.flow.private_id).currency = "mad"
            db.session.commit()
        self.flow.login_as(self.flow.brand_id)
        self.flow.send_offer(self.flow.creator_ids[0][1])
        with self.app.app_context():
            self.assertEqual(CollaborationOffer.query.count(), 0)

    def test_new_campaign_currency_is_server_selected(self):
        self.flow.login_as(self.flow.brand_id)
        response = self.client.post("/campaigns/new", data={
            "title": "New MAD campaign", "campaign_mode": "public", "industry": "Technology",
            "target_niche": "Technology", "target_platforms": "instagram", "target_country": "Morocco",
            "budget_min": "800", "budget_max": "1500", "goal": "Awareness",
            "brief": "A new campaign in Moroccan dirhams.", "deliverables": "One video.", "currency": "usd",
        })
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            campaign = Campaign.query.filter_by(title="New MAD campaign").one()
            self.assertEqual(campaign.currency, "mad")
            self.assertEqual(campaign.budget_min, 800)
        self.assertIn(b"BUDGET (MAD)", self.client.get("/campaigns/new").data)

    def test_creator_rate_edit_preserves_legacy_currency(self):
        creator_id, profile_id = self.flow.creator_ids[0]
        self.flow.login_as(creator_id)
        self.assertIn(b"PRICE (USD)", self.client.get("/creators/onboarding").data)
        with self.app.app_context():
            self.assertEqual(db.session.get(CreatorProfile, profile_id).currency, "usd")

    def test_new_creator_rate_currency_is_server_selected(self):
        with self.app.app_context():
            user = self.flow._user("new-mad-creator@flow.test", "influencer", "+212612345678")
            db.session.commit()
            user_id = user.id
        self.flow.login_as(user_id)
        self.assertIn(b"PRICE (MAD)", self.client.get("/creators/onboarding").data)
        response = self.client.post("/creators/onboarding", data={
            "display_name": "MAD Creator", "niche": "Technology", "audience_country": "Morocco",
            "engagement_rate": "4.5", "starting_rate": "500", "currency": "usd",
            "media_kit_summary": "Technology content in Morocco.", "platforms": "instagram",
            "social_url_instagram": "https://instagram.com/madcreator", "audience_count_instagram": "12000",
            "primary_platform": "instagram",
        })
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            profile = CreatorProfile.query.filter_by(user_id=user_id).one()
            self.assertEqual(profile.currency, "mad")
            self.assertEqual(profile.starting_rate, 500)

    def test_invalid_bank_currency_disables_instructions(self):
        self.app.config["COMPANY_BANK_CURRENCY"] = "not-a-currency"
        with self.app.app_context():
            self.assertIsNone(bank_details())


class CurrencyMigrationTests(unittest.TestCase):
    def test_legacy_schema_preserves_usd_and_amounts_on_repeated_migration(self):
        class TestConfig:
            TESTING = True
            SECRET_KEY = "migration-test"
            SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
        app = create_app(TestConfig)
        with app.app_context():
            for ddl in (
                "CREATE TABLE users (id INTEGER PRIMARY KEY, phone_number TEXT, phone_region TEXT, phone_confirmed_at TIMESTAMP)",
                "CREATE TABLE campaigns (id INTEGER PRIMARY KEY, budget_min INTEGER, visibility TEXT, closed_at TIMESTAMP)",
                "CREATE TABLE creator_profiles (id INTEGER PRIMARY KEY, starting_rate INTEGER)",
                "CREATE TABLE collaboration_offers (id INTEGER PRIMARY KEY, amount_cents INTEGER)",
                "INSERT INTO campaigns (id, budget_min) VALUES (1, 800)",
                "INSERT INTO creator_profiles (id, starting_rate) VALUES (1, 500)",
                "INSERT INTO collaboration_offers (id, amount_cents) VALUES (1, 80000)",
            ):
                db.session.execute(text(ddl))
            db.session.commit()
            with patch("services.schema_service._backfill_profile_data"):
                apply_compatible_schema_updates()
                apply_compatible_schema_updates()
            self.assertEqual(tuple(db.session.execute(text("SELECT budget_min, currency FROM campaigns")).one()), (800, "usd"))
            self.assertEqual(tuple(db.session.execute(text("SELECT starting_rate, currency FROM creator_profiles")).one()), (500, "usd"))
            self.assertEqual(tuple(db.session.execute(text("SELECT amount_cents, currency FROM collaboration_offers")).one()), (80000, "usd"))
