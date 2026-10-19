import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agenda import Agenda, AiSuggestion

ItemStatus = Literal["todo", "in_progress", "done"]


class ItemBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    status: ItemStatus = "todo"
    agenda: Agenda | None = None


class ItemCreate(ItemBase):
    # What the parser suggested, when the agenda started as a pasted text. It is
    # written, never read back by the app: it is there to be compared offline.
    ai_suggestion: AiSuggestion | None = None


class ItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    status: ItemStatus | None = None
    # null removes the agenda; leaving the field out keeps it.
    agenda: Agenda | None = None
    ai_suggestion: AiSuggestion | None = None


class ItemRead(ItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ItemList(BaseModel):
    items: list[ItemRead]
    total: int
