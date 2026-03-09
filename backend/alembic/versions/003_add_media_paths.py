"""Add audio_path and video_path to episodes

Revision ID: 003
Revises: 002
Create Date: 2026-03-05

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("episodes", sa.Column("audio_path", sa.String(500), nullable=True))
    op.add_column("episodes", sa.Column("video_path", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("episodes", "video_path")
    op.drop_column("episodes", "audio_path")
