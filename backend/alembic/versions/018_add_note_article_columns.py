"""Add note_analysis_article, note_video_article to episodes

Revision ID: 018
Revises: 017
Create Date: 2026-03-18
"""

import sqlalchemy as sa

from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("episodes", sa.Column("note_analysis_article", sa.Text(), nullable=True))
    op.add_column("episodes", sa.Column("note_video_article", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("episodes", "note_video_article")
    op.drop_column("episodes", "note_analysis_article")
