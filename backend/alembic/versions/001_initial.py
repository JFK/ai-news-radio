"""Initial migration

Revision ID: 001
Revises:
Create Date: 2026-03-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "episodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "in_progress", "completed", "published", name="episodestatus"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "news_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("episode_id", sa.Integer(), sa.ForeignKey("episodes.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(2000), nullable=False),
        sa.Column("source_name", sa.String(200), nullable=False),
        sa.Column("fact_check_status", sa.String(50), nullable=True),
        sa.Column("fact_check_score", sa.Integer(), nullable=True),
        sa.Column("fact_check_details", sa.Text(), nullable=True),
        sa.Column("reference_urls", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("analysis_data", postgresql.JSON(), nullable=True),
        sa.Column("script_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "pipeline_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("episode_id", sa.Integer(), sa.ForeignKey("episodes.id"), nullable=False),
        sa.Column(
            "step_name",
            sa.Enum("collection", "factcheck", "analysis", "script", "voice", "video", "publish", name="stepname"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "needs_approval", "approved", "rejected", name="stepstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("input_data", postgresql.JSON(), nullable=True),
        sa.Column("output_data", postgresql.JSON(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "api_usages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("episode_id", sa.Integer(), sa.ForeignKey("episodes.id"), nullable=False),
        sa.Column("step_name", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0"),
        sa.Column("output_tokens", sa.Integer(), server_default="0"),
        sa.Column("cost_usd", sa.Float(), server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("api_usages")
    op.drop_table("pipeline_steps")
    op.drop_table("news_items")
    op.drop_table("episodes")
    sa.Enum(name="episodestatus").drop(op.get_bind())
    sa.Enum(name="stepname").drop(op.get_bind())
    sa.Enum(name="stepstatus").drop(op.get_bind())
