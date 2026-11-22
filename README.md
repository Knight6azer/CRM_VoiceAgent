# Riverwood AI CRM Voice Agent

> Automating real estate customer relationship management, construction updates, and site-visit inquiries through bilingual (Hindi-English) voice conversations and intelligent CRM callback logging.

---

## Problem

Real-estate developers and relationship managers (RMs) face substantial communication overhead managing inquiries from existing property buyers and prospective investors:
- Repetitive status inquiries regarding construction milestones, road development, and foundation progress consume significant manual RM bandwidth.
- Prospective buyers calling outside office hours or during peak times encounter busy signals or delayed responses, increasing drop-off rates.
- Conversational inquiries in the Indian real estate market naturally blend English and Hindi ("Hinglish"), which standard interactive voice response (IVR) systems fail to understand.
- Unconstrained conversational bots risk hallucinating critical financial commitments, legal possession dates, or payment discounts, exposing developers to liability.

## Why It Matters

- **Property Buyers & Investors**: Receive instantaneous, 24/7 project progress updates and clear, professional guidance on next steps without waiting on hold.
- **Relationship Managers**: Free up hours of routine status calls to focus on high-value client negotiations; receive structured, pre-qualified callback requests with caller context and conversation summaries.
- **Riverwood Estate Developers**: Maintain consistent, polished customer relationship management, enforce strict legal and pricing boundaries, and capture every prospective buyer's intent in real-time.

---

## Architecture

The system operates across two primary interaction channels: **Telephony (Twilio Webhooks)** and **Local Interactive CLI / File Processing**.

```
                           [ Property Buyer / Caller ]
                                      │
         ┌────────────────────────────┴───────────────────────────┐
         │ (Telephony Channel: Voice Call)                         │ (Local Developer Channel: CLI / Audio)
         ▼                                                         ▼
[ Twilio Voice Platform ]                                   [ cli_agent.py CLI ]
  │ POST /voice/incoming                                           │
  ▼                                                                │
[ FastAPI Webhook Server ]                                         │
  │ HMAC-SHA1 Signature Verification (TwilioSignatureValidator)   │
  │ XML TwiML <Say voice="Polly.Aditi-Neural"> + <Gather>          │
  ▼                                                                │
[ Twilio Speech Recognition (STT) ]                                │
  │ POST /voice/respond (SpeechResult)                             │
  └───────────────────────────┬────────────────────────────────────┘
                              │
                              ▼
               [ RiverwoodVoiceAgent Orchestrator ]
                              │
               ├── ConversationStore (In-memory, Session-isolated, LRU evicted)
               │
               ├── OpenAIConversationEngine
               │     ├── System Prompt (KNOWLEDGE_BASE + CRM boundaries)
               │     ├── GPT-4o-mini (Bounded timeout: 8.0s)
               │     └── (On Error/Timeout) ──> Deterministic Keyword Fallback
               │
               ├── Commercial Intent & Callback Classifier
               │     └── Checks CALLBACK_KEYWORDS (price, legal, visit, emi, etc.)
               │
               ├── CRM Data Logging (JsonlLogger)
               │     ├── logs/transcripts.jsonl (Audit trail with masked PII)
               │     └── logs/callbacks.jsonl   (Actionable RM callback records)
               │
               └── Voice Synthesis Engine
                     ├── Telephony: Twilio Polly.Aditi-Neural (XML TwiML stream)
                     └── CLI / File: ElevenLabs -> OpenAI TTS (tts-1) -> Windows System TTS
```

---

## Dataset

- **Training Dataset**: No conventional machine learning model training dataset is used. The application uses zero-shot and few-shot instruction prompting grounded in a deterministic domain knowledge base.
- **Knowledge Base Source**: Structured domain rules defined in `riverwood/constants.py` covering Riverwood Estate Sector A (roads 75% complete, bituminous layering in progress) and Sector B (landscaping and clubhouse foundation works underway).
- **Callback Taxonomy**: A targeted lexicon of commercial intent triggers (`CALLBACK_KEYWORDS`) encompassing pricing, legal documentation, payment plans, home loans, possession timelines, and site visits.
- **Test Fixtures**: 45 automated unit, mock, and integration test cases covering happy paths, security failures, provider timeouts, and concurrency boundaries.

