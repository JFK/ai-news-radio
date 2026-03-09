"""Add episode_id indexes to news_items, pipeline_steps, api_usages

Revision ID: 006
Revises: 005
Create Date: 2026-03-09

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(op.f("ix_news_items_episode_id"), "news_items", ["episode_id"])
    op.create_index(op.f("ix_pipeline_steps_episode_id"), "pipeline_steps", ["episode_id"])
    op.create_index(op.f("ix_api_usages_episode_id"), "api_usages", ["episode_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_api_usages_episode_id"), table_name="api_usages")
    op.drop_index(op.f("ix_pipeline_steps_episode_id"), table_name="pipeline_steps")
    op.drop_index(op.f("ix_news_items_episode_id"), table_name="news_items")
