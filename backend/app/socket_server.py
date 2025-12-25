"""실시간 통신을 위한 Socket.io 서버."""

import asyncio
import logging
import os
import time

import socketio
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ActionJudgment, Character, GameSession, SessionParticipant, StoryLog
from app.utils.backups import backup_session
from app.utils.timezone import to_kst_iso

# Logger for AI-related events
logger = logging.getLogger("ai_gm.socket")

# Create AsyncServer instance with ASGI mode
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*", logger=True, engineio_logger=True)

# In-memory Action Queue (volatile storage)
# Structure: {session_id: [actions]}
# Each action is a dict with: id, player_id, character_name, action_text, order
action_queues = {}

# Global counter for unique action IDs
action_counter = 0

# Track socket connections to sessions
# Structure: {sid: {'session_id': int, 'user_id': int}}
socket_sessions = {}

# Track pending dice rolls for 3-phase process
# Structure: {session_id: {'round_id': int, 'pending_characters': set, 'analyses': dict}}
pending_dice_rolls: dict[int, dict] = {}

# Presence tracking for session page heartbeat
# Structure: {sid: { 'session_id': int, 'user_id': int, 'last_ts': float }}
session_presence: dict[str, dict] = {}

# Background presence monitor control
_presence_task_started = False

HEARTBEAT_INTERVAL_SEC = 5
# Allow one miss => disconnect after 2 missed intervals
HEARTBEAT_TIMEOUT_SEC = HEARTBEAT_INTERVAL_SEC * 2 + 0.5  # small buffer


# ===== Participant Management Helper Functions =====


def add_participant(db: Session, session_id: int, user_id: int, character_id: int) -> SessionParticipant:
    """
    Add or update a participant record.
    Handles duplicate prevention by checking for existing records.

    Args:
        db: Database session
        session_id: The game session ID
        user_id: The user ID
        character_id: The character ID being used

    Returns:
        SessionParticipant: The created or updated participant record

    Raises:
        Exception: If database operation fails (caller should handle rollback)
    """
    from datetime import datetime

    # Check for existing participant
    existing = (
        db.query(SessionParticipant)
        .filter(SessionParticipant.session_id == session_id, SessionParticipant.user_id == user_id)
        .first()
    )

    if existing:
        # Update character_id and joined_at if changed
        existing.character_id = character_id
        existing.joined_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    # Create new participant
    participant = SessionParticipant(
        session_id=session_id, user_id=user_id, character_id=character_id, joined_at=datetime.utcnow()
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant


def remove_participant(db: Session, session_id: int, user_id: int) -> bool:
    """
    Remove a participant record.

    Args:
        db: Database session
        session_id: The game session ID
        user_id: The user ID

    Returns:
        bool: True if a record was removed, False otherwise

    Raises:
        Exception: If database operation fails (caller should handle rollback)
    """
    participant = (
        db.query(SessionParticipant)
        .filter(SessionParticipant.session_id == session_id, SessionParticipant.user_id == user_id)
        .first()
    )

    if participant:
        db.delete(participant)
        db.commit()
        return True

    return False


def get_participant_count(db: Session, session_id: int) -> int:
    """
    Get the current participant count for a session.

    Args:
        db: Database session
        session_id: The game session ID

    Returns:
        int: The number of participants in the session
    """
    return db.query(SessionParticipant).filter(SessionParticipant.session_id == session_id).count()


def get_participants(db: Session, session_id: int) -> list[dict]:
    """
    Get all participants for a session with character names and IDs.

    Args:
        db: Database session
        session_id: The game session ID

    Returns:
        list[dict]: List of participant dictionaries with user_id, character_id, and character_name
    """
    results = (
        db.query(SessionParticipant.user_id, SessionParticipant.character_id, Character.name.label("character_name"))
        .join(Character, Character.id == SessionParticipant.character_id)
        .filter(SessionParticipant.session_id == session_id)
        .all()
    )

    return [{"user_id": r.user_id, "character_id": r.character_id, "character_name": r.character_name} for r in results]


# ===== End Participant Management Helper Functions =====


async def check_and_deactivate_session(session_id: int, db: Session) -> bool:
    """
    Check if session should be deactivated and deactivate if needed.

    A session is deactivated when the participant count reaches 0.
    When deactivating:
    1. Set is_active to False
    2. Backup story logs
    3. Remove all SessionParticipant records
    4. Broadcast session_ended event
    5. Close socket room
    6. Clear presence entries

    Args:
        session_id: The game session ID
        db: Database session

    Returns:
        bool: True if session was deactivated, False otherwise

    Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5
    """
    try:
        # Requirement 2.2: Check participant count
        count = get_participant_count(db, session_id)

        if count > 0:
            return False

        # Get session
        session = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not session or not session.is_active:
            return False

        # Requirement 2.1: Set is_active to False
        session.is_active = False

        # Requirement 2.5: Backup story logs before deactivation
        try:
            backup_session(session_id)
        except Exception as e:
            print(f"Backup failed for session {session_id}: {e}")

        # Requirement 2.2: Remove any remaining participants (should be 0, but be safe)
        db.query(SessionParticipant).filter(SessionParticipant.session_id == session_id).delete()

        db.commit()

        # Requirement 2.3: Broadcast session_ended event
        room_name = f"session_{session_id}"
        await sio.emit("session_ended", {"session_id": session_id, "reason": "no_participants"}, room=room_name)

        # Requirement 2.4: Close socket room
        try:
            await sio.close_room(room_name)
        except Exception as e:
            print(f"Failed to close room {room_name}: {e}")

        # Clear presence entries for this session
        for sid, info in list(session_presence.items()):
            if info.get("session_id") == session_id:
                session_presence.pop(sid, None)

        logger.info(f"세션 {session_id} 비활성화: 참가자 없음")
        return True

    except Exception as e:
        logger.error(f"check_and_deactivate_session 에러: {e}")
        db.rollback()
        return False


async def _presence_monitor():
    """
    Periodically checks heartbeats and removes inactive clients from session rooms.

    Requirements:
        - 1.3: Decrement participant count after heartbeat timeout
        - 4.1: Remove client when heartbeat not received within timeout
        - 4.2: Remove SessionParticipant record on timeout
        - 4.3: Broadcast user_left event on timeout
        - 4.4: Check if session should be deactivated after timeout
        - 4.5: Deactivate session immediately if timed-out client was host
    """
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SEC)
        now = time.monotonic()
        # Iterate over a snapshot to allow modification during loop
        for sid, info in list(session_presence.items()):
            last_ts = info.get("last_ts", 0)
            session_id = info.get("session_id")
            user_id = info.get("user_id")

            if not session_id or not user_id:
                continue

            # Requirement 4.1: Check if heartbeat timeout exceeded
            if now - last_ts > HEARTBEAT_TIMEOUT_SEC:
                db = SessionLocal()
                try:
                    # Get character name before removing participant
                    char_row = (
                        db.query(Character.name)
                        .join(SessionParticipant, SessionParticipant.character_id == Character.id)
                        .filter(SessionParticipant.session_id == session_id, SessionParticipant.user_id == user_id)
                        .first()
                    )
                    character_name = char_row[0] if char_row else None

                    # Requirement 4.2: Remove participant from database
                    remove_participant(db, session_id, user_id)

                    # Requirement 1.3: Get updated participant list from DB
                    participants = get_participants(db, session_id)

                    # Requirement 4.3: Broadcast user_left with participant list and count
                    room_name = f"session_{session_id}"
                    await sio.emit(
                        "user_left",
                        {
                            "user_id": user_id,
                            "session_id": session_id,
                            "character_name": character_name,
                            "participants": participants,
                            "participant_count": len(participants),
                        },
                        room=room_name,
                    )

                    # Remove client from socket room
                    await sio.leave_room(sid, room_name)

                    # Clear presence record for this sid
                    session_presence.pop(sid, None)

                    print(f"Client {sid} timed out from session {session_id}")

                    # Requirement 4.5: If user was host, end the session immediately
                    # This must be done before check_and_deactivate_session
                    await _maybe_end_session_if_host(session_id, user_id)

                    # Requirement 4.4: Check if session should be deactivated
                    # This will only deactivate if not already deactivated by host disconnect
                    await check_and_deactivate_session(session_id, db)

                except Exception as e:
                    logger.error(f"presence 타임아웃 처리 에러: {sid}, {e}")
                    db.rollback()
                finally:
                    db.close()


