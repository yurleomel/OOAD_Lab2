#!/usr/bin/env python3
"""Replay part of a day of payments into Kinesis, in the order in which they reached us.

    python producer.py ../streaming/events-2026-10-15.jsonl --between 17:00 17:10
    python producer.py ../streaming/events-2026-10-15.jsonl --between 18:00 18:10 --fail-rate 0.3
"""

import argparse
import hashlib
import json
import time

import boto3

EVENTS_PER_PAYMENT = 3  # created, processing, then success or failure
MAX_RECORDS_PER_CALL = 500  # the limit of PutRecords


def read_events(path: str, between: list[str]) -> list[dict]:
    with open(path, encoding="utf-8") as file:
        events = [json.loads(line) for line in file]
    events.sort(key=lambda event: event["receivedAt"])
    start, end = between
    return [e for e in events if start <= e["receivedAt"][11:16] < end]


def is_chosen_to_fail(invoice_id: str, rate: float) -> bool:
    """Decided by the id, so a payment's duplicate events fail together."""
    digest = hashlib.sha256(invoice_id.encode()).digest()
    return int.from_bytes(digest[:4]) / 2**32 < rate


def put_with_retries(kinesis, stream: str, records: list[dict]) -> None:
    """PutRecords can succeed as a call and still reject some records: send those again."""
    while records:
        response = kinesis.put_records(StreamName=stream, Records=records)
        if response["FailedRecordCount"] == 0:
            return
        records = [
            record
            for record, result in zip(records, response["Records"], strict=True)
            if "ErrorCode" in result
        ]
        print(f"retrying {len(records)} rejected records", flush=True)
        time.sleep(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file")
    parser.add_argument("--stream", default="peach-lab8-payments")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--payments-per-second", type=float, default=20)
    parser.add_argument("--between", nargs=2, required=True, metavar=("HH:MM", "HH:MM"))
    parser.add_argument("--fail-rate", type=float, default=0, help="make this share of payments fail")
    args = parser.parse_args()

    events = read_events(args.file, args.between)
    kinesis = boto3.client("kinesis", region_name=args.region)
    per_second = int(args.payments_per_second * EVENTS_PER_PAYMENT)
    print(f"sending {len(events)} events at {per_second} events/s", flush=True)

    started = time.monotonic()
    for batch_number, first in enumerate(range(0, len(events), per_second)):
        records = []
        for event in events[first : first + per_second]:
            if event["status"] == "success" and is_chosen_to_fail(event["invoiceId"], args.fail_rate):
                event.update(status="failure", finalAmount=0, failureReason="Injected by the experiment")
            records.append(
                {
                    # Firehose joins records as they are, and Athena reads one JSON object per line.
                    "Data": (json.dumps(event, ensure_ascii=False) + "\n").encode(),
                    # All the events of one payment land in one shard, in order.
                    "PartitionKey": event["invoiceId"],
                }
            )
        for start in range(0, len(records), MAX_RECORDS_PER_CALL):
            put_with_retries(kinesis, args.stream, records[start : start + MAX_RECORDS_PER_CALL])

        ahead = started + batch_number + 1 - time.monotonic()
        if ahead > 0:
            time.sleep(ahead)

    print(f"done: {len(events)} events in {time.monotonic() - started:.0f} s", flush=True)


if __name__ == "__main__":
    main()
