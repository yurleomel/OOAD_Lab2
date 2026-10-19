"""The agenda of a task, and what the parser suggested for it.

``ParsedAgenda`` is the parser's contract with the model (app/ai/agenda.py): the
input schema of its ``record_agenda`` tool. ``Agenda`` is what the user saves
through the items endpoints - the same lists, without the fields that belong to
the task itself (its name) or only to the parse (the language).
"""

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class AgendaItem(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    owner: str | None = Field(default=None, max_length=120)  # a name or an email, as written
    minutes: int | None = Field(default=None, ge=1, le=480)


class ActionItem(BaseModel):
    task: str = Field(min_length=1, max_length=300)
    owner: str | None = Field(default=None, max_length=120)
    due: date | None = None


class Agenda(BaseModel):
    """Saved on a task. Every field is optional except the list of topics."""

    starts_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    items: list[AgendaItem] = Field(default_factory=list, max_length=50)
    action_items: list[ActionItem] = Field(default_factory=list, max_length=50)


class ParsedAgenda(BaseModel):
    """What the model must return. None means "the text does not say"."""

    title: str | None = Field(default=None, max_length=120)
    # Wall-clock time, no offset: the browser attaches the offset of that very
    # day. Models get the offset wrong across a DST change (agenda-v1 put
    # Monday 26 October 10:00 Kyiv at +03:00, an hour off).
    starts_at: str | None = Field(
        default=None,
        description="Local date and time in the user's time zone, YYYY-MM-DDTHH:MM, "
        "no UTC offset. Only when the text gives a clock time.",
    )
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    items: list[AgendaItem] = Field(max_length=50)
    action_items: list[ActionItem] = Field(default_factory=list, max_length=50)
    language: str = Field(min_length=2, max_length=10)  # "uk", "en", …

    @field_validator("starts_at")
    @classmethod
    def _wall_clock(cls, value: str | None) -> str | None:
        """Any ISO-like form the model writes ("2026-10-27 13:00:00", "...+03:00")
        becomes YYYY-MM-DDTHH:MM:SS with no offset: the time as the text said it."""
        if value is None or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError:
            raise ValueError("starts_at must be a date and time, YYYY-MM-DDTHH:MM") from None
        return parsed.replace(tzinfo=None).isoformat(timespec="seconds")


class AiSuggestion(BaseModel):
    """Stored next to the saved agenda: the difference between the two is the
    quality signal, and model + prompt version say which parse produced it."""

    agenda: ParsedAgenda
    model: str = Field(min_length=1, max_length=100)
    prompt_version: str = Field(min_length=1, max_length=40)
