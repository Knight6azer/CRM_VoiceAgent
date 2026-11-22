"""Unit tests for AI and TTS providers using controlled mocks."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from riverwood.config import AgentConfig
from riverwood.constants import (
    FALLBACK_CALLBACK_REPLY,
    FALLBACK_DEFAULT_REPLY,
    FALLBACK_PROGRESS_REPLY,
)
from riverwood.logging import JsonlLogger
from riverwood.memory import ConversationStore
from riverwood.providers.openai_provider import OpenAIConversationEngine
from riverwood.providers.tts_provider import ElevenLabsTTS, OpenAITTS, WindowsSystemTTS


class ProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_path = Path(self.temp_dir.name) / "transcripts.jsonl"
        self.logger = JsonlLogger(self.log_path)
        self.memory = ConversationStore()
        self.config = AgentConfig(
            openai_api_key="valid-mock-key",
            elevenlabs_api_key="valid-eleven-key",
            model="gpt-4o-mini",
            transcription_model="whisper-1",
            openai_tts_model="tts-1",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_deterministic_fallback_replies(self) -> None:
        engine = OpenAIConversationEngine(self.config, self.memory, self.logger)

        self.assertEqual(engine.fallback_reply("How is construction going?"), FALLBACK_PROGRESS_REPLY)
        self.assertEqual(engine.fallback_reply("What is the price of a 3BHK?"), FALLBACK_CALLBACK_REPLY)
        self.assertEqual(engine.fallback_reply("Can I book a site visit?"), FALLBACK_CALLBACK_REPLY)
        self.assertEqual(engine.fallback_reply("Hello there"), FALLBACK_DEFAULT_REPLY)

    @patch("riverwood.providers.openai_provider.OpenAI")
    def test_generate_reply_with_mocked_openai(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content="Namaste! Construction is on track."))]
        mock_client.chat.completions.create.return_value = mock_completion
        mock_openai_cls.return_value = mock_client

        engine = OpenAIConversationEngine(self.config, self.memory, self.logger)
        reply = engine.generate_reply("session-1", "Update please")

        self.assertEqual(reply, "Namaste! Construction is on track.")
        self.assertEqual(len(self.memory.as_messages("session-1")), 2)
        # Check transcript log written
        self.assertTrue(self.log_path.exists())

    @patch("riverwood.providers.openai_provider.OpenAI")
    def test_generate_reply_fallback_on_api_exception(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("OpenAI rate limit or timeout")
        mock_openai_cls.return_value = mock_client

        engine = OpenAIConversationEngine(self.config, self.memory, self.logger)
        reply = engine.generate_reply("session-err", "What is the construction status?")

        self.assertEqual(reply, FALLBACK_PROGRESS_REPLY)

    def test_transcribe_audio_validation(self) -> None:
        engine = OpenAIConversationEngine(self.config, self.memory, self.logger)

        # 1. Non-existent file
        with self.assertRaises(FileNotFoundError):
            engine.transcribe(Path(self.temp_dir.name) / "missing.wav")

        # 2. Unsupported extension
        unsupported = Path(self.temp_dir.name) / "sample.txt"
        unsupported.write_text("not audio", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            engine.transcribe(unsupported)
        self.assertIn("Unsupported audio format", str(ctx.exception))

        # 3. Empty audio file
        empty_wav = Path(self.temp_dir.name) / "empty.wav"
        empty_wav.write_bytes(b"")
        with self.assertRaises(ValueError) as ctx:
            engine.transcribe(empty_wav)
        self.assertIn("is empty", str(ctx.exception))

    @patch("requests.post")
    def test_elevenlabs_tts_success(self, mock_post: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_post.return_value = mock_response

        tts = ElevenLabsTTS(self.config)
        output_path = Path(self.temp_dir.name) / "test_eleven.mp3"
        result = tts.synthesize("Namaste", output_path)

        self.assertEqual(result, output_path)
        self.assertTrue(output_path.exists())
        self.assertEqual(output_path.read_bytes(), b"chunk1chunk2")

    @patch("requests.post")
    def test_elevenlabs_tts_failure_returns_none(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = Exception("ElevenLabs connection error")

        tts = ElevenLabsTTS(self.config)
        output_path = Path(self.temp_dir.name) / "fail.mp3"
        result = tts.synthesize("Namaste", output_path)

        self.assertIsNone(result)

    @patch("riverwood.providers.tts_provider.OpenAI")
    def test_openai_tts_uses_valid_model(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_speech = MagicMock()
        mock_client.audio.speech.create.return_value = mock_speech
        mock_openai_cls.return_value = mock_client

        tts = OpenAITTS(self.config)
        output_path = Path(self.temp_dir.name) / "openai_speech.mp3"
        result = tts.synthesize("Hello", output_path)

        self.assertEqual(result, output_path)
        # Verify valid model 'tts-1' was passed, not 'gpt-4o-mini-tts'
        mock_client.audio.speech.create.assert_called_once()
        call_kwargs = mock_client.audio.speech.create.call_args[1]
        self.assertEqual(call_kwargs["model"], "tts-1")


if __name__ == "__main__":
    unittest.main()
