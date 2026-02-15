"""add judgments_data to story_logs

Revision ID: 010_add_judgments_data_to_story_logs
Revises: 009_add_event_probability
Create Date: 2026-02-14
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "010_add_judgments_data_to_story_logs"
down_revision = "009_add_event_probability"
branch_labels = None
depends_on = None


def upgrade():
    """Add judgments_data JSON column for persisting judgment snapshots."""
    op.add_column(
        "story_logs",
        sa.Column("judgments_data", sa.JSON(), nullable=True),
    )


def downgrade():
    """Remove judgments_data column from story_logs."""
    op.drop_column("story_logs", "judgments_data")
