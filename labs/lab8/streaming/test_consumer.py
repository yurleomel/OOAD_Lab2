"""The window logic, without a broker: run `pytest` in this directory."""

from consumer import Windows


def event(invoice, status, at, method="card"):
    return {"invoiceId": invoice, "status": status, "modifiedDate": f"2026-10-15T{at}Z", "paymentMethod": method}


def on_one_partition(grace=0):
    windows = Windows(grace)
    windows.assign([0])
    return windows


def counts(closed):
    return [(failed, total) for _, _, failed, total in closed]


def test_duplicate_is_counted_once():
    w = on_one_partition()
    w.add(event("a", "failure", "08:00:10"), 0)
    w.add(event("a", "failure", "08:00:10"), 0)
    assert w.stats["duplicates"] == 1
    assert counts(w.flush()) == [(1, 1)]


def test_only_final_statuses_count_towards_the_share():
    w = on_one_partition()
    for invoice, status, at in [("a", "created", "01"), ("a", "processing", "02"), ("a", "success", "03"), ("b", "failure", "04")]:
        w.add(event(invoice, status, f"08:00:{at}"), 0)
    assert counts(w.flush()) == [(1, 2)]


def test_the_window_comes_from_event_time_not_arrival_order():
    w = on_one_partition(grace=120)
    w.add(event("a", "success", "08:01:30"), 0)
    w.add(event("b", "failure", "08:00:30"), 0)  # arrives second, happened in the earlier minute
    assert counts(w.flush()) == [(1, 1), (0, 1)]


def test_a_window_closes_after_its_end_plus_the_grace_period():
    w = on_one_partition(grace=120)
    w.add(event("a", "success", "08:00:10"), 0)
    assert w.add(event("b", "created", "08:02:59"), 0) == []  # end 08:01 + grace 2 min = 08:03
    assert counts(w.add(event("c", "created", "08:03:00"), 0)) == [(0, 1)]


def test_an_event_for_a_closed_window_is_rejected_and_counted():
    w = on_one_partition(grace=120)
    w.add(event("a", "success", "08:00:10"), 0)
    w.add(event("b", "created", "08:03:00"), 0)  # closes 08:00
    w.add(event("c", "failure", "08:00:20"), 0)
    assert w.stats["late"] == 1
    assert w.flush() == []


def test_inside_the_grace_period_a_late_event_still_counts():
    w = on_one_partition(grace=120)
    w.add(event("a", "success", "08:00:10"), 0)
    w.add(event("b", "created", "08:02:00"), 0)
    w.add(event("c", "failure", "08:00:20"), 0)
    assert w.stats["late"] == 0
    assert counts(w.flush()) == [(1, 2)]


def test_the_slowest_partition_holds_the_watermark_back():
    w = Windows(120)
    w.assign([0, 1])
    w.add(event("a", "success", "09:00:00"), 0)  # partition 0 is an hour ahead
    w.add(event("b", "failure", "08:00:10"), 1)
    assert w.stats["late"] == 0
    assert counts(w.flush()) == [(1, 1), (0, 1)]
