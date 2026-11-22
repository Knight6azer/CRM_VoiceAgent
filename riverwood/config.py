"""Configuration management and environment validation for Riverwood Voice Agent."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

from riverwood.constants import (
    DEFAULT_ELEVENLABS_MODEL_ID,
    DEFAULT_ELEVENLABS_VOICE_ID,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_OPENAI_TTS_MODEL,
    DEFAULT_TRANSCRIPTION_MODEL,
    PLACEHOLDER_MARKERS,
)

load_dotenv()


def sanitize_env(value: Optional[str]) -> Optional[str]:
    """Strip whitespace and return None if empty."""
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def looks_like_placeholder(value: Optional[str]) -> bool:
    """Return True if value is None, empty, whitespace-only, or matches common placeholder patterns."""
    if not value or not value.strip():
        return True
    lowered = value.strip().lower()
    if lowered in {
        "your_openai_api_key",
        "your_elevenlabs_api_key",
        "your_twilio_account_sid",
        "your_twilio_auth_token",
        "your_twilio_phone_number",
        "https://your-public-twilio-webhook-domain.com",
    }:
        return True
    if any(marker in lowered for marker in ("your_", "your-", "replace_me", "changeme", "xxxx", "acxxxxxxxx")):
        return True
    return False


def parse_bool_env(value: Optional[str], default: bool = False) -> bool:
    """Parse boolean environment variables safely."""
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class AgentConfig:
    """Strongly typed application configuration."""

    openai_api_key: Optional[str] = None
    elevenlabs_api_key: Optional[str] = None
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_phone_number: Optional[str] = None
    twilio_webhook_base_url: Optional[str] = None
    apollo_api_key: Optional[str] = None
    vapi_api_key: Optional[str] = None

    model: str = DEFAULT_OPENAI_MODEL
    transcription_model: str = DEFAULT_TRANSCRIPTION_MODEL
    openai_tts_model: str = DEFAULT_OPENAI_TTS_MODEL
    elevenlabs_voice_id: str = DEFAULT_ELEVENLABS_VOICE_ID
    elevenlabs_model_id: str = DEFAULT_ELEVENLABS_MODEL_ID

    validate_twilio_signature: bool = False
    mask_phone_in_logs: bool = True
    llm_timeout_seconds: float = 8.0

    output_dir: Path = field(default_factory=lambda: Path("generated_audio"))
    log_dir: Path = field(default_factory=lambda: Path("logs"))

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load and sanitize configuration from environment variables."""
        return cls(
            openai_api_key=sanitize_env(os.getenv("OPENAI_API_KEY")),
            elevenlabs_api_key=sanitize_env(os.getenv("ELEVENLABS_API_KEY")),
            twilio_account_sid=sanitize_env(os.getenv("TWILIO_ACCOUNT_SID")),
            twilio_auth_token=sanitize_env(os.getenv("TWILIO_AUTH_TOKEN")),
            twilio_phone_number=sanitize_env(os.getenv("TWILIO_PHONE_NUMBER")),
            twilio_webhook_base_url=sanitize_env(os.getenv("TWILIO_WEBHOOK_BASE_URL")),
            apollo_api_key=sanitize_env(os.getenv("APOLLO_API_KEY")),
            vapi_api_key=sanitize_env(os.getenv("VAPI_API_KEY")),
            model=sanitize_env(os.getenv("OPENAI_MODEL")) or DEFAULT_OPENAI_MODEL,
            transcription_model=sanitize_env(os.getenv("OPENAI_TRANSCRIPTION_MODEL")) or DEFAULT_TRANSCRIPTION_MODEL,
            openai_tts_model=sanitize_env(os.getenv("OPENAI_TTS_MODEL")) or DEFAULT_OPENAI_TTS_MODEL,
            elevenlabs_voice_id=sanitize_env(os.getenv("ELEVENLABS_VOICE_ID")) or DEFAULT_ELEVENLABS_VOICE_ID,
            elevenlabs_model_id=sanitize_env(os.getenv("ELEVENLABS_MODEL_ID")) or DEFAULT_ELEVENLABS_MODEL_ID,
            validate_twilio_signature=parse_bool_env(os.getenv("TWILIO_VALIDATE_SIGNATURE"), default=False),
            mask_phone_in_logs=parse_bool_env(os.getenv("LOG_MASK_PHONE"), default=True),
            llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "8.0")),
        )

    def ensure_directories(self) -> None:
        """Create output and logging directories if they do not exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def missing_for_cli(self) -> List[str]:
        missing: List[str] = []
        if looks_like_placeholder(self.openai_api_key):
            missing.append("OPENAI_API_KEY")
        return missing

    def missing_for_voice_output(self) -> List[str]:
        missing: List[str] = []
        if looks_like_placeholder(self.elevenlabs_api_key):
            missing.append("ELEVENLABS_API_KEY")
        return missing

    def missing_for_phone_mode(self) -> List[str]:
        return self.missing_for_cli()

    def missing_for_outbound_call(self) -> List[str]:
        missing: List[str] = []
        if not self.twilio_account_sid or looks_like_placeholder(self.twilio_account_sid):
            missing.append("TWILIO_ACCOUNT_SID")
        if not self.twilio_auth_token or looks_like_placeholder(self.twilio_auth_token):
            missing.append("TWILIO_AUTH_TOKEN")
        if not self.twilio_phone_number or looks_like_placeholder(self.twilio_phone_number):
            missing.append("TWILIO_PHONE_NUMBER")
        if not self.twilio_webhook_base_url or looks_like_placeholder(self.twilio_webhook_base_url):
            missing.append("TWILIO_WEBHOOK_BASE_URL")
        return missing

    def provider_status(self) -> Dict[str, str]:
        """Return readiness status for operational and optional integrations."""
        return {
            "OpenAI": "ready" if not looks_like_placeholder(self.openai_api_key) else "missing",
            "ElevenLabs": "ready" if not looks_like_placeholder(self.elevenlabs_api_key) else "missing",
            "Twilio": "ready"
            if (
                self.twilio_account_sid
                and not looks_like_placeholder(self.twilio_account_sid)
                and self.twilio_auth_token
                and not looks_like_placeholder(self.twilio_auth_token)
                and self.twilio_phone_number
                and not looks_like_placeholder(self.twilio_phone_number)
            )
            else "missing",
            "Twilio Webhook": "ready"
            if self.twilio_webhook_base_url and not looks_like_placeholder(self.twilio_webhook_base_url)
            else "missing",
            "Twilio Security": "enforced" if self.validate_twilio_signature else "disabled (dev mode)",
            "Apollo": "optional (not integrated)",
            "Vapi": "optional (not integrated)",
        }