async def verify_host_authorization(session_id: int, user_id: int, db: Session) -> tuple[bool, str | None]:
    """
    Verify if user is the host of the session.

    Args:
        session_id: The game session ID
        user_id: The user attempting the operation
        db: Database session

    Returns:
        Tuple of (is_authorized, error_message)
        - (True, None) if authorized
        - (False, error_message) if not authorized
    """
    try:
        session = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not session:
            return False, "Session not found"

        if session.host_user_id != user_id:
            return False, "Unauthorized: Only the host can perform this action"

        return True, None
    except Exception as e:
        logger.error(f"verify_host_authorization 에러: {e}")
        return False, "Internal server error"


def validate_chat_message(message: str) -> tuple[bool, str | None]:
    """
    Validate chat message content.

    Args:
        message: The message text to validate

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if valid
        - (False, error_message) if invalid
    """
    # Check if message is empty after trimming
    if not message or not message.strip():
        return False, "Message cannot be empty"

    # Check if message is only whitespace
    if message.strip() == "":
        return False, "Message cannot be only whitespace"

    # Check message length
    if len(message) > 500:
        return False, "Message exceeds maximum length of 500 characters"

    return True, None


@sio.event
async def chat_message(sid, data):
    """
    Handle ephemeral general chat messages (not persisted).

    Args:
        sid: Socket session ID
        data: Dictionary containing:
            - session_id: int
            - user_id: int
            - message: str
    """
    try:
        session_id = data.get("session_id")
        user_id = data.get("user_id")
        # Resolve character name from DB
        db = SessionLocal()
        try:
            row = (
                db.query(Character.name)
                .join(SessionParticipant, SessionParticipant.character_id == Character.id)
                .filter(SessionParticipant.session_id == session_id, SessionParticipant.user_id == user_id)
                .first()
            )
            username = row[0] if row else (f"User {user_id}" if user_id else "User")
        finally:
            db.close()
        message = data.get("message") or ""

        if not session_id:
            await sio.emit("error", {"message": "session_id is required"}, room=sid)
            return

        # Validate chat message
        is_valid, error_message = validate_chat_message(message)
        if not is_valid:
            await sio.emit("error", {"message": error_message}, room=sid)
            return

        # Validate session exists
        db = SessionLocal()
        try:
            session = db.query(GameSession).filter(GameSession.id == session_id).first()
            if not session:
                await sio.emit("error", {"message": "Session not found"}, room=sid)
                return
        finally:
            db.close()

        room_name = f"session_{session_id}"
        # Broadcast chat_message to room (ephemeral)
        await sio.emit(
            "chat_message",
            {
                "session_id": session_id,
                "user_id": user_id,
                "character_name": username,
                "message": message.strip(),
            },
            room=room_name,
        )

    except Exception as e:
        print(f"Error in chat_message: {e}")
        await sio.emit("error", {"message": "Failed to send chat message"}, room=sid)


@sio.event
async def connect(sid, environ):
    """
    Handle client connection.

    Args:
        sid: Socket session ID (unique identifier for this connection)
        environ: ASGI environment dictionary
    """
    global _presence_task_started
    logger.info(f"클라이언트 연결: {sid}")
    # Start presence monitor once, lazily on first connection
    if not _presence_task_started:
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(_presence_monitor())
            _presence_task_started = True
        except Exception as e:
            print(f"Failed to start presence monitor: {e}")


@sio.event
async def disconnect(sid):
    """
    Handle client disconnection.
    Cleans up the connection and removes client from all rooms.

    Requirements:
        - 3.3: Remove SessionParticipant record on disconnect
        - 10.1: Clear presence tracking on disconnect

    Args:
        sid: Socket session ID
    """
    logger.info(f"클라이언트 연결 해제: {sid}")

    # Requirement 10.1: Clear presence tracking for this sid
    info = session_presence.pop(sid, None)

    if info and info.get("session_id") and info.get("user_id"):
        session_id = info["session_id"]
        user_id = info["user_id"]

        db = SessionLocal()
        try:
            # Get character name before removing participant
            char_row = (
                db.query(Character.name)
                .join(SessionParticipant, SessionParticipant.character_id == Character.id)
                .filter(SessionParticipant.session_id == session_id, SessionParticipant.user_id == user_id)
                .first()
            )
            character_name = char_row[0] if char_row else None

            # Requirement 3.3: Ensure SessionParticipant removal on disconnect
            removed = remove_participant(db, session_id, user_id)

            if removed:
                # Get updated participant list
                participants = get_participants(db, session_id)

                # Broadcast user_left event
                room_name = f"session_{session_id}"
                await sio.emit(
                    "user_left",
                    {
                        "user_id": user_id,
                        "session_id": session_id,
                        "character_name": character_name,
                        "participants": participants,
                        "participant_count": len(participants),
                    },
                    room=room_name,
                )

                logger.info(f"클라이언트 {sid} 세션 {session_id}에서 연결 해제, 참가자 제거됨")

            # If the disconnected user is the host, end the session
            await _maybe_end_session_if_host(session_id, user_id)

            # Check if session should be deactivated (if not already deactivated by host disconnect)
            await check_and_deactivate_session(session_id, db)

        except Exception as e:
            print(f"Error during disconnect cleanup for {sid}: {e}")
            db.rollback()
        finally:
            db.close()


