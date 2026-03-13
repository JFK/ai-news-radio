"""Add Brave Search pricing data

Revision ID: 013
Revises: 012
Create Date: 2026-03-13
"""

from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None

# Brave Search API: $5 per 1,000 queries = $5,000 per 1M queries
# We use input_price_per_1m to store per-1M-query price, output_price is 0.
BRAVE_PRICING = {
    "model_prefix": "brave-search",
    "provider": "brave",
    "input_price_per_1m": 5000.0,  # $5 per 1K = $5,000 per 1M
    "output_price_per_1m": 0.0,
}


def upgrade() -> None:
    op.execute(
        f"INSERT INTO model_pricing (model_prefix, provider, input_price_per_1m, output_price_per_1m) "
        f"VALUES ('{BRAVE_PRICING['model_prefix']}', '{BRAVE_PRICING['provider']}', "
        f"{BRAVE_PRICING['input_price_per_1m']}, {BRAVE_PRICING['output_price_per_1m']}) "
        f"ON CONFLICT (model_prefix) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM model_pricing WHERE model_prefix = 'brave-search'")
