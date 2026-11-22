"""Integration tests for FastAPI endpoints and Twilio webhook signature verification."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from riverwood.agent import RiverwoodVoiceAgent
from riverwood.api import create_app
from riverwood.config import AgentConfig


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_root = Path(self.temp_dir.name)
        self.auth_token = "secret_auth_token_for_tests"
        self.config = AgentConfig(
            openai_api_key="valid-mock-key",
            elevenlabs_api_key=None,
            twilio_account_sid="test-sid",
            twilio_auth_token=self.auth_token,
            twilio_phone_number="+15551234567",
            twilio_webhook_base_url="https://example.com",
            validate_twilio_signature=False,  # default dev mode for standard tests
            output_dir=temp_root / "audio",
            log_dir=temp_root / "logs",
        )
        self.agent = RiverwoodVoiceAgent(self.config)
        self.app = create_app(self.agent)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("providers", data)
        self.assertIn("timestamp", data)

    def test_voice_incoming_endpoint(self) -> None:
        response = self.client.post("/voice/incoming")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/xml", response.headers["content-type"])
        self.assertIn("Riverwood Estate", response.text)
        self.assertIn("<Gather", response.text)

    def test_voice_respond_empty_speech(self) -> None:
        response = self.client.post("/voice/respond", data={})
        self.assertEqual(response.status_code, 200)
        self.assertIn("could not hear that clearly", response.text)

    @patch("riverwood.providers.openai_provider.OpenAI")
    def test_voice_respond_with_speech_result(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content="Sector A roads are 75% complete."))]
        mock_client.chat.completions.create.return_value = mock_completion
        mock_openai_cls.return_value = mock_client

        response = self.client.post(
            "/voice/respond",
            data={
                "SpeechResult": "How is Sector A coming along?",
                "CallSid": "CA111222333",
                "Caller": "+15559876543",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/xml", response.headers["content-type"])
        self.assertIn("Sector A roads are 75% complete", response.text)

    def test_signature_verification_enforced(self) -> None:
        # Create an agent with signature enforcement active
        secure_config = AgentConfig(
            openai_api_key="valid-mock-key",
            twilio_account_sid="test-sid",
            twilio_auth_token=self.auth_token,
            twilio_phone_number="+15551234567",
            twilio_webhook_base_url="https://example.com",
            validate_twilio_signature=True,
            output_dir=Path(self.temp_dir.name) / "secure_audio",
            log_dir=Path(self.temp_dir.name) / "secure_logs",
        )
        secure_agent = RiverwoodVoiceAgent(secure_config)
        secure_app = create_app(secure_agent)
        client = TestClient(secure_app)

        # 1. Unauthenticated request without X-Twilio-Signature returns 403
        unauthed_resp = client.post("/voice/incoming")
        self.assertEqual(unauthed_resp.status_code, 403)
        self.assertIn("Missing Twilio signature", unauthed_resp.json()["detail"])

        # 2. Forged signature returns 403
        forged_resp = client.post(
            "/voice/incoming",
            headers={"X-Twilio-Signature": "invalid-forged-signature"},
        )
        self.assertEqual(forged_resp.status_code, 403)
        self.assertIn("signature verification failed", forged_resp.json()["detail"])

        # 3. Valid signature succeeds
        url = "https://example.com/voice/incoming"
        params: dict = {}
        rv = RequestValidator(self.auth_token)
        valid_sig = rv.compute_signature(url, params)

        authed_resp = client.post(
            "/voice/incoming",
            headers={"X-Twilio-Signature": valid_sig},
        )
        self.assertEqual(authed_resp.status_code, 200)
        self.assertIn("<Gather", authed_resp.text)


if __name__ == "__main__":
    unittest.main()