---

## Approach

### 1. Conversational AI & Safety Guardrails
- **Model**: OpenAI `gpt-4o-mini` with a conservative temperature ($0.55$) and max token limit ($220$) to ensure concise, natural, voice-friendly answers.
- **Boundary Control**: The system prompt strictly prohibits fabricating legal status, possession guarantees, or unverified pricing. Any commercial uncertainty immediately triggers an offer for a human relationship manager callback within 2 working hours.
- **Deterministic Offline Fallback**: If OpenAI is unreachable, times out, or fails authentication, the conversation engine immediately falls back to deterministic rule-based responses without dropping the caller or leaving dead air.

### 2. Telephony & Webhook Security
- **Twilio Integration**: Bidirectional voice calls using Twilio Voice API and standard TwiML `<Gather input="speech">` elements.
- **Voice Persona**: Amazon Polly Aditi Neural (`Polly.Aditi-Neural`) configured with Indian English (`en-IN`) for natural bilingual articulation.
- **Cryptographic Webhook Authentication**: All incoming Twilio requests are validated using HMAC-SHA1 signatures against `TWILIO_AUTH_TOKEN` (`X-Twilio-Signature`), preventing forged requests and replay attacks.
- **Asynchronous Event Loop Protection**: Synchronous AI completions and file logging are offloaded via `asyncio.to_thread`, ensuring the FastAPI event loop remains responsive under concurrent load.

### 3. Speech Recognition & Synthesis
- **Incoming Voice (Phone)**: Real-time telephony transcription performed by Twilio Speech-to-Text.
- **File Transcription (CLI)**: OpenAI Whisper (`whisper-1`) with file existence, format extension, and 25MB payload size validation.
- **Voice Generation Cascade (CLI/Audio Output)**:
  1. *Primary*: ElevenLabs multilingual REST API (`eleven_multilingual_v2` / Rachel voice `pNInz6ovhh85mx4SdID9`).
  2. *Secondary Fallback*: OpenAI Audio Speech API (`tts-1` model with `alloy` voice).
  3. *Local Fallback*: Windows `System.Speech.Synthesis` PowerShell synthesizer (zero cloud dependency).

### 4. Memory & CRM Logging
- **Thread-Safe Memory**: `ConversationStore` maintains dialogue turns with strict session isolation (`session_id`), turn bounds (`max_turns=12`), and capacity limits (`max_sessions=1000`) with LRU eviction to prevent memory leaks.
- **Privacy-Conscious CRM Logs**: Writes structured JSONL records to `logs/transcripts.jsonl` and `logs/callbacks.jsonl` with configurable PII masking (e.g., `+1555***4567`) to protect customer data.

---

## Results

All benchmarks below are empirically measured directly on the local runtime environment:

| Component / Operation | Measured Latency | Success Rate | Test / Benchmark Method |
| :--- | :--- | :--- | :--- |
| **Deterministic Fallback Engine** | `0.001 ms/req` | 100% | 100-iteration micro-benchmark |
| **TwiML XML Generation** | `0.022 ms/req` | 100% | 100-iteration micro-benchmark |
| **Session Memory (Append + Fetch)** | `0.003 ms/req` | 100% | 100-iteration micro-benchmark |
| **JSONL Disk Audit Logging** | `0.371 ms/req` | 100% | Thread-locked filesystem write |
| **Automated Test Suite Execution** | `1.44 seconds total` | 100% (45/45 passing) | Python `unittest` full suite |

*Note: Classical ML metrics (Precision, Recall, F1) are not applicable as this system employs zero-shot prompt engineering and rule-based dispatching rather than a trained classification model.*

---

## Error Analysis

