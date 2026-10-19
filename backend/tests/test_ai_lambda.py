"""The parser's Lambda handler: who may call it, what it refuses, what it logs."""

import base64
import json
import logging
from datetime import date
from typing import Any

import httpx
import pytest
from anthropic import RateLimitError
from botocore.exceptions import ClientError

from app.ai import agenda_lambda
from app.ai.agenda import AgendaParseError
from app.schemas.agenda import ParsedAgenda
from tests.tokens import make_token

AGENDA = ParsedAgenda.model_validate(
    {"title": "Pricing sync", "items": [{"topic": "Pro plan", "owner": "Olena"}], "language": "en"}
)
USAGE = {"input_tokens": 2400, "output_tokens": 350}


def _event(body: Any = None, *, token: str | None = "default", b64: bool = False) -> dict:
    if body is None:
        body = {"text": "Monday 10:00 pricing sync", "today": "2026-10-19", "tz": "Europe/Kyiv"}
    raw = body if isinstance(body, str) else json.dumps(body)
    headers = {"content-type": "application/json"}
    if token == "default":
        token = make_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if b64:
        raw = base64.b64encode(raw.encode()).decode()
    return {"headers": headers, "body": raw, "isBase64Encoded": b64}


@pytest.fixture
def parsed(monkeypatch) -> list[tuple]:
    """Replace the model call; records what it was asked."""
    calls: list[tuple] = []

    def fake(text: str, today: date, tz: str) -> tuple[ParsedAgenda, dict]:
        calls.append((text, today, tz))
        return AGENDA, dict(USAGE)

    monkeypatch.setattr(agenda_lambda, "parse_agenda", fake)
    return calls


def _body(response: dict) -> dict:
    return json.loads(response["body"])


def test_parses_and_logs_one_line(parsed, caplog) -> None:
    caplog.set_level(logging.INFO, logger="agenda-parser")

    response = agenda_lambda.handler(_event(), None)

    assert response["statusCode"] == 200
    body = _body(response)
    assert body["agenda"]["items"][0]["owner"] == "Olena"
    assert body["model"] == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert body["prompt_version"] == "agenda-v2"
    assert parsed == [("Monday 10:00 pricing sync", date(2026, 10, 19), "Europe/Kyiv")]

    lines = [json.loads(r.getMessage()) for r in caplog.records if r.name == "agenda-parser"]
    assert len(lines) == 1
    line = lines[0]
    assert line["event"] == "agenda_parsed"
    assert line["user"] == "alice-sub"
    assert line["input_tokens"] == 2400 and line["output_tokens"] == 350
    assert line["api"] == "converse"
    assert line["cost_usd"] == pytest.approx(2400 * 1 / 1e6 + 350 * 5 / 1e6)
    assert isinstance(line["latency_ms"], int)
    # Nothing of the pasted text reaches the log.
    assert "pricing" not in json.dumps(line)


def test_base64_body(parsed) -> None:
    assert agenda_lambda.handler(_event(b64=True), None)["statusCode"] == 200


@pytest.mark.parametrize(
    "token", [None, "not-a-jwt", make_token(token_use="access"), make_token(aud="other-client")]
)
def test_rejects_anyone_without_an_id_token(parsed, token) -> None:
    response = agenda_lambda.handler(_event(token=token), None)
    assert response["statusCode"] == 401
    assert parsed == []


def test_long_text_is_refused_before_the_model(parsed) -> None:
    body = {"text": "x" * 10_001, "today": "2026-10-19", "tz": "Europe/Kyiv"}
    response = agenda_lambda.handler(_event(body), None)
    assert response["statusCode"] == 413
    assert _body(response)["error"] == "too_long"
    assert parsed == []


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        {"text": "x"},
        {"text": "x", "today": "Monday", "tz": "Europe/Kyiv"},
        {"text": "x", "today": "2026-10-19", "tz": "Mars/Olympus"},
        {"text": "   ", "today": "2026-10-19", "tz": "Europe/Kyiv"},
    ],
)
def test_bad_requests(parsed, body) -> None:
    assert agenda_lambda.handler(_event(body), None)["statusCode"] == 400
    assert parsed == []


def test_no_agenda_is_a_422_and_still_logged(monkeypatch, caplog) -> None:
    caplog.set_level(logging.INFO, logger="agenda-parser")

    def fails(*_: Any) -> None:
        raise AgendaParseError("the text has no agenda in it", dict(USAGE), no_agenda=True)

    monkeypatch.setattr(agenda_lambda, "parse_agenda", fails)
    response = agenda_lambda.handler(_event(), None)

    assert response["statusCode"] == 422
    assert _body(response)["error"] == "no_agenda"
    line = json.loads(caplog.records[-1].getMessage())
    assert line["event"] == "agenda_parse_failed"
    assert line["input_tokens"] == 2400


def test_throttling_is_a_429(monkeypatch) -> None:
    request = httpx.Request("POST", "https://bedrock-mantle.us-east-1.api.aws/v1/messages")

    def throttled(*_: Any) -> None:
        raise RateLimitError(
            "Too many tokens", response=httpx.Response(429, request=request), body=None
        )

    monkeypatch.setattr(agenda_lambda, "parse_agenda", throttled)
    response = agenda_lambda.handler(_event(), None)
    assert response["statusCode"] == 429
    assert _body(response)["error"] == "busy"


@pytest.mark.parametrize(("code", "status"), [("ThrottlingException", 429), ("ModelError", 503)])
def test_converse_errors(monkeypatch, code, status) -> None:
    def fails(*_: Any) -> None:
        raise ClientError({"Error": {"Code": code, "Message": "nope"}}, "Converse")

    monkeypatch.setattr(agenda_lambda, "parse_agenda", fails)
    assert agenda_lambda.handler(_event(), None)["statusCode"] == status
