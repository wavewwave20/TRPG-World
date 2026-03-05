"""add separate activation flag for image models

Revision ID: 018_add_llm_image_purpose
Revises: 017_add_session_activity_logs
Create Date: 2026-03-05
"""

import sqlalchemy as sa
from alembic import op

revision = "018_add_llm_image_purpose"
down_revision = "017_add_session_activity_logs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "llm_models",
        sa.Column("is_active_image", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade():
    op.drop_column("llm_models", "is_active_image")
