"""Add model_pricing table with initial data

Revision ID: 004
Revises: 003
Create Date: 2026-03-09

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Initial pricing data (per 1M tokens, USD) — 2026-03
INITIAL_PRICING = [
    # OpenAI
    ("gpt-5.2", "openai", 1.75, 14.00),
    ("gpt-5", "openai", 1.25, 10.00),
    ("gpt-4o-mini", "openai", 0.15, 0.60),
    ("gpt-4o", "openai", 2.50, 10.00),
    ("gpt-4-turbo", "openai", 10.00, 30.00),
    ("o1-mini", "openai", 1.10, 4.40),
    ("o1", "openai", 15.00, 60.00),
    ("tts-1", "openai", 15.00, 0.0),
    ("tts-1-hd", "openai", 30.00, 0.0),
    # Anthropic
    ("claude-opus-4-6", "anthropic", 5.00, 25.00),
    ("claude-sonnet-4-5", "anthropic", 3.00, 15.00),
    ("claude-haiku-4-5", "anthropic", 1.00, 5.00),
    ("claude-sonnet-4-20250514", "anthropic", 3.00, 15.00),
    ("claude-opus-4-20250514", "anthropic", 5.00, 25.00),
    # Google
    ("gemini-3.1-pro", "google", 2.00, 12.00),
    ("gemini-2.5-pro", "google", 1.25, 10.00),
    ("gemini-2.5-flash", "google", 0.50, 3.00),
    ("gemini-2.0-flash", "google", 0.10, 0.40),
]


def upgrade() -> None:
    table = op.create_table(
        "model_pricing",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_prefix", sa.String(100), unique=True, nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("input_price_per_1m", sa.Float(), nullable=False, server_default="0"),
        sa.Column("output_price_per_1m", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.bulk_insert(
        table,
        [
            {
                "model_prefix": prefix,
                "provider": provider,
                "input_price_per_1m": input_price,
                "output_price_per_1m": output_price,
            }
            for prefix, provider, input_price, output_price in INITIAL_PRICING
        ],
    )


def downgrade() -> None:
    op.drop_table("model_pricing")
