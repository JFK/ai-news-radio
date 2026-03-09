"""Add TTS provider pricing data

Revision ID: 005
Revises: 004
Create Date: 2026-03-09

"""
from collections.abc import Sequence

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# TTS pricing (per 1M characters, approximated as input tokens for cost tracking)
TTS_PRICING = [
    # ElevenLabs (standard voices ~$0.30/1K = $300/1M chars)
    ("elevenlabs-v2", "elevenlabs", 300.00, 0.0),
    ("elevenlabs-turbo", "elevenlabs", 150.00, 0.0),
    # Google Cloud TTS
    ("google-tts-standard", "google", 4.00, 0.0),
    ("google-tts-wavenet", "google", 16.00, 0.0),
    ("google-tts-neural2", "google", 16.00, 0.0),
    ("google-tts-journey", "google", 30.00, 0.0),
    # OpenAI TTS (already in 004, but add gpt-4o-mini-tts)
    ("gpt-4o-mini-tts", "openai", 0.60, 12.00),
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
            for prefix, provider, input_price, output_price in TTS_PRICING
        ],
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM model_pricing WHERE provider = 'elevenlabs' "
        "OR model_prefix IN ('google-tts-standard', 'google-tts-wavenet', "
        "'google-tts-neural2', 'google-tts-journey', 'gpt-4o-mini-tts')"
    )
