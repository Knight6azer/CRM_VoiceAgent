"""Unit tests for phone normalization, E.164 validation, input sanitization, and Twilio signatures."""

import unittest

from twilio.request_validator import RequestValidator

from riverwood.security import (
    TwilioSignatureValidator,
    is_valid_e164,
    mask_phone_number,
    normalize_phone_number,
    sanitize_user_input,
)


class SecurityTests(unittest.TestCase):
    def test_phone_normalization(self) -> None:
        self.assertIsNone(normalize_phone_number(None))
        self.assertIsNone(normalize_phone_number(""))
        self.assertEqual(normalize_phone_number("+1 (555) 123-4567"), "+15551234567")
        self.assertEqual(normalize_phone_number("  +91 98765 43210  "), "+919876543210")
        self.assertEqual(normalize_phone_number("9876543210"), "9876543210")

    def test_e164_validation(self) -> None:
        self.assertTrue(is_valid_e164("+15551234567"))
        self.assertTrue(is_valid_e164("+919876543210"))
        self.assertFalse(is_valid_e164("5551234567"))  # Missing leading plus
        self.assertFalse(is_valid_e164("+0123456789"))  # Leading zero after plus invalid in E.164
        self.assertFalse(is_valid_e164("+1234567890123456"))  # Over 15 digits
        self.assertFalse(is_valid_e164(None))
        self.assertFalse(is_valid_e164(""))

    def test_mask_phone_number(self) -> None:
        self.assertEqual(mask_phone_number(None), "<anonymous>")
        self.assertEqual(mask_phone_number(""), "<anonymous>")
        self.assertEqual(mask_phone_number("+15551234567"), "+1555***4567")
        self.assertEqual(mask_phone_number("+919876543210"), "+9198***3210")

    def test_sanitize_user_input(self) -> None:
        self.assertEqual(sanitize_user_input(None), "")
        self.assertEqual(sanitize_user_input(""), "")
        self.assertEqual(sanitize_user_input("  normal input  "), "normal input")
        # Null byte injection removal
        self.assertEqual(sanitize_user_input("hello\x00world"), "helloworld")
        # Oversized text truncation
        long_text = "a" * 1500
        truncated = sanitize_user_input(long_text, max_chars=100)
        self.assertEqual(len(truncated), 100)

    def test_twilio_signature_validator_disabled(self) -> None:
        validator = TwilioSignatureValidator(auth_token="dummy_token", enabled=False)
        self.assertTrue(validator.validate("https://example.com/voice", {}, None))

    def test_twilio_signature_validator_enabled(self) -> None:
        auth_token = "test_auth_token_secret_12345"
        validator = TwilioSignatureValidator(auth_token=auth_token, enabled=True)

        url = "https://example.com/voice/respond"
        params = {"SpeechResult": "Hello", "CallSid": "CA12345"}

        # Generate a genuinely valid signature using Twilio's standard algorithm
        rv = RequestValidator(auth_token)
        valid_signature = rv.compute_signature(url, params)

        # 1. Valid signature passes
        self.assertTrue(validator.validate(url, params, valid_signature))

        # 2. Missing signature fails
        self.assertFalse(validator.validate(url, params, None))
        self.assertFalse(validator.validate(url, params, ""))

        # 3. Invalid / forged signature fails
        self.assertFalse(validator.validate(url, params, "forged_signature_value"))

        # 4. Tampered params fail
        tampered_params = dict(params)
        tampered_params["SpeechResult"] = "Tampered speech"
        self.assertFalse(validator.validate(url, tampered_params, valid_signature))

        # 5. Tampered URL fails
        self.assertFalse(validator.validate("https://attacker.com/voice/respond", params, valid_signature))


if __name__ == "__main__":
    unittest.main()
