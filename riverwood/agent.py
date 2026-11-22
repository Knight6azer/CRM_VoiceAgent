"""Riverwood Voice Agent orchestrator coordinating memory, LLM engine, TTS fallback, and CRM callbacks."""

import uuid
from pathlib import Path
from typing import Optional

from riverwood.config import AgentConfig
from riverwood.constants import CALLBACK_KEYWORDS
from riverwood.logging import JsonlLogger, now_iso
from riverwood.memory import ConversationStore
from riverwood.providers.openai_provider import OpenAIConversationEngine
from riverwood.providers.tts_provider import ElevenLabsTTS, OpenAITTS, WindowsSystemTTS
from riverwood.telephony import (
    build_initial_greeting_twiml,
    build_silence_twiml,
    build_twiml,
)


class RiverwoodVoiceAgent:
    """Core voice agent coordinating conversational AI, voice generation, and CRM logging."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.config.ensure_directories()
        self.memory = ConversationStore(max_turns=12)

        self.transcript_logger = JsonlLogger(
            self.config.log_dir / "transcripts.jsonl",
            mask_pii=self.config.mask_phone_in_logs,
        )
        self.callback_logger = JsonlLogger(
            self.config.log_dir / "callbacks.jsonl",
            mask_pii=self.config.mask_phone_in_logs,
        )

        self.engine = OpenAIConversationEngine(config, self.memory, self.transcript_logger)
        self.primary_tts = ElevenLabsTTS(config)
        self.fallback_tts = OpenAITTS(config)
        self.local_tts = WindowsSystemTTS()

    def should_log_callback(self, user_text: str, reply_text: str) -> bool:
        """Evaluate if conversation turn indicates commercial interest or callback intent."""
        combined = f"{user_text} {reply_text}".lower()
        return any(keyword in combined for keyword in CALLBACK_KEYWORDS)

    def record_callback(self, session_id: str, caller: Optional[str], user_text: str, reply_text: str) -> None:
        """Record high-priority CRM callback event for relationship manager follow-up."""
        self.callback_logger.write(
            {
                "timestamp": now_iso(),
                "session_id": session_id,
                "caller": caller,
                "source": "voice-agent",
                "reason": user_text,
                "agent_reply": reply_text,
            }
        )

    def answer(self, user_text: str, session_id: str = "cli-session", caller: Optional[str] = None) -> str:
        """Process caller message and return agent response, recording callbacks when triggered."""
        reply = self.engine.generate_reply(session_id=session_id, user_text=user_text, caller=caller)
        if self.should_log_callback(user_text, reply):
            self.record_callback(session_id=session_id, caller=caller, user_text=user_text, reply_text=reply)
        return reply

    def transcribe_file(self, audio_path: Path) -> str:
        """Transcribe audio file into text."""
        return self.engine.transcribe(audio_path)

    def speak_to_file(self, text: str) -> Optional[Path]:
        """Synthesize text to audio with cascading fallback: ElevenLabs -> OpenAI TTS -> Local OS TTS."""
        output_mp3 = self.config.output_dir / f"riverwood-{uuid.uuid4().hex}.mp3"

        # 1. Primary: ElevenLabs
        audio_file = self.primary_tts.synthesize(text=text, output_path=output_mp3)
        if audio_file:
            return audio_file

        # 2. Secondary fallback: OpenAI TTS
        audio_file = self.fallback_tts.synthesize(text=text, output_path=output_mp3)
        if audio_file:
            return audio_file

        # 3. Local OS fallback: Windows System.Speech
        output_wav = self.config.output_dir / f"riverwood-{uuid.uuid4().hex}.wav"
        return self.local_tts.synthesize(text=text, output_path=output_wav)

    def initial_greeting_twiml(self) -> str:
        """TwiML greeting when call first connects."""
        return build_initial_greeting_twiml(gather_action="/voice/respond")

    def silence_twiml(self) -> str:
        """TwiML response when speech recognition detects silence."""
        return build_silence_twiml(gather_action="/voice/respond")

    def response_twiml(self, user_text: str, session_id: str, caller: Optional[str]) -> str:
        """Generate conversational response and wrap in interactive TwiML Gather."""
        reply = self.answer(user_text=user_text, session_id=session_id, caller=caller)
        return build_twiml(prompt=reply, gather_action="/voice/respond")

    def build_twiml(self, prompt: str, gather_action: str) -> str:
        """Backward-compatible helper method for TwiML generation."""
        return build_twiml(prompt=prompt, gather_action=gather_action)
