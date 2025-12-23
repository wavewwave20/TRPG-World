"""add index on session_participants (session_id, user_id)

Revision ID: 004_add_session_participants_index
Revises: 003_add_action_judgments
Create Date: 2025-12-17
"""


from alembic import op

# revision identifiers, used by Alembic.
revision = '004_add_session_participants_index'
down_revision = '003_add_action_judgments'
branch_labels = None
depends_on = None


def upgrade():
    """Add composite index on (session_id, user_id) for performance."""
    op.create_index(
        'idx_session_participants_session_user',
        'session_participants',
        ['session_id', 'user_id'],
        unique=False
    )


def downgrade():
    """Remove composite index on (session_id, user_id)."""
    op.drop_index(
        'idx_session_participants_session_user',
        table_name='session_participants'
    )
