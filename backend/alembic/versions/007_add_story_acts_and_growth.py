"""add story_acts, character_growth_logs, and story_logs.act_id

Revision ID: 007_add_story_acts_and_growth
Revises: 006_fix_action_judgments_nullable
Create Date: 2025-12-18

스토리 막(Act) 시스템과 캐릭터 성장 시스템을 위한 테이블을 추가합니다.
- story_acts: 막 정보 (번호, 제목, 부제, 시작/종료 시각)
- character_growth_logs: 캐릭터 성장 기록 (막 종료 시 보상)
- story_logs.act_id: StoryLog와 StoryAct 연결
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "007_add_story_acts_and_growth"
down_revision = "006_fix_action_judgments_nullable"
branch_labels = None
depends_on = None


def upgrade():
    # 1. story_acts 테이블 생성
    op.create_table(
        "story_acts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("game_sessions.id"),
            nullable=False,
        ),
        sa.Column("act_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("subtitle", sa.String(200), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column(
            "start_story_log_id",
            sa.Integer(),
            sa.ForeignKey("story_logs.id"),
            nullable=True,
        ),
        sa.Column(
            "end_story_log_id",
            sa.Integer(),
            sa.ForeignKey("story_logs.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_story_acts_id", "story_acts", ["id"])
    op.create_index("ix_story_acts_session_id", "story_acts", ["session_id"])

    # 2. character_growth_logs 테이블 생성
    op.create_table(
        "character_growth_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("game_sessions.id"),
            nullable=False,
        ),
        sa.Column(
            "act_id",
            sa.Integer(),
            sa.ForeignKey("story_acts.id"),
            nullable=False,
        ),
        sa.Column(
            "character_id",
            sa.Integer(),
            sa.ForeignKey("characters.id"),
            nullable=False,
        ),
        sa.Column("growth_type", sa.String(50), nullable=False),
        sa.Column("growth_detail", sa.JSON(), nullable=False),
        sa.Column("narrative_reason", sa.Text(), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_character_growth_logs_id", "character_growth_logs", ["id"])

    # 3. story_logs에 act_id 컬럼 추가 (nullable)
    # SQLite는 ALTER TABLE로 FK 제약조건 추가를 지원하지 않으므로 batch mode 사용
    with op.batch_alter_table("story_logs") as batch_op:
        batch_op.add_column(
            sa.Column("act_id", sa.Integer(), nullable=True),
        )
        batch_op.create_foreign_key(
            "fk_story_logs_act_id",
            "story_acts",
            ["act_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("story_logs") as batch_op:
        batch_op.drop_constraint("fk_story_logs_act_id", type_="foreignkey")
        batch_op.drop_column("act_id")
    op.drop_table("character_growth_logs")
    op.drop_table("story_acts")
