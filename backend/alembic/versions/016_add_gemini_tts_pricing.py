"""Add Gemini TTS pricing data

Revision ID: 016
Revises: 015
Create Date: 2026-03-15
"""

from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None

GEMINI_TTS_PRICING = [
    {
        "model_prefix": "gemini-2.5-flash-preview-tts",
        "provider": "gemini-tts",
        "input_price_per_1m": 0.50,
        "output_price_per_1m": 10.00,
    },
    {
        "model_prefix": "gemini-2.5-pro-preview-tts",
        "provider": "gemini-tts",
        "input_price_per_1m": 1.00,
        "output_price_per_1m": 20.00,
    },
]


def upgrade() -> None:
    for p in GEMINI_TTS_PRICING:
        op.execute(
            f"INSERT INTO model_pricing (model_prefix, provider, input_price_per_1m, output_price_per_1m) "
            f"VALUES ('{p['model_prefix']}', '{p['provider']}', "
            f"{p['input_price_per_1m']}, {p['output_price_per_1m']}) "
            f"ON CONFLICT (model_prefix) DO NOTHING"
        )


def downgrade() -> None:
    for p in GEMINI_TTS_PRICING:
        op.execute(f"DELETE FROM model_pricing WHERE model_prefix = '{p['model_prefix']}'")
