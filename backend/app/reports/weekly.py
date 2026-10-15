"""The weekly report: one ISO week of tasks, as a CSV.

Plain code with no AWS in it, so it runs - and is debugged - against the
Compose database before it ever runs in a Lambda:

    make report-local WEEK=2026-W40

Two rules the rest of the pipeline relies on:

- The week is a parameter. Nothing here says "last week"; whoever calls decides,
  which is what lets an old report be rebuilt.
- One week, one key: ``reports/2026-W40.csv``. Building a week twice overwrites
  one file, so a message delivered twice does no harm.
"""

import asyncio
import csv
import io
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.models import Item, User

# Weeks start on Monday at midnight here, not in UTC: the report goes out at
# 07:00 Kyiv time and describes the week its readers lived through.
TIMEZONE = ZoneInfo("Europe/Kyiv")
PREFIX = "reports/"
TOP_TASKS = 5

_WEEK = re.compile(r"(\d{4})-W(\d{2})")


def week_bounds(week: str) -> tuple[datetime, datetime]:
    """Monday 00:00 to the next Monday 00:00, Kyiv time, for an ISO week like "2026-W40"."""
    match = _WEEK.fullmatch(week)
    if match is None:
        raise ValueError(f"not an ISO week: {week!r} (expected e.g. 2026-W40)")
    try:
        monday = date.fromisocalendar(int(match[1]), int(match[2]), 1)
    except ValueError:
        raise ValueError(f"{week} does not exist") from None
    start = datetime.combine(monday, time(), TIMEZONE)
    # Wall-clock arithmetic: still midnight a week later, across a DST change.
    return start, start + timedelta(days=7)


def week_of(moment: datetime) -> str:
    iso = moment.astimezone(TIMEZONE).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def week_before(week: str) -> str:
    start, _ = week_bounds(week)
    return week_of(start - timedelta(days=7))


def previous_week(now: datetime | None = None) -> str:
    """The last complete week - what a report sent on Monday morning describes."""
    return week_of((now or datetime.now(TIMEZONE)) - timedelta(days=7))


def report_key(week: str) -> str:
    week_bounds(week)  # a key is only ever made for a real week
    return f"{PREFIX}{week}.csv"


# --- queries ---------------------------------------------------------------


@dataclass(frozen=True)
class Totals:
    created: int
    completed: int
    hours: float  # creation to completion, summed over the tasks completed


@dataclass(frozen=True)
class LongTask:
    name: str
    owner: str
    created_at: datetime
    completed_at: datetime

    @property
    def hours(self) -> float:
        return (self.completed_at - self.created_at).total_seconds() / 3600


@dataclass
class PersonRow:
    name: str
    created: int = 0
    completed: int = 0
    hours: float = 0.0


_DURATION_SECONDS = func.extract("epoch", Item.completed_at - Item.created_at)


def _created_in(start: datetime, end: datetime):
    return (Item.created_at >= start) & (Item.created_at < end)


def _completed_in(start: datetime, end: datetime):
    return (Item.completed_at >= start) & (Item.completed_at < end)


async def _totals(session: AsyncSession, start: datetime, end: datetime) -> Totals:
    created = await session.scalar(
        select(func.count()).select_from(Item).where(_created_in(start, end))
    )
    completed, seconds = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(_DURATION_SECONDS), 0)).where(
                _completed_in(start, end)
            )
        )
    ).one()
    return Totals(created=created or 0, completed=completed, hours=float(seconds) / 3600)


async def _longest(session: AsyncSession, start: datetime, end: datetime) -> list[LongTask]:
    rows = await session.execute(
        select(Item.name, User.name, Item.created_at, Item.completed_at)
        .join(User, User.id == Item.owner_id)
        .where(_completed_in(start, end))
        .order_by(_DURATION_SECONDS.desc(), Item.created_at, Item.id)
        .limit(TOP_TASKS)
    )
    return [LongTask(*row) for row in rows]


async def _by_person(session: AsyncSession, start: datetime, end: datetime) -> list[PersonRow]:
    people: dict[uuid.UUID, PersonRow] = {}
    created = await session.execute(
        select(User.id, User.name, func.count())
        .join(Item, Item.owner_id == User.id)
        .where(_created_in(start, end))
        .group_by(User.id, User.name)
    )
    for user_id, name, count in created:
        people.setdefault(user_id, PersonRow(name)).created = count
    completed = await session.execute(
        select(User.id, User.name, func.count(), func.sum(_DURATION_SECONDS))
        .join(Item, Item.owner_id == User.id)
        .where(_completed_in(start, end))
        .group_by(User.id, User.name)
    )
    for user_id, name, count, seconds in completed:
        row = people.setdefault(user_id, PersonRow(name))
        row.completed, row.hours = count, float(seconds) / 3600
    return [people[key] for key in sorted(people, key=lambda key: (people[key].name, str(key)))]


# --- rendering -------------------------------------------------------------


def _local(moment: datetime) -> str:
    return moment.astimezone(TIMEZONE).strftime("%Y-%m-%d %H:%M")


def _change(now: float, before: float, digits: int = 0) -> str:
    delta = round(now - before, digits)
    return f"{delta:+.{digits}f}" if delta else "0"


async def render_weekly_report(session: AsyncSession, week: str) -> bytes:
    """The CSV for one week, read through an open session."""
    start, end = week_bounds(week)
    before = week_before(week)
    previous_start, _ = week_bounds(before)

    this, last = await _totals(session, start, end), await _totals(session, previous_start, start)
    longest = await _longest(session, start, end)
    people = await _by_person(session, start, end)

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Lanora weekly report", week])
    writer.writerow(["from", f"{_local(start)} {TIMEZONE.key}"])
    writer.writerow(["to", f"{_local(end)} {TIMEZONE.key}"])
    writer.writerow([])
    writer.writerow(["metric", week, before, "change"])
    writer.writerow(
        ["tasks created", this.created, last.created, _change(this.created, last.created)]
    )
    writer.writerow(
        ["tasks completed", this.completed, last.completed, _change(this.completed, last.completed)]
    )
    writer.writerow(
        [
            "hours from creation to completion",
            f"{this.hours:.1f}",
            f"{last.hours:.1f}",
            _change(this.hours, last.hours, 1),
        ]
    )
    writer.writerow([])
    writer.writerow([f"longest tasks completed in {week}"])
    writer.writerow(["task", "owner", "created", "completed", "hours"])
    for task in longest:
        writer.writerow(
            [
                task.name,
                task.owner,
                _local(task.created_at),
                _local(task.completed_at),
                f"{task.hours:.1f}",
            ]
        )
    writer.writerow([])
    writer.writerow(["by person"])
    writer.writerow(["person", "created", "completed", "hours"])
    for person in people:
        writer.writerow([person.name, person.created, person.completed, f"{person.hours:.1f}"])
    # With a byte-order mark, Excel opens Cyrillic task names as text, not mojibake.
    return out.getvalue().encode("utf-8-sig")


async def _build(week: str) -> bytes:
    # An engine of its own, not app.db's: each call runs in a fresh event loop,
    # and pooled asyncpg connections cannot move between loops.
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            return await render_weekly_report(session, week)
    finally:
        await engine.dispose()


def build_weekly_report(week: str) -> bytes:
    """Query the tasks of one ISO week (e.g. "2026-W40") and return the CSV."""
    week_bounds(week)
    return asyncio.run(_build(week))


if __name__ == "__main__":
    sys.stdout.buffer.write(
        build_weekly_report(sys.argv[1] if len(sys.argv) > 1 else previous_week())
    )