@sio.event
async def join_session(sid, data):
    """
    Handle session join request.

    Requirements:
        - 1.1: Increment participant count when user joins
        - 3.1: Add SessionParticipant record to database
        - 5.1: Check if session is_active is True
        - 5.2: Emit error event for inactive sessions
        - 5.3: Display error message for inactive sessions

    Args:
        sid: Socket session ID
        data: Dictionary containing session_id, user_id, and character_id
    """
    try:
        session_id = data.get("session_id")
        user_id = data.get("user_id")
        character_id = data.get("character_id")

        # Requirement 3.1: character_id is now required
        if not session_id or not user_id or not character_id:
            await sio.emit("error", {"message": "session_id, user_id, and character_id are required"}, room=sid)
            return

        # Verify session exists in database and is active
        db = SessionLocal()
        try:
            session = db.query(GameSession).filter(GameSession.id == session_id).first()
            if not session:
                await sio.emit("error", {"message": "세션을 찾을 수 없습니다."}, room=sid)
                return

            # Requirement 5.1, 5.2, 5.3: Handle inactive session rejection
            if not session.is_active:
                await sio.emit("error", {"message": "세션이 종료되었습니다."}, room=sid)
                return

            # Requirement 3.1: Add participant to database (creates/updates SessionParticipant record)
            add_participant(db, session_id, user_id, character_id)

            # Get character name
            character = db.query(Character).filter(Character.id == character_id).first()
            character_name = character.name if character else None

            # Add client to the session room
            room_name = f"session_{session_id}"
            await sio.enter_room(sid, room_name)

            # Initialize presence record on join (will be updated by heartbeat)
            session_presence[sid] = {
                "session_id": session_id,
                "user_id": user_id,
                "last_ts": time.monotonic(),
            }

            # Requirement 1.1: Get updated participant list from DB
            participants = get_participants(db, session_id)

            # Broadcast join notification with participant list and count
            await sio.emit(
                "user_joined",
                {
                    "user_id": user_id,
                    "session_id": session_id,
                    "character_name": character_name,
                    "participants": participants,
                    "participant_count": len(participants),
                },
                room=room_name,
            )

            logger.info(f"클라이언트 {sid} 세션 {session_id} 참가: 캐릭터={character_name}")

        finally:
            db.close()

    except Exception as e:
        print(f"Error in join_session: {e}")
        await sio.emit("error", {"message": "Failed to join session"}, room=sid)


@sio.event
async def leave_session(sid, data):
    """
    Handle session leave request.

    Requirements:
        - 1.2: Decrement participant count when user leaves
        - 3.2: Remove SessionParticipant record from database
        - 7.1: Remove SessionParticipant record on leave_session event
        - 7.2: Remove user from socket room
        - 7.3: Broadcast user_left event to remaining participants
        - 7.4: Clear presence tracking record
        - 7.5: Check if session should be deactivated

    Args:
        sid: Socket session ID
        data: Dictionary containing session_id and user_id
    """
    try:
        session_id = data.get("session_id")
        user_id = data.get("user_id")

        if not session_id or not user_id:
            await sio.emit("error", {"message": "session_id and user_id are required"}, room=sid)
            return

        db = SessionLocal()
        try:
            # Get character name before removing participant
            char_row = (
                db.query(Character.name)
                .join(SessionParticipant, SessionParticipant.character_id == Character.id)
                .filter(SessionParticipant.session_id == session_id, SessionParticipant.user_id == user_id)
                .first()
            )
            character_name = char_row[0] if char_row else None

            # Requirement 3.2, 7.1: Remove participant from database
            remove_participant(db, session_id, user_id)

            # Requirement 7.2: Remove from socket room
            room_name = f"session_{session_id}"
            await sio.leave_room(sid, room_name)

            # Requirement 7.4: Clear presence tracking
            session_presence.pop(sid, None)

            # Requirement 1.2: Get updated participant list from DB
            participants = get_participants(db, session_id)

            # Requirement 7.3: Broadcast leave notification with updated list
            await sio.emit(
                "user_left",
                {
                    "user_id": user_id,
                    "session_id": session_id,
                    "character_name": character_name,
                    "participants": participants,
                    "participant_count": len(participants),
                },
                room=room_name,
            )

            logger.info(f"클라이언트 {sid} 세션 {session_id} 퇴장")

            # Requirement 7.5: Check if session should be deactivated
            await check_and_deactivate_session(session_id, db)

        finally:
            db.close()

    except Exception as e:
        print(f"Error in leave_session: {e}")
        await sio.emit("error", {"message": "Failed to leave session"}, room=sid)


@sio.event
async def submit_action(sid, data):
    """
    Handle action submission from player.

    Args:
        sid: Socket session ID
        data: Dictionary containing:
            - session_id: int
            - player_id: int
            - character_name: str
            - action_text: str
    """
    global action_counter

    try:
        session_id = data.get("session_id")
        player_id = data.get("player_id")
        character_name = data.get("character_name")
        action_text = data.get("action_text", "").strip()

        # Validate action_text is non-empty
        if not action_text:
            await sio.emit("error", {"message": "Action text cannot be empty"}, room=sid)
            return

        # Initialize queue for session if needed
        if session_id not in action_queues:
            action_queues[session_id] = []

        # Create action with auto-incremented ID
        action_counter += 1
        action = {
            "id": action_counter,
            "player_id": player_id,
            "character_name": character_name,
            "action_text": action_text,
            "order": len(action_queues[session_id]),
        }

        # Add action to queue
        action_queues[session_id].append(action)

        # Emit action_submitted event to session room with action data and queue count
        room_name = f"session_{session_id}"
        await sio.emit(
            "action_submitted",
            {"session_id": session_id, "action": action, "queue_count": len(action_queues[session_id])},
            room=room_name,
        )

        logger.info(f"행동 제출: 세션={session_id}, 플레이어={player_id}, 캐릭터={character_name}")

    except Exception as e:
        print(f"Error in submit_action: {e}")
        await sio.emit("error", {"message": "Failed to submit action"}, room=sid)


@sio.event
async def get_queue(sid, data):
    """
    Get current action queue for a session.

    Args:
        sid: Socket session ID
        data: Dictionary containing:
            - session_id: int
    """
    try:
        session_id = data.get("session_id")

        # Initialize empty queue if session not in action_queues
        if session_id not in action_queues:
            action_queues[session_id] = []

        # Return current queue state for requested session
        await sio.emit("queue_data", {"actions": action_queues[session_id]}, room=sid)

        print(f"Queue retrieved: session={session_id}, count={len(action_queues[session_id])}")

    except Exception as e:
        print(f"Error in get_queue: {e}")
        await sio.emit("error", {"message": "Failed to retrieve queue"}, room=sid)


# =============================================================================
# 3-Phase AI Process Event Handlers
# =============================================================================


