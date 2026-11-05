#!/usr/bin/env python3
"""Share of failed payments per payment method, in one-minute windows of event time.

    python consumer.py --group baseline
    python consumer.py --group grace-zero --grace 0
"""

import argparse
import json
import signal
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

from confluent_kafka import Consumer

WINDOW_SECONDS = 60
ALERT_SHARE = 0.10


class Windows:
    def __init__(self, grace_seconds):
        self.grace = grace_seconds
        self.seen = set()  # grows without limit; a real service keeps it in Redis with a TTL
        self.counts = defaultdict(lambda: defaultdict(lambda: [0, 0]))  # start -> method -> [failed, total]
        self.newest = {}  # partition -> the newest event time read from it
        self.watermark = 0
        self.stats = Counter()

    def assign(self, partitions):
        self.newest = {p: self.newest.get(p, 0) for p in partitions}

    def add(self, event, partition):
        """Take one event; return the windows it closed."""
        self.stats["read"] += 1
        identity = (event["invoiceId"], event["status"])
        if identity in self.seen:
            self.stats["duplicates"] += 1
            return []
        self.seen.add(identity)

        happened = int(datetime.fromisoformat(event["modifiedDate"]).timestamp())

        # The slowest partition sets the watermark. A consumer catching up reads a whole batch from
        # one partition first; with one global maximum, the other partitions would all look late.
        self.newest[partition] = max(self.newest.get(partition, 0), happened)
        self.watermark = max(self.watermark, min(self.newest.values()))

        start = happened - happened % WINDOW_SECONDS
        if self._is_closed(start):
            self.stats["late"] += 1
        elif event["status"] in ("success", "failure"):
            counts = self.counts[start][event["paymentMethod"]]
            counts[0] += event["status"] == "failure"
            counts[1] += 1

        return [w for s in sorted(self.counts) if self._is_closed(s) for w in self._pop(s)]

    def flush(self):
        """The stream has ended: close everything."""
        return [w for s in sorted(self.counts) for w in self._pop(s)]

    def _is_closed(self, start):
        return start + WINDOW_SECONDS + self.grace <= self.watermark

    def _pop(self, start):
        return [(start, method, *counts) for method, counts in sorted(self.counts.pop(start).items())]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", required=True, help="consumers in one group share the partitions")
    parser.add_argument("--grace", type=int, default=120, help="seconds a window waits for late events")
    parser.add_argument("--idle-exit", type=float, help="end the stream after this many silent seconds")
    args = parser.parse_args()

    windows = Windows(args.grace)
    consumer = Consumer(
        {
            "bootstrap.servers": "127.0.0.1:19092",
            "group.id": args.group,
            "auto.offset.reset": "earliest",  # a new group starts at the beginning of the log
        }
    )

    def on_assign(_, partitions):
        windows.assign([p.partition for p in partitions])
        print(f"{time.strftime('%H:%M:%S')} assigned partitions {[p.partition for p in partitions]}", flush=True)

    consumer.subscribe(["payments"], on_assign=on_assign)

    # A signal only sets this flag, so a message already taken from the log still gets processed.
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    alerts = closed = 0

    def report(batch):
        nonlocal alerts, closed
        for start, method, failed, total in batch:
            label = datetime.fromtimestamp(start, timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
            line = f"{label} {method} failed={failed} total={total} share={failed / total:.1%}"
            print("window", line, flush=True)
            closed += 1
            if failed / total > ALERT_SHARE:
                print("ALERT", line, flush=True)
                alerts += 1

    first_offset, last_offset = {}, {}
    last_message = time.monotonic()
    while not stopping:
        message = consumer.poll(0.5)
        if message is None:
            if args.idle_exit and windows.stats["read"] and time.monotonic() - last_message > args.idle_exit:
                report(windows.flush())
                break
            continue
        if message.error():
            print("error:", message.error(), flush=True)
            continue
        last_message = time.monotonic()
        first_offset.setdefault(message.partition(), message.offset())
        last_offset[message.partition()] = message.offset()
        report(windows.add(json.loads(message.value()), message.partition()))

    # When stopped, what is still in open windows dies with this process.
    consumer.close()  # saves the group's place in the log
    summary = {**windows.stats, "windows": closed, "alerts": alerts, "seen": len(windows.seen)}
    summary |= {"first_offset": first_offset, "last_offset": last_offset}
    print("summary", json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
