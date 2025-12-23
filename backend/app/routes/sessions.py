"""세션 관리 API 라우트."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Character, GameSession, SessionParticipant, StoryLog
from app.socket_server import sio
from app.utils.backups import backup_session
from app.utils.timezone import to_kst_iso

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionCreate(BaseModel):
    """Request model for creating a new game session."""

    host_user_id: int = Field(..., description="ID of the user hosting the session")
    title: str = Field(..., min_length=1, description="Session title")
    world_prompt: str = Field(..., min_length=1, description="AI system prompt for the game world")

    class Config:
        json_schema_extra = {
            "example": {
                "host_user_id": 1,
                "title": "던전 탐험",
                "world_prompt": "중세 판타지 세계관에서 플레이어들은 고대 던전을 탐험합니다...",
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
            .filter(GameSession.is_active == True)
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
    # Validation: Check for empty title or world_prompt (Requirement 4.1)
    if not session_data.title or not session_data.title.strip():
        raise HTTPException(status_code=400, detail="Title is required and cannot be empty")

    if not session_data.world_prompt or not session_data.world_prompt.strip():
        raise HTTPException(status_code=400, detail="World prompt is required and cannot be empty")

    try:
        # Create new session (Requirement 4.2)
        new_session = GameSession(
            host_user_id=session_data.host_user_id,
            title=session_data.title.strip(),
            world_prompt=session_data.world_prompt.strip(),
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
        HTTPException 400: If already joined or character doesn't belong to user
    """
    # Verify session exists
    session = db.query(GameSession).filter(GameSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session with id {session_id} not found")

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

    if existing:
        raise HTTPException(status_code=400, detail="User already joined this session")

    try:
        # Create participant record
        participant = SessionParticipant(
            session_id=session_id,
            user_id=join_data.user_id,
            character_id=join_data.character_id,
            joined_at=datetime.utcnow(),
        )

        db.add(participant)
        db.commit()

        return {"message": "Successfully joined session", "character_name": character.name}

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
    is_active: bool
    created_at: str
    participant_count: int


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
            is_active=s.is_active,
            created_at=to_kst_iso(s.created_at),
            participant_count=count,
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
        # Remove related participants and story logs
        db.query(SessionParticipant).filter(SessionParticipant.session_id == session_id).delete()
        db.query(StoryLog).filter(StoryLog.session_id == session_id).delete()
        # Remove the session
        db.delete(session)
        db.commit()
        return {"message": "Session deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {e}")
