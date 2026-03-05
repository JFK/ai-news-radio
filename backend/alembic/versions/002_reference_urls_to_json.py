"""Change reference_urls from VARCHAR[] to JSON

Revision ID: 002
Revises: 001
Create Date: 2026-03-05

"""
from collections.abc import Sequence

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Convert VARCHAR[] to JSON, casting existing array data
    op.execute(
        "ALTER TABLE news_items "
        "ALTER COLUMN reference_urls TYPE JSON "
        "USING to_json(reference_urls)"
    )


def downgrade() -> None:
    # Convert JSON back to VARCHAR[]
    op.execute(
        "ALTER TABLE news_items "
        "ALTER COLUMN reference_urls TYPE VARCHAR[] "
        "USING ARRAY(SELECT jsonb_array_elements_text(reference_urls::jsonb))"
    )
