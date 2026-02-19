"""add story_flow_metrics table and host_instruction to game_sessions

Revision ID: 013_add_story_flow_metrics_and_host_instruction
Revises: 012_add_event_triggered_to_story_logs
Create Date: 2026-02-20
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "013_add_story_flow_metrics_and_host_instruction"
down_revision = "012_add_event_triggered_to_story_logs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "game_sessions",
        sa.Column("host_instruction", sa.Text(), nullable=False, server_default=""),
    )

    op.create_table(
        "story_flow_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("game_sessions.id"), nullable=False),
        sa.Column("story_log_id", sa.Integer(), sa.ForeignKey("story_logs.id"), nullable=True),
        sa.Column("act_id", sa.Integer(), sa.ForeignKey("story_acts.id"), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("tension", sa.Integer(), nullable=False, server_default="45"),
        sa.Column("consecutive_crisis", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("judgments_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("critical_failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("critical_success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("auto_success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("host_instruction_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("host_instruction_length", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_story_flow_metrics_session_id", "story_flow_metrics", ["session_id"])
    op.create_index("ix_story_flow_metrics_story_log_id", "story_flow_metrics", ["story_log_id"])
    op.create_index("ix_story_flow_metrics_act_id", "story_flow_metrics", ["act_id"])
    op.create_index("ix_story_flow_metrics_created_at", "story_flow_metrics", ["created_at"])


def downgrade():
    op.drop_index("ix_story_flow_metrics_created_at", table_name="story_flow_metrics")
    op.drop_index("ix_story_flow_metrics_act_id", table_name="story_flow_metrics")
    op.drop_index("ix_story_flow_metrics_story_log_id", table_name="story_flow_metrics")
    op.drop_index("ix_story_flow_metrics_session_id", table_name="story_flow_metrics")
    op.drop_table("story_flow_metrics")

    op.drop_column("game_sessions", "host_instruction")
