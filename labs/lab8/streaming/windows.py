"""The share of failed payments per payment method, in one-minute windows of event time.

There is no Kafka in this file, so the logic can be tested without a broker.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

WINDOW_SECONDS = 60
FINAL_STATUSES = {"success", "failure"}


@dataclass(frozen=True)
class ClosedWindow:
    start: int  # Unix seconds
    method: str
    failed: int
    total: int

    @property
    def share(self) -> float:
        return self.failed / self.total

    @property
    def label(self) -> str:
        return datetime.fromtimestamp(self.start, tz=timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def event_time(event: dict) -> int:
    """When the status happened, not when we heard about it."""
    return int(datetime.fromisoformat(event["modifiedDate"]).timestamp())


class FailureWindows:
    """Drops duplicates, counts each payment's final status into the window of its event time,
    and closes a window once the watermark has passed its end by the grace period.
    """

    def __init__(self, grace_seconds: int = 120):
        self.grace = grace_seconds
        self.seen: set[tuple[str, str]] = set()  # grows without limit; see the notes on TTL state
        self.open: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
        self.newest_by_partition: dict[int, int] = {}
        self.watermark = 0
        self.events = 0
        self.duplicates = 0
        self.late = 0
        self.late_final = 0

    def assign(self, partitions: list[int]) -> None:
        """A partition we have not read yet holds the watermark back: its value is 0 until then."""
        for partition in partitions:
            self.newest_by_partition.setdefault(partition, 0)

    def revoke(self, partitions: list[int]) -> None:
        for partition in partitions:
            self.newest_by_partition.pop(partition, None)

    def add(self, event: dict, partition: int) -> list[ClosedWindow]:
        """Take one event; return the windows it closed."""
        self.events += 1

        identity = (event["invoiceId"], event["status"])
        if identity in self.seen:
            self.duplicates += 1
            return []
        self.seen.add(identity)

        seconds = event_time(event)
        self._advance_watermark(partition, seconds)

        start = seconds - seconds % WINDOW_SECONDS
        is_final = event["status"] in FINAL_STATUSES
        if self._is_closed(start):
            self.late += 1
            self.late_final += is_final
        elif is_final:
            counts = self.open[start][event["paymentMethod"]]
            counts[0] += event["status"] == "failure"
            counts[1] += 1

        return self._close_ready()

    def flush(self) -> list[ClosedWindow]:
        """Close everything: the stream has ended."""
        closed = [w for start in sorted(self.open) for w in self._emit(start)]
        self.open.clear()
        return closed

    def open_payments(self) -> int:
        return sum(c[1] for methods in self.open.values() for c in methods.values())

    def _advance_watermark(self, partition: int, seconds: int) -> None:
        # One watermark per partition, and the slowest one wins. With a single global maximum, a
        # consumer catching up gets a whole batch from one partition first, and that batch would
        # make every event still waiting in the other partitions look late.
        newest = self.newest_by_partition.get(partition, 0)
        self.newest_by_partition[partition] = max(newest, seconds)
        self.watermark = max(self.watermark, min(self.newest_by_partition.values()))

    def _is_closed(self, start: int) -> bool:
        return start + WINDOW_SECONDS + self.grace <= self.watermark

    def _close_ready(self) -> list[ClosedWindow]:
        closed: list[ClosedWindow] = []
        for start in sorted(self.open):
            if not self._is_closed(start):
                break
            closed.extend(self._emit(start))
            del self.open[start]
        return closed

    def _emit(self, start: int) -> list[ClosedWindow]:
        return [
            ClosedWindow(start, method, failed, total)
            for method, (failed, total) in sorted(self.open[start].items())
        ]
