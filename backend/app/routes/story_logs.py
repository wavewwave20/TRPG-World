"""스토리 로그 API 라우트."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ActionJudgment, Character, GameSession, StoryAct, StoryLog
from app.services.session_activity_logger import log_session_activity
from app.utils.timezone import to_kst_iso

router = APIRouter(prefix="/api/story_logs", tags=["story_logs"])


class JudgmentSummary(BaseModel):
    """Summary of a judgment result for display in chat."""

    id: int
    character_id: int
    character_name: str
    action_text: str
    action_type: str | None
    dice_result: int | None
    modifier: int
    final_value: int | None
    difficulty: int
    outcome: str | None

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "character_id": 1,
                "character_name": "엘프 궁수",
                "action_text": "나는 활을 쏜다",
                "action_type": "dexterity",
                "dice_result": 15,
                "modifier": 3,
                "final_value": 18,
                "difficulty": 15,
                "outcome": "success",
            }
        }


class StoryLogResponse(BaseModel):
    """Response model for a single story log entry."""

    id: int
    role: str
    content: str
    created_at: str
    judgments: list[JudgmentSummary] | None = None
    event_triggered: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "role": "USER",
                "content": "엘프 궁수: 나는 활을 쏜다\n드워프 전사: 나는 도끼를 휘두른다",
                "created_at": "2025-12-15T10:30:00",
                "judgments": None,
            }
        }


class StoryLogsListResponse(BaseModel):
    """Response model for list of story logs."""

    session_id: int
    logs: list[StoryLogResponse]

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": 1,
                "logs": [
                    {
                        "id": 1,
                        "role": "USER",
                        "content": "엘프 궁수: 나는 활을 쏜다",
                        "created_at": "2025-12-15T10:30:00",
                    },
                    {
                        "id": 2,
                        "role": "AI",
                        "content": "화살이 목표물을 향해 날아갑니다...",
                        "created_at": "2025-12-15T10:31:00",
                    },
                ],
            }
        }


class StoryLogCreateRequest(BaseModel):
    """Request model for creating a story log entry."""

    role: str = Field(..., description="Either USER or AI")
    content: str = Field(..., min_length=1, description="Story message content")


class StoryLogUpdateRequest(BaseModel):
    """Request model for updating a story log entry."""

    role: str | None = Field(default=None, description="Either USER or AI")
    content: str | None = Field(default=None, description="Updated story message content")


def _to_judgment_summary(
    judgment: ActionJudgment,
    char_name_map: dict[int, str],
) -> JudgmentSummary:
    """Convert ActionJudgment ORM row to API summary payload."""
    return JudgmentSummary(
        id=judgment.id,
        character_id=judgment.character_id,
        character_name=char_name_map.get(judgment.character_id, "Unknown"),
        action_text=judgment.action_text,
        action_type=judgment.action_type,
        dice_result=judgment.dice_result,
        modifier=judgment.modifier,
        final_value=judgment.final_value,
        difficulty=judgment.difficulty,
        outcome=judgment.outcome,
    )


def _normalize_role(role: str) -> str:
    normalized = role.strip().upper()
    if normalized not in {"USER", "AI"}:
        raise HTTPException(status_code=400, detail="role must be either USER or AI")
    return normalized


def _ensure_host_manageable_session(session: GameSession | None, user_id: int) -> GameSession:
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.host_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the host can manage story logs")
    if session.is_active:
        raise HTTPException(status_code=400, detail="End the session before managing story logs")
    return session


@router.get("/{session_id}", response_model=StoryLogsListResponse)
async def get_story_logs(session_id: int, db: Session = Depends(get_db)):
    """
    Get all story logs for a session in chronological order.

    For AI messages, includes associated judgment results.

    Args:
        session_id: ID of the game session
        db: Database session dependency

    Returns:
        StoryLogsListResponse containing session_id and list of logs

    Raises:
        HTTPException 404: If session does not exist
        HTTPException 500: If database operation fails

    Requirements: 7.5
    """
    try:
        # Verify session exists in database (Requirement 7.5)
        session = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail=f"Session with id {session_id} not found")

        # Query StoryLog table ordered by created_at ascending (Requirement 7.5)
        logs = db.query(StoryLog).filter(StoryLog.session_id == session_id).order_by(StoryLog.created_at.asc()).all()

        # Query all linked judgments once and group by story_log_id for display.
        linked_judgments = (
            db.query(ActionJudgment)
            .filter(ActionJudgment.session_id == session_id, ActionJudgment.story_log_id.isnot(None))
            .order_by(ActionJudgment.id.asc())
            .all()
        )

        judgments_by_story_log_id: dict[int, list[ActionJudgment]] = {}
        for judgment in linked_judgments:
            if judgment.story_log_id is None:
                continue
            judgments_by_story_log_id.setdefault(judgment.story_log_id, []).append(judgment)

        # Build character name lookup
        characters = db.query(Character).all()
        char_name_map = {c.id: c.name for c in characters}

        # Build response with judgments.
        # Display policy:
        # - USER log: primary source is judgments_data snapshot.
        # - Also merge any additional judgments linked to the next AI log
        #   (e.g., orphan/duplicate data from previous flows) so host can manage them
        #   from the USER-side action context.
        # - AI log: do not attach judgments in API response.
        response_logs = []
        for i, log in enumerate(logs):
            judgments_list = None

            if log.role == "USER":
                merged_judgments: list[JudgmentSummary] = []
                snapshot_ids: set[int] = set()

                if log.judgments_data:
                    # 우선: StoryLog에 직접 저장된 판정 스냅샷 사용
                    for j_data in log.judgments_data:
                        summary = JudgmentSummary(**j_data)
                        merged_judgments.append(summary)
                        snapshot_ids.add(summary.id)

                # 하위호환 + 관리 편의: 직후 AI 로그에 연결된 판정도 USER 로그에 병합 표시
                next_ai_log = None
                for j in range(i + 1, len(logs)):
                    if logs[j].role == "AI":
                        next_ai_log = logs[j]
                        break

                if next_ai_log:
                    linked_judgments_for_next_ai = judgments_by_story_log_id.get(next_ai_log.id, [])
                    for judgment in linked_judgments_for_next_ai:
                        if judgment.id in snapshot_ids:
                            continue
                        merged_judgments.append(_to_judgment_summary(judgment, char_name_map))

                if merged_judgments:
                    judgments_list = merged_judgments

            response_logs.append(
                StoryLogResponse(
                    id=log.id,
                    role=log.role,
                    content=log.content,
                    created_at=to_kst_iso(log.created_at),
                    judgments=judgments_list,
                    event_triggered=log.event_triggered,
                )
            )

        return StoryLogsListResponse(session_id=session_id, logs=response_logs)

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(status_code=500, detail=f"Failed to retrieve story logs: {e!s}")


@router.post("/{session_id}/entries", response_model=StoryLogResponse, status_code=201)
def create_story_log(
    session_id: int,
    payload: StoryLogCreateRequest,
    user_id: int,
    db: Session = Depends(get_db),
):
    """Create a story log entry for an ended session (host only)."""
    session = db.query(GameSession).filter(GameSession.id == session_id).first()
    _ensure_host_manageable_session(session, user_id)

    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="content cannot be empty")

    new_log = StoryLog(
        session_id=session_id,
        role=_normalize_role(payload.role),
        content=content,
        created_at=datetime.utcnow(),
    )

    try:
        db.add(new_log)
        db.flush()
        log_session_activity(
            db,
            session_id=session_id,
            actor_user_id=user_id,
            source="api",
            action_type="story.create",
            status="success",
            message="스토리 메시지 추가",
            detail={"story_log_id": new_log.id, "role": new_log.role},
        )
        db.commit()
        db.refresh(new_log)
        return StoryLogResponse(
            id=new_log.id,
            role=new_log.role,
            content=new_log.content,
            created_at=to_kst_iso(new_log.created_at),
            judgments=None,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create story log: {e!s}")


@router.put("/entry/{log_id}", response_model=StoryLogResponse)
def update_story_log(
    log_id: int,
    payload: StoryLogUpdateRequest,
    user_id: int,
    db: Session = Depends(get_db),
):
    """Update a story log entry for an ended session (host only)."""
    log = db.query(StoryLog).filter(StoryLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Story log not found")

    session = db.query(GameSession).filter(GameSession.id == log.session_id).first()
    _ensure_host_manageable_session(session, user_id)

    if payload.role is None and payload.content is None:
        raise HTTPException(status_code=400, detail="No update fields provided")

    if payload.role is not None:
        log.role = _normalize_role(payload.role)

    if payload.content is not None:
        content = payload.content.strip()
        if not content:
            raise HTTPException(status_code=400, detail="content cannot be empty")
        log.content = content

    try:
        log_session_activity(
            db,
            session_id=log.session_id,
            actor_user_id=user_id,
            source="api",
            action_type="story.update",
            status="success",
            message="스토리 메시지 수정",
            detail={"story_log_id": log.id, "role": log.role},
        )
        db.commit()
        db.refresh(log)
        return StoryLogResponse(
            id=log.id,
            role=log.role,
            content=log.content,
            created_at=to_kst_iso(log.created_at),
            judgments=None,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update story log: {e!s}")


@router.delete("/entry/{log_id}", status_code=200)
def delete_story_log(log_id: int, user_id: int, db: Session = Depends(get_db)):
    """Delete a story log entry for an ended session (host only)."""
    log = db.query(StoryLog).filter(StoryLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Story log not found")

    session = db.query(GameSession).filter(GameSession.id == log.session_id).first()
    _ensure_host_manageable_session(session, user_id)

    try:
        session_id = log.session_id
        detached_judgments = (
            db.query(ActionJudgment)
            .filter(ActionJudgment.story_log_id == log.id)
            .update({"story_log_id": None, "phase": 2})
        )
        db.query(StoryAct).filter(StoryAct.start_story_log_id == log.id).update({"start_story_log_id": None})
        db.query(StoryAct).filter(StoryAct.end_story_log_id == log.id).update({"end_story_log_id": None})
        log_session_activity(
            db,
            session_id=session_id,
            actor_user_id=user_id,
            source="api",
            action_type="story.delete",
            status="success",
            message="스토리 메시지 삭제",
            detail={"story_log_id": log.id, "detached_judgment_count": detached_judgments},
        )
        db.delete(log)
        db.commit()
        return {
            "message": "Story log deleted",
            "detached_judgment_count": detached_judgments,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete story log: {e!s}")


@router.delete("/judgment/{judgment_id}", status_code=200)
def delete_judgment(judgment_id: int, user_id: int, db: Session = Depends(get_db)):
    """Delete a single action judgment for an ended session (host only)."""
    judgment = db.query(ActionJudgment).filter(ActionJudgment.id == judgment_id).first()
    if not judgment:
        raise HTTPException(status_code=404, detail="Judgment not found")

    session = db.query(GameSession).filter(GameSession.id == judgment.session_id).first()
    _ensure_host_manageable_session(session, user_id)

    try:
        session_id = judgment.session_id
        removed_from_snapshots = 0
        user_logs = (
            db.query(StoryLog)
            .filter(StoryLog.session_id == judgment.session_id, StoryLog.role == "USER")
            .all()
        )

        # Keep USER snapshot data consistent if it references the removed judgment.
        for user_log in user_logs:
            if not user_log.judgments_data:
                continue
            original_items = user_log.judgments_data
            filtered_items = [item for item in original_items if item.get("id") != judgment.id]
            if len(filtered_items) != len(original_items):
                removed_from_snapshots += len(original_items) - len(filtered_items)
                user_log.judgments_data = filtered_items or None

        log_session_activity(
            db,
            session_id=session_id,
            actor_user_id=user_id,
            actor_character_id=judgment.character_id,
            source="api",
            action_type="story.judgment_delete",
            status="success",
            message="행동 메시지 삭제",
            detail={"judgment_id": judgment.id, "removed_from_snapshots": removed_from_snapshots},
        )
        db.delete(judgment)
        db.commit()
        return {
            "message": "Judgment deleted",
            "removed_from_snapshots": removed_from_snapshots,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete judgment: {e!s}")
