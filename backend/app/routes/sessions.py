"""세션 관리 API 라우트."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    ActionJudgment,
    Character,
    CharacterGrowthLog,
    DiceRollState,
    GameSession,
    SessionParticipant,
    StoryAct,
    StoryLog,
)
from app.socket_server import sio
from app.utils.backups import backup_session
from app.utils.timezone import to_kst_iso

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionCreate(BaseModel):
    """Request model for creating a new game session."""

    host_user_id: int = Field(..., description="ID of the user hosting the session")
    title: str = Field(..., min_length=1, description="Session title")
    world_prompt: str | None = Field(default=None, description="AI system prompt for the game world")
    system_prompt: str | None = Field(default=None, description="Alias for world_prompt")

    class Config:
        json_schema_extra = {
            "example": {
                "host_user_id": 1,
                "title": "던전 탐험",
                "system_prompt": "중세 판타지 세계관에서 플레이어들은 고대 던전을 탐험합니다...",
            }
        }


class SessionResponse(BaseModel):
    """Response model for session creation."""

    session_id: int

    class Config:
        json_schema_extra = {"example": {"session_id": 1}}


class SessionJoinRequest(BaseModel):
    """Request model for joining a session."""

    user_id: int
    character_id: int

    class Config:
        json_schema_extra = {"example": {"user_id": 1, "character_id": 1}}


class SessionListItem(BaseModel):
    """Response model for session list item."""

    id: int
    title: str
    host_user_id: int
    participant_count: int
    created_at: str
    is_active: bool | None = None

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[SessionListItem])
async def list_sessions(db: Session = Depends(get_db)):
    """
    Get list of all game sessions with participant counts.

    Args:
        db: Database session dependency

    Returns:
        List of sessions with id, title, host_user_id, participant_count, and created_at
    """
    try:
        # Only show sessions where host is currently a participant
        # Query only active sessions with participant counts
        sessions_with_counts = (
            db.query(GameSession, func.count(SessionParticipant.id).label("participant_count"))
            .outerjoin(SessionParticipant, GameSession.id == SessionParticipant.session_id)
            .filter(GameSession.is_active.is_(True))
            .group_by(GameSession.id)
            .order_by(GameSession.created_at.desc())
            .all()
        )

        return [
            SessionListItem(
                id=session.id,
                title=session.title,
                host_user_id=session.host_user_id,
                participant_count=count,
                created_at=to_kst_iso(session.created_at),
                is_active=session.is_active,
            )
            for session, count in sessions_with_counts
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve sessions: {e!s}")


@router.post("/", response_model=SessionResponse, status_code=201)
async def create_session(session_data: SessionCreate, db: Session = Depends(get_db)):
    """
    Create a new game session.

    Args:
        session_data: Session creation data including host_user_id, title, and world_prompt
        db: Database session dependency

    Returns:
        SessionResponse containing the newly created session_id

    Raises:
        HTTPException 400: If title or world_prompt are empty
        HTTPException 500: If database operation fails

    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
    """
    # Validation: Check for empty title or system/world prompt (Requirement 4.1)
    if not session_data.title or not session_data.title.strip():
        raise HTTPException(status_code=400, detail="Title is required and cannot be empty")

    prompt_value = session_data.system_prompt if session_data.system_prompt is not None else session_data.world_prompt
    if not prompt_value or not prompt_value.strip():
        raise HTTPException(status_code=400, detail="System prompt is required and cannot be empty")

    try:
        # Create new session (Requirement 4.2)
        new_session = GameSession(
            host_user_id=session_data.host_user_id,
            title=session_data.title.strip(),
            world_prompt=prompt_value.strip(),
        )

        # Insert into database
        db.add(new_session)
        db.commit()
        db.refresh(new_session)

        # Return session ID (Requirement 4.3)
        return SessionResponse(session_id=new_session.id)

    except Exception as e:
        # Rollback on error
        db.rollback()

        # Error handling (Requirement 4.4)
        raise HTTPException(status_code=500, detail=f"Failed to create session: {e!s}")


@router.post("/{session_id}/join", status_code=200)
def join_session(session_id: int, join_data: SessionJoinRequest, db: Session = Depends(get_db)):
    """
    Join a session with a character.

    Args:
        session_id: Session ID to join
        join_data: User and character IDs
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException 404: If session or character not found
        HTTPException 400: If session is inactive or character doesn't belong to user
    """
    # Verify session exists
    session = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session with id {session_id} not found")
    if not session.is_active:
        raise HTTPException(status_code=400, detail="세션이 종료되었습니다.")

    # Verify character exists and belongs to user
    character = (
        db.query(Character)
        .filter(Character.id == join_data.character_id, Character.user_id == join_data.user_id)
        .first()
    )

    if not character:
        raise HTTPException(status_code=404, detail="Character not found or doesn't belong to user")

    # Check if already joined
    existing = (
        db.query(SessionParticipant)
        .filter(SessionParticipant.session_id == session_id, SessionParticipant.user_id == join_data.user_id)
        .first()
    )

    try:
        if existing:
            # Rejoin should be idempotent: refresh joined_at and allow character switch.
            existing.character_id = join_data.character_id
            existing.joined_at = datetime.utcnow()
            db.commit()
            return {
                "message": "Successfully rejoined session",
                "character_name": character.name,
                "rejoined": True,
            }

        # Create participant record
        db.add(
            SessionParticipant(
                session_id=session_id,
                user_id=join_data.user_id,
                character_id=join_data.character_id,
                joined_at=datetime.utcnow(),
            )
        )
        db.commit()

        return {
            "message": "Successfully joined session",
            "character_name": character.name,
            "rejoined": False,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to join session: {e!s}")


@router.post("/{session_id}/leave", status_code=200)
def leave_session(session_id: int, user_id: int, db: Session = Depends(get_db)):
    """
    Leave a session.

    Args:
        session_id: Session ID to leave
        user_id: User ID
        db: Database session

    Returns:
        Success message
    """
    participant = (
        db.query(SessionParticipant)
        .filter(SessionParticipant.session_id == session_id, SessionParticipant.user_id == user_id)
        .first()
    )

    if participant:
        db.delete(participant)
        db.commit()

    return {"message": "Successfully left session"}


class HostSessionItem(BaseModel):
    id: int
    title: str
    world_prompt: str
    system_prompt: str
    is_active: bool
    created_at: str
    participant_count: int
    story_log_count: int


class SessionUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, description="Updated session title")
    world_prompt: str | None = Field(default=None, description="Updated world prompt")
    system_prompt: str | None = Field(default=None, description="Alias for world_prompt")


class SessionDuplicateResponse(BaseModel):
    session_id: int
    message: str


@router.get("/host/{host_user_id}", response_model=list[HostSessionItem])
def list_host_sessions(host_user_id: int, db: Session = Depends(get_db)):
    """List all sessions created by the host (active and inactive)."""
    sessions_with_counts = (
        db.query(GameSession, func.count(SessionParticipant.id).label("participant_count"))
        .outerjoin(SessionParticipant, GameSession.id == SessionParticipant.session_id)
        .filter(GameSession.host_user_id == host_user_id)
        .group_by(GameSession.id)
        .order_by(GameSession.created_at.desc())
        .all()
    )
    return [
        HostSessionItem(
            id=s.id,
            title=s.title,
            world_prompt=s.world_prompt,
            system_prompt=s.world_prompt,
            is_active=s.is_active,
            created_at=to_kst_iso(s.created_at),
            participant_count=count,
            story_log_count=db.query(StoryLog).filter(StoryLog.session_id == s.id).count(),
        )
        for s, count in sessions_with_counts
    ]


@router.post("/{session_id}/end", status_code=200)
async def end_session(session_id: int, user_id: int, db: Session = Depends(get_db)):
    """End a session (host only): mark inactive and remove participants."""
    session = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.host_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the host can end the session")
    session.is_active = False
    # Backup story logs automatically before clearing participants
    try:
        backup_session(session_id)
    except Exception as e:
        # Non-fatal: proceed even if backup fails
        print(f"Backup failed for session {session_id}: {e}")
    db.query(SessionParticipant).filter(SessionParticipant.session_id == session_id).delete()
    db.commit()

    # Notify all clients in the room and close it
    room_name = f"session_{session_id}"
    try:
        await sio.emit("session_ended", {"session_id": session_id, "reason": "host_ended"}, room=room_name)
        await sio.close_room(room_name)
    except Exception as e:
        print(f"Failed to broadcast/close room for session {session_id}: {e}")

    return {"message": "Session ended"}


@router.post("/{session_id}/restart", status_code=200)
def restart_session(session_id: int, user_id: int, db: Session = Depends(get_db)):
    """Restart a previously ended session (host only): mark active again."""
    session = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.host_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the host can restart the session")
    session.is_active = True
    db.commit()
    return {"message": "Session restarted"}


@router.put("/{session_id}", status_code=200)
def update_session(
    session_id: int,
    payload: SessionUpdateRequest,
    user_id: int,
    db: Session = Depends(get_db),
):
    """Update an ended session's title/world prompt (host only)."""
    session = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.host_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the host can update the session")
    if session.is_active:
        raise HTTPException(status_code=400, detail="End the session before updating")

    title = payload.title.strip()
    prompt_value = payload.system_prompt if payload.system_prompt is not None else payload.world_prompt
    if prompt_value is None:
        raise HTTPException(status_code=400, detail="system_prompt (or world_prompt) is required")

    world_prompt = prompt_value.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required and cannot be empty")
    if not world_prompt:
        raise HTTPException(status_code=400, detail="System prompt is required and cannot be empty")

    session.title = title
    session.world_prompt = world_prompt
    db.commit()
    return {"message": "Session updated"}


