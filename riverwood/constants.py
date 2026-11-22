"""Central constants, knowledge base, and prompt definitions for Riverwood AI CRM."""

from typing import Set

DEFAULT_OPENAI_MODEL: str = "gpt-4o-mini"
DEFAULT_TRANSCRIPTION_MODEL: str = "whisper-1"
DEFAULT_OPENAI_TTS_MODEL: str = "tts-1"
DEFAULT_ELEVENLABS_VOICE_ID: str = "pNInz6ovhh85mx4SdID9"
DEFAULT_ELEVENLABS_MODEL_ID: str = "eleven_multilingual_v2"

TWILIO_POLLY_VOICE: str = "Polly.Aditi-Neural"
TWILIO_LANGUAGE: str = "en-IN"

PLACEHOLDER_MARKERS = (
    "your_",
    "replace_me",
    "example",
    "changeme",
    "xxxx",
    "acxxxxxxxx",
)

KNOWLEDGE_BASE: str = """
You are the Riverwood AI Voice Agent, a warm and premium relationship manager for Riverwood Estate.

Voice and behavior rules:
1. Greet warmly in natural Hindi-English.
2. Keep responses concise, voice-friendly, and polished.
3. Sound confident, calm, and proactive.
4. If the caller asks about pricing, legal matters, payment plans, possession timelines, or anything uncertain,
   offer a callback from a human relationship manager within 2 working hours.
5. If the caller sounds interested in a site visit, collect that intent naturally and encourage a callback.
6. Never fabricate legal status, guarantees, or exact financial figures not provided in the knowledge context.

Riverwood project context:
- Sector A road works are 75 percent complete and bituminous layering is in progress.
- Sector B landscaping and clubhouse foundation work have started.
- The estate is progressing steadily with a focus on premium infrastructure and long-term value.
""".strip()

CALLBACK_KEYWORDS: Set[str] = {
    "price",
    "pricing",
    "cost",
    "payment",
    "emi",
    "loan",
    "registry",
    "legal",
    "possession",
    "visit",
    "site visit",
    "discount",
}

FALLBACK_PROGRESS_REPLY: str = (
    "Namaste. Riverwood Estate is progressing well. Sector A roads are about 75 percent complete "
    "with bituminous layering in progress, and Sector B landscaping plus clubhouse foundation work "
    "have started beautifully."
)

FALLBACK_CALLBACK_REPLY: str = (
    "Namaste. For pricing, legal guidance, or visit planning, I can arrange a callback from your "
    "Relationship Manager within 2 working hours."
)

FALLBACK_DEFAULT_REPLY: str = (
    "Namaste. Riverwood Estate is progressing steadily, and I can help with project updates, site-visit "
    "interest, or arranging a callback from a Relationship Manager within 2 working hours."
)
