"""
Session state manager for tracking dice rolls in the 3-phase AI process.

This module provides functions to manage session state during the 3-phase
AI workflow, specifically tracking which players have rolled dice and
collecting their results.

The state can be managed either:
1. In-memory (for volatile, fast access)
2. In database (for persistence across restarts)

Requirements: 1-B.5, 1.4
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models import DiceRollState, SessionParticipant

logger = logging.getLogger("ai_gm.session_state")


@dataclass
class RoundState:
    """
    State for a single round of dice rolling.

    Attributes:
        round_id: Unique identifier for this round
        pending_characters: Set of character IDs that haven't rolled yet
        rolled_characters: Set of character IDs that have rolled
        analyses: Dict mapping character_id to ActionAnalysis data
        dice_results: Dict mapping character_id to dice roll result
        created_at: When this round was created
    """

    round_id: int
    pending_characters: set[int] = field(default_factory=set)
    rolled_characters: set[int] = field(default_factory=set)
    analyses: dict[int, dict[str, Any]] = field(default_factory=dict)
    dice_results: dict[int, int] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


class SessionStateManager:
    """
    Manager for tracking dice roll state across game sessions.

    This class provides both in-memory and database-backed state management
    for the 3-phase AI process. It tracks:
    - Which characters need to roll dice
    - Which characters have already rolled
    - The dice results for each character

    The manager supports multiple concurrent sessions and rounds.

    Requirements:
        - 1-B.5: Track when all players have rolled
        - 1.4: Trigger Phase 3 when all players have rolled
    """

    def __init__(self):
        """Initialize the session state manager with empty state."""
        # In-memory state: {session_id: RoundState}
        self._session_states: dict[int, RoundState] = {}
        # Round counter per session
        self._round_counters: dict[int, int] = {}

    def initialize_round(
        self, session_id: int, character_ids: list[int], analyses: dict[int, dict[str, Any]] | None = None
    ) -> int:
        """
        Initialize a new round of dice rolling for a session.

        This should be called after Phase 1 completes, when all players
        have received their modifiers and DCs.

        Args:
            session_id: ID of the game session
            character_ids: List of character IDs that need to roll
            analyses: Optional dict mapping character_id to analysis data
                      (modifier, difficulty, etc.)

        Returns:
            int: The round_id for this new round

        Requirements: 1-B.5 (track pending dice rolls)
        """
        # Increment round counter
        if session_id not in self._round_counters:
            self._round_counters[session_id] = 0
        self._round_counters[session_id] += 1
        round_id = self._round_counters[session_id]

        # Create new round state
        round_state = RoundState(
            round_id=round_id,
            pending_characters=set(character_ids),
            rolled_characters=set(),
            analyses=analyses or {},
            dice_results={},
        )

        self._session_states[session_id] = round_state

        logger.info(
            f"Initialized round {round_id} for session {session_id} "
            f"with {len(character_ids)} pending characters: {character_ids}"
        )

        return round_id

    def record_dice_roll(self, session_id: int, character_id: int, dice_result: int, db: Session | None = None) -> bool:
        """
        Record a dice roll for a character.

        Args:
            session_id: ID of the game session
            character_id: ID of the character who rolled
            dice_result: The d20 roll result (1-20)
            db: Optional database session for persistence

        Returns:
            bool: True if the roll was recorded, False if character
                  wasn't pending or session not found

        Requirements: 1-B.5 (track dice rolls)
        """
        round_state = self._session_states.get(session_id)
        if not round_state:
            logger.warning(f"No round state found for session {session_id}")
            return False

        if character_id not in round_state.pending_characters:
            logger.warning(f"Character {character_id} not in pending list for session {session_id}")
            return False

        # Move from pending to rolled
        round_state.pending_characters.discard(character_id)
        round_state.rolled_characters.add(character_id)
        round_state.dice_results[character_id] = dice_result

        logger.info(
            f"Recorded dice roll for character {character_id} in session {session_id}: "
            f"dice={dice_result}, pending={len(round_state.pending_characters)}"
        )

        # Optionally persist to database
        if db:
            self._persist_dice_roll(
                db=db,
                session_id=session_id,
                round_id=round_state.round_id,
                character_id=character_id,
                dice_result=dice_result,
            )

        return True

    def _persist_dice_roll(
        self, db: Session, session_id: int, round_id: int, character_id: int, dice_result: int
    ) -> None:
        """
        Persist dice roll to database.

        Args:
            db: Database session
            session_id: ID of the game session
            round_id: ID of the current round
            character_id: ID of the character who rolled
            dice_result: The d20 roll result
        """
        try:
            # Check if record already exists
            existing = (
                db.query(DiceRollState)
                .filter(
                    and_(
                        DiceRollState.session_id == session_id,
                        DiceRollState.round_id == round_id,
                        DiceRollState.character_id == character_id,
                    )
                )
                .first()
            )

            if existing:
                existing.dice_result = dice_result
                existing.has_rolled = True
            else:
                dice_state = DiceRollState(
                    session_id=session_id,
                    round_id=round_id,
                    character_id=character_id,
                    dice_result=dice_result,
                    has_rolled=True,
                )
                db.add(dice_state)

            db.commit()

        except Exception as e:
            logger.error(f"Failed to persist dice roll: {e}")
            db.rollback()

    def check_all_rolled(self, session_id: int) -> bool:
        """
        Check if all players have rolled dice for the current round.

        Args:
            session_id: ID of the game session

        Returns:
            bool: True if all pending characters have rolled,
                  False otherwise

        Requirements: 1-B.5 (check all players rolled)
        """
        round_state = self._session_states.get(session_id)
        if not round_state:
            logger.warning(f"No round state found for session {session_id}")
            return False

        all_rolled = len(round_state.pending_characters) == 0

        logger.debug(
            f"Check all rolled for session {session_id}: "
            f"pending={len(round_state.pending_characters)}, "
            f"rolled={len(round_state.rolled_characters)}, "
            f"all_rolled={all_rolled}"
        )

        return all_rolled

    def get_dice_results(self, session_id: int) -> dict[int, int]:
        """
        Get all dice results for the current round.

        Args:
            session_id: ID of the game session

        Returns:
            Dict[int, int]: Mapping of character_id to dice result

        Requirements: 1.4 (collect dice results for Phase 3)
        """
        round_state = self._session_states.get(session_id)
        if not round_state:
            logger.warning(f"No round state found for session {session_id}")
            return {}

        return dict(round_state.dice_results)

    def get_pending_characters(self, session_id: int) -> set[int]:
        """
        Get the set of characters that haven't rolled yet.

        Args:
            session_id: ID of the game session

        Returns:
            Set[int]: Set of character IDs that haven't rolled
        """
        round_state = self._session_states.get(session_id)
        if not round_state:
            return set()

        return set(round_state.pending_characters)

    def get_rolled_characters(self, session_id: int) -> set[int]:
        """
        Get the set of characters that have already rolled.

        Args:
            session_id: ID of the game session

        Returns:
            Set[int]: Set of character IDs that have rolled
        """
        round_state = self._session_states.get(session_id)
        if not round_state:
            return set()

        return set(round_state.rolled_characters)

    def get_round_state(self, session_id: int) -> RoundState | None:
        """
        Get the current round state for a session.

        Args:
            session_id: ID of the game session

        Returns:
            Optional[RoundState]: The current round state, or None if not found
        """
        return self._session_states.get(session_id)

    def get_analysis(self, session_id: int, character_id: int) -> dict[str, Any] | None:
        """
        Get the analysis data for a specific character.

        Args:
            session_id: ID of the game session
            character_id: ID of the character

        Returns:
            Optional[Dict]: Analysis data (modifier, difficulty, etc.)
        """
        round_state = self._session_states.get(session_id)
        if not round_state:
            return None

        return round_state.analyses.get(character_id)

    def set_analysis(self, session_id: int, character_id: int, analysis: dict[str, Any]) -> bool:
        """
        Store analysis data for a character.

        Args:
            session_id: ID of the game session
            character_id: ID of the character
            analysis: Analysis data (modifier, difficulty, etc.)

        Returns:
            bool: True if stored successfully, False if session not found
        """
        round_state = self._session_states.get(session_id)
        if not round_state:
            logger.warning(f"No round state found for session {session_id}")
            return False

        round_state.analyses[character_id] = analysis
        return True

    def reset_round(self, session_id: int) -> bool:
        """
        Reset the round state for a session.

        This should be called after Phase 3 completes to prepare
        for the next round of actions.

        Args:
            session_id: ID of the game session

        Returns:
            bool: True if reset successfully, False if session not found

        Requirements: 1.4 (reset state after Phase 3)
        """
        if session_id in self._session_states:
            del self._session_states[session_id]
            logger.info(f"Reset round state for session {session_id}")
            return True

        logger.warning(f"No round state found to reset for session {session_id}")
        return False

    def clear_session(self, session_id: int) -> bool:
        """
        Clear all state for a session.

        This should be called when a session ends.

        Args:
            session_id: ID of the game session

        Returns:
            bool: True if cleared successfully
        """
        cleared = False

        if session_id in self._session_states:
            del self._session_states[session_id]
            cleared = True

        if session_id in self._round_counters:
            del self._round_counters[session_id]
            cleared = True

        if cleared:
            logger.info(f"Cleared all state for session {session_id}")

        return cleared


# Global singleton instance
_session_state_manager: SessionStateManager | None = None


def get_session_state_manager() -> SessionStateManager:
    """
    Get the global session state manager instance.

    Returns:
        SessionStateManager: The singleton instance
    """
    global _session_state_manager
    if _session_state_manager is None:
        _session_state_manager = SessionStateManager()
    return _session_state_manager


# =============================================================================
# Database-backed helper functions
# =============================================================================


def initialize_round_from_db(db: Session, session_id: int, round_id: int) -> bool:
    """
    Initialize dice roll state records in database for all session participants.

    Args:
        db: Database session
        session_id: ID of the game session
        round_id: ID of the current round

    Returns:
        bool: True if initialized successfully
    """
    try:
        # Get all participants in the session
        participants = db.query(SessionParticipant).filter(SessionParticipant.session_id == session_id).all()

        for participant in participants:
            # Check if record already exists
            existing = (
                db.query(DiceRollState)
                .filter(
                    and_(
                        DiceRollState.session_id == session_id,
                        DiceRollState.round_id == round_id,
                        DiceRollState.character_id == participant.character_id,
                    )
                )
                .first()
            )

            if not existing:
                dice_state = DiceRollState(
                    session_id=session_id, round_id=round_id, character_id=participant.character_id, has_rolled=False
                )
                db.add(dice_state)

        db.commit()

        logger.info(f"Initialized {len(participants)} dice roll states for session {session_id}, round {round_id}")

        return True

    except Exception as e:
        logger.error(f"Failed to initialize round from DB: {e}")
        db.rollback()
        return False


def check_all_rolled_from_db(db: Session, session_id: int, round_id: int) -> bool:
    """
    Check if all players have rolled dice using database state.

    Args:
        db: Database session
        session_id: ID of the game session
        round_id: ID of the current round

    Returns:
        bool: True if all players have rolled
    """
    try:
        # Count pending rolls
        pending_count = (
            db.query(DiceRollState)
            .filter(
                and_(
                    DiceRollState.session_id == session_id,
                    DiceRollState.round_id == round_id,
                    DiceRollState.has_rolled == False,
                )
            )
            .count()
        )

        return pending_count == 0

    except Exception as e:
        logger.error(f"Failed to check all rolled from DB: {e}")
        return False


def get_dice_results_from_db(db: Session, session_id: int, round_id: int) -> list[dict[str, Any]]:
    """
    Get all dice results from database for a round.

    Args:
        db: Database session
        session_id: ID of the game session
        round_id: ID of the current round

    Returns:
        List[Dict]: List of dice result records
    """
    try:
        results = (
            db.query(DiceRollState)
            .filter(
                and_(
                    DiceRollState.session_id == session_id,
                    DiceRollState.round_id == round_id,
                    DiceRollState.has_rolled == True,
                )
            )
            .all()
        )

        return [
            {"character_id": r.character_id, "dice_result": r.dice_result, "judgment_id": r.judgment_id}
            for r in results
        ]

    except Exception as e:
        logger.error(f"Failed to get dice results from DB: {e}")
        return []


def reset_round_in_db(db: Session, session_id: int, round_id: int) -> bool:
    """
    Reset dice roll state in database for a round.

    Args:
        db: Database session
        session_id: ID of the game session
        round_id: ID of the current round

    Returns:
        bool: True if reset successfully
    """
    try:
        db.query(DiceRollState).filter(
            and_(DiceRollState.session_id == session_id, DiceRollState.round_id == round_id)
        ).delete()

        db.commit()

        logger.info(f"Reset dice roll state for session {session_id}, round {round_id}")

        return True

    except Exception as e:
        logger.error(f"Failed to reset round in DB: {e}")
        db.rollback()
        return False
