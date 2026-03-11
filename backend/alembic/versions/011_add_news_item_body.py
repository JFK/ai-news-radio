"""Add body column to news_items

Revision ID: 011
Revises: 010
Create Date: 2026-03-11
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("news_items", sa.Column("body", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("news_items", "body")
