"""Lab 8: email when more than 10% of the payments in a batch failed."""

import base64
import json
import os

import boto3

ALERT_SHARE = 0.10

sns = boto3.client("sns")


def handler(event, context):
    """One batch from one shard: up to a minute of events, by the time they arrived."""
    seen = set()
    failed = total = 0
    for record in event["Records"]:
        payment = json.loads(base64.b64decode(record["kinesis"]["data"]))
        identity = (payment["invoiceId"], payment["status"])
        if identity in seen or payment["status"] not in ("success", "failure"):
            continue
        seen.add(identity)
        total += 1
        failed += payment["status"] == "failure"

    share = failed / total if total else 0
    print(json.dumps({"records": len(event["Records"]), "total": total, "failed": failed, "share": round(share, 4)}))
    if share > ALERT_SHARE:
        sns.publish(
            TopicArn=os.environ["TOPIC_ARN"],
            Subject="Lab 8: failed payments above 10%",
            Message=f"{failed} of {total} payments failed in the last batch ({share:.1%}).",
        )