| Failure Scenario | Root Cause & Risk | Mitigation Implemented |
| :--- | :--- | :--- |
| **OpenAI API Timeout / Slow Latency** | Twilio webhook drops call after 15s of silence if LLM takes too long. | Configured strict `llm_timeout_seconds=8.0s`. On timeout, gracefully catches error and returns deterministic construction/callback response. |
| **Forged Webhook Invocations** | Malicious third-party submitting fake transcripts to `/voice/respond`. | `TwilioSignatureValidator` verifies HMAC-SHA1 signature on all incoming POST requests; rejects invalid or missing signatures with HTTP 403 Forbidden. |
| **Speech Recognition Silence** | Caller stays silent or background noise obscures utterance. | `/voice/respond` detects empty `SpeechResult`, returning polite reprompt TwiML without crashing or terminating call prematurely. |
| **Unbounded Memory Growth** | Long-running webhook server tracking thousands of unique caller sessions. | `ConversationStore` enforces LRU eviction at `max_sessions=1000` and bounds dialogue history at `max_turns=12`. |
| **Audio File Input Errors** | Non-existent, corrupted, empty, or oversized audio files supplied to CLI. | Strict pre-flight checks: file presence, extension whitelist (`.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`, `.webm`), zero-byte check, and 25MB size limit. |
| **Prompt Injection Attacks** | Caller attempts to override agent instructions or extract API keys. | System prompt boundaries, input sanitization stripping control characters, and offline fallback isolation ensure secrets are never exposed. |

---

## Tech Stack

- **Runtime**: Python 3.10 / 3.11 / 3.12 / 3.13
- **Web Framework**: FastAPI, Starlette, Uvicorn, Python-Multipart
- **Telephony & Speech**: Twilio REST API, Twilio RequestValidator, Amazon Polly Neural
- **AI Core**: OpenAI API (GPT-4o-mini, Whisper-1, TTS-1)
- **Voice Synthesis**: ElevenLabs REST API, Windows System.Speech
- **Testing & Tooling**: Python `unittest`, `unittest.mock`, `httpx`
- **Configuration & Security**: `python-dotenv`, HMAC-SHA1 validation

---

## Demo & Usage

### 1. Interactive CLI Mode
Start an interactive terminal conversation:
```bash
python cli_agent.py cli
```
*Options:*
- Type any message to converse.
- Type `voice: path/to/recording.wav` to transcribe and answer an audio file.
- Type `exit` or `quit` to end the session.
- Pass `--no-autoplay` to suppress opening generated audio in media player.

### 2. Transcribe Audio File
```bash
python cli_agent.py transcribe sample.wav
```

### 3. Generate Speech
```bash
python cli_agent.py speak "Namaste, your Riverwood estate update is ready."
```

### 4. Run Telephony Webhook Server
```bash
python cli_agent.py server --host 0.0.0.0 --port 8000
```
Available endpoints:
- `GET /health`: JSON system health check and provider readiness.
- `POST /voice/incoming`: Twilio voice webhook entry point (returns greeting TwiML).
- `POST /voice/respond`: Twilio speech callback (processes caller transcript and returns TwiML).

### 5. Initiate Outbound Call
```bash
python cli_agent.py call --to +15551234567
```

---

## Installation & Setup

### Prerequisites
- Python 3.10+ installed.
- Git.

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/Knight6azer/CRM_VoiceAgent.git
cd CRM_VoiceAgent
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Populate your credentials in `.env`:
```env
# Required for AI Conversation
OPENAI_API_KEY=your_actual_openai_key

# Optional for High-Fidelity Voice Output
ELEVENLABS_API_KEY=your_actual_elevenlabs_key

# Required for Twilio Phone Calls & Webhooks
TWILIO_ACCOUNT_SID=your_actual_twilio_sid
TWILIO_AUTH_TOKEN=your_actual_twilio_auth_token
TWILIO_PHONE_NUMBER=+15551234567
TWILIO_WEBHOOK_BASE_URL=https://your-public-subdomain.ngrok-free.app

# Security & Privacy Settings
TWILIO_VALIDATE_SIGNATURE=false   # Set to 'true' in production
LOG_MASK_PHONE=true
```

