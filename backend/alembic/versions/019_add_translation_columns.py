"""Add body_original, source_language to news_items

Revision ID: 019
Revises: 018
Create Date: 2026-03-21
"""

import sqlalchemy as sa

from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("news_items", sa.Column("body_original", sa.Text(), nullable=True))
    op.add_column("news_items", sa.Column("source_language", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("news_items", "source_language")
    op.drop_column("news_items", "body_original")
