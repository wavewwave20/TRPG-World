"""add llm_api_keys and llm_models tables

Revision ID: 011_add_llm_settings
Revises: 010_add_judgments_data_to_story_logs
Create Date: 2026-02-14
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "011_add_llm_settings"
down_revision = "010_add_judgments_data_to_story_logs"
branch_labels = None
depends_on = None


def upgrade():
    """Create llm_api_keys and llm_models tables."""
    op.create_table(
        "llm_api_keys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(50), nullable=False, unique=True),
        sa.Column("provider_display", sa.String(100), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "llm_models",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model_id", sa.String(200), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    """Drop llm_models and llm_api_keys tables."""
    op.drop_table("llm_models")
    op.drop_table("llm_api_keys")
