"""add separate activation flags for story and judgment models

Revision ID: 016_add_llm_model_purposes
Revises: 015_add_action_skill_columns
Create Date: 2026-03-04
"""

import sqlalchemy as sa
from alembic import op

revision = "016_add_llm_model_purposes"
down_revision = "015_add_action_skill_columns"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "llm_models",
        sa.Column("is_active_story", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "llm_models",
        sa.Column("is_active_judgment", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.execute("UPDATE llm_models SET is_active_story = is_active WHERE is_active = true")
    op.execute(
        "UPDATE llm_models SET is_active_judgment = is_active WHERE is_active = true AND is_active_judgment = false"
    )


def downgrade():
    op.drop_column("llm_models", "is_active_judgment")
    op.drop_column("llm_models", "is_active_story")
