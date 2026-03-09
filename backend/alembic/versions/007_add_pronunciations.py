"""Add pronunciations table for reading dictionary

Revision ID: 007
Revises: 006
Create Date: 2026-03-09

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pronunciations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("surface", sa.String(200), unique=True, nullable=False),
        sa.Column("reading", sa.String(200), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("pronunciations")
