"""Abstract interfaces for LLM and TTS providers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class BaseTTSProvider(ABC):
    """Abstract base class for text-to-speech providers."""

    @abstractmethod
    def available(self) -> bool:
        """Return True if credentials and prerequisites are satisfied."""
        pass

    @abstractmethod
    def synthesize(self, text: str, output_path: Path) -> Optional[Path]:
        """Synthesize text into audio file, returning path on success or None on failure."""
        pass


class BaseLLMProvider(ABC):
    """Abstract base class for LLM conversation engines."""

    @abstractmethod
    def available(self) -> bool:
        """Return True if credentials and prerequisites are satisfied."""
        pass