@sio.event
async def submit_player_action(sid, data):
    """
    Phase 1: Handle player action submission for 3-phase AI process.

    This handler triggers Phase 1 of the AI workflow:
    1. Receives player action
    2. Calls AI to analyze action and determine DC
    3. Calculates modifier from character stats
    4. Returns judgment_ready event with modifier + DC

    Args:
        sid: Socket session ID
        data: Dictionary containing:
            - session_id: int
            - character_id: int
            - action_text: str
            - action_type: str (strength, dexterity, constitution, intelligence, wisdom, charisma)

    Events emitted:
        - judgment_ready: When Phase 1 completes (modifier + DC)
        - action_analysis_error: When Phase 1 fails

    Requirements: 1.1, 1.2, 9.2
    """
    try:
        session_id = data.get("session_id")
        character_id = data.get("character_id")
        action_text = data.get("action_text", "").strip()
        action_type = data.get("action_type", "dexterity").lower()

        logger.info(f"Phase 1 - 행동 제출: 세션={session_id}, 캐릭터={character_id}")

        # Validate required fields
        if not session_id or not character_id:
            await sio.emit(
                "action_analysis_error",
                {"session_id": session_id, "error": "session_id and character_id are required"},
                to=sid,
            )
            return

        if not action_text:
            await sio.emit(
                "action_analysis_error", {"session_id": session_id, "error": "Action text cannot be empty"}, to=sid
            )
            return

        db = SessionLocal()
        try:
            # Verify session exists and is active
            session = db.query(GameSession).filter(GameSession.id == session_id).first()
            if not session:
                await sio.emit(
                    "action_analysis_error", {"session_id": session_id, "error": "Session not found"}, to=sid
                )
                return

            if not session.is_active:
                await sio.emit(
                    "action_analysis_error", {"session_id": session_id, "error": "Session is not active"}, to=sid
                )
                return

            # Verify character exists
            character = db.query(Character).filter(Character.id == character_id).first()
            if not character:
                await sio.emit(
                    "action_analysis_error", {"session_id": session_id, "error": "Character not found"}, to=sid
                )
                return

            # Import AI services
            from app.schemas import ActionType, PlayerAction
            from app.services.ai_gm_service_v2 import AIGMServiceV2

            # Map action_type string to ActionType enum
            action_type_map = {
                "strength": ActionType.STRENGTH,
                "dexterity": ActionType.DEXTERITY,
                "constitution": ActionType.CONSTITUTION,
                "intelligence": ActionType.INTELLIGENCE,
                "wisdom": ActionType.WISDOM,
                "charisma": ActionType.CHARISMA,
            }

            action_type_enum = action_type_map.get(action_type, ActionType.DEXTERITY)

            # Create PlayerAction
            player_action = PlayerAction(
                character_id=character_id, action_text=action_text, action_type=action_type_enum
            )

            # Initialize AI GM service
            llm_model = os.getenv("LLM_MODEL", "gpt-4o")

            ai_service = AIGMServiceV2(db=db, llm_model=llm_model)

            # Execute Phase 1: Action Analysis
            analyses = await ai_service.analyze_actions(session_id=session_id, player_actions=[player_action])

            if not analyses:
                raise ValueError("No analysis results returned")

            analysis = analyses[0]

            # Save Phase 1 result to database
            action_judgment = ActionJudgment(
                session_id=session_id,
                character_id=character_id,
                action_text=action_text,
                action_type=action_type,
                modifier=analysis.modifier,
                difficulty=analysis.difficulty,
                difficulty_reasoning=analysis.difficulty_reasoning,
                phase=1,  # Phase 1: Analysis complete
            )
            db.add(action_judgment)
            db.commit()
            db.refresh(action_judgment)

            logger.info(f"Phase 1 완료: 캐릭터={character_id}, 보정치={analysis.modifier:+d}, DC={analysis.difficulty}")

            # Emit judgment_ready event to the player
            await sio.emit(
                "judgment_ready",
                {
                    "session_id": session_id,
                    "character_id": character_id,
                    "judgment_id": action_judgment.id,
                    "action_text": action_text,
                    "modifier": analysis.modifier,
                    "difficulty": analysis.difficulty,
                    "difficulty_reasoning": analysis.difficulty_reasoning,
                },
                to=sid,
            )

            # Also broadcast to room so other players can see
            room_name = f"session_{session_id}"
            await sio.emit(
                "player_action_analyzed",
                {
                    "session_id": session_id,
                    "character_id": character_id,
                    "character_name": character.name,
                    "judgment_id": action_judgment.id,
                    "action_text": action_text,
                    "modifier": analysis.modifier,
                    "difficulty": analysis.difficulty,
                    "difficulty_reasoning": analysis.difficulty_reasoning,
                },
                room=room_name,
                skip_sid=sid,
            )

        except Exception as e:
            logger.error(f"Phase 1 에러: {e}", exc_info=True)
            await sio.emit(
                "action_analysis_error",
                {"session_id": session_id, "character_id": character_id, "error": str(e)},
                to=sid,
            )
        finally:
            db.close()

    except Exception as e:
        logger.error(f"submit_player_action 에러: {e}", exc_info=True)
        await sio.emit(
            "action_analysis_error", {"session_id": data.get("session_id"), "error": "Failed to analyze action"}, to=sid
        )


