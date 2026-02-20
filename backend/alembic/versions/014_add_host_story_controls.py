"""add host_story_controls to game_sessions

Revision ID: 014_add_host_story_controls
Revises: 013_add_story_flow_metrics_and_host_instruction
Create Date: 2026-02-20
"""

import sqlalchemy as sa
from alembic import op

revision = "014_add_host_story_controls"
down_revision = "013_add_story_flow_metrics_and_host_instruction"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "game_sessions",
        sa.Column("host_story_controls", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade():
    op.drop_column("game_sessions", "host_story_controls")
