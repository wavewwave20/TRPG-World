"""add event_triggered column to story_logs

Revision ID: 012_add_event_triggered_to_story_logs
Revises: 011_add_llm_settings
Create Date: 2026-02-16
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "012_add_event_triggered_to_story_logs"
down_revision = "011_add_llm_settings"
branch_labels = None
depends_on = None


def upgrade():
    """Add event_triggered boolean column to story_logs table."""
    op.add_column(
        "story_logs",
        sa.Column("event_triggered", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )


def downgrade():
    """Remove event_triggered column from story_logs table."""
    op.drop_column("story_logs", "event_triggered")
