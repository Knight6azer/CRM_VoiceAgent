"""FastAPI web service for Twilio voice webhooks with HMAC-SHA1 signature authentication and async offload."""

import asyncio
import uuid
from typing import Optional

from riverwood.agent import RiverwoodVoiceAgent
from riverwood.logging import now_iso
from riverwood.security import TwilioSignatureValidator, normalize_phone_number

try:
    from fastapi import FastAPI, HTTPException, Request, Response, status
    from fastapi.responses import JSONResponse
except ImportError:  # pragma: no cover
    FastAPI = None
    HTTPException = None
    Request = None
    Response = None
    JSONResponse = None
    status = None


def create_app(agent: RiverwoodVoiceAgent) -> "FastAPI":
    """Create and configure the FastAPI application instance."""
    if FastAPI is None or Response is None or JSONResponse is None:
        raise RuntimeError(
            "FastAPI dependencies are not installed. Run `pip install -r requirements.txt` first."
        )

    app = FastAPI(
        title="Riverwood AI CRM Voice Agent",
        description="Twilio webhook endpoints and diagnostics for Riverwood Estate Voice Assistant.",
        version="2.1.0",
    )

    validator = TwilioSignatureValidator(
        auth_token=agent.config.twilio_auth_token,
        enabled=agent.config.validate_twilio_signature,
    )

    async def verify_twilio_request(request: Request, form_data: dict) -> None:
        """Verify HMAC-SHA1 signature on incoming Twilio webhooks if signature verification is enabled."""
        if not agent.config.validate_twilio_signature:
            return

        signature = request.headers.get("X-Twilio-Signature")
        if not signature:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing Twilio signature header (X-Twilio-Signature)",
            )

        # Build full URL as seen by Twilio (support configured public base URL if behind reverse proxy)
        if agent.config.twilio_webhook_base_url:
            base_url = agent.config.twilio_webhook_base_url.rstrip("/")
            path = request.url.path
            effective_url = f"{base_url}{path}"
        else:
            effective_url = str(request.url)

        # Twilio form parameters are passed as dict of string values
        params = {k: str(v) for k, v in form_data.items()}

        is_valid = validator.validate(url=effective_url, params=params, signature=signature)
        if not is_valid:
            # Also try raw request.url in case webhook base URL differs slightly in protocol/path
            if str(request.url) != effective_url:
                is_valid = validator.validate(url=str(request.url), params=params, signature=signature)

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Twilio signature verification failed. Untrusted webhook sender.",
            )

    @app.get("/health")
    async def health() -> JSONResponse:
        """Health check and provider diagnostics."""
        return JSONResponse(
            {
                "status": "ok",
                "providers": agent.config.provider_status(),
                "timestamp": now_iso(),
            }
        )

    @app.post("/voice/incoming")
    async def voice_incoming(request: Request) -> Response:
        """Initial Twilio voice webhook returning greeting and speech Gather."""
        form = await request.form()
        form_dict = dict(form)
        await verify_twilio_request(request, form_dict)

        twiml = agent.initial_greeting_twiml()
        return Response(content=twiml, media_type="application/xml")

    @app.post("/voice/respond")
    async def voice_respond(request: Request) -> Response:
        """Twilio voice callback receiving speech recognition result and returning AI TwiML response."""
        form = await request.form()
        form_dict = dict(form)
        await verify_twilio_request(request, form_dict)

        speech_result = str(form.get("SpeechResult") or "").strip()
        call_sid = str(form.get("CallSid") or uuid.uuid4().hex)
        caller = normalize_phone_number(str(form.get("Caller") or ""))

        if not speech_result:
            twiml = agent.silence_twiml()
            return Response(content=twiml, media_type="application/xml")

        # Offload synchronous LLM completion and logging to threadpool to avoid event loop blocking
        twiml = await asyncio.to_thread(agent.response_twiml, speech_result, call_sid, caller)
        return Response(content=twiml, media_type="application/xml")

    return app
