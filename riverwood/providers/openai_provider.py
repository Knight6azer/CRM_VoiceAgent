"""OpenAI conversation engine and Whisper transcription provider."""

from pathlib import Path
from typing import Optional

from openai import OpenAI

from riverwood.config import AgentConfig, looks_like_placeholder
from riverwood.constants import (
    FALLBACK_CALLBACK_REPLY,
    FALLBACK_DEFAULT_REPLY,
    FALLBACK_PROGRESS_REPLY,
    KNOWLEDGE_BASE,
)
from riverwood.logging import JsonlLogger, now_iso
from riverwood.memory import ConversationStore
from riverwood.providers.base import BaseLLMProvider
from riverwood.security import sanitize_user_input

SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm"}
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB OpenAI Whisper limit


class OpenAIConversationEngine(BaseLLMProvider):
    """Handles conversation completion via OpenAI GPT models and transcription via Whisper."""

    def __init__(self, config: AgentConfig, memory: ConversationStore, transcript_logger: JsonlLogger) -> None:
        self.config = config
        self.memory = memory
        self.transcript_logger = transcript_logger
        self._client: Optional[OpenAI] = None

    def available(self) -> bool:
        return not looks_like_placeholder(self.config.openai_api_key)

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            if not self.available():
                raise RuntimeError("OPENAI_API_KEY is missing or set to a placeholder.")
            self._client = OpenAI(
                api_key=self.config.openai_api_key,
                timeout=self.config.llm_timeout_seconds,
            )
        return self._client

    def build_system_prompt(self, session_id: str, caller: Optional[str] = None) -> str:
        extra = f"\nCurrent session id: {session_id}."
        if caller:
            extra += f"\nCaller phone number: {caller}."
        extra += (
            "\nIf a callback seems useful, explicitly say a relationship manager can call back within 2 working hours."
        )
        return KNOWLEDGE_BASE.strip() + extra

    def fallback_reply(self, user_text: str) -> str:
        """Deterministic offline fallback response based on keyword analysis."""
        lowered = user_text.lower()
        if any(keyword in lowered for keyword in {"progress", "update", "status", "construction"}):
            return FALLBACK_PROGRESS_REPLY
        if any(keyword in lowered for keyword in {"price", "pricing", "legal", "payment", "visit", "emi", "cost"}):
            return FALLBACK_CALLBACK_REPLY
        return FALLBACK_DEFAULT_REPLY

    def generate_reply(self, session_id: str, user_text: str, caller: Optional[str] = None) -> str:
        """Generate AI response with strict timeout and deterministic fallback."""
        sanitized_input = sanitize_user_input(user_text)
        if not sanitized_input:
            sanitized_input = "Hello"

        messages = [{"role": "system", "content": self.build_system_prompt(session_id=session_id, caller=caller)}]
        messages.extend(self.memory.as_messages(session_id))
        messages.append({"role": "user", "content": sanitized_input})

        content: str = ""
        if self.available():
            try:
                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=0.55,
                    max_tokens=220,
                    timeout=self.config.llm_timeout_seconds,
                )
                content = (response.choices[0].message.content or "").strip()
            except Exception as exc:
                print(f"[warn] OpenAI chat completion failed ({exc}), engaging offline fallback.")
                content = self.fallback_reply(sanitized_input)
        else:
            content = self.fallback_reply(sanitized_input)

        if not content:
            content = (
                "Namaste. I am here to help with Riverwood Estate updates. "
                "Please tell me what you would like to know."
            )

        self.memory.append(session_id, sanitized_input, content)
        self.transcript_logger.write(
            {
                "timestamp": now_iso(),
                "session_id": session_id,
                "caller": caller,
                "user": sanitized_input,
                "assistant": content,
            }
        )
        return content

    def transcribe(self, audio_path: Path) -> str:
        """Transcribe an audio file using OpenAI Whisper with format and size checks."""
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if audio_path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
            raise ValueError(
                f"Unsupported audio format '{audio_path.suffix}'. Supported: {', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))}"
            )

        file_size = audio_path.stat().st_size
        if file_size == 0:
            raise ValueError(f"Audio file '{audio_path}' is empty.")
        if file_size > MAX_AUDIO_BYTES:
            raise ValueError(
                f"Audio file '{audio_path}' ({file_size / (1024*1024):.1f}MB) exceeds 25MB Whisper limit."
            )

        if not self.available():
            raise RuntimeError("OPENAI_API_KEY is required for audio transcription.")

        with audio_path.open("rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(
                model=self.config.transcription_model,
                file=audio_file,
            )
        return transcript.text.strip()
