"""Twilio telephony integration, TwiML response generation, and outbound call dispatching."""

import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional

import requests

from riverwood.config import AgentConfig
from riverwood.constants import TWILIO_LANGUAGE, TWILIO_POLLY_VOICE
from riverwood.security import is_valid_e164, normalize_phone_number


def build_twiml(
    prompt: str,
    gather_action: str = "/voice/respond",
    voice: str = TWILIO_POLLY_VOICE,
    language: str = TWILIO_LANGUAGE,
) -> str:
    """Generate standardized TwiML with Polly speech output and speech recognition Gather."""
    root = ET.Element("Response")

    say_tag = ET.SubElement(root, "Say", voice=voice, language=language)
    say_tag.text = prompt

    gather = ET.SubElement(
        root,
        "Gather",
        input="speech",
        action=gather_action,
        method="POST",
        speechTimeout="auto",
        language=language,
    )
    gather_prompt = ET.SubElement(gather, "Say", voice=voice, language=language)
    gather_prompt.text = "Please go ahead. I am listening."

    fallback = ET.SubElement(root, "Say", voice=voice, language=language)
    fallback.text = "I did not hear anything, so I will end the call for now. Thank you."
    ET.SubElement(root, "Hangup")
    return ET.tostring(root, encoding="unicode")


def build_initial_greeting_twiml(gather_action: str = "/voice/respond") -> str:
    """Return initial TwiML greeting for incoming calls."""
    return build_twiml(
        prompt=(
            "Namaste and hello. You have reached the Riverwood Estate voice desk. "
            "How may I assist you today?"
        ),
        gather_action=gather_action,
    )


def build_silence_twiml(gather_action: str = "/voice/respond") -> str:
    """Return TwiML when no speech was detected."""
    return build_twiml(
        prompt="I could not hear that clearly. Please speak after the prompt.",
        gather_action=gather_action,
    )


def start_outbound_call(config: AgentConfig, to_number: str) -> Dict[str, Any]:
    """
    Dispatch an outbound phone call via the Twilio REST API.
    Validates E.164 phone formats and webhook configuration before dispatch.
    """
    missing = config.missing_for_outbound_call()
    if missing:
        raise ValueError(f"Outbound calling configuration is incomplete. Missing: {', '.join(missing)}")

    normalized_to = normalize_phone_number(to_number)
    if not normalized_to or not is_valid_e164(normalized_to):
        raise ValueError(
            f"Invalid destination phone number '{to_number}'. Must be in ITU E.164 format (e.g. +15551234567)."
        )

    normalized_from = normalize_phone_number(config.twilio_phone_number)
    if not normalized_from or not is_valid_e164(normalized_from):
        raise ValueError(
            f"Invalid Twilio source phone number '{config.twilio_phone_number}'. Must be in ITU E.164 format."
        )

    base_url = (config.twilio_webhook_base_url or "").rstrip("/")
    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        raise ValueError(
            f"Invalid TWILIO_WEBHOOK_BASE_URL '{config.twilio_webhook_base_url}'. Must start with http:// or https://."
        )

    callback_url = f"{base_url}/voice/incoming"
    api_url = f"https://api.twilio.com/2010-04-01/Accounts/{config.twilio_account_sid}/Calls.json"

    try:
        response = requests.post(
            api_url,
            auth=(config.twilio_account_sid or "", config.twilio_auth_token or ""),
            data={
                "To": normalized_to,
                "From": normalized_from,
                "Url": callback_url,
                "Method": "POST",
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        return {
            "sid": payload.get("sid"),
            "status": payload.get("status"),
            "to": payload.get("to"),
            "from": payload.get("from"),
            "callback_url": callback_url,
        }
    except Exception as exc:
        raise RuntimeError(f"Twilio API outbound call creation failed: {exc}") from exc
