"""AWS Lambda entry point of the agenda parser (infra/ai.tf), behind its own function URL.

``POST {"text": ..., "today": "2026-10-19", "tz": "Europe/Kyiv"}`` with a Cognito
ID token answers ``{"agenda": ..., "model": ..., "prompt_version": ...}``. The
browser sends ``today`` and ``tz`` because the user's "Monday" is in the user's
time zone, not this function's, which runs in UTC.

It runs outside the VPC: it needs Bedrock and the pool's public keys, both on
the internet, and never the database. It only suggests. Saving goes through
the API's items endpoints, with their validation; nothing here writes anything.

Every call costs money, so it is authenticated, the text is capped before the
model sees it, and every parse logs one JSON line with its tokens and cost.
"""

import base64
import json
import logging
import time
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ValidationError

from app.ai.agenda import MAX_TEXT_CHARS, PROMPT_VERSION, AgendaParseError, parse_agenda
from app.ai.pricing import cost_usd
from app.config import get_settings
from app.id_tokens import InvalidToken, KeysUnavailable, verify_pool_token

# Bedrock's error codes for "slow down" on the Converse API.
THROTTLED = {"ThrottlingException", "TooManyRequestsException", "ServiceQuotaExceededException"}

logger = logging.getLogger("agenda-parser")
logger.setLevel(logging.INFO)


class ParseRequest(BaseModel):
    text: str
    today: date
    tz: str


def _reply(status: int, body: dict[str, Any]) -> dict[str, Any]:
    # CORS headers are added by the function URL itself (infra/ai.tf).
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def _error(status: int, code: str, message: str) -> dict[str, Any]:
    return _reply(status, {"error": code, "message": message})


def _log(event: str, user: str, started: float, usage: dict[str, int], **extra: Any) -> None:
    settings = get_settings()
    model = settings.parser_model
    logger.info(
        json.dumps(
            {
                "event": event,
                "user": user,
                "api": settings.parser_api,
                "model": model,
                "prompt_version": PROMPT_VERSION,
                **usage,
                "latency_ms": int((time.monotonic() - started) * 1000),
                "cost_usd": cost_usd(model, usage),
                **extra,
            }
        )
    )


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    settings = get_settings()
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}

    scheme, _, token = headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        return _error(401, "unauthorized", "Not signed in")
    try:
        user = verify_pool_token(token, settings)["sub"]
    except InvalidToken:
        return _error(401, "unauthorized", "Invalid token")
    except KeysUnavailable as exc:
        logger.warning("could not check the token: %s", exc)
        return _error(503, "unavailable", "Sign-in cannot be checked right now")

    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8", errors="replace")
    try:
        request = ParseRequest.model_validate_json(raw)
        ZoneInfo(request.tz)
    except ValidationError, ZoneInfoNotFoundError, ValueError:
        return _error(400, "bad_request", 'Expected {"text", "today", "tz"}')

    if not request.text.strip():
        return _error(400, "bad_request", "The text is empty")
    # Before the model is called: every character of a pasted novel is paid for.
    if len(request.text) > MAX_TEXT_CHARS:
        return _error(413, "too_long", f"The text is longer than {MAX_TEXT_CHARS:,} characters")

    from anthropic import APIConnectionError, APIStatusError, OverloadedError, RateLimitError
    from botocore.exceptions import BotoCoreError, ClientError

    started = time.monotonic()
    try:
        agenda, usage = parse_agenda(request.text, request.today, request.tz)
    except AgendaParseError as exc:
        _log("agenda_parse_failed", user, started, exc.usage, reason=str(exc))
        code = "no_agenda" if exc.no_agenda else "invalid_output"
        return _error(422, code, str(exc))
    except RateLimitError, OverloadedError:
        logger.warning("bedrock throttled the parse")
        return _error(429, "busy", "The parser is busy, try again in a minute")
    except ClientError as exc:  # the Converse API
        if exc.response.get("Error", {}).get("Code") in THROTTLED:
            logger.warning("bedrock throttled the parse")
            return _error(429, "busy", "The parser is busy, try again in a minute")
        logger.exception("bedrock call failed: %s", exc)
        return _error(503, "unavailable", "The parser is unavailable right now")
    except (APIStatusError, APIConnectionError, BotoCoreError) as exc:
        # Every other error status and a failed connection: Bedrock, not the text, is the problem.
        logger.exception("bedrock call failed: %s", exc)
        return _error(503, "unavailable", "The parser is unavailable right now")

    _log("agenda_parsed", user, started, usage)
    return _reply(
        200,
        {
            "agenda": agenda.model_dump(mode="json"),
            "model": settings.parser_model,
            "prompt_version": PROMPT_VERSION,
        },
    )
