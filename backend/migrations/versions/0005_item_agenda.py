"""agenda on a task, and what the parser suggested for it

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-19

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("items", sa.Column("agenda", postgresql.JSONB(), nullable=True))
    op.add_column("items", sa.Column("ai_suggestion", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("items", "ai_suggestion")
    op.drop_column("items", "agenda")
