"""add action_judgments table

Revision ID: 003_add_action_judgments
Revises: 002_add_is_active
Create Date: 2025-12-16
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '003_add_action_judgments'
down_revision = '002_add_is_active'
branch_labels = None
depends_on = None


def upgrade():
    """Create action_judgments table for storing AI judgment results."""
    op.create_table('action_judgments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('character_id', sa.Integer(), nullable=False),
        sa.Column('story_log_id', sa.Integer(), nullable=True),
        sa.Column('action_text', sa.Text(), nullable=False),
        sa.Column('dice_result', sa.Integer(), nullable=False),
        sa.Column('modifier', sa.Integer(), nullable=False),
        sa.Column('final_value', sa.Integer(), nullable=False),
        sa.Column('difficulty', sa.Integer(), nullable=False),
        sa.Column('difficulty_reasoning', sa.Text(), nullable=True),
        sa.Column('outcome', sa.String(length=50), nullable=False),
        sa.Column('outcome_reasoning', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ),
        sa.ForeignKeyConstraint(['session_id'], ['game_sessions.id'], ),
        sa.ForeignKeyConstraint(['story_log_id'], ['story_logs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_action_judgments_id'), 'action_judgments', ['id'], unique=False)


def downgrade():
    """Drop action_judgments table."""
    op.drop_index(op.f('ix_action_judgments_id'), table_name='action_judgments')
    op.drop_table('action_judgments')
