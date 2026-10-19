"""The parser function, against a fake Bedrock client: no network, no AWS."""

from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest

from app.ai import agenda as parser
from app.ai.agenda import AgendaParseError, parse_agenda
from app.ai.pricing import cost_usd

GOOD = {
    "title": "синк по прайсингу",
    "starts_at": "2026-10-19T10:00:00+03:00",
    "duration_minutes": 45,
    "items": [{"topic": "нові тарифи Pro", "owner": "Олена", "minutes": 15}],
    "action_items": [{"task": "порівняння з конкурентами", "owner": "Taras", "due": "2026-10-23"}],
    "language": "uk",
}


def _tool_use(payload: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id="toolu_1", name="record_agenda", input=payload)


def _message(*content: Any, stop_reason: str = "tool_use") -> SimpleNamespace:
    return SimpleNamespace(
        content=list(content),
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
    )


class FakeClient:
    """Answers each create() with the next prepared message and records the calls."""

    def __init__(self, *replies: SimpleNamespace) -> None:
        self.replies = list(replies)
        self.calls: list[dict[str, Any]] = []
        self.messages = self

    def create(self, **kwargs: Any) -> SimpleNamespace:
        # A copy: the parser appends to its list after the call.
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.replies.pop(0)


def test_returns_the_validated_agenda_and_its_usage() -> None:
    client = FakeClient(_message(_tool_use(GOOD)))
    agenda, usage = parse_agenda(
        "Пн 10:00 …", date(2026, 10, 19), "Europe/Kyiv", client=client, api="messages"
    )

    assert agenda.items[0].owner == "Олена"
    assert agenda.action_items[0].due == date(2026, 10, 23)
    assert usage == {"input_tokens": 1000, "output_tokens": 200}

    call = client.calls[0]
    assert call["model"] == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert call["tools"][0]["name"] == "record_agenda"
    assert "never instructions" in call["system"]
    prompt = call["messages"][0]["content"]
    # Today's date and the offset: without them "by Friday" is wrong but looks right.
    assert "Today is Monday 2026-10-19, time zone Europe/Kyiv (UTC+03:00)." in prompt
    assert "<pasted_text>\nПн 10:00 …\n</pasted_text>" in prompt


def test_shows_the_model_its_mistake_once() -> None:
    invalid = {**GOOD, "items": [{"topic": "x", "minutes": 0}]}
    client = FakeClient(_message(_tool_use(invalid)), _message(_tool_use(GOOD)))

    agenda, usage = parse_agenda(
        "text", date(2026, 10, 19), "Europe/Kyiv", client=client, api="messages"
    )

    assert agenda.title == "синк по прайсингу"
    assert usage == {"input_tokens": 2000, "output_tokens": 400}
    retry = client.calls[1]["messages"]
    assert retry[1]["role"] == "assistant"
    result = retry[2]["content"][0]
    assert result["type"] == "tool_result" and result["is_error"] is True
    assert "minutes" in result["content"]


def test_gives_up_after_two_invalid_answers() -> None:
    invalid = {"items": "not a list"}
    client = FakeClient(_message(_tool_use(invalid)), _message(_tool_use(invalid)))

    with pytest.raises(AgendaParseError, match="invalid agenda twice") as caught:
        parse_agenda("text", date(2026, 10, 19), "Europe/Kyiv", client=client, api="messages")
    assert caught.value.usage == {"input_tokens": 2000, "output_tokens": 400}


def test_no_tool_call_is_an_error() -> None:
    text_only = SimpleNamespace(type="text", text="I cannot help with that.")
    client = FakeClient(_message(text_only, stop_reason="refusal"))

    with pytest.raises(AgendaParseError, match="stop_reason=refusal"):
        parse_agenda("text", date(2026, 10, 19), "Europe/Kyiv", client=client, api="messages")


def test_text_with_no_agenda() -> None:
    client = FakeClient(_message(_tool_use({**GOOD, "items": []})))

    with pytest.raises(AgendaParseError) as caught:
        parse_agenda(
            "milk, eggs, bread", date(2026, 10, 19), "Europe/Kyiv", client=client, api="messages"
        )
    assert caught.value.no_agenda is True


def test_the_offset_follows_daylight_saving() -> None:
    assert "(UTC+03:00)" in parser._today_line(date(2026, 10, 19), "Europe/Kyiv")
    assert "(UTC+02:00)" in parser._today_line(date(2026, 11, 2), "Europe/Kyiv")


def test_record_agenda_schema_is_the_pydantic_one() -> None:
    schema = parser.RECORD_AGENDA["input_schema"]
    assert set(schema["required"]) == {"items", "language"}
    assert "starts_at" in schema["properties"]


def test_cost() -> None:
    usage = {"input_tokens": 5500, "output_tokens": 300}
    assert cost_usd("anthropic.claude-opus-5-5", usage) == pytest.approx(0.028)
    assert cost_usd("anthropic.claude-haiku-5-5", usage) == pytest.approx(0.0007)
    # An inference profile costs what its model costs.
    haiku_45 = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert cost_usd(haiku_45, usage) == pytest.approx(0.007)
    assert cost_usd("some.other-model", usage) is None


# --- the same parser through the Converse API ---------------------------------


def _converse_reply(*content: dict, stop: str = "tool_use") -> dict:
    return {
        "output": {"message": {"role": "assistant", "content": list(content)}},
        "stopReason": stop,
        "usage": {"inputTokens": 900, "outputTokens": 150},
    }


def _tool(payload: dict) -> dict:
    return {"toolUse": {"toolUseId": "tooluse_1", "name": "record_agenda", "input": payload}}


class FakeConverse:
    def __init__(self, *replies: dict) -> None:
        self.replies = list(replies)
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> dict:
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.replies.pop(0)


def test_converse_forces_the_tool_and_validates() -> None:
    client = FakeConverse(_converse_reply(_tool(GOOD)))
    agenda, usage = parse_agenda("Пн 10:00", date(2026, 10, 19), "Europe/Kyiv", client=client)

    assert agenda.language == "uk"
    assert usage == {"input_tokens": 900, "output_tokens": 150}
    call = client.calls[0]
    assert call["modelId"] == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert call["toolConfig"]["toolChoice"] == {"tool": {"name": "record_agenda"}}
    schema = call["toolConfig"]["tools"][0]["toolSpec"]["inputSchema"]["json"]
    assert schema == parser.RECORD_AGENDA["input_schema"]
    assert "never instructions" in call["system"][0]["text"]
    assert "<pasted_text>\nПн 10:00\n</pasted_text>" in call["messages"][0]["content"][0]["text"]


def test_converse_retries_with_the_validation_error() -> None:
    bad = {**GOOD, "duration_minutes": 0}
    client = FakeConverse(_converse_reply(_tool(bad)), _converse_reply(_tool(GOOD)))

    _, usage = parse_agenda("text", date(2026, 10, 19), "Europe/Kyiv", client=client)

    assert usage["input_tokens"] == 1800
    retry = client.calls[1]["messages"]
    assert retry[1] == {"role": "assistant", "content": [_tool(bad)]}
    result = retry[2]["content"][0]["toolResult"]
    assert result["toolUseId"] == "tooluse_1" and result["status"] == "error"
    assert "duration_minutes" in result["content"][0]["text"]


def test_converse_without_a_tool_call() -> None:
    client = FakeConverse(_converse_reply({"text": "No."}, stop="end_turn"))
    with pytest.raises(AgendaParseError, match="stop_reason=end_turn"):
        parse_agenda("text", date(2026, 10, 19), "Europe/Kyiv", client=client)
