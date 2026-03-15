"""Remove publish step and published episode status

Revision ID: 015
Revises: 014
Create Date: 2026-03-15
"""

from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Delete any existing publish pipeline steps
    op.execute("DELETE FROM pipeline_steps WHERE step_name = 'publish'")

    # Remove 'publish' from stepname enum
    # PostgreSQL requires ALTER TYPE to remove enum values (9.1+ workaround: recreate)
    op.execute("ALTER TYPE stepname RENAME TO stepname_old")
    op.execute("CREATE TYPE stepname AS ENUM ('collection', 'factcheck', 'analysis', 'script', 'voice', 'video')")
    op.execute("ALTER TABLE pipeline_steps ALTER COLUMN step_name TYPE stepname USING step_name::text::stepname")
    op.execute("DROP TYPE stepname_old")

    # Remove 'published' from episodestatus enum
    # Update any 'published' episodes to 'completed' first
    op.execute("UPDATE episodes SET status = 'completed' WHERE status = 'published'")
    op.execute("ALTER TYPE episodestatus RENAME TO episodestatus_old")
    op.execute("CREATE TYPE episodestatus AS ENUM ('draft', 'in_progress', 'completed')")
    op.execute("ALTER TABLE episodes ALTER COLUMN status TYPE episodestatus USING status::text::episodestatus")
    op.execute("DROP TYPE episodestatus_old")


def downgrade() -> None:
    # Re-add 'publish' to stepname enum
    op.execute("ALTER TYPE stepname RENAME TO stepname_old")
    op.execute("CREATE TYPE stepname AS ENUM ('collection', 'factcheck', 'analysis', 'script', 'voice', 'video', 'publish')")
    op.execute("ALTER TABLE pipeline_steps ALTER COLUMN step_name TYPE stepname USING step_name::text::stepname")
    op.execute("DROP TYPE stepname_old")

    # Re-add 'published' to episodestatus enum
    op.execute("ALTER TYPE episodestatus RENAME TO episodestatus_old")
    op.execute("CREATE TYPE episodestatus AS ENUM ('draft', 'in_progress', 'completed', 'published')")
    op.execute("ALTER TABLE episodes ALTER COLUMN status TYPE episodestatus USING status::text::episodestatus")
    op.execute("DROP TYPE episodestatus_old")
