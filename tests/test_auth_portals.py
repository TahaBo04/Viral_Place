import unittest

from app import create_app, initialize_database
from models.user import User


class AuthPortalTests(unittest.TestCase):
    def setUp(self):
        class TestConfig:
            TESTING = True
            SECRET_KEY = "portal-test"
            SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            SQLALCHEMY_ENGINE_OPTIONS = {}
            SESSION_COOKIE_SECURE = False
            WTF_CSRF_ENABLED = False

        self.app = create_app(TestConfig)
        initialize_database(self.app)
        self.client = self.app.test_client()

    def register_brand(self):
        return self.client.post(
            "/auth/register/business",
            data={
                "first_name": "Brand",
                "last_name": "Owner",
                "email": "brand-portal@test.local",
                "password": "BrandPass123!",
                "company_name": "Portal Brand",
                "company_website": "https://example.com",
                "phone_region": "MA",
                "phone_national_number": "0612345610",
                "phone_active_confirmed": "on",
            },
        )

    def register_creator(self):
        return self.client.post(
            "/auth/register/influencer",
            data={
                "first_name": "Creator",
                "last_name": "One",
                "email": "creator-portal@test.local",
                "password": "CreatorPass123!",
                "platforms": "instagram",
                "social_url_instagram": "https://instagram.com/creator",
                "audience_count_instagram": "12000",
                "primary_platform": "instagram",
                "phone_region": "MA",
                "phone_national_number": "0612345611",
                "phone_active_confirmed": "on",
            },
        )

    def test_registration_forms_only_show_relevant_fields(self):
        brand_form = self.client.get("/auth/register/business").data
        creator_form = self.client.get("/auth/register/influencer").data
        self.assertIn(b'name="company_name"', brand_form)
        self.assertNotIn(b'name="social_url_instagram"', brand_form)
        self.assertIn(b'name="social_url_instagram"', creator_form)
        self.assertNotIn(b'name="company_name"', creator_form)

    def test_accounts_only_enter_through_their_own_portal(self):
        self.register_brand()
        self.client.post("/auth/logout")
        self.register_creator()
        self.client.post("/auth/logout")

        creator_in_brand_portal = self.client.post(
            "/auth/login/business",
            data={"email": "creator-portal@test.local", "password": "CreatorPass123!"},
        )
        self.assertEqual(creator_in_brand_portal.status_code, 403)
        self.assertIn(b"influencer portal", creator_in_brand_portal.data)

        brand_in_creator_portal = self.client.post(
            "/auth/login/influencer",
            data={"email": "brand-portal@test.local", "password": "BrandPass123!"},
        )
        self.assertEqual(brand_in_creator_portal.status_code, 403)
        self.assertIn(b"brand portal", brand_in_creator_portal.data)

    def test_brand_can_open_profile_and_update_phone(self):
        self.register_brand()
        dashboard = self.client.get("/business/dashboard")
        self.assertIn(b'href="/profile/edit"', dashboard.data)

        response = self.client.post(
            "/profile/edit",
            data={
                "first_name": "Brand",
                "last_name": "Owner",
                "company_name": "Portal Brand",
                "company_website": "https://example.com",
                "phone_region": "MA",
                "phone_national_number": "0612345619",
                "phone_active_confirmed": "on",
                "bio": "Updated contact details.",
            },
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            user = User.query.filter_by(email="brand-portal@test.local").first()
            self.assertEqual(user.phone_number, "+212612345619")


if __name__ == "__main__":
    unittest.main()