@router.post("/{session_id}/duplicate", response_model=SessionDuplicateResponse, status_code=201)
def duplicate_session(session_id: int, user_id: int, db: Session = Depends(get_db)):
    """Duplicate an ended session (host only), including saved story history."""
    source = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Session not found")
    if source.host_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the host can duplicate the session")
    if source.is_active:
        raise HTTPException(status_code=400, detail="End the session before duplicating")

    try:
        # Create duplicated session in inactive state so host can manage before restart.
        cloned = GameSession(
            host_user_id=source.host_user_id,
            title=f"{source.title} (복제본)",
            world_prompt=source.world_prompt,
            ai_summary=source.ai_summary,
            is_active=False,
            created_at=datetime.utcnow(),
        )
        db.add(cloned)
        db.flush()

        # Copy story logs and keep old->new mapping.
        story_logs = (
            db.query(StoryLog)
            .filter(StoryLog.session_id == source.id)
            .order_by(StoryLog.id.asc())
            .all()
        )
        log_id_map: dict[int, int] = {}
        cloned_log_pairs: list[tuple[StoryLog, StoryLog]] = []
        for log in story_logs:
            new_log = StoryLog(
                session_id=cloned.id,
                role=log.role,
                content=log.content,
                act_id=None,  # resolve after acts are duplicated
                created_at=log.created_at,
            )
            db.add(new_log)
            db.flush()
            log_id_map[log.id] = new_log.id
            cloned_log_pairs.append((log, new_log))

        # Copy acts and keep old->new mapping.
        acts = (
            db.query(StoryAct)
            .filter(StoryAct.session_id == source.id)
            .order_by(StoryAct.id.asc())
            .all()
        )
        act_id_map: dict[int, int] = {}
        for act in acts:
            new_act = StoryAct(
                session_id=cloned.id,
                act_number=act.act_number,
                title=act.title,
                subtitle=act.subtitle,
                started_at=act.started_at,
                ended_at=act.ended_at,
                start_story_log_id=log_id_map.get(act.start_story_log_id) if act.start_story_log_id else None,
                end_story_log_id=log_id_map.get(act.end_story_log_id) if act.end_story_log_id else None,
            )
            db.add(new_act)
            db.flush()
            act_id_map[act.id] = new_act.id

        # Backfill StoryLog.act_id using duplicated act IDs.
        for old_log, new_log in cloned_log_pairs:
            if old_log.act_id and old_log.act_id in act_id_map:
                new_log.act_id = act_id_map[old_log.act_id]

        # Copy action judgments so prior rounds and result history stay visible.
        judgments = (
            db.query(ActionJudgment)
            .filter(ActionJudgment.session_id == source.id)
            .order_by(ActionJudgment.id.asc())
            .all()
        )
        for j in judgments:
            db.add(
                ActionJudgment(
                    session_id=cloned.id,
                    character_id=j.character_id,
                    story_log_id=log_id_map.get(j.story_log_id) if j.story_log_id else None,
                    action_text=j.action_text,
                    action_type=j.action_type,
                    dice_result=j.dice_result,
                    modifier=j.modifier,
                    final_value=j.final_value,
                    difficulty=j.difficulty,
                    difficulty_reasoning=j.difficulty_reasoning,
                    outcome=j.outcome,
                    phase=j.phase,
                    created_at=j.created_at,
                )
            )

        # Copy growth logs if acts were duplicated.
        growth_logs = (
            db.query(CharacterGrowthLog)
            .filter(CharacterGrowthLog.session_id == source.id)
            .order_by(CharacterGrowthLog.id.asc())
            .all()
        )
        for g in growth_logs:
            new_act_id = act_id_map.get(g.act_id)
            if not new_act_id:
                continue
            db.add(
                CharacterGrowthLog(
                    session_id=cloned.id,
                    act_id=new_act_id,
                    character_id=g.character_id,
                    growth_type=g.growth_type,
                    growth_detail=g.growth_detail,
                    narrative_reason=g.narrative_reason,
                    applied_at=g.applied_at,
                )
            )

        db.commit()
        return SessionDuplicateResponse(session_id=cloned.id, message="Session duplicated")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to duplicate session: {e!s}")


