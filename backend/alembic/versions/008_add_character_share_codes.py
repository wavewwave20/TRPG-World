"""add character_share_codes table

Revision ID: 008_add_character_share_codes
Revises: 007_add_story_acts_and_growth
Create Date: 2026-02-13
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "008_add_character_share_codes"
down_revision = "007_add_story_acts_and_growth"
branch_labels = None
depends_on = None


def upgrade():
    """Create character_share_codes table for cross-user character sharing."""
    op.create_table(
        "character_share_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=9), nullable=False),
        sa.Column("source_character_id", sa.Integer(), nullable=False),
        sa.Column("source_user_id", sa.Integer(), nullable=False),
        sa.Column("redeemed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["source_character_id"], ["characters.id"]),
        sa.ForeignKeyConstraint(["source_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["redeemed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_character_share_codes_id"), "character_share_codes", ["id"], unique=False)
    op.create_index(op.f("ix_character_share_codes_code"), "character_share_codes", ["code"], unique=True)


def downgrade():
    """Drop character_share_codes table."""
    op.drop_index(op.f("ix_character_share_codes_code"), table_name="character_share_codes")
    op.drop_index(op.f("ix_character_share_codes_id"), table_name="character_share_codes")
    op.drop_table("character_share_codes")
