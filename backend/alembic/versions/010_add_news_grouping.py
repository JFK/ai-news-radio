"""Add group_id and is_group_primary to news_items

Revision ID: 010
Revises: 009
Create Date: 2026-03-11
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("news_items", sa.Column("group_id", sa.Integer(), nullable=True))
    op.add_column("news_items", sa.Column("is_group_primary", sa.Boolean(), nullable=True))
    op.create_index("ix_news_items_group_id", "news_items", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_news_items_group_id", table_name="news_items")
    op.drop_column("news_items", "is_group_primary")
    op.drop_column("news_items", "group_id")
