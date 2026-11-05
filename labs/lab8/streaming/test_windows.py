"""The window logic, without a broker: run with `pytest` in this directory."""

from windows import FailureWindows


def event(invoice, status, at, method="card"):
    return {"invoiceId": invoice, "status": status, "modifiedDate": f"2026-10-15T{at}Z", "paymentMethod": method}


def windows_on_one_partition(grace=0):
    windows = FailureWindows(grace_seconds=grace)
    windows.assign([0])
    return windows


def test_duplicate_is_counted_once():
    w = windows_on_one_partition()
    w.add(event("a", "failure", "08:00:10"), 0)
    w.add(event("a", "failure", "08:00:10"), 0)
    assert w.duplicates == 1
    [closed] = w.flush()
    assert (closed.failed, closed.total) == (1, 1)


def test_only_final_statuses_count_towards_the_share():
    w = windows_on_one_partition()
    w.add(event("a", "created", "08:00:01"), 0)
    w.add(event("a", "processing", "08:00:02"), 0)
    w.add(event("a", "success", "08:00:03"), 0)
    w.add(event("b", "failure", "08:00:04"), 0)
    [closed] = w.flush()
    assert (closed.failed, closed.total, closed.share) == (1, 2, 0.5)


def test_the_window_comes_from_event_time_not_arrival_order():
    w = windows_on_one_partition(grace=120)
    w.add(event("a", "success", "08:01:30"), 0)
    w.add(event("b", "failure", "08:00:30"), 0)  # arrives second, happened in the earlier minute
    first, second = w.flush()
    assert (first.label, first.failed) == ("2026-10-15T08:00Z", 1)
    assert (second.label, second.failed) == ("2026-10-15T08:01Z", 0)


def test_a_window_closes_only_after_its_end_plus_the_grace_period():
    w = windows_on_one_partition(grace=120)
    w.add(event("a", "success", "08:00:10"), 0)
    assert w.add(event("b", "created", "08:02:59"), 0) == []  # end 08:01 + grace 2 min = 08:03
    [closed] = w.add(event("c", "created", "08:03:00"), 0)
    assert closed.total == 1


def test_an_event_for_a_closed_window_is_rejected_and_counted():
    w = windows_on_one_partition(grace=120)
    w.add(event("a", "success", "08:00:10"), 0)
    w.add(event("b", "created", "08:03:00"), 0)  # closes 08:00
    assert w.add(event("c", "failure", "08:00:20"), 0) == []
    assert (w.late, w.late_final) == (1, 1)
    assert w.flush() == []


def test_inside_the_grace_period_a_late_event_is_still_counted():
    w = windows_on_one_partition(grace=120)
    w.add(event("a", "success", "08:00:10"), 0)
    w.add(event("b", "created", "08:02:00"), 0)
    w.add(event("c", "failure", "08:00:20"), 0)
    assert w.late == 0
    [closed] = w.flush()
    assert (closed.failed, closed.total) == (1, 2)


def test_the_slowest_partition_holds_the_watermark_back():
    # A consumer catching up reads one partition far ahead of the others: not a reason to call
    # the events still waiting in the others late.
    w = FailureWindows(grace_seconds=120)
    w.assign([0, 1])
    w.add(event("a", "success", "09:00:00"), 0)
    w.add(event("b", "failure", "08:00:10"), 1)
    assert w.late == 0
    assert [closed.label for closed in w.flush()] == ["2026-10-15T08:00Z", "2026-10-15T09:00Z"]


def test_a_revoked_partition_no_longer_holds_the_watermark_back():
    w = FailureWindows(grace_seconds=0)
    w.assign([0, 1])
    w.add(event("a", "success", "08:00:10"), 0)
    w.revoke([1])
    [closed] = w.add(event("b", "created", "08:01:00"), 0)
    assert closed.label == "2026-10-15T08:00Z"