@sio.event
async def roll_dice(sid, data):
    """
    Phase 2: Handle player dice roll for 3-phase AI process.
    
    **Enhanced with Pre-rolled Dice**
    
    This handler now returns pre-rolled dice values instead of generating new ones:
    1. Receives dice confirmation from player (dice_result is ignored)
    2. Fetches pre-rolled dice from database (phase=0)
    3. Updates ActionJudgment to phase=2 (confirmed)
    4. Broadcasts dice_rolled event to all participants
    5. Checks if all players have confirmed

    Args:
        sid: Socket session ID
        data: Dictionary containing:
            - session_id: int
            - character_id: int
            - judgment_id: int (from judgment_ready event)
            - dice_result: int (IGNORED - for backward compatibility only)

    Events emitted:
        - dice_rolled: Broadcast to all participants
        - all_dice_rolled: When all players have confirmed
        - dice_roll_error: When dice confirmation fails

    Requirements: 3.1, 3.2, 3.3, 3.4
    """
    try:
        session_id = data.get("session_id")
        character_id = data.get("character_id")

        logger.info(f"Phase 2 - 주사위 확인: 세션={session_id}, 캐릭터={character_id}")

        # Validate required fields
        if not session_id or not character_id:
            await sio.emit(
                "dice_roll_error",
                {"session_id": session_id, "error": "session_id and character_id are required"},
                to=sid,
            )
            return

        db = SessionLocal()
        try:
            # Use AIGMServiceV2 to confirm dice roll
            from app.services.ai_gm_service_v2 import AIGMServiceV2

            ai_service = AIGMServiceV2(db=db)
            dice_result_obj = await ai_service.confirm_dice_roll(
                session_id=session_id,
                character_id=character_id
            )

            # Get the confirmed judgment for additional info
            judgment = db.query(ActionJudgment).filter(
                ActionJudgment.session_id == session_id,
                ActionJudgment.character_id == character_id,
                ActionJudgment.phase == 2
            ).order_by(ActionJudgment.id.desc()).first()
            
            if not judgment:
                await sio.emit("dice_roll_error", {"session_id": session_id, "error": "Judgment not found"}, to=sid)
                return

            # Get character name for broadcast
            character = db.query(Character).filter(Character.id == character_id).first()
            character_name = character.name if character else f"Character {character_id}"

            logger.info(
                f"Phase 2 완료: 캐릭터={character_id}, "
                f"주사위={judgment.dice_result}, 보정치={judgment.modifier:+d}, "
                f"최종={judgment.final_value}, DC={judgment.difficulty}, 결과={judgment.outcome}"
            )

            # Broadcast dice_rolled event to all participants
            room_name = f"session_{session_id}"
            await sio.emit(
                "dice_rolled",
                {
                    "session_id": session_id,
                    "character_id": character_id,
                    "character_name": character_name,
                    "judgment_id": judgment.id,
                    "dice_result": judgment.dice_result,
                    "modifier": judgment.modifier,
                    "final_value": judgment.final_value,
                    "difficulty": judgment.difficulty,
                    "outcome": judgment.outcome,
                },
                room=room_name,
            )

            # Check if all players have confirmed (phase=0 means not confirmed yet)
            pending_judgments = (
                db.query(ActionJudgment)
                .filter(
                    ActionJudgment.session_id == session_id,
                    ActionJudgment.phase == 0,  # Still waiting for confirmation
                )
                .count()
            )

            if pending_judgments == 0:
                logger.info(f"모든 주사위 확인 완료: 세션={session_id}")

                # Emit all_dice_rolled event
                await sio.emit("all_dice_rolled", {"session_id": session_id}, room=room_name)

        except Exception as e:
            logger.error(f"Phase 2 에러: {e}", exc_info=True)
            db.rollback()
            await sio.emit(
                "dice_roll_error", {"session_id": session_id, "character_id": character_id, "error": str(e)}, to=sid
            )
        finally:
            db.close()

    except Exception as e:
        logger.error(f"roll_dice 에러: {e}", exc_info=True)
        await sio.emit(
            "dice_roll_error", {"session_id": data.get("session_id"), "error": "Failed to process dice roll"}, to=sid
        )


@sio.event
async def next_judgment(sid, data):
    """
    Move to the next judgment in the sequence.

    This handler is called when a player finishes their dice roll
    and clicks "다음" to proceed to the next judgment.

    Args:
        sid: Socket session ID
        data: Dictionary containing:
            - session_id: int
            - current_index: int (current judgment index)

    Events emitted:
        - next_judgment: Broadcast to all participants with new index
    """
    try:
        session_id = data.get("session_id")
        current_index = data.get("current_index", 0)

        if not session_id:
            await sio.emit("error", {"message": "session_id is required"}, room=sid)
            return

        # Broadcast next_judgment event to all participants
        room_name = f"session_{session_id}"
        await sio.emit("next_judgment", {"judgment_index": current_index + 1}, room=room_name)

        logger.info(f"다음 판정으로 이동: 세션={session_id}, 인덱스={current_index + 1}")

    except Exception as e:
        logger.error(f"next_judgment 에러: {e}", exc_info=True)
        await sio.emit("error", {"message": "Failed to move to next judgment"}, room=sid)


@sio.event
async def request_narrative_stream(sid, data):
    """
    Request narrative stream from buffer.
    
    **New Handler for Streaming Optimization**
    
    This handler streams the narrative that was generated in the background
    during Phase 1. The narrative tokens are replayed from the buffer with
    a typing effect delay.

    Args:
        sid: Socket session ID
        data: Dictionary containing:
            - session_id: int

    Events emitted:
        - narrative_stream_started: When streaming begins
        - narrative_token: Each token from the buffer
        - narrative_complete: When streaming finishes
        - narrative_error: If buffer not found or error occurred

    Requirements: 2.1, 2.3, 6.3, 6.4
    """
    try:
        session_id = data.get("session_id")

        if not session_id:
            await sio.emit("error", {"message": "session_id is required"}, room=sid)
            return

        logger.info(f"이야기 스트림 요청: 세션={session_id}")

        db = SessionLocal()
        try:
            room_name = f"session_{session_id}"
            
            # Emit stream started event
            await sio.emit("narrative_stream_started", {"session_id": session_id}, room=room_name)
            
            # Use AIGMServiceV2 to stream narrative
            from app.services.ai_gm_service_v2 import AIGMServiceV2
            
            ai_service = AIGMServiceV2(db=db)
            
            # Stream tokens
            token_count = 0
            async for token in ai_service.stream_narrative(session_id):
                await sio.emit(
                    "narrative_token",
                    {"session_id": session_id, "token": token},
                    room=room_name
                )
                token_count += 1
            
            logger.info(f"이야기 토큰 {token_count}개 전송: room={room_name}")
            
            # Emit complete event
            await sio.emit("narrative_complete", {"session_id": session_id}, room=room_name)
            
            logger.info(f"이야기 스트림 완료: 세션={session_id}")
            
        except ValueError as e:
            logger.error(f"이야기 스트림 에러: 세션={session_id}, {e}")
            await sio.emit(
                "narrative_error",
                {"session_id": session_id, "error": str(e)},
                room=f"session_{session_id}"
            )
        finally:
            db.close()

    except Exception as e:
        logger.error(f"request_narrative_stream 에러: {e}", exc_info=True)
        await sio.emit("error", {"message": "Failed to stream narrative"}, room=sid)


@sio.event
async def trigger_story_generation(sid, data):
    """
    Manually trigger story generation after all judgments are complete.

    This handler is called when the last player clicks "이야기 진행"
    after completing their dice roll.

    Args:
        sid: Socket session ID
        data: Dictionary containing:
            - session_id: int

    Events emitted:
        - story_generation_started: When Phase 3 begins
        - narrative_token: Streaming narrative tokens
        - story_generation_complete: When Phase 3 completes
    """
    try:
        session_id = data.get("session_id")

        if not session_id:
            await sio.emit("error", {"message": "session_id is required"}, room=sid)
            return

        logger.info(f"수동 이야기 생성 트리거: 세션={session_id}")

        db = SessionLocal()
        try:
            room_name = f"session_{session_id}"
            await trigger_story_generation_internal(session_id, db, room_name)
        finally:
            db.close()

    except Exception as e:
        logger.error(f"trigger_story_generation 에러: {e}", exc_info=True)
        await sio.emit("error", {"message": "Failed to trigger story generation"}, room=sid)


