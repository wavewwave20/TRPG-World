"""add image concept field to game sessions

Revision ID: 019_add_session_image_concept
Revises: 018_add_llm_image_purpose
Create Date: 2026-03-05
"""

import sqlalchemy as sa
from alembic import op

revision = "019_add_session_image_concept"
down_revision = "018_add_llm_image_purpose"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "game_sessions",
        sa.Column("image_concept", sa.Text(), nullable=False, server_default=sa.text("''")),
    )


def downgrade():
    op.drop_column("game_sessions", "image_concept")
