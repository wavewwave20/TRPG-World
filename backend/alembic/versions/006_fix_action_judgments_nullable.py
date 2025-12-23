"""fix action_judgments nullable columns for 3-phase process

Revision ID: 006_fix_action_judgments_nullable
Revises: 005_add_3phase_process_fields
Create Date: 2025-12-17

This migration fixes the action_judgments table to allow NULL values
for dice_result, final_value, and outcome columns, which are required
for the 3-phase process where Phase 1 saves without dice results.

SQLite doesn't support ALTER COLUMN, so we need to recreate the table.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '006_fix_action_judgments_nullable'
down_revision = '005_add_3phase_process_fields'
branch_labels = None
depends_on = None


def upgrade():
    """Recreate action_judgments table with nullable columns."""
    # Create new table with correct schema
    op.create_table('action_judgments_new',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('character_id', sa.Integer(), nullable=False),
        sa.Column('story_log_id', sa.Integer(), nullable=True),
        sa.Column('action_text', sa.Text(), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=True),
        sa.Column('dice_result', sa.Integer(), nullable=True),  # Nullable for Phase 1
        sa.Column('modifier', sa.Integer(), nullable=False),
        sa.Column('final_value', sa.Integer(), nullable=True),  # Nullable for Phase 1
        sa.Column('difficulty', sa.Integer(), nullable=False),
        sa.Column('difficulty_reasoning', sa.Text(), nullable=True),
        sa.Column('outcome', sa.String(length=50), nullable=True),  # Nullable for Phase 1
        sa.Column('phase', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ),
        sa.ForeignKeyConstraint(['session_id'], ['game_sessions.id'], ),
        sa.ForeignKeyConstraint(['story_log_id'], ['story_logs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Copy data from old table
    op.execute('''
        INSERT INTO action_judgments_new
        (id, session_id, character_id, story_log_id, action_text, action_type,
         dice_result, modifier, final_value, difficulty, difficulty_reasoning,
         outcome, phase, created_at)
        SELECT id, session_id, character_id, story_log_id, action_text, action_type,
               dice_result, modifier, final_value, difficulty, difficulty_reasoning,
               outcome, phase, created_at
        FROM action_judgments
    ''')

    # Drop old table
    op.drop_table('action_judgments')

    # Rename new table
    op.rename_table('action_judgments_new', 'action_judgments')

    # Recreate index
    op.create_index(op.f('ix_action_judgments_id'), 'action_judgments', ['id'], unique=False)


def downgrade():
    """Revert to non-nullable columns (data loss possible)."""
    # Create old table schema
    op.create_table('action_judgments_old',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('character_id', sa.Integer(), nullable=False),
        sa.Column('story_log_id', sa.Integer(), nullable=True),
        sa.Column('action_text', sa.Text(), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=True),
        sa.Column('dice_result', sa.Integer(), nullable=False),
        sa.Column('modifier', sa.Integer(), nullable=False),
        sa.Column('final_value', sa.Integer(), nullable=False),
        sa.Column('difficulty', sa.Integer(), nullable=False),
        sa.Column('difficulty_reasoning', sa.Text(), nullable=True),
        sa.Column('outcome', sa.String(length=50), nullable=False),
        sa.Column('phase', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ),
        sa.ForeignKeyConstraint(['session_id'], ['game_sessions.id'], ),
        sa.ForeignKeyConstraint(['story_log_id'], ['story_logs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Copy data (only complete records)
    op.execute('''
        INSERT INTO action_judgments_old
        (id, session_id, character_id, story_log_id, action_text, action_type,
         dice_result, modifier, final_value, difficulty, difficulty_reasoning,
         outcome, phase, created_at)
        SELECT id, session_id, character_id, story_log_id, action_text, action_type,
               dice_result, modifier, final_value, difficulty, difficulty_reasoning,
               outcome, phase, created_at
        FROM action_judgments
        WHERE dice_result IS NOT NULL AND final_value IS NOT NULL AND outcome IS NOT NULL
    ''')

    # Drop new table
    op.drop_table('action_judgments')

    # Rename old table
    op.rename_table('action_judgments_old', 'action_judgments')

    # Recreate index
    op.create_index(op.f('ix_action_judgments_id'), 'action_judgments', ['id'], unique=False)
