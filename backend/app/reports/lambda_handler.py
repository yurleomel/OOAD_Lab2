"""AWS Lambda entry point of the report builder (infra/reports.yaml).

The API's image, started with this handler instead. It runs in the API's VPC
and security group, reaches the database directly and S3 through the gateway
endpoint, and nothing else - there is no NAT.

Two event shapes arrive here, both carrying the same payload,
``{"week": "2026-W40" | null, "source": "schedule" | "make" | ...}``:

- a direct invocation, where the event is the payload (by hand, or a schedule
  that targets the function itself);
- an SQS event from report-requests, with the payload as each record's body.
  The schedule and ``make report-now`` both send these.

A null week means the last complete one. Anything that raises sends the
message back to the queue; after three attempts it waits in the dead-letter
queue instead of disappearing.
"""

import json
import logging
from functools import cache
from typing import Any

from app.config import get_settings
from app.reports.weekly import build_weekly_report, previous_week, report_key

logger = logging.getLogger("report-builder")
# The Lambda runtime puts its handler on the root logger, which passes only
# warnings; this logger's own level is what lets the trigger lines through.
logger.setLevel(logging.INFO)


@cache
def _s3() -> Any:
    import boto3  # part of the Lambda runtime, not a dependency of the API

    return boto3.client("s3")


def requests_in(event: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """(transport, payload) for every report the event asks for."""
    records = event.get("Records")
    if records:
        return [
            ("sqs", json.loads(record["body"] or "{}"))
            for record in records
            if record.get("eventSource") == "aws:sqs"
        ]
    return [("direct", event)]


def detect_trigger(transport: str, payload: dict[str, Any]) -> str:
    """What started this run: the schedule, an SQS message, or a direct call.

    The schedule speaks through the queue too, so its messages are told apart
    by the source they carry.
    """
    return "schedule" if payload.get("source") == "schedule" else transport


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    settings = get_settings()
    bucket = settings.reports_bucket
    built = []
    for transport, payload in requests_in(event):
        week = payload.get("week") or previous_week()
        trigger = detect_trigger(transport, payload)
        logger.info(
            "report-builder triggered: trigger=%s via=%s source=%s week=%s",
            trigger,
            transport,
            payload.get("source", "-"),
            week,
            extra={"trigger": trigger, "week": week},
        )
        key = report_key(week)
        # For the dead-letter exercise (PROJECT.md section 12): one chosen week fails.
        if week == settings.reports_fail_week:
            raise RuntimeError(f"REPORTS_FAIL_WEEK is {week}: failing this report on purpose")

        body = build_weekly_report(week)
        _s3().put_object(Bucket=bucket, Key=key, Body=body, ContentType="text/csv; charset=utf-8")
        logger.info("report saved: s3://%s/%s (%d bytes)", bucket, key, len(body))
        built.append({"week": week, "key": key})
    return {"reports": built}
