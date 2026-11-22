"""Riverwood AI CRM Voice Agent CLI and entry point.

Maintains complete backward compatibility with original commands:
- python cli_agent.py cli
- python cli_agent.py transcribe <audio_path>
- python cli_agent.py speak "<text>"
- python cli_agent.py server --host 0.0.0.0 --port 8000
- python cli_agent.py call --to <E.164_NUMBER>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, Optional

from riverwood.agent import RiverwoodVoiceAgent
from riverwood.api import create_app as create_fastapi_app
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

try:
    import uvicorn
except ImportError:  # pragma: no cover
    uvicorn = None

__all__ = [
    "AgentConfig",
    "RiverwoodVoiceAgent",
    "looks_like_placeholder",
    "sanitize_env",
    "now_iso",
    "KNOWLEDGE_BASE",
    "CALLBACK_KEYWORDS",
    "TWILIO_LANGUAGE",
    "TWILIO_POLLY_VOICE",
    "ConversationStore",
    "JsonlLogger",
    "ElevenLabsTTS",
    "OpenAITTS",
    "WindowsSystemTTS",
    "OpenAIConversationEngine",
    "normalize_phone_number",
    "is_valid_e164",
    "mask_phone_number",
    "sanitize_user_input",
    "build_twiml",
    "build_initial_greeting_twiml",
    "build_silence_twiml",
    "start_outbound_call",
    "create_fastapi_app",
    "run_cli",
    "build_parser",
    "main",
]


def open_audio_file(file_path: Path) -> None:
    """Open audio file in the host operating system's default media player."""
    try:
        if os.name == "nt":
            os.startfile(str(file_path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{file_path}"')
        else:
            os.system(f'xdg-open "{file_path}"')
    except Exception as exc:  # pragma: no cover - OS-specific
        print(f"[warn] Unable to open audio automatically: {exc}")


def print_status_table(status: Dict[str, str]) -> None:
    """Print clean diagnostics table in terminal."""
    print("=" * 64)
    print(" Riverwood AI Voice Agent")
    print("=" * 64)
    for name, state in status.items():
        print(f" {name:<18} : {state}")
    print("=" * 64)


def run_cli(agent: RiverwoodVoiceAgent, autoplay: bool = True) -> int:
    """Interactive command-line chat session."""
    print_status_table(agent.config.provider_status())

    missing = agent.config.missing_for_cli()
    if missing:
        print(f"Missing required configuration: {', '.join(missing)}")
        return 1

    print("Type your message, `voice: <path>` to transcribe an audio file, or `exit` to quit.")
    print(
        "\nAgent: Namaste. Hello. I am your Riverwood Estate voice assistant. "
        "How can I help you today?"
    )

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAgent: Thank you for your time. Have a wonderful day.")
            return 0

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit", "bye"}:
            print("\nAgent: Thank you for speaking with Riverwood Estate. Have a wonderful day.")
            return 0

        if user_input.lower().startswith("voice:"):
            audio_path = Path(user_input.split(":", 1)[1].strip()).expanduser()
            try:
                user_input = agent.transcribe_file(audio_path)
                print(f'[transcript] "{user_input}"')
            except Exception as exc:
                print(f"[error] Unable to transcribe audio: {exc}")
                continue

        try:
            reply = agent.answer(user_text=user_input)
        except Exception as exc:
            print(f"[error] Failed to generate a response: {exc}")
            continue

        print(f"\nAgent: {reply}")

        if (
            not agent.primary_tts.available()
            and not agent.fallback_tts.available()
            and not agent.local_tts.available()
        ):
            continue

        audio_file = agent.speak_to_file(reply)
        if not audio_file:
            print("[warn] Voice synthesis failed, so only text was returned.")
            continue

        print(f"[voice] Saved reply to {audio_file}")
        if autoplay:
            open_audio_file(audio_file)


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser with subcommands."""
    parser = argparse.ArgumentParser(description="Riverwood AI voice agent")
    subparsers = parser.add_subparsers(dest="command")

    cli_parser = subparsers.add_parser("cli", help="Run the interactive CLI voice assistant")
    cli_parser.add_argument("--no-autoplay", action="store_true", help="Do not auto-open generated audio")

    transcribe_parser = subparsers.add_parser("transcribe", help="Transcribe an audio file")
    transcribe_parser.add_argument("audio_path", help="Path to an audio file")

    speak_parser = subparsers.add_parser("speak", help="Generate spoken audio from text")
    speak_parser.add_argument("text", help="Text to convert into audio")

    server_parser = subparsers.add_parser("server", help="Run the FastAPI phone webhook server")
    server_parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    server_parser.add_argument("--port", type=int, default=8000, help="Port to bind")

    call_parser = subparsers.add_parser("call", help="Start an outbound Twilio voice call")
    call_parser.add_argument("--to", required=True, help="Destination phone number in E.164 format")

    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not args.command:
        args = parser.parse_args(["cli"])

    config = AgentConfig.from_env()
    agent = RiverwoodVoiceAgent(config=config)

    if args.command == "cli":
        return run_cli(agent=agent, autoplay=not args.no_autoplay)

    if args.command == "transcribe":
        missing = config.missing_for_cli()
        if missing:
            print(f"Missing required configuration: {', '.join(missing)}")
            return 1
        try:
            print(agent.transcribe_file(Path(args.audio_path).expanduser()))
            return 0
        except Exception as exc:
            print(f"[error] {exc}")
            return 1

    if args.command == "speak":
        missing = config.missing_for_voice_output()
        if missing:
            print(f"Missing required configuration: {', '.join(missing)}")
            return 1
        audio_file = agent.speak_to_file(args.text)
        if not audio_file:
            print("[error] Failed to generate speech")
            return 1
        print(audio_file)
        return 0

    if args.command == "server":
        missing = config.missing_for_phone_mode()
        if missing:
            print(f"Phone mode is not ready. Missing: {', '.join(missing)}")
            return 1
        if uvicorn is None:
            print("FastAPI server dependencies are missing. Run `pip install -r requirements.txt`.")
            return 1
        app = create_fastapi_app(agent)
        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    if args.command == "call":
        try:
            result = start_outbound_call(config=config, to_number=args.to)
        except Exception as exc:
            print(f"[error] Failed to start outbound call: {exc}")
            return 1
        print(json.dumps(result, indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