async def trigger_story_generation_internal(session_id: int, db: Session, room_name: str):
    """
    Phase 3: Trigger story generation after all players have rolled dice.

    This function:
    1. Collects all Phase 2 judgments (dice rolled)
    2. Calls AI to generate narrative
    3. Streams narrative tokens to all participants
    4. Saves results to database
    5. Broadcasts completion event

    Args:
        session_id: ID of the game session
        db: Database session
        room_name: Socket room name for broadcasting

    Events emitted:
        - story_generation_started: When Phase 3 begins
        - narrative_token: Streaming narrative tokens
        - story_generation_complete: When Phase 3 completes
        - story_generation_error: When Phase 3 fails (to host only)

    Requirements: 1.4, 1-C.2, 9.4, 9.5, 9.6, 9.7
    """
    logger.info(f"Phase 3 - 이야기 생성 시작: 세션={session_id}")

    # Broadcast story_generation_started event
    await sio.emit("story_generation_started", {"session_id": session_id}, room=room_name)

    try:
        # Get all Phase 2 judgments (dice rolled, not yet narrated)
        judgments = (
            db.query(ActionJudgment).filter(ActionJudgment.session_id == session_id, ActionJudgment.phase == 2).all()
        )

        if not judgments:
            raise ValueError("No judgments found for story generation")

        # Import AI services
        from app.schemas import DiceResult
        from app.services.ai_gm_service_v2 import AIGMServiceV2

        # Convert judgments to DiceResult objects
        dice_results = []
        for j in judgments:
            dice_result = DiceResult(
                character_id=j.character_id,
                action_text=j.action_text,
                dice_roll=j.dice_result,
                modifier=j.modifier,
                difficulty=j.difficulty,
            )
            dice_results.append(dice_result)

        # Initialize AI GM service
        llm_model = os.getenv("LLM_MODEL", "gpt-4o")

        ai_service = AIGMServiceV2(db=db, llm_model=llm_model)

        # Execute Phase 3: Generate narrative
        result = await ai_service.generate_narrative(session_id=session_id, dice_results=dice_results)

        # Stream narrative tokens
        narrative = result.full_narrative
        chunk_size = 50  # Characters per chunk

        for i in range(0, len(narrative), chunk_size):
            chunk = narrative[i : i + chunk_size]
            await sio.emit("narrative_token", {"session_id": session_id, "token": chunk}, room=room_name)
            # Small delay to simulate streaming
            await asyncio.sleep(0.03)

        # Update all judgments to Phase 3
        for j in judgments:
            j.phase = 3
        db.commit()

        # Convert judgments to serializable format
        judgments_data = [
            {
                "character_id": j.character_id,
                "action_text": j.action_text,
                "dice_result": j.dice_result,
                "modifier": j.modifier,
                "final_value": j.final_value,
                "difficulty": j.difficulty,
                "difficulty_reasoning": j.difficulty_reasoning,
                "outcome": j.outcome,
            }
            for j in result.judgments
        ]

        # Broadcast story_generation_complete event
        await sio.emit(
            "story_generation_complete",
            {"session_id": session_id, "narrative": result.full_narrative, "judgments": judgments_data},
            room=room_name,
        )

        logger.info(f"Phase 3 완료: 세션={session_id}, 이야기 길이={len(narrative)}")

    except Exception as e:
        logger.error(f"Phase 3 에러: {e}", exc_info=True)

        # Get host's socket ID to send error
        session = db.query(GameSession).filter(GameSession.id == session_id).first()
        if session:
            # Find host's socket ID from presence tracking
            host_sid = None
            for sid, info in session_presence.items():
                if info.get("session_id") == session_id and info.get("user_id") == session.host_user_id:
                    host_sid = sid
                    break

            if host_sid:
                await sio.emit("story_generation_error", {"session_id": session_id, "error": str(e)}, to=host_sid)
            else:
                # Fallback: broadcast to room
                await sio.emit("story_generation_error", {"session_id": session_id, "error": str(e)}, room=room_name)


@sio.event
async def edit_action(sid, data):
    """
    Edit an action in the queue.

    Args:
        sid: Socket session ID
        data: Dictionary containing:
            - session_id: int
            - action_id: int
            - new_text: str
            - user_id: int
    """
    try:
        session_id = data.get("session_id")
        action_id = data.get("action_id")
        new_text = data.get("new_text", "").strip()
        user_id = data.get("user_id")

        # Verify host authorization
        db = SessionLocal()
        try:
            is_authorized, error_message = await verify_host_authorization(session_id, user_id, db)
            if not is_authorized:
                await sio.emit("error", {"message": error_message}, room=sid)
                return
        finally:
            db.close()

        # Validate new_text is non-empty
        if not new_text:
            await sio.emit("error", {"message": "Action text cannot be empty"}, room=sid)
            return

        # Find action by ID and update action_text
        if session_id in action_queues:
            for action in action_queues[session_id]:
                if action["id"] == action_id:
                    action["action_text"] = new_text
                    break

        # Emit queue_updated event to session room
        room_name = f"session_{session_id}"
        await sio.emit("queue_updated", {"actions": action_queues.get(session_id, [])}, room=room_name)

        print(f"Action edited: session={session_id}, action_id={action_id}")

    except Exception as e:
        print(f"Error in edit_action: {e}")
        await sio.emit("error", {"message": "Failed to edit action"}, room=sid)


@sio.event
async def reorder_actions(sid, data):
    """
    Reorder actions in the queue.

    Args:
        sid: Socket session ID
        data: Dictionary containing:
            - session_id: int
            - action_ids: list[int] - Array of action IDs in new order
            - user_id: int
    """
    try:
        session_id = data.get("session_id")
        action_ids = data.get("action_ids", [])
        user_id = data.get("user_id")

        # Verify host authorization
        db = SessionLocal()
        try:
            is_authorized, error_message = await verify_host_authorization(session_id, user_id, db)
            if not is_authorized:
                await sio.emit("error", {"message": error_message}, room=sid)
                return
        finally:
            db.close()

        # Rebuild queue preserving all action data except order field
        if session_id in action_queues:
            # Create a map of id -> action
            action_map = {action["id"]: action for action in action_queues[session_id]}

            # Rebuild queue in new order
            reordered = []
            for idx, action_id in enumerate(action_ids):
                if action_id in action_map:
                    action = action_map[action_id]
                    action["order"] = idx
                    reordered.append(action)

            action_queues[session_id] = reordered

        # Emit queue_updated event to session room
        room_name = f"session_{session_id}"
        await sio.emit("queue_updated", {"actions": action_queues.get(session_id, [])}, room=room_name)

        print(f"Actions reordered: session={session_id}, new_order={action_ids}")

    except Exception as e:
        print(f"Error in reorder_actions: {e}")
        await sio.emit("error", {"message": "Failed to reorder actions"}, room=sid)


