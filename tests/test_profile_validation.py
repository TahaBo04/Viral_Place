import unittest

from werkzeug.datastructures import MultiDict

from services.contact_service import country_catalog, normalize_phone, phone_region
from services.platform_service import parse_social_accounts
from services.url_service import safe_https_url


class ProfileValidationTests(unittest.TestCase):
    def test_worldwide_phone_catalog_and_normalization(self):
        regions = {item["region"] for item in country_catalog()}
        self.assertTrue({"MA", "FR", "US", "JP", "BR", "ZA"}.issubset(regions))
        self.assertEqual(normalize_phone("06 12 34 56 78", "MA"), "+212612345678")
        self.assertEqual(normalize_phone("202-555-0123", "US"), "+12025550123")
        self.assertEqual(phone_region("+33612345678"), "FR")
        self.assertIsNone(normalize_phone("123", "FR"))

    def test_known_platform_requires_official_domain(self):
        valid = MultiDict(
            [
                ("platforms", "instagram"),
                ("social_url_instagram", "https://www.instagram.com/creator"),
                ("audience_count_instagram", "25000"),
                ("primary_platform", "instagram"),
            ]
        )
        self.assertEqual(parse_social_accounts(valid)[0]["audience_count"], 25000)

        invalid = valid.copy()
        invalid.setlist("social_url_instagram", ["https://evil.example/instagram/creator"])
        with self.assertRaises(ValueError):
            parse_social_accounts(invalid)

    def test_other_platform_rejects_unsafe_links(self):
        for unsafe in ("http://example.com/me", "https://127.0.0.1/me", "https://localhost/me", "javascript:alert(1)"):
            form = MultiDict(
                [
                    ("platforms", "other"),
                    ("other_platform_name", "New Network"),
                    ("social_url_other", unsafe),
                    ("audience_count_other", "500"),
                ]
            )
            with self.assertRaises(ValueError):
                parse_social_accounts(form)
        self.assertEqual(safe_https_url("https://images.example.com/avatar.jpg"), "https://images.example.com/avatar.jpg")
        self.assertIsNone(safe_https_url("https://user:pass@example.com/avatar.jpg"))

    def test_at_least_one_social_account_is_required(self):
        with self.assertRaises(ValueError):
            parse_social_accounts(MultiDict())


if __name__ == "__main__":
    unittest.main()