@router.delete("/{session_id}", status_code=200)
def delete_session(session_id: int, user_id: int, db: Session = Depends(get_db)):
    """Delete a session (host only). Only allowed from host management list.

    If the session is active, require it to be ended first to prevent accidental deletion.
    """
    session = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.host_user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the host can delete the session")
    if session.is_active:
        raise HTTPException(status_code=400, detail="End the session before deleting")

    try:
        # Remove related rows in dependency order.
        db.query(SessionParticipant).filter(SessionParticipant.session_id == session_id).delete()
        db.query(DiceRollState).filter(DiceRollState.session_id == session_id).delete()
        db.query(CharacterGrowthLog).filter(CharacterGrowthLog.session_id == session_id).delete()
        db.query(ActionJudgment).filter(ActionJudgment.session_id == session_id).delete()
        db.query(StoryLog).filter(StoryLog.session_id == session_id).update({"act_id": None})
        db.query(StoryAct).filter(StoryAct.session_id == session_id).update(
            {"start_story_log_id": None, "end_story_log_id": None}
        )
        db.query(StoryAct).filter(StoryAct.session_id == session_id).delete()
        db.query(StoryLog).filter(StoryLog.session_id == session_id).delete()
        # Remove the session
        db.delete(session)
        db.commit()
        return {"message": "Session deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {e}")


