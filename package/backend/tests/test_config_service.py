import unittest

from app.services.config_service import ConfigUpdateError, _validated_updates


class ConfigServiceTests(unittest.TestCase):
    def test_unknown_keys_are_rejected(self):
        with self.assertRaises(ConfigUpdateError):
            _validated_updates({"SECRET_KEY": "unexpected"})

    def test_newlines_are_rejected(self):
        with self.assertRaises(ConfigUpdateError):
            _validated_updates({"POLISH_MODEL": "model\nADMIN_PASSWORD=changed"})

    def test_blank_secret_preserves_existing_value(self):
        self.assertEqual(_validated_updates({"POLISH_API_KEY": ""}), {})

    def test_private_provider_url_is_rejected(self):
        with self.assertRaises(ConfigUpdateError):
            _validated_updates({"POLISH_BASE_URL": "https://127.0.0.1/v1"})


if __name__ == "__main__":
    unittest.main()
