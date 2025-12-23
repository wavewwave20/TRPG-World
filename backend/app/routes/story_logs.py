"""스토리 로그 API 라우트."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ActionJudgment, Character, GameSession, StoryLog
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

                print(f"📝 USER Message {log.id}: next_ai_log = {next_ai_log.id if next_ai_log else None}")

                # Get judgments from the next AI message
                if next_ai_log:
                    judgments = db.query(ActionJudgment).filter(ActionJudgment.story_log_id == next_ai_log.id).all()

                    print(f"🎲 Found {len(judgments)} judgments for AI message {next_ai_log.id}")

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
                        print(f"✅ Attaching {len(judgments_list)} judgments to USER message {log.id}")

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
