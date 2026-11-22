"""Security hardening, input validation, phone normalization, and Twilio signature verification."""

import re
from typing import Dict, Optional

try:
    from twilio.request_validator import RequestValidator
except ImportError:  # pragma: no cover
    RequestValidator = None


E164_REGEX = re.compile(r"^\+[1-9]\d{1,14}$")


def normalize_phone_number(raw_value: Optional[str]) -> Optional[str]:
    """Strip whitespace, parentheses, dashes, etc., retaining leading + and digits."""
    if not raw_value:
        return None
    cleaned = re.sub(r"[^\d+]", "", raw_value.strip())
    return cleaned or None


def is_valid_e164(phone: Optional[str]) -> bool:
    """Validate whether phone number conforms to ITU-T E.164 standard (+[1-9][0-9]{1,14})."""
    if not phone:
        return False
    return bool(E164_REGEX.match(phone))


def mask_phone_number(phone: Optional[str]) -> str:
    """Mask phone number for privacy-conscious logging (e.g. +1555***4567)."""
    if not phone:
        return "<anonymous>"
    cleaned = normalize_phone_number(phone)
    if not cleaned:
        return "<invalid>"
    if len(cleaned) <= 6:
        return cleaned[:2] + "***" + cleaned[-1:]
    return f"{cleaned[:5]}***{cleaned[-4:]}"


def sanitize_user_input(text: Optional[str], max_chars: int = 1000) -> str:
    """Sanitize and constrain user input text to prevent oversized payloads and control-char injection."""
    if not text:
        return ""
    # Strip null bytes and non-printable control chars, keeping standard whitespace
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    cleaned = cleaned.strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].strip()
    return cleaned


class TwilioSignatureValidator:
    """Validates Twilio webhook signatures using HMAC-SHA1."""

    def __init__(self, auth_token: Optional[str], enabled: bool = True) -> None:
        self.auth_token = auth_token
        self.enabled = enabled
        self._validator = RequestValidator(auth_token) if (auth_token and RequestValidator) else None

    def validate(self, url: str, params: Dict[str, str], signature: Optional[str]) -> bool:
        """
        Validate whether the given request signature matches the expected HMAC-SHA1.
        If validation is disabled (e.g. dev mode), always returns True.
        """
        if not self.enabled:
            return True

        if not self.auth_token or not self._validator:
            return False

        if not signature:
            return False

        try:
            return bool(self._validator.validate(url, params, signature))
        except Exception:
            return False
