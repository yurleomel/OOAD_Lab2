import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Item(Base):
    """A task on the board. Every item belongs to exactly one user."""

    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("status IN ('todo', 'in_progress', 'done')", name="ck_items_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="todo")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    # Set when the status becomes done, cleared when it leaves done. The weekly
    # report counts completions by it: updated_at moves on every later edit.
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    # The agenda, when the task is a meeting (app/schemas/agenda.py), and what
    # the parser suggested for it. Validated by the API schemas on the way in.
    agenda: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ai_suggestion: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
