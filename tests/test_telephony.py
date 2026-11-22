"""Unit tests for Twilio telephony, TwiML generation, and outbound calling."""

import unittest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from riverwood.config import AgentConfig
from riverwood.telephony import (
    build_initial_greeting_twiml,
    build_silence_twiml,
    build_twiml,
    start_outbound_call,
)


class TelephonyTests(unittest.TestCase):
    def test_build_twiml_structure(self) -> None:
        twiml = build_twiml("Namaste from Riverwood", gather_action="/voice/respond")
        root = ET.fromstring(twiml)

        self.assertEqual(root.tag, "Response")
        say_tags = root.findall("Say")
        self.assertTrue(len(say_tags) >= 1)
        self.assertEqual(say_tags[0].text, "Namaste from Riverwood")
        self.assertEqual(say_tags[0].attrib.get("voice"), "Polly.Aditi-Neural")
        self.assertEqual(say_tags[0].attrib.get("language"), "en-IN")

        gather = root.find("Gather")
        self.assertIsNotNone(gather)
        self.assertEqual(gather.attrib.get("action"), "/voice/respond")
        self.assertEqual(gather.attrib.get("input"), "speech")

        hangup = root.find("Hangup")
        self.assertIsNotNone(hangup)

    def test_greeting_and_silence_twiml(self) -> None:
        greeting = build_initial_greeting_twiml()
        self.assertIn("Riverwood Estate", greeting)
        self.assertIn("/voice/respond", greeting)

        silence = build_silence_twiml()
        self.assertIn("could not hear that clearly", silence)

    def test_outbound_call_missing_config_raises(self) -> None:
        config = AgentConfig(
            openai_api_key="valid-key",
            twilio_account_sid=None,  # Missing
        )
        with self.assertRaises(ValueError) as ctx:
            start_outbound_call(config, "+15551234567")
        self.assertIn("Missing:", str(ctx.exception))

    def test_outbound_call_invalid_phone_raises(self) -> None:
        config = AgentConfig(
            openai_api_key="valid-key",
            twilio_account_sid="AC12345678",
            twilio_auth_token="auth-token",
            twilio_phone_number="+15551234567",
            twilio_webhook_base_url="https://api.riverwood.com",
        )
        # Invalid phone without E.164 plus
        with self.assertRaises(ValueError) as ctx:
            start_outbound_call(config, "1234567")
        self.assertIn("Must be in ITU E.164 format", str(ctx.exception))

    def test_outbound_call_invalid_webhook_url_raises(self) -> None:
        config = AgentConfig(
            openai_api_key="valid-key",
            twilio_account_sid="AC12345678",
            twilio_auth_token="auth-token",
            twilio_phone_number="+15551234567",
            twilio_webhook_base_url="invalid-no-protocol.com",
        )
        with self.assertRaises(ValueError) as ctx:
            start_outbound_call(config, "+15559876543")
        self.assertIn("Must start with http:// or https://", str(ctx.exception))

    @patch("requests.post")
    def test_outbound_call_success_mock(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "sid": "CA123456789",
            "status": "queued",
            "to": "+15559876543",
            "from": "+15551234567",
        }
        mock_post.return_value = mock_response

        config = AgentConfig(
            openai_api_key="valid-key",
            twilio_account_sid="AC12345678",
            twilio_auth_token="auth-token",
            twilio_phone_number="+15551234567",
            twilio_webhook_base_url="https://api.riverwood.com",
        )
        result = start_outbound_call(config, "+15559876543")

        self.assertEqual(result["sid"], "CA123456789")
        self.assertEqual(result["status"], "queued")
        self.assertEqual(result["callback_url"], "https://api.riverwood.com/voice/incoming")

    @patch("requests.post")
    def test_outbound_call_api_error_mock(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = Exception("Twilio API unreachable")

        config = AgentConfig(
            openai_api_key="valid-key",
            twilio_account_sid="AC12345678",
            twilio_auth_token="auth-token",
            twilio_phone_number="+15551234567",
            twilio_webhook_base_url="https://api.riverwood.com",
        )
        with self.assertRaises(RuntimeError) as ctx:
            start_outbound_call(config, "+15559876543")
        self.assertIn("Twilio API outbound call creation failed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
