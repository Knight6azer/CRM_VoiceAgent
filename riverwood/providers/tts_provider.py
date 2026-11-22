"""Text-to-speech providers for ElevenLabs, OpenAI TTS, and local system speech."""

import os
import subprocess
from pathlib import Path
from typing import Optional

import requests
from openai import OpenAI

from riverwood.config import AgentConfig, looks_like_placeholder
from riverwood.providers.base import BaseTTSProvider


class ElevenLabsTTS(BaseTTSProvider):
    """ElevenLabs REST TTS provider."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config

    def available(self) -> bool:
        return bool(self.config.elevenlabs_api_key and not looks_like_placeholder(self.config.elevenlabs_api_key))

    def synthesize(self, text: str, output_path: Path) -> Optional[Path]:
        if not self.available():
            return None

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.config.elevenlabs_voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.config.elevenlabs_api_key or "",
        }
        payload = {
            "text": text,
            "model_id": self.config.elevenlabs_model_id,
            "voice_settings": {"stability": 0.45, "similarity_boost": 0.75},
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15, stream=True)
            response.raise_for_status()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        handle.write(chunk)
            return output_path
        except Exception as exc:
            print(f"[warn] ElevenLabs synthesis failed: {exc}")
            return None


class OpenAITTS(BaseTTSProvider):
    """OpenAI TTS provider using verified models (tts-1 / tts-1-hd)."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._client: Optional[OpenAI] = None

    def available(self) -> bool:
        return bool(self.config.openai_api_key and not looks_like_placeholder(self.config.openai_api_key))

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            if not self.available():
                raise RuntimeError("OPENAI_API_KEY is missing or set to a placeholder.")
            self._client = OpenAI(
                api_key=self.config.openai_api_key,
                timeout=15.0,
            )
        return self._client

    def synthesize(self, text: str, output_path: Path) -> Optional[Path]:
        if not self.available():
            return None

        try:
            response = self.client.audio.speech.create(
                model=self.config.openai_tts_model,
                voice="alloy",
                input=text,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            response.stream_to_file(output_path)
            return output_path
        except Exception as exc:
            print(f"[warn] OpenAI speech synthesis failed: {exc}")
            return None


class WindowsSystemTTS(BaseTTSProvider):
    """Local Windows System.Speech synthesizer via PowerShell."""

    def available(self) -> bool:
        return os.name == "nt"

    def synthesize(self, text: str, output_path: Path) -> Optional[Path]:
        if not self.available():
            return None

        output_path.parent.mkdir(parents=True, exist_ok=True)
        escaped_text = text.replace("'", "''")
        escaped_output = str(output_path).replace("'", "''")
        command = (
            "Add-Type -AssemblyName System.Speech; "
            "$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$speaker.SetOutputToWaveFile('{escaped_output}'); "
            f"$speaker.Speak('{escaped_text}'); "
            "$speaker.Dispose();"
        )

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip() or "Unknown PowerShell speech error"
                print(f"[warn] Windows speech synthesis failed: {stderr}")
                return None
            return output_path
        except Exception as exc:
            print(f"[warn] Windows speech synthesis failed: {exc}")
            return None
