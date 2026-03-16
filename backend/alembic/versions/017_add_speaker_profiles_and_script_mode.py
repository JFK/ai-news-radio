"""Add speaker_profiles table, script_mode/script_data to news_items, shorts_enabled to episodes

Revision ID: 017
Revises: 016
Create Date: 2026-03-16
"""

import sqlalchemy as sa
from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None

DEFAULT_SPEAKERS = [
    {
        "name": "レイナ",
        "role": "anchor",
        "voice_name": "Kore",
        "voice_instructions": "落ち着いたニュースキャスターのように、明瞭で聞き取りやすく話してください。テンポよく、信頼感のあるトーンで。",
        "avatar_position": "right",
        "description": "メインMC。番組の進行役として、ニュースの導入や話題の切り替えを担当。",
    },
    {
        "name": "タクヤ",
        "role": "expert",
        "voice_name": "Charon",
        "voice_instructions": "知的で分析的なトーンで話してください。専門家として自信を持ちつつも、わかりやすく丁寧に解説する口調で。",
        "avatar_position": "left",
        "description": "解説者。ニュースの背景や複数の視点を深掘りし、専門的な分析を提供。",
    },
    {
        "name": "アオイ",
        "role": "narrator",
        "voice_name": "Aoede",
        "voice_instructions": "自然な語りのトーンで、聞きやすいペースで話してください。感情を込めすぎず、落ち着いたナレーションで。",
        "avatar_position": "right",
        "description": "ソロナレーター。1人でニュースの要点から分析まで通して伝える。",
    },
]


def upgrade() -> None:
    op.create_table(
        "speaker_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, unique=True),
        sa.Column("voice_name", sa.String(50), server_default="Kore"),
        sa.Column("voice_instructions", sa.Text(), server_default=""),
        sa.Column("avatar_path", sa.String(500), nullable=True),
        sa.Column("avatar_position", sa.String(10), server_default="right"),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Seed default speakers
    for s in DEFAULT_SPEAKERS:
        op.execute(
            "INSERT INTO speaker_profiles (name, role, voice_name, voice_instructions, avatar_position, description) "
            f"VALUES ('{s['name']}', '{s['role']}', '{s['voice_name']}', "
            f"'{s['voice_instructions']}', '{s['avatar_position']}', '{s['description']}')"
        )

    op.add_column("news_items", sa.Column("script_mode", sa.String(20), nullable=True))
    op.add_column("news_items", sa.Column("script_data", sa.JSON(), nullable=True))

    op.add_column(
        "episodes",
        sa.Column("shorts_enabled", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("episodes", "shorts_enabled")
    op.drop_column("news_items", "script_data")
    op.drop_column("news_items", "script_mode")
    op.drop_table("speaker_profiles")
