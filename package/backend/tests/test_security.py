import unittest

from fastapi import HTTPException

from app.config import settings
from app.schemas import ModelConfig
from app.security import (
    SlidingWindowRateLimiter,
    validate_ai_base_url,
    validate_runtime_security,
)
from app.utils.auth import get_password_hash, verify_password


class SecurityTests(unittest.TestCase):
    def test_bcrypt_password_hash_round_trip(self):
        password_hash = get_password_hash("StrongPassword!2026")

        self.assertTrue(verify_password("StrongPassword!2026", password_hash))
        self.assertFalse(verify_password("wrong-password", password_hash))
        self.assertFalse(verify_password("StrongPassword!2026", "not-a-bcrypt-hash"))

    def test_bcrypt_rejects_passwords_over_72_bytes(self):
        with self.assertRaises(ValueError):
            get_password_hash("密" * 25)

    def setUp(self):
        self.original = {
            "ENVIRONMENT": settings.ENVIRONMENT,
            "SECRET_KEY": settings.SECRET_KEY,
            "ADMIN_PASSWORD": settings.ADMIN_PASSWORD,
            "ADMIN_PASSWORD_HASH": settings.ADMIN_PASSWORD_HASH,
        }

    def tearDown(self):
        for key, value in self.original.items():
            setattr(settings, key, value)

    def test_production_rejects_insecure_credentials(self):
        settings.ENVIRONMENT = "production"
        settings.SECRET_KEY = "replace-with-a-random-secret"
        settings.ADMIN_PASSWORD = "admin123"
        settings.ADMIN_PASSWORD_HASH = None

        with self.assertRaises(RuntimeError):
            validate_runtime_security()

    def test_production_accepts_strong_credentials(self):
        settings.ENVIRONMENT = "production"
        settings.SECRET_KEY = "s" * 48
        settings.ADMIN_PASSWORD = "a-strong-admin-password"
        settings.ADMIN_PASSWORD_HASH = None

        validate_runtime_security()

    def test_ai_url_rejects_private_and_plain_http_endpoints(self):
        with self.assertRaises(ValueError):
            validate_ai_base_url("https://127.0.0.1/v1")
        with self.assertRaises(ValueError):
            validate_ai_base_url("http://8.8.8.8/v1")
        self.assertEqual(validate_ai_base_url("https://8.8.8.8/v1"), "https://8.8.8.8/v1")

    def test_custom_ai_endpoint_requires_its_own_key(self):
        with self.assertRaises(ValueError):
            ModelConfig(model="test", base_url="https://8.8.8.8/v1")

    def test_login_limiter_blocks_after_the_limit(self):
        limiter = SlidingWindowRateLimiter(attempts=2, window_seconds=60)
        limiter.record_failure("admin")
        limiter.record_failure("admin")
        with self.assertRaises(HTTPException) as caught:
            limiter.check("admin")
        self.assertEqual(caught.exception.status_code, 429)

    def test_login_limiter_bounds_distinct_keys(self):
        limiter = SlidingWindowRateLimiter(attempts=2, window_seconds=60, max_keys=3)
        for index in range(10):
            limiter.record_failure(f"user-{index}")

        self.assertLessEqual(len(limiter._events), 3)


if __name__ == "__main__":
    unittest.main()
