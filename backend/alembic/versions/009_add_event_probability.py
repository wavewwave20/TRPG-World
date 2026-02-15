"""add event_probability to game_sessions

Revision ID: 009_add_event_probability
Revises: 008_add_character_share_codes
Create Date: 2026-02-14
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "009_add_event_probability"
down_revision = "008_add_character_share_codes"
branch_labels = None
depends_on = None


def upgrade():
    """Add event_probability column for progressive random event system."""
    op.add_column(
        "game_sessions",
        sa.Column(
            "event_probability",
            sa.Float(),
            nullable=False,
            server_default="0.10",
        ),
    )


def downgrade():
    """Remove event_probability column from game_sessions."""
    op.drop_column("game_sessions", "event_probability")
