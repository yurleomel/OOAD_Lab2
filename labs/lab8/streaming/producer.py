#!/usr/bin/env python3
"""Replay one day of payments into the topic, in the order in which they reached us.

    python producer.py events-2026-10-15.jsonl
    python producer.py events-2026-10-15.jsonl --between 17:00 19:00 --fail-rate 0.3
"""

import argparse
import hashlib
import json
import time

from confluent_kafka import Producer

EVENTS_PER_PAYMENT = 3  # created, processing, then success or failure


def read_events(path: str, between: list[str] | None) -> list[dict]:
    with open(path, encoding="utf-8") as file:
        events = [json.loads(line) for line in file]
    # The file is grouped by payment. Sorting by processing time is what makes a late event late:
    # it comes after events that happened later than it did.
    events.sort(key=lambda event: event["receivedAt"])
    if between:
        start, end = between
        events = [e for e in events if start <= e["receivedAt"][11:16] < end]
    return events


def is_chosen_to_fail(invoice_id: str, rate: float) -> bool:
    """Decided by the id, so a payment's duplicate events fail together, in every run."""
    digest = hashlib.sha256(invoice_id.encode()).digest()
    return int.from_bytes(digest[:4]) / 2**32 < rate


def inject_failure(event: dict) -> None:
    event.update(status="failure", finalAmount=0, failureReason="Injected by the experiment")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file")
    parser.add_argument("--payments-per-second", type=float, default=20)
    parser.add_argument("--between", nargs=2, metavar=("HH:MM", "HH:MM"), help="replay only this part of the day")
    parser.add_argument("--fail-rate", type=float, default=0, help="make this share of payments fail")
    args = parser.parse_args()

    events = read_events(args.file, args.between)
    producer = Producer({"bootstrap.servers": "127.0.0.1:19092"})

    gap = 1 / (args.payments_per_second * EVENTS_PER_PAYMENT)
    started = time.monotonic()
    print(f"replaying {len(events)} events at {1 / gap:.0f} events/s, about {len(events) * gap / 60:.1f} min", flush=True)

    for sent, event in enumerate(events):
        if event["status"] == "success" and is_chosen_to_fail(event["invoiceId"], args.fail_rate):
            inject_failure(event)

        # The key picks the partition, so all the events of one payment stay in order, together.
        producer.produce("payments", key=event["invoiceId"], value=json.dumps(event, ensure_ascii=False))
        producer.poll(0)  # delivers callbacks and frees the send queue

        # Pace by the clock, not by sleeping a fixed gap: the error does not accumulate.
        ahead = started + sent * gap - time.monotonic()
        if ahead > 0:
            time.sleep(ahead)
        if sent and sent % 10_000 == 0:
            print(f"sent {sent} of {len(events)}, event time received {event['receivedAt']}", flush=True)

    producer.flush()
    print(f"done: {len(events)} events in {time.monotonic() - started:.0f} s", flush=True)


if __name__ == "__main__":
    main()
