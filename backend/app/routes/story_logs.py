"""스토리 로그 API 라우트."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ActionJudgment, Character, GameSession, StoryAct, StoryLog
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

        # Build character name lookup
        characters = db.query(Character).all()
        char_name_map = {c.id: c.name for c in characters}

        # Build response with judgments
        # For USER messages, attach judgments from the next AI message
        # For AI messages, attach judgments directly linked to them
        response_logs = []
        for i, log in enumerate(logs):
            judgments_list = None

            if log.role == "USER":
                # Find the next AI message
                next_ai_log = None
                for j in range(i + 1, len(logs)):
                    if logs[j].role == "AI":
                        next_ai_log = logs[j]
                        break

                # Get judgments from the next AI message
                if next_ai_log:
                    judgments = db.query(ActionJudgment).filter(ActionJudgment.story_log_id == next_ai_log.id).all()

                    if judgments:
                        judgments_list = [
                            JudgmentSummary(
                                id=j.id,
                                character_id=j.character_id,
                                character_name=char_name_map.get(j.character_id, "Unknown"),
                                action_text=j.action_text,
                                action_type=j.action_type,
                                dice_result=j.dice_result,
                                modifier=j.modifier,
                                final_value=j.final_value,
                                difficulty=j.difficulty,
                                outcome=j.outcome,
                            )
                            for j in judgments
                        ]

            response_logs.append(
                StoryLogResponse(
                    id=log.id,
                    role=log.role,
                    content=log.content,
                    created_at=to_kst_iso(log.created_at),
                    judgments=judgments_list,
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
        detached_judgments = (
            db.query(ActionJudgment)
            .filter(ActionJudgment.story_log_id == log.id)
            .update({"story_log_id": None})
        )
        db.query(StoryAct).filter(StoryAct.start_story_log_id == log.id).update({"start_story_log_id": None})
        db.query(StoryAct).filter(StoryAct.end_story_log_id == log.id).update({"end_story_log_id": None})
        db.delete(log)
        db.commit()
        return {
            "message": "Story log deleted",
            "detached_judgment_count": detached_judgments,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete story log: {e!s}")
