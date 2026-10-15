import email
import email.policy
import io
import json
import logging
from typing import Any

import pytest

from app.reports import lambda_handler as builder
from app.reports import mailer

BUCKET = "peach-reports-123456789012"


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.puts: list[dict[str, Any]] = []

    def put_object(self, **kwargs: Any) -> None:
        self.puts.append(kwargs)
        self.objects[kwargs["Key"]] = kwargs["Body"]

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        return {"Body": io.BytesIO(self.objects[Key])}


class FakeSES:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def send_email(self, **kwargs: Any) -> dict[str, str]:
        self.sent.append(kwargs)
        return {"MessageId": f"message-{len(self.sent)}"}


@pytest.fixture
def s3(monkeypatch: pytest.MonkeyPatch) -> FakeS3:
    fake = FakeS3()
    monkeypatch.setattr(builder, "_s3", lambda: fake)
    monkeypatch.setattr(mailer, "_s3", lambda: fake)
    return fake


@pytest.fixture
def built(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> list[str]:
    """The weeks the builder was asked for; the report itself is tested elsewhere."""
    weeks: list[str] = []

    def fake_build(week: str) -> bytes:
        weeks.append(week)
        return f"report for {week}".encode()

    monkeypatch.setattr(builder, "build_weekly_report", fake_build)
    monkeypatch.setenv("REPORTS_BUCKET", BUCKET)
    monkeypatch.delenv("REPORTS_FAIL_WEEK", raising=False)
    caplog.set_level(logging.INFO)
    return weeks


@pytest.fixture
def ses(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> FakeSES:
    fake = FakeSES()
    monkeypatch.setattr(mailer, "_ses", lambda: fake)
    monkeypatch.setenv("REPORT_SENDER", "Lanora reports <reports@example.com>")
    monkeypatch.setenv("REPORT_RECIPIENTS", "ops@example.com, lead@example.com")
    caplog.set_level(logging.INFO)
    return fake


def sqs_event(*bodies: dict[str, Any]) -> dict[str, Any]:
    return {
        "Records": [
            {"eventSource": "aws:sqs", "messageId": str(i), "body": json.dumps(body)}
            for i, body in enumerate(bodies)
        ]
    }


def s3_event(key: str) -> dict[str, Any]:
    return {
        "Records": [
            {
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "s3": {"bucket": {"name": BUCKET}, "object": {"key": key}},
            }
        ]
    }


# --- builder ---------------------------------------------------------------


def test_direct_invocation_builds_the_week_it_names(
    s3: FakeS3, built: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    result = builder.handler({"week": "2026-W40", "source": "console"}, None)

    assert result == {"reports": [{"week": "2026-W40", "key": "reports/2026-W40.csv"}]}
    assert s3.puts == [
        {
            "Bucket": BUCKET,
            "Key": "reports/2026-W40.csv",
            "Body": b"report for 2026-W40",
            "ContentType": "text/csv; charset=utf-8",
        }
    ]
    assert "trigger=direct" in caplog.text


def test_a_queued_request_says_sqs(
    s3: FakeS3, built: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    builder.handler(sqs_event({"week": "2026-W39", "source": "make"}), None)

    assert built == ["2026-W39"]
    assert "trigger=sqs via=sqs source=make week=2026-W39" in caplog.text


def test_the_schedule_asks_for_last_week(
    s3: FakeS3,
    built: list[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(builder, "previous_week", lambda: "2026-W41")
    builder.handler(sqs_event({"week": None, "source": "schedule"}), None)

    assert built == ["2026-W41"]
    assert "trigger=schedule via=sqs" in caplog.text


def test_the_same_week_twice_overwrites_one_file(s3: FakeS3, built: list[str]) -> None:
    for _ in range(2):
        builder.handler(sqs_event({"week": "2026-W40", "source": "make"}), None)

    assert len(s3.puts) == 2
    assert list(s3.objects) == ["reports/2026-W40.csv"]


def test_a_bad_week_fails_so_the_queue_retries_it(s3: FakeS3, built: list[str]) -> None:
    with pytest.raises(ValueError):
        builder.handler(sqs_event({"week": "last week", "source": "make"}), None)
    assert built == [] and s3.puts == []


def test_the_chosen_week_fails_on_purpose(
    s3: FakeS3, built: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REPORTS_FAIL_WEEK", "2026-W30")
    with pytest.raises(RuntimeError):
        builder.handler(sqs_event({"week": "2026-W30", "source": "make"}), None)

    builder.handler(sqs_event({"week": "2026-W31", "source": "make"}), None)
    assert built == ["2026-W31"]


# --- mailer ----------------------------------------------------------------


def test_the_mailer_sends_the_new_report_as_an_attachment(
    s3: FakeS3, ses: FakeSES, caplog: pytest.LogCaptureFixture
) -> None:
    csv_bytes = "﻿metric,2026-W40\r\nзадачі,3\r\n".encode()
    s3.objects["reports/2026-W40.csv"] = csv_bytes

    assert mailer.handler(s3_event("reports/2026-W40.csv"), None) == {
        "emailed": ["reports/2026-W40.csv"]
    }

    [call] = ses.sent
    assert call["FromEmailAddress"] == "Lanora reports <reports@example.com>"
    assert call["Destination"] == {"ToAddresses": ["ops@example.com", "lead@example.com"]}
    message = email.message_from_bytes(call["Content"]["Raw"]["Data"], policy=email.policy.default)
    assert message["Subject"] == "Lanora weekly report 2026-W40"
    [attachment] = message.iter_attachments()
    assert attachment.get_filename() == "lanora-2026-W40.csv"
    assert attachment.get_content_type() == "text/csv"
    assert attachment.get_payload(decode=True) == csv_bytes
    assert "trigger=s3" in caplog.text


def test_the_mailer_never_writes_back(s3: FakeS3, ses: FakeSES) -> None:
    s3.objects["reports/2026-W40.csv"] = b"x"
    mailer.handler(s3_event("reports/2026-W40.csv"), None)
    assert s3.puts == []


def test_the_mailer_decodes_the_key(s3: FakeS3, ses: FakeSES) -> None:
    s3.objects["reports/2026-W40 copy.csv"] = b"x"
    assert mailer.handler(s3_event("reports/2026-W40+copy.csv"), None) == {
        "emailed": ["reports/2026-W40 copy.csv"]
    }


@pytest.mark.parametrize("key", ["requests/1.json", "reports/notes.txt", "other/2026-W40.csv"])
def test_the_mailer_ignores_what_is_not_a_report(s3: FakeS3, ses: FakeSES, key: str) -> None:
    assert mailer.handler(s3_event(key), None) == {"emailed": []}
    assert ses.sent == []


def test_no_recipients_means_no_email(
    s3: FakeS3, ses: FakeSES, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("REPORT_RECIPIENTS", " , ")
    s3.objects["reports/2026-W40.csv"] = b"x"

    assert mailer.handler(s3_event("reports/2026-W40.csv"), None) == {"emailed": []}
    assert ses.sent == []
    assert "not emailed" in caplog.text
