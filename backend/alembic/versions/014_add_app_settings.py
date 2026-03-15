"""Add app_settings table and drive columns to episodes

Revision ID: 014
Revises: 013
Create Date: 2026-03-13
"""

import sqlalchemy as sa
from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("value", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.add_column(
        "episodes",
        sa.Column("drive_file_id", sa.String(200), nullable=True),
    )
    op.add_column(
        "episodes",
        sa.Column("drive_file_url", sa.String(2000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("episodes", "drive_file_url")
    op.drop_column("episodes", "drive_file_id")
    op.drop_table("app_settings")