### 3. Run Automated Tests
```bash
python -m unittest discover -s tests -v
```

---

## Screenshots

> *Architecture and telephony workflows are documented above. Visual dashboard screenshots from earlier prototypes have been replaced with production CLI logs, structured JSONL CRM audits, and automated test suite reports.*

```
================================================================
 Riverwood AI Voice Agent Diagnostics
================================================================
 OpenAI             : ready
 ElevenLabs         : ready
 Twilio             : ready
 Twilio Webhook     : ready
 Twilio Security    : disabled (dev mode)
 Apollo             : optional (not integrated)
 Vapi               : optional (not integrated)
================================================================
```

---

## Feature Implementation Status

| Feature / Capability | Classification | Technical Evidence |
| :--- | :--- | :--- |
| **Interactive CLI Agent** | **Implemented** | `cli_agent.py` supports text input, audio file transcription, and speech playback. |
| **OpenAI GPT-4o-mini Conversation** | **Implemented** | `riverwood.providers.openai_provider` with timeout handling and persona prompt. |
| **Deterministic Offline Fallback** | **Implemented** | Rule-based fallback covering construction, pricing, and general inquiries. |
| **Twilio Voice Webhooks (Incoming/Respond)** | **Implemented** | FastAPI routes returning Polly Aditi XML TwiML with `<Gather>`. |
| **Twilio Webhook HMAC Signature Security** | **Implemented** | `TwilioSignatureValidator` checking `X-Twilio-Signature` on all webhook endpoints. |
| **Twilio Outbound Calling Dispatcher** | **Implemented** | REST API call creation with E.164 phone number validation. |
| **Whisper Audio Transcription** | **Implemented** | Validated file transcription via OpenAI Whisper API. |
| **Cascading Speech Synthesis (TTS)** | **Implemented** | ElevenLabs -> OpenAI TTS (`tts-1`) -> Local Windows System.Speech. |
| **CRM JSONL Logging (Transcripts & Callbacks)** | **Implemented** | Thread-safe, PII-masked logging in `logs/transcripts.jsonl` and `logs/callbacks.jsonl`. |
| **Automated Unit & Integration Test Suite** | **Implemented** | 45 test cases passing in `tests/`. |
| **Multi-Platform CI/CD Pipeline** | **Implemented** | GitHub Actions workflow (`.github/workflows/ci.yml`) on Ubuntu and Windows. |
| **Redis / Celery Distributed Task Queue** | **Planned** | Architectural roadmap for dispatching 1000+ simultaneous outbound campaigns. |
| **Direct CRM REST Integration (Salesforce/HubSpot)** | **Planned** | Webhook emission from `callbacks.jsonl` to enterprise CRM platforms. |
| **Apollo / Vapi Native Integrations** | **Not Implemented** | Legacy configuration placeholders retained for future adapter development. |

---

## Future Improvements

### 1. Immediate Engineering (P2)
- Structured log rotation (`RotatingFileHandler`) for high-volume deployments.
- Structured correlation IDs (`X-Request-ID` / `CallSid`) threaded through all logger entries.

### 2. Scalability Improvements
- **Asynchronous Task Queue**: Integrate Redis and Celery/ARQ to queue batch outbound calling campaigns.
- **Stateless Horizontal Scaling**: Externalize dialogue session storage to Redis for multi-instance deployments behind a load balancer.

### 3. AI & Domain Capabilities
- **Dynamic CRM Grounding**: Connect knowledge retrieval to real-time construction site ERP / project management systems.
- **Fine-grained Intent Extraction**: Extract requested site visit dates and unit preferences into structured JSON fields.

### 4. Observability & Monitoring
- Export Prometheus metrics for webhook latency, OpenAI API response time, and fallback trigger rates.
- Sentry error monitoring integration for unhandled exceptions.
