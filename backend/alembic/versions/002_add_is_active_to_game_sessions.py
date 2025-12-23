"""add is_active to game_sessions

Revision ID: 002_add_is_active
Revises: 001_initial_schema
Create Date: 2025-12-15
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '002_add_is_active'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('game_sessions') as batch_op:
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
    # Remove server_default after population
    with op.batch_alter_table('game_sessions') as batch_op:
        batch_op.alter_column('is_active', server_default=None)


def downgrade():
    with op.batch_alter_table('game_sessions') as batch_op:
        batch_op.drop_column('is_active')

