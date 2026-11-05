#!/usr/bin/env python3
"""Read the topic and print the failure share per payment method for every closed window.

    python consumer.py --group baseline
    python consumer.py --group grace-zero --grace 0
"""

import argparse
import json
import signal
import sys
import time

from confluent_kafka import Consumer, KafkaError

from windows import ClosedWindow, FailureWindows

ALERT_SHARE = 0.10


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", required=True, help="consumers in one group share the partitions")
    parser.add_argument("--topic", default="payments")
    parser.add_argument("--brokers", default="127.0.0.1:19092")
    parser.add_argument("--grace", type=int, default=120, help="seconds to wait for late events after a window ends")
    parser.add_argument("--min-payments", type=int, default=10, help="no alert on fewer payments than this in a window")
    parser.add_argument("--idle-exit", type=float, default=0, help="end the stream after this many silent seconds")
    args = parser.parse_args()

    windows = FailureWindows(grace_seconds=args.grace)
    consumer = Consumer(
        {
            "bootstrap.servers": args.brokers,
            "group.id": args.group,
            "auto.offset.reset": "earliest",  # a new group starts at the beginning of the log
            "enable.auto.commit": True,  # the group's place in the log, saved every 5 s and on close
        }
    )

    def on_assign(_consumer, partitions):
        numbers = [p.partition for p in partitions]
        windows.assign(numbers)
        log(f"assigned partitions {numbers}")

    def on_revoke(_consumer, partitions):
        numbers = [p.partition for p in partitions]
        windows.revoke(numbers)
        log(f"revoked partitions {numbers}")

    consumer.subscribe([args.topic], on_assign=on_assign, on_revoke=on_revoke)

    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    first_offset: dict[int, int] = {}
    last_offset: dict[int, int] = {}
    per_partition: dict[int, int] = {}
    closed = alerts = 0
    last_message = time.monotonic()
    ended = False

    def report(batch: list[ClosedWindow]) -> None:
        nonlocal closed, alerts
        for window in batch:
            closed += 1
            print(f"window {window.label} {window.method} failed={window.failed} total={window.total} share={window.share:.1%}")
            if window.share > ALERT_SHARE and window.total >= args.min_payments:
                alerts += 1
                print(f"ALERT  {window.label} {window.method} failed={window.failed} total={window.total} share={window.share:.1%}")
        sys.stdout.flush()

    while not stopping:
        message = consumer.poll(0.5)
        if message is None:
            if args.idle_exit and windows.events and time.monotonic() - last_message > args.idle_exit:
                ended = True
                break
            continue
        if message.error():
            if message.error().code() != KafkaError._PARTITION_EOF:
                log(f"error: {message.error()}")
            continue

        last_message = time.monotonic()
        partition = message.partition()
        first_offset.setdefault(partition, message.offset())
        last_offset[partition] = message.offset()
        per_partition[partition] = per_partition.get(partition, 0) + 1
        report(windows.add(json.loads(message.value()), partition))

    lost_in_open_windows = 0
    if ended:
        report(windows.flush())  # the stream is over: nothing more can arrive for these windows
    else:
        lost_in_open_windows = windows.open_payments()  # state lives only in this process

    consumer.close()  # commits the offsets and leaves the group at once

    summary = {
        "group": args.group,
        "grace_seconds": args.grace,
        "how_it_ended": "stream ended" if ended else "stopped",
        "messages_read": windows.events,
        "duplicates_dropped": windows.duplicates,
        "late_rejected": windows.late,
        "late_rejected_final_statuses": windows.late_final,
        "windows_closed": closed,
        "alerts": alerts,
        "payments_lost_in_open_windows": lost_in_open_windows,
        "seen_set_size": len(windows.seen),
        "messages_per_partition": dict(sorted(per_partition.items())),
        "first_offset": dict(sorted(first_offset.items())),
        "last_offset": dict(sorted(last_offset.items())),
    }
    print("summary " + json.dumps(summary), flush=True)


def log(text: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {text}", flush=True)


if __name__ == "__main__":
    main()
