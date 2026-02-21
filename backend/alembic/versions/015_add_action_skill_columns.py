"""add action skill metadata columns to action_judgments

Revision ID: 015_add_action_skill_columns
Revises: 014_add_host_story_controls
Create Date: 2026-02-20
"""

import sqlalchemy as sa
from alembic import op

revision = "015_add_action_skill_columns"
down_revision = "014_add_host_story_controls"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "action_judgments",
        sa.Column("action_mode", sa.String(length=20), nullable=False, server_default="normal"),
    )
    op.add_column(
        "action_judgments",
        sa.Column("skill_name", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "action_judgments",
        sa.Column("skill_description", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column("action_judgments", "skill_description")
    op.drop_column("action_judgments", "skill_name")
    op.drop_column("action_judgments", "action_mode")
