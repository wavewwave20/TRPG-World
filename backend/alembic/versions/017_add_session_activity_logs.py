"""add session activity logs table

Revision ID: 017_add_session_activity_logs
Revises: 016_add_llm_model_purposes
Create Date: 2026-03-04
"""

import sqlalchemy as sa
from alembic import op

revision = "017_add_session_activity_logs"
down_revision = "016_add_llm_model_purposes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "session_activity_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_character_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default=sa.text("'system'")),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'info'")),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("dedupe_key", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["actor_character_id"], ["characters.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["game_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_session_activity_logs_id"), "session_activity_logs", ["id"], unique=False)
    op.create_index(
        op.f("ix_session_activity_logs_session_id"),
        "session_activity_logs",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_session_activity_logs_actor_user_id"),
        "session_activity_logs",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_session_activity_logs_actor_character_id"),
        "session_activity_logs",
        ["actor_character_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_session_activity_logs_action_type"),
        "session_activity_logs",
        ["action_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_session_activity_logs_dedupe_key"),
        "session_activity_logs",
        ["dedupe_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_session_activity_logs_created_at"),
        "session_activity_logs",
        ["created_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_session_activity_logs_created_at"), table_name="session_activity_logs")
    op.drop_index(op.f("ix_session_activity_logs_dedupe_key"), table_name="session_activity_logs")
    op.drop_index(op.f("ix_session_activity_logs_action_type"), table_name="session_activity_logs")
    op.drop_index(op.f("ix_session_activity_logs_actor_character_id"), table_name="session_activity_logs")
    op.drop_index(op.f("ix_session_activity_logs_actor_user_id"), table_name="session_activity_logs")
    op.drop_index(op.f("ix_session_activity_logs_session_id"), table_name="session_activity_logs")
    op.drop_index(op.f("ix_session_activity_logs_id"), table_name="session_activity_logs")
    op.drop_table("session_activity_logs")