@sio.event
async def delete_action(sid, data):
    """
    Delete an action from the queue.

    Args:
        sid: Socket session ID
        data: Dictionary containing:
            - session_id: int
            - action_id: int
            - user_id: int
    """
    try:
        session_id = data.get("session_id")
        action_id = data.get("action_id")
        user_id = data.get("user_id")

        # Verify host authorization
        db = SessionLocal()
        try:
            is_authorized, error_message = await verify_host_authorization(session_id, user_id, db)
            if not is_authorized:
                await sio.emit("error", {"message": error_message}, room=sid)
                return
        finally:
            db.close()

        # Remove action from queue by ID
        if session_id in action_queues:
            action_queues[session_id] = [action for action in action_queues[session_id] if action["id"] != action_id]

            # Reindex remaining actions' order fields
            for idx, action in enumerate(action_queues[session_id]):
                action["order"] = idx

        # Emit queue_updated event with new queue_count
        room_name = f"session_{session_id}"
        await sio.emit(
            "queue_updated",
            {"actions": action_queues.get(session_id, []), "queue_count": len(action_queues.get(session_id, []))},
            room=room_name,
        )

        print(f"Action deleted: session={session_id}, action_id={action_id}")

    except Exception as e:
        print(f"Error in delete_action: {e}")
        await sio.emit("error", {"message": "Failed to delete action"}, room=sid)


@sio.event
async def commit_actions(sid, data):
    """
    Commit all actions in queue to StoryLog, trigger AI generation, and broadcast results.

    This handler implements the complete 2-phase AI workflow:
    1. Save player actions to database
    2. Trigger AI generation (judgment + narration)
    3. Stream results to all clients in real-time

    Args:
        sid: Socket session ID
        data: Dictionary containing:
            - session_id: int
            - user_id: int

    Events emitted:
        - ai_generation_started: When AI generation begins
        - judgments_complete: When phase 1 (judgment) completes
        - narrative_token: Streaming narrative tokens (phase 2)
        - ai_generation_complete: When generation completes successfully
        - ai_generation_error: When generation fails (to host only)
        - story_committed: When player actions are saved
        - queue_updated: When action queue is cleared

    Requirements:
        - 9.1: WebSocket event triggering
        - 9.2: Generation started event
        - 9.3: Token streaming
        - 9.4: Generation complete event
        - 9.5: Error handling and host notification
    """
    try:
        session_id = data.get("session_id")
        user_id = data.get("user_id")

        # Verify host authorization
        db = SessionLocal()
        try:
            is_authorized, error_message = await verify_host_authorization(session_id, user_id, db)
            if not is_authorized:
                await sio.emit("error", {"message": error_message}, room=sid)
                return

            # Validate queue is non-empty
            if session_id not in action_queues or not action_queues[session_id]:
                await sio.emit("error", {"message": "No actions to commit"}, room=sid)
                return

            # Sort actions by order field
            actions = sorted(action_queues[session_id], key=lambda a: a["order"])

            # Combine action texts into narrative format: "character_name: action_text"
            narrative_parts = [f"{action['character_name']}: {action['action_text']}" for action in actions]
            combined_narrative = "\n".join(narrative_parts)

            # Insert StoryLog record with role='USER' and combined content
            story_entry = StoryLog(session_id=session_id, role="USER", content=combined_narrative)
            db.add(story_entry)
            db.commit()
            db.refresh(story_entry)

            # Clear action queue after successful commit
            action_queues[session_id] = []

            # Broadcast story_committed event to all clients in session
            room_name = f"session_{session_id}"
            await sio.emit(
                "story_committed",
                {
                    "story_entry": {
                        "id": story_entry.id,
                        "session_id": story_entry.session_id,
                        "role": story_entry.role,
                        "content": story_entry.content,
                        "created_at": to_kst_iso(story_entry.created_at),
                    }
                },
                room=room_name,
            )

            # Emit queue_updated event with count 0 to reset queue count display
            await sio.emit("queue_updated", {"actions": [], "queue_count": 0}, room=room_name)

            logger.info(f"행동 커밋: 세션={session_id}, 행동 수={len(actions)}")

            # ===== AI GENERATION WORKFLOW =====
            # Requirement 9.2: Broadcast generation started event (Phase 1: judgment)
            await sio.emit("ai_generation_started", {"session_id": session_id, "phase": "judgment"}, room=room_name)

            try:
                # Import AI services
                import os

                from app.schemas import ActionType, PlayerAction
                from app.services.ai_gm_service_v2 import AIGMServiceV2

                # Get character IDs from actions and map to action types
                # For now, we'll use DEXTERITY as default action type
                # In a real implementation, this would be determined by the action text
                player_actions = []
                for action in actions:
                    # Find character from SessionParticipant using player_id (user_id)
                    participant = (
                        db.query(SessionParticipant)
                        .filter(
                            SessionParticipant.session_id == session_id,
                            SessionParticipant.user_id == action["player_id"],
                        )
                        .first()
                    )

                    if participant:
                        char = db.query(Character).filter(Character.id == participant.character_id).first()
                        if char:
                            player_actions.append(
                                PlayerAction(
                                    character_id=char.id,
                                    action_text=action["action_text"],
                                    action_type=ActionType.DEXTERITY,  # Default for now
                                )
                            )
                            logger.info(f"행동 매핑: 유저 {action['player_id']} -> 캐릭터 {char.id} ({char.name})")
                        else:
                            logger.warning(f"캐릭터 없음: user_id={action['player_id']}, character_id={participant.character_id}")
                    else:
                        # Fallback: try to find by character_name
                        char = db.query(Character).filter(Character.name == action["character_name"]).first()
                        if char:
                            player_actions.append(
                                PlayerAction(
                                    character_id=char.id,
                                    action_text=action["action_text"],
                                    action_type=ActionType.DEXTERITY,
                                )
                            )
                            logger.info(f"캐릭터명으로 매핑: {action['character_name']} -> {char.id}")
                        else:
                            logger.warning(f"캐릭터 찾기 실패: player_id={action['player_id']}, character_name={action['character_name']}")

                if not player_actions:
                    raise ValueError(f"Could not map any actions to characters. Actions: {actions}")

                # Initialize AI GM service
                llm_model = os.getenv("LLM_MODEL", "gpt-4o")

                ai_service = AIGMServiceV2(db=db, llm_model=llm_model)

                # Execute Phase 1: Analyze all actions and determine DC
                # This does NOT roll dice - players will roll their own dice
                analyses = await ai_service.analyze_actions(session_id=session_id, player_actions=player_actions)

                if not analyses:
                    raise ValueError("No analysis results returned from AI")
                
                # **NEW: Emit judgments_ready event to all participants**
                room_name = f"session_{session_id}"
                await sio.emit(
                    "judgments_ready",
                    {
                        "session_id": session_id,
                        "analyses": [
                            {
                                "character_id": analysis.character_id,
                                "action_text": analysis.action_text,
                                "modifier": analysis.modifier,
                                "difficulty": analysis.difficulty,
                                "difficulty_reasoning": analysis.difficulty_reasoning,
                            }
                            for analysis in analyses
                        ]
                    },
                    room=room_name
                )
                logger.info(f"judgments_ready 이벤트 전송: 세션={session_id}")

                # Get pre-rolled judgments from database (created by _preroll_dice in analyze_actions)
                # and send judgment_ready to each player
                for analysis in analyses:
                    character = db.query(Character).filter(Character.id == analysis.character_id).first()

                    if not character:
                        continue

                    # Get the pre-rolled judgment (phase=0) created by analyze_actions
                    action_judgment = db.query(ActionJudgment).filter(
                        ActionJudgment.session_id == session_id,
                        ActionJudgment.character_id == analysis.character_id,
                        ActionJudgment.phase == 0
                    ).order_by(ActionJudgment.id.desc()).first()

                    if not action_judgment:
                        logger.warning(f"사전 굴림 판정 없음: 캐릭터={analysis.character_id}")
                        continue

                    # Find the player's socket ID to send judgment_ready
                    # Look up user_id from SessionParticipant
                    participant = (
                        db.query(SessionParticipant)
                        .filter(
                            SessionParticipant.session_id == session_id,
                            SessionParticipant.character_id == analysis.character_id,
                        )
                        .first()
                    )

                    if participant:
                        # Find socket ID for this user
                        player_sid = None
                        for s_id, info in session_presence.items():
                            if info.get("session_id") == session_id and info.get("user_id") == participant.user_id:
                                player_sid = s_id
                                break

                        if player_sid:
                            # Send judgment_ready to the specific player
                            await sio.emit(
                                "judgment_ready",
                                {
                                    "session_id": session_id,
                                    "character_id": analysis.character_id,
                                    "judgment_id": action_judgment.id,
                                    "action_text": analysis.action_text,
                                    "modifier": analysis.modifier,
                                    "difficulty": analysis.difficulty,
                                    "difficulty_reasoning": analysis.difficulty_reasoning,
                                },
                                to=player_sid,
                            )

                    # Broadcast to other players (including host) that action was analyzed
                    await sio.emit(
                        "player_action_analyzed",
                        {
                            "session_id": session_id,
                            "character_id": analysis.character_id,
                            "character_name": character.name,
                            "judgment_id": action_judgment.id,
                            "action_text": analysis.action_text,
                            "modifier": analysis.modifier,
                            "difficulty": analysis.difficulty,
                            "difficulty_reasoning": analysis.difficulty_reasoning,
                        },
                        room=room_name,
                        skip_sid=player_sid if participant else None,
                    )

                logger.info(f"Phase 1 완료: 세션={session_id}, {len(analyses)}개 행동 분석됨")

                # Phase 2 and 3 will be triggered when players roll dice
                # via the roll_dice event handler

            except Exception as ai_error:
                # Requirement 9.5: Send error to host only
                print(f"AI generation error: {ai_error}")
                await sio.emit("ai_generation_error", {"session_id": session_id, "error": str(ai_error)}, to=sid)

        except Exception as e:
            # Handle database errors without clearing queue
            print(f"Database error in commit_actions: {e}")
            await sio.emit("error", {"message": "Failed to commit actions"}, room=sid)
        finally:
            db.close()

    except Exception as e:
        print(f"Error in commit_actions: {e}")
        await sio.emit("error", {"message": "Failed to commit actions"}, room=sid)


