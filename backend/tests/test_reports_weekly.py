import csv
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Item, User
from app.reports.weekly import (
    TIMEZONE,
    previous_week,
    render_weekly_report,
    report_key,
    week_before,
    week_bounds,
)


def kyiv(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp).replace(tzinfo=TIMEZONE)


# --- weeks -----------------------------------------------------------------


def test_a_week_runs_from_monday_midnight_in_kyiv() -> None:
    start, end = week_bounds("2026-W40")
    assert start == kyiv("2026-09-28 00:00")
    assert end == kyiv("2026-10-05 00:00")
    assert start.utcoffset() == timedelta(hours=3)


def test_the_week_dst_ends_still_ends_at_midnight() -> None:
    # Clocks go back on Sunday 2026-10-25, so this week is an hour longer.
    start, end = week_bounds("2026-W43")
    assert end == kyiv("2026-10-26 00:00")
    assert end.utcoffset() == timedelta(hours=2)
    assert end.astimezone(UTC) - start.astimezone(UTC) == timedelta(days=7, hours=1)


@pytest.mark.parametrize("week", ["2026-40", "2026-W4", "W40", "2026-W00", "2025-W53", ""])
def test_rejects_what_is_not_a_week(week: str) -> None:
    with pytest.raises(ValueError):
        week_bounds(week)


def test_week_53_exists_in_a_long_year() -> None:
    assert week_bounds("2026-W53")[0] == kyiv("2026-12-28 00:00")


def test_previous_week_on_monday_morning() -> None:
    assert previous_week(kyiv("2026-10-12 07:00")) == "2026-W41"


def test_previous_week_is_judged_in_kyiv_not_utc() -> None:
    # Sunday night in UTC is already Monday in Kyiv.
    assert previous_week(datetime(2026, 10, 11, 22, 30, tzinfo=UTC)) == "2026-W41"


def test_week_before_crosses_the_year() -> None:
    assert week_before("2027-W01") == "2026-W53"
    assert previous_week(kyiv("2027-01-04 07:00")) == "2026-W53"


def test_one_week_one_key() -> None:
    assert report_key("2026-W40") == "reports/2026-W40.csv"
    assert report_key("2026-W40") == report_key("2026-W40")
    with pytest.raises(ValueError):
        report_key("last-week")


# --- the report ------------------------------------------------------------


async def _user(session: AsyncSession, name: str) -> User:
    user = User(cognito_sub=f"{name}-sub", email=f"{name}@example.com", name=name)
    session.add(user)
    await session.flush()
    return user


def _item(owner: User, name: str, created: str, completed: str | None = None) -> Item:
    return Item(
        owner_id=owner.id,
        name=name,
        status="done" if completed else "todo",
        created_at=kyiv(created),
        completed_at=kyiv(completed) if completed else None,
    )


def _rows(report: bytes) -> list[list[str]]:
    return list(csv.reader(report.decode("utf-8-sig").splitlines()))


def _section(rows: list[list[str]], header: list[str]) -> list[list[str]]:
    start = rows.index(header) + 1
    end = rows.index([], start) if [] in rows[start:] else len(rows)
    return rows[start:end]


@pytest.fixture
async def two_weeks(session: AsyncSession) -> None:
    alice, bob = await _user(session, "alice"), await _user(session, "bob")
    session.add_all(
        [
            _item(alice, "Long one", "2026-09-20 10:00", "2026-09-29 10:00"),  # done in W40, 216 h
            _item(alice, "Quick", "2026-09-30 09:00", "2026-09-30 11:00"),  # W40, 2 h
            _item(alice, "Open", "2026-10-01 12:00"),  # created in W40
            _item(bob, "Late Sunday", "2026-10-04 23:30"),  # still W40 in Kyiv
            _item(bob, "Next Monday", "2026-10-05 00:00"),  # W41: excluded
            _item(bob, "Last week", "2026-09-22 10:00", "2026-09-23 10:00"),  # W39, 24 h
        ]
    )
    await session.flush()


async def test_report_counts_one_week_against_the_one_before(
    session: AsyncSession, two_weeks: None
) -> None:
    rows = _rows(await render_weekly_report(session, "2026-W40"))

    assert rows[0] == ["Lanora weekly report", "2026-W40"]
    assert rows[1] == ["from", "2026-09-28 00:00 Europe/Kyiv"]
    assert _section(rows, ["metric", "2026-W40", "2026-W39", "change"]) == [
        ["tasks created", "3", "1", "+2"],
        ["tasks completed", "2", "1", "+1"],
        ["hours from creation to completion", "218.0", "24.0", "+194.0"],
    ]


async def test_report_lists_the_longest_tasks_and_each_person(
    session: AsyncSession, two_weeks: None
) -> None:
    rows = _rows(await render_weekly_report(session, "2026-W40"))

    assert _section(rows, ["task", "owner", "created", "completed", "hours"]) == [
        ["Long one", "alice", "2026-09-20 10:00", "2026-09-29 10:00", "216.0"],
        ["Quick", "alice", "2026-09-30 09:00", "2026-09-30 11:00", "2.0"],
    ]
    assert _section(rows, ["person", "created", "completed", "hours"]) == [
        ["alice", "2", "2", "218.0"],
        ["bob", "1", "0", "0.0"],
    ]


async def test_same_week_same_file(session: AsyncSession, two_weeks: None) -> None:
    first = await render_weekly_report(session, "2026-W40")
    assert await render_weekly_report(session, "2026-W40") == first


async def test_only_the_five_longest_are_listed(session: AsyncSession) -> None:
    owner = await _user(session, "carol")
    session.add_all(
        _item(owner, f"Task {hours}", "2026-09-28 01:00", f"2026-09-28 {1 + hours:02d}:00")
        for hours in range(1, 8)
    )
    await session.flush()

    rows = _rows(await render_weekly_report(session, "2026-W40"))
    listed = _section(rows, ["task", "owner", "created", "completed", "hours"])
    assert [row[0] for row in listed] == ["Task 7", "Task 6", "Task 5", "Task 4", "Task 3"]


async def test_an_empty_week_is_still_a_report(session: AsyncSession) -> None:
    report = await render_weekly_report(session, "2026-W40")
    assert report.startswith(b"\xef\xbb\xbf")  # Excel reads it as UTF-8
    rows = _rows(report)
    assert ["tasks created", "0", "0", "0"] in rows
    assert _section(rows, ["person", "created", "completed", "hours"]) == []


async def test_names_survive_in_cyrillic(session: AsyncSession) -> None:
    owner = await _user(session, "Олена")
    session.add(_item(owner, "Звіт за тиждень", "2026-09-29 09:00", "2026-09-29 10:00"))
    await session.flush()

    rows = _rows(await render_weekly_report(session, "2026-W40"))
    assert ["Олена", "1", "1", "1.0"] in rows
    assert rows[rows.index(["task", "owner", "created", "completed", "hours"]) + 1][0] == (
        "Звіт за тиждень"
    )
