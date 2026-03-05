"""add session story pacing fields

Revision ID: 020_add_session_story_pacing
Revises: 019_add_session_image_concept
Create Date: 2026-03-05
"""

import sqlalchemy as sa
from alembic import op

revision = "020_add_session_story_pacing"
down_revision = "019_add_session_image_concept"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "game_sessions",
        sa.Column("max_acts", sa.Integer(), nullable=True),
    )
    op.add_column(
        "game_sessions",
        sa.Column("act_min_narrative_turns", sa.Integer(), nullable=True),
    )
    op.execute("UPDATE game_sessions SET max_acts = 4 WHERE max_acts IS NULL")
    op.execute("UPDATE game_sessions SET act_min_narrative_turns = 5 WHERE act_min_narrative_turns IS NULL")


def downgrade():
    op.drop_column("game_sessions", "act_min_narrative_turns")
    op.drop_column("game_sessions", "max_acts")
