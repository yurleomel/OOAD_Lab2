"""AWS Lambda entry point of the report mailer (infra/reports.tf).

S3 invokes it for every ``reports/*.csv`` that is created. It downloads the
file and emails it as an attachment through SES. The builder does not know it
exists: they are joined by the event, so a second listener (Slack, say) would be
one more notification on the bucket and no change to the builder.

It runs outside the VPC, because SES is on the internet and the VPC has no NAT,
and it never touches the database. Only the standard library and boto3 here -
importing the app's database code would be pointless outside the VPC.

It reads ``reports/`` and never writes to it: a function triggered by uploads
to a prefix that uploads to the same prefix would call itself forever.
"""

import logging
import os
from email.message import EmailMessage
from functools import cache
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote_plus

PREFIX = "reports/"

logger = logging.getLogger("report-mailer")
logger.setLevel(logging.INFO)


@cache
def _s3() -> Any:
    import boto3

    return boto3.client("s3")


@cache
def _ses() -> Any:
    import boto3

    return boto3.client("sesv2")


def recipients() -> list[str]:
    """From the environment, never from the code: REPORT_RECIPIENTS, comma-separated."""
    return [a.strip() for a in os.environ.get("REPORT_RECIPIENTS", "").split(",") if a.strip()]


def build_message(*, sender: str, to: list[str], key: str, body: bytes) -> EmailMessage:
    week = PurePosixPath(key).stem
    message = EmailMessage()
    message["Subject"] = f"Lanora weekly report {week}"
    message["From"] = sender
    message["To"] = ", ".join(to)
    message.set_content(
        f"The Lanora weekly report for {week} is attached.\n\n"
        f"It was built from the database, saved as {key}, and this email went out\n"
        "because the file appeared there.\n"
    )
    message.add_attachment(body, maintype="text", subtype="csv", filename=f"lanora-{week}.csv")
    return message


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    sender = os.environ.get("REPORT_SENDER", "")
    sent = []
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        # S3 URL-encodes keys in events, with + for spaces.
        key = unquote_plus(record["s3"]["object"]["key"])
        logger.info(
            "report-mailer triggered: trigger=s3 event=%s object=s3://%s/%s",
            record.get("eventName", "-"),
            bucket,
            key,
            extra={"trigger": "s3", "key": key},
        )
        if not (key.startswith(PREFIX) and key.endswith(".csv")):
            logger.warning("not a report, skipped: %s", key)
            continue
        to = recipients()
        if not (sender and to):
            logger.warning("REPORT_SENDER or REPORT_RECIPIENTS is empty - %s not emailed", key)
            continue

        body = _s3().get_object(Bucket=bucket, Key=key)["Body"].read()
        message = build_message(sender=sender, to=to, key=key, body=body)
        response = _ses().send_email(
            FromEmailAddress=sender,
            Destination={"ToAddresses": to},
            Content={"Raw": {"Data": message.as_bytes()}},
        )
        logger.info(
            "report emailed: %s to %d recipient(s), message %s",
            key,
            len(to),
            response.get("MessageId", "-"),
        )
        sent.append(key)
    return {"emailed": sent}