@router.get("/{session_id}/current-act")
def get_current_act(session_id: int, db: Session = Depends(get_db)):
    """현재 진행 중인 막 정보를 반환합니다.

    재접속 시 현재 막을 로드하기 위해 사용합니다.
    """
    from app.services.context_loader import get_current_act as _get_current_act

    act = _get_current_act(db, session_id)
    if not act:
        return None
    return act.model_dump()


@router.get("/{session_id}/acts")
def get_session_acts(session_id: int, db: Session = Depends(get_db)):
    """세션의 모든 막 정보를 반환합니다."""
    from app.services.context_loader import get_all_acts

    acts = get_all_acts(db, session_id)
    return [act.model_dump() for act in acts]


@router.get("/{session_id}/growth-history")
def get_growth_history(session_id: int, db: Session = Depends(get_db)):
    """세션의 성장 보상 기록을 act별로 그룹화하여 반환합니다."""
    logs = (
        db.query(CharacterGrowthLog)
        .filter(CharacterGrowthLog.session_id == session_id)
        .order_by(CharacterGrowthLog.applied_at.asc())
        .all()
    )
    if not logs:
        return []

    # 캐릭터 이름 resolve
    char_ids = {log.character_id for log in logs}
    char_name_map = {
        c.id: c.name
        for c in db.query(Character).filter(Character.id.in_(char_ids)).all()
    }

    # act 정보 resolve
    act_ids = {log.act_id for log in logs}
    acts = {
        a.id: a
        for a in db.query(StoryAct).filter(StoryAct.id.in_(act_ids)).all()
    }

    # act별 그룹화
    from collections import defaultdict
    grouped: dict[int, list] = defaultdict(list)
    for log in logs:
        grouped[log.act_id].append({
            "character_id": log.character_id,
            "character_name": char_name_map.get(log.character_id, f"캐릭터 {log.character_id}"),
            "growth_type": log.growth_type,
            "growth_detail": log.growth_detail,
            "narrative_reason": log.narrative_reason,
        })

    result = []
    for act_id, rewards in grouped.items():
        act = acts.get(act_id)
        result.append({
            "act_id": act_id,
            "act_number": act.act_number if act else 0,
            "act_title": act.title if act else "???",
            "act_subtitle": act.subtitle if act else None,
            "rewards": rewards,
        })

    result.sort(key=lambda x: x["act_number"])
    return result
