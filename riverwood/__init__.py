"""Riverwood AI CRM Voice Agent package."""

from riverwood.agent import RiverwoodVoiceAgent
from riverwood.config import AgentConfig, looks_like_placeholder, sanitize_env
from riverwood.constants import (
    CALLBACK_KEYWORDS,
    KNOWLEDGE_BASE,
    TWILIO_LANGUAGE,
    TWILIO_POLLY_VOICE,
)
from riverwood.logging import JsonlLogger, now_iso
from riverwood.memory import ConversationStore
from riverwood.providers import (
    ElevenLabsTTS,
    OpenAIConversationEngine,
    OpenAITTS,
    WindowsSystemTTS,
)
from riverwood.security import (
    TwilioSignatureValidator,
    is_valid_e164,
    mask_phone_number,
    normalize_phone_number,
    sanitize_user_input,
)
from riverwood.telephony import (
    build_initial_greeting_twiml,
    build_silence_twiml,
    build_twiml,
    start_outbound_call,
)

__all__ = [
    "RiverwoodVoiceAgent",
    "AgentConfig",
    "looks_like_placeholder",
    "sanitize_env",
    "KNOWLEDGE_BASE",
    "CALLBACK_KEYWORDS",
    "TWILIO_LANGUAGE",
    "TWILIO_POLLY_VOICE",
    "JsonlLogger",
    "now_iso",
    "ConversationStore",
    "OpenAIConversationEngine",
    "ElevenLabsTTS",
    "OpenAITTS",
    "WindowsSystemTTS",
    "TwilioSignatureValidator",
    "is_valid_e164",
    "mask_phone_number",
    "normalize_phone_number",
    "sanitize_user_input",
    "build_twiml",
    "build_initial_greeting_twiml",
    "build_silence_twiml",
    "start_outbound_call",
]
