#!/usr/bin/env python3
"""What each experiment changed: its logs against the day read straight from the file."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from consumer import Windows

HERE = Path(__file__).parent
LINE = re.compile(r"^window (\S+) (\S+) failed=(\d+) total=(\d+)")


def label(start):
    return datetime.fromtimestamp(start, timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def truth():
    """Every final status in its own window, with no time limit: nothing is ever late."""
    windows = Windows(10**9)
    windows.assign([0])
    with (HERE / "events-2026-10-15.jsonl").open(encoding="utf-8") as file:
        for line in file:
            windows.add(json.loads(line), 0)
    return {(label(s), m): (f, t) for s, m, f, t in windows.flush()}


def read(*names):
    """Windows and summaries of some logs; a window reported twice is added up."""
    counts, summaries = {}, []
    for name in names:
        for line in (HERE / "output" / f"{name}.log").read_text().splitlines():
            if match := LINE.match(line):
                failed, total = counts.get((match[1], match[2]), (0, 0))
                counts[match[1], match[2]] = (failed + int(match[3]), total + int(match[4]))
            elif line.startswith("summary "):
                summaries.append(json.loads(line[len("summary ") :]))
    return counts, summaries


def alerts(counts, minimum=1):
    return sum(1 for failed, total in counts.values() if total >= minimum and failed / total > 0.10)


def show(title, counts, summaries, true=None):
    payments = sum(t for _, t in counts.values())
    print(f"\n{title}")
    print(f"  read {sum(s['read'] for s in summaries)}, duplicates {sum(s.get('duplicates', 0) for s in summaries)}, late {sum(s.get('late', 0) for s in summaries)}")
    print(f"  payments in windows {payments}, failed {sum(f for f, _ in counts.values()) / payments:.2%}")
    print(f"  alerts {alerts(counts)}, of them in windows of 10+ payments {alerts(counts, 10)}")
    if true:
        print(f"  windows differing from the truth: {sum(counts.get(k, (0, 0)) != v for k, v in true.items())} of {len(true)}")
    for s in summaries:
        print(f"  offsets first {s['first_offset']} last {s['last_offset']}")


def main():
    true = truth()
    print("the truth, from the file")
    print(f"  payments {sum(t for _, t in true.values())}, failed {sum(f for f, _ in true.values()) / sum(t for _, t in true.values()):.2%}, windows {len(true)}")

    baseline = read("baseline")
    show("baseline: grace 2 minutes", *baseline, true)
    show("experiment 1: stopped for a minute", *read("exp1-restart-part1", "exp1-restart-part2"), true)
    show("experiment 2: consumer a, partitions 0 and 1 after the rebalance", *read("exp2-consumer-a"))
    show("experiment 2: consumer b, partition 2", *read("exp2-consumer-b"))
    show("experiment 2: both added up", *read("exp2-consumer-a", "exp2-consumer-b"), true)
    show("experiment 3: 17:00-19:00, 30% made to fail", *read("exp3-failures"))
    peak = {k: v for k, v in baseline[0].items() if k[0].startswith(("2026-10-15T17", "2026-10-15T18"))}
    print(f"  the same hours in the baseline: failed {sum(f for f, _ in peak.values()) / sum(t for _, t in peak.values()):.2%}, alerts {alerts(peak)}, of them in windows of 10+ payments {alerts(peak, 10)}")
    show("experiment 4: grace zero", *read("exp4-grace-zero"), true)


if __name__ == "__main__":
    main()
