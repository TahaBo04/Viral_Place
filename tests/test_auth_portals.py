import unittest

from app import create_app, initialize_database


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
                "phone_number": "+212612345610",
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
                "social_profile_url": "https://instagram.com/creator",
                "phone_number": "+212612345611",
                "phone_active_confirmed": "on",
            },
        )

    def test_registration_forms_only_show_relevant_fields(self):
        brand_form = self.client.get("/auth/register/business").data
        creator_form = self.client.get("/auth/register/influencer").data
        self.assertIn(b'name="company_name"', brand_form)
        self.assertNotIn(b'name="social_profile_url"', brand_form)
        self.assertIn(b'name="social_profile_url"', creator_form)
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


if __name__ == "__main__":
    unittest.main()
