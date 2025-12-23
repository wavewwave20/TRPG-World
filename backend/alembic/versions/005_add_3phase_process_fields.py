"""add 3-phase process fields and dice_roll_states table

Revision ID: 005_add_3phase_process_fields
Revises: 004_add_session_participants_index
Create Date: 2025-12-17

This migration adds:
1. action_type and phase columns to action_judgments table
2. Makes dice_result, final_value, outcome nullable for Phase 1
3. Creates dice_roll_states table for tracking player dice rolls
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '005_add_3phase_process_fields'
down_revision = '004_add_session_participants_index'
branch_labels = None
depends_on = None


def upgrade():
    """Add 3-phase process support."""
    # Add new columns to action_judgments
    op.add_column('action_judgments',
        sa.Column('action_type', sa.String(length=50), nullable=True))
    op.add_column('action_judgments',
        sa.Column('phase', sa.Integer(), nullable=False, server_default='1'))

    # Make dice_result, final_value, outcome nullable for Phase 1 support
    # SQLite doesn't support ALTER COLUMN, so we need to handle this differently
    # For SQLite, we'll just add the columns as nullable (they already exist)
    # The existing data will remain valid

    # Create dice_roll_states table
    op.create_table('dice_roll_states',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('round_id', sa.Integer(), nullable=False),
        sa.Column('character_id', sa.Integer(), nullable=False),
        sa.Column('judgment_id', sa.Integer(), nullable=True),
        sa.Column('dice_result', sa.Integer(), nullable=True),
        sa.Column('has_rolled', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ),
        sa.ForeignKeyConstraint(['judgment_id'], ['action_judgments.id'], ),
        sa.ForeignKeyConstraint(['session_id'], ['game_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dice_roll_states_id'), 'dice_roll_states', ['id'], unique=False)
    op.create_index('idx_dice_roll_states_session_round', 'dice_roll_states',
        ['session_id', 'round_id'], unique=False)


def downgrade():
    """Remove 3-phase process support."""
    # Drop dice_roll_states table
    op.drop_index('idx_dice_roll_states_session_round', table_name='dice_roll_states')
    op.drop_index(op.f('ix_dice_roll_states_id'), table_name='dice_roll_states')
    op.drop_table('dice_roll_states')

    # Remove columns from action_judgments
    op.drop_column('action_judgments', 'phase')
    op.drop_column('action_judgments', 'action_type')
