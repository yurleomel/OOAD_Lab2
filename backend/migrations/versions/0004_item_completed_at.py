"""record when an item was completed

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("items", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    # The best guess for items already done: the last time they changed. It is
    # exact for every item that was not edited after it was finished.
    op.execute("UPDATE items SET completed_at = updated_at WHERE status = 'done'")
    op.create_index("ix_items_completed_at", "items", ["completed_at"])


def downgrade() -> None:
    op.drop_index("ix_items_completed_at", table_name="items")
    op.drop_column("items", "completed_at")
