#!/usr/bin/env python3
"""Compare every experiment's windows with the truth computed from the file itself."""

import json
import re
from pathlib import Path

from windows import FailureWindows

OUT = Path(__file__).parent / "output"
DAY = Path(__file__).parent / "events-2026-10-15.jsonl"
LINE = re.compile(r"^window (\S+) (\S+) failed=(\d+) total=(\d+)")
ALERT_SHARE = 0.10
PEAK = ("2026-10-15T17:", "2026-10-15T18:")

Counts = dict[tuple[str, str], tuple[int, int]]


def truth() -> Counts:
    """Every final status of the day in its own window, with no time limit: nothing is ever late."""
    windows = FailureWindows(grace_seconds=10**9)
    windows.assign([0])
    with DAY.open(encoding="utf-8") as file:
        for line in file:
            windows.add(json.loads(line), 0)
    return {(w.label, w.method): (w.failed, w.total) for w in windows.flush()}


def read(*names: str) -> tuple[Counts, list[dict]]:
    """Windows and summaries of one group; a window reported by two runs is added up."""
    counts: Counts = {}
    summaries = []
    for name in names:
        for line in (OUT / f"{name}.log").read_text().splitlines():
            if match := LINE.match(line):
                key = (match[1], match[2])
                failed, total = counts.get(key, (0, 0))
                counts[key] = (failed + int(match[3]), total + int(match[4]))
            elif line.startswith("summary "):
                summaries.append(json.loads(line[len("summary ") :]))
    return counts, summaries


def alerts(counts: Counts, minimum: int) -> int:
    return sum(1 for failed, total in counts.values() if total >= minimum and failed / total > ALERT_SHARE)


def print_run(title: str, counts: Counts, summaries: list[dict], true: Counts) -> None:
    final = sum(total for _, total in counts.values())
    true_final = sum(total for _, total in true.values())
    wrong = sum(1 for key, value in true.items() if counts.get(key, (0, 0)) != value)
    print(f"\n{title}")
    print(f"  messages read            {sum(s['messages_read'] for s in summaries)}")
    print(f"  duplicates dropped       {sum(s['duplicates_dropped'] for s in summaries)}")
    print(f"  late rejected, all       {sum(s['late_rejected'] for s in summaries)}")
    print(f"  late rejected, final     {sum(s['late_rejected_final_statuses'] for s in summaries)}")
    print(f"  lost in open windows     {sum(s['payments_lost_in_open_windows'] for s in summaries)}")
    print(f"  payments in windows      {final} of {true_final} ({final / true_final:.2%})")
    print(f"  failed share overall     {sum(f for f, _ in counts.values()) / final:.2%}")
    print(f"  windows differing        {wrong} of {len(true)}")
    print(f"  alerts, 10+ payments     {alerts(counts, 10)}")
    print(f"  alerts, any size         {alerts(counts, 1)}")
    for summary in summaries:
        print(
            f"  {summary['how_it_ended']:12} first offsets {summary['first_offset']} "
            f"last offsets {summary['last_offset']} per partition {summary['messages_per_partition']}"
        )


def peak_only(counts: Counts) -> Counts:
    return {key: value for key, value in counts.items() if key[0].startswith(PEAK)}


def main() -> None:
    true = truth()
    print("the truth, from the file")
    print(f"  windows x methods        {len(true)}")
    print(f"  payments finished        {sum(total for _, total in true.values())}")
    print(f"  failed share             {sum(f for f, _ in true.values()) / sum(t for _, t in true.values()):.2%}")
    print(f"  alerts, 10+ payments     {alerts(true, 10)}")
    print(f"  alerts, any size         {alerts(true, 1)}")

    baseline, baseline_summary = read("baseline")
    print_run("baseline: grace 2 minutes", baseline, baseline_summary, true)
    print_run("experiment 1: stopped for a minute", *read("exp1-restart-part1", "exp1-restart-part2"), true)
    print_run("experiment 2: both consumers added up", *read("exp2-consumer-a", "exp2-consumer-b"), true)
    for name in ("exp2-consumer-a", "exp2-consumer-b"):
        print_run(f"experiment 2: {name} alone", *read(name), true)
    print_run("experiment 4: grace zero", *read("exp4-grace-zero"), true)

    failing, failing_summary = read("exp3-failures")
    print("\nexperiment 3: 17:00-19:00, 30% of the payments made to fail")
    print(f"  messages read            {sum(s['messages_read'] for s in failing_summary)}")
    print(f"  failed share overall     {sum(f for f, _ in failing.values()) / sum(t for _, t in failing.values()):.2%}")
    print(f"  windows x methods        {len(failing)}")
    print(f"  alerts, 10+ payments     {alerts(failing, 10)}")
    print(f"  alerts, any size         {alerts(failing, 1)}")
    peak = peak_only(baseline)
    print("  the same hours in the baseline:")
    print(f"  failed share overall     {sum(f for f, _ in peak.values()) / sum(t for _, t in peak.values()):.2%}")
    print(f"  windows x methods        {len(peak)}")
    print(f"  alerts, 10+ payments     {alerts(peak, 10)}")
    print(f"  alerts, any size         {alerts(peak, 1)}")


if __name__ == "__main__":
    main()
