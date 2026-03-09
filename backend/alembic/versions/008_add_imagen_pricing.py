"""Add Imagen pricing data

Revision ID: 008
Revises: 007
Create Date: 2026-03-09

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Imagen pricing: per-image, stored as cost_usd directly (not per 1M tokens)
# These entries exist for reference in the pricing table
IMAGEN_PRICING = [
    # Imagen 4 Fast: $0.04/image (input_price = price per image, output = 0)
    ("imagen-4.0-fast", "google", 40.00, 0.0),
    # Imagen 4 Standard: $0.06/image
    ("imagen-4.0-generate", "google", 60.00, 0.0),
    # Imagen 4 Ultra: $0.08/image
    ("imagen-4.0-ultra", "google", 80.00, 0.0),
]


def upgrade() -> None:
    from sqlalchemy import table, column, String, Float

    model_pricing = table(
        "model_pricing",
        column("model_prefix", String),
        column("provider", String),
        column("input_price_per_1m", Float),
        column("output_price_per_1m", Float),
    )

    op.bulk_insert(
        model_pricing,
        [
            {
                "model_prefix": prefix,
                "provider": provider,
                "input_price_per_1m": input_price,
                "output_price_per_1m": output_price,
            }
            for prefix, provider, input_price, output_price in IMAGEN_PRICING
        ],
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM model_pricing WHERE model_prefix LIKE 'imagen-4.0%'"
    )
