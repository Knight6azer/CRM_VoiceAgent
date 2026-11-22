"""Unit tests for AgentConfig, environment validation, and placeholder detection."""

import os
import unittest
from unittest.mock import patch

from riverwood.config import AgentConfig, looks_like_placeholder, parse_bool_env, sanitize_env


class AgentConfigTests(unittest.TestCase):
    def test_sanitize_env(self) -> None:
        self.assertIsNone(sanitize_env(None))
        self.assertIsNone(sanitize_env("   "))
        self.assertEqual(sanitize_env("  hello  "), "hello")

    def test_looks_like_placeholder(self) -> None:
        self.assertTrue(looks_like_placeholder(None))
        self.assertTrue(looks_like_placeholder(""))
        self.assertTrue(looks_like_placeholder("   "))
        self.assertTrue(looks_like_placeholder("your_openai_api_key"))
        self.assertTrue(looks_like_placeholder("replace_me_with_key"))
        self.assertTrue(looks_like_placeholder("ACxxxxxxxxxxxxxxxxxxxxxxx"))
        self.assertTrue(looks_like_placeholder("https://your-public-twilio-webhook-domain.com"))
        self.assertFalse(looks_like_placeholder("sk-proj-validRealLookingKey12345"))
        self.assertFalse(looks_like_placeholder("https://api.myestate.com"))

    def test_parse_bool_env(self) -> None:
        self.assertTrue(parse_bool_env("true"))
        self.assertTrue(parse_bool_env("TRUE"))
        self.assertTrue(parse_bool_env("1"))
        self.assertTrue(parse_bool_env("yes"))
        self.assertFalse(parse_bool_env("false"))
        self.assertFalse(parse_bool_env("0"))
        self.assertFalse(parse_bool_env(None, default=False))
        self.assertTrue(parse_bool_env(None, default=True))

    def test_from_env_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = AgentConfig.from_env()
            self.assertEqual(config.model, "gpt-4o-mini")
            self.assertEqual(config.transcription_model, "whisper-1")
            self.assertEqual(config.openai_tts_model, "tts-1")
            self.assertFalse(config.validate_twilio_signature)
            self.assertTrue(config.mask_phone_in_logs)
            self.assertEqual(config.missing_for_cli(), ["OPENAI_API_KEY"])

    def test_missing_for_outbound_call(self) -> None:
        config = AgentConfig(
            openai_api_key="valid-key",
            elevenlabs_api_key=None,
            twilio_account_sid="your_twilio_account_sid",
            twilio_auth_token=None,
            twilio_phone_number="+15551234567",
            twilio_webhook_base_url="https://api.riverwood.com",
        )
        missing = config.missing_for_outbound_call()
        self.assertIn("TWILIO_ACCOUNT_SID", missing)
        self.assertIn("TWILIO_AUTH_TOKEN", missing)
        self.assertNotIn("TWILIO_PHONE_NUMBER", missing)
        self.assertNotIn("TWILIO_WEBHOOK_BASE_URL", missing)

    def test_provider_status_dictionary(self) -> None:
        config = AgentConfig(
            openai_api_key="valid-key",
            elevenlabs_api_key="valid-eleven",
            twilio_account_sid="AC12345678",
            twilio_auth_token="token",
            twilio_phone_number="+15551234567",
            twilio_webhook_base_url="https://api.riverwood.com",
            validate_twilio_signature=True,
        )
        status = config.provider_status()
        self.assertEqual(status["OpenAI"], "ready")
        self.assertEqual(status["ElevenLabs"], "ready")
        self.assertEqual(status["Twilio"], "ready")
        self.assertEqual(status["Twilio Webhook"], "ready")
        self.assertEqual(status["Twilio Security"], "enforced")


if __name__ == "__main__":
    unittest.main()
