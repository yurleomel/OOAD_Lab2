"""add users and give every item an owner

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("cognito_sub", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cognito_sub", name="uq_users_cognito_sub"),
    )

    # Items made before sign-in existed have nobody to belong to. No deployed
    # database holds any, so they are dropped rather than parked on a made-up user.
    op.execute("DELETE FROM items")
    op.add_column("items", sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False))
    op.create_foreign_key(
        "items_owner_id_fkey", "items", "users", ["owner_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_items_owner_id", "items", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_items_owner_id", table_name="items")
    op.drop_constraint("items_owner_id_fkey", "items", type_="foreignkey")
    op.drop_column("items", "owner_id")
    op.drop_table("users")