@sio.event
async def session_heartbeat(sid, data):
    """Receive periodic heartbeat from clients while they are on the session page.

    Expects: { 'session_id': int, 'user_id': int }
    """
    try:
        session_id = data.get("session_id")
        user_id = data.get("user_id")
        if not session_id or not user_id:
            # Ignore malformed heartbeat
            return

        # Update presence for this sid
        session_presence[sid] = {
            "session_id": session_id,
            "user_id": user_id,
            "last_ts": time.monotonic(),
        }
    except Exception as e:
        logger.error(f"session_heartbeat 에러: {e}")


async def _maybe_end_session_if_host(session_id: int | None, user_id: int | None):
    """
    End session immediately if the disconnecting user is the host.

    When the host disconnects, the session is immediately deactivated regardless
    of remaining participants. This ensures sessions don't continue without a host.

    Requirements:
        - 6.1: Immediately deactivate session when host disconnects
        - 6.2: Broadcast session_ended event with reason "host_disconnected"
        - 6.3: Remove all SessionParticipant records for that session
        - 6.4: Backup the session's story logs
        - 6.5: Close the socket room for that session

    Args:
        session_id: The game session ID
        user_id: The user ID that is disconnecting
    """
    if not session_id or not user_id:
        return

    db = SessionLocal()
    try:
        session = db.query(GameSession).filter(GameSession.id == session_id).first()
        if not session:
            return

        # Only proceed if the disconnecting user is the host
        if session.host_user_id != user_id:
            return

        # Requirement 6.1: Mark session inactive immediately
        session.is_active = False

        # Requirement 6.4: Backup story logs before clearing participants
        try:
            backup_session(session_id)
        except Exception as e:
            print(f"Backup failed for session {session_id}: {e}")

        # Requirement 6.3: Remove all SessionParticipant records
        db.query(SessionParticipant).filter(SessionParticipant.session_id == session_id).delete()

        db.commit()

        logger.info(f"세션 {session_id} 종료: 호스트 연결 해제 (user_id={user_id})")

    except Exception as e:
        print(f"Error in _maybe_end_session_if_host: {e}")
        db.rollback()
    finally:
        db.close()

    room_name = f"session_{session_id}"

    # Requirement 6.2: Broadcast session_ended event with reason "host_disconnected"
    await sio.emit("session_ended", {"session_id": session_id, "reason": "host_disconnected"}, room=room_name)

    # Requirement 6.5: Close the socket room
    try:
        await sio.close_room(room_name)
    except Exception as e:
        print(f"Failed to close room {room_name}: {e}")

    # Clear presence entries for this session
    for sid, info in list(session_presence.items()):
        if info.get("session_id") == session_id:
            session_presence.pop(sid, None)


def _remove_participant_db(session_id: int | None, user_id: int | None) -> None:
    """Remove participant row from DB if present (best-effort)."""
    if not session_id or not user_id:
        return
    db = SessionLocal()
    try:
        participant = (
            db.query(SessionParticipant)
            .filter(
                SessionParticipant.session_id == session_id,
                SessionParticipant.user_id == user_id,
            )
            .first()
        )
        if participant:
            db.delete(participant)
            db.commit()
    except Exception as e:
        print(f"Failed to remove participant from DB (session={session_id}, user={user_id}): {e}")
    finally:
        db.close()
