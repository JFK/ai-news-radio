"""Add excluded and excluded_at_step to news_items

Revision ID: 012
Revises: 011
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("news_items", sa.Column("excluded", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("news_items", sa.Column("excluded_at_step", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("news_items", "excluded_at_step")
    op.drop_column("news_items", "excluded")
