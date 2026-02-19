"""
AI 게임 마스터 서비스 V2 - 리팩토링 버전

LangChain을 직접 사용하여 더 명확한 구조로 재작성했습니다.
프롬프트 로딩과 AI 호출 로직이 분리되어 있어 이해하기 쉽습니다.

주요 변경사항:
- PromptLoader를 사용한 명확한 프롬프트 관리
- 각 Phase를 독립적인 노드 함수로 분리
- LangChain ChatOpenAI를 직접 사용
- LangGraph 없이 단순한 함수 호출 체인
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import AsyncIterator

from sqlalchemy.orm import Session

from app.models import ActionJudgment, Character, CharacterGrowthLog, GameSession, StoryAct, StoryLog
from app.schemas import (
    ActionAnalysis,
    ActTransitionResult,
    DiceResult,
    GrowthReward,
    JudgmentOutcome,
    JudgmentResult,
    NarrativeResult,
    PlayerAction,
    StoryActInfo,
)
from app.services.ai_nodes import analyze_and_judge_actions, generate_narrative, generate_narrative_streaming
from app.services.ai_nodes.narrative_node import parse_narrative_xml
from app.services.background_task_manager import get_task_manager
from app.services.context_loader import ContextLoadError, GameContext, load_game_context
from app.services.dice_system import DiceSystem
from app.services.session_state_manager import get_session_state_manager
from app.services.story_director import get_story_director_service
from app.services.stream_buffer import get_buffer_manager
from app.services.act_resolver import resolve_current_open_act

logger = logging.getLogger("ai_gm.service_v2")


class AIGMServiceV2:
    """
    AI 게임 마스터 서비스 V2

    더 명확한 구조로 재작성된 버전:
    - 프롬프트 로딩이 명확함
    - AI 호출부가 분리되어 있음
    - 각 Phase의 역할이 명확함

    사용 예시:
        service = AIGMServiceV2(db=db_session)

        # Phase 1: 행동 분석
        analyses = await service.analyze_actions(
            session_id=1,
            player_actions=[...]
        )

        # Phase 2: 플레이어가 주사위 굴림 (프론트엔드)

        # Phase 3: 서술 생성
        result = await service.generate_narrative(
            session_id=1,
            dice_results=[...]
        )
    """

    def __init__(self, db: Session, llm_model: str = "gpt-4o"):
        """
        AI GM 서비스를 초기화합니다.

        Args:
            db: SQLAlchemy 데이터베이스 세션
            llm_model: 사용할 LLM 모델 (기본값: "gpt-4o")
        """
        self.db = db
        self.llm_model = llm_model
        self.dice_system = DiceSystem()

        logger.info(f"AIGMServiceV2 초기화: 모델={llm_model}")

    async def analyze_actions(self, session_id: int, player_actions: list[PlayerAction]) -> list[ActionAnalysis]:
        """
        Phase 1: 플레이어 행동을 분석하고 보정치 + DC를 반환합니다.

        **Enhanced with Pre-rolling and Background Generation**

        프로세스:
        1. 게임 컨텍스트 로드 (세션, 캐릭터, 히스토리)
        2. 캐릭터 스탯에서 보정치 계산
        3. AI를 사용하여 난이도(DC) 결정
        4. **NEW: 모든 주사위 미리 굴림 (phase=0)**
        5. **NEW: 백그라운드에서 이야기 생성 시작**

        Args:
            session_id: 게임 세션 ID
            player_actions: 분석할 플레이어 행동 목록

        Returns:
            List[ActionAnalysis]: 각 행동에 대한 보정치와 DC

        Raises:
            ValueError: 입력 검증 실패 또는 컨텍스트 로드 실패 시

        Requirements: 1.1, 1.2
        """
        logger.info(f"Phase 1 - 행동 분석 시작: 세션={session_id}, 행동 수={len(player_actions)}")

        # 입력 검증
        if not player_actions:
            raise ValueError("플레이어 행동이 제공되지 않았습니다")

        try:
            # 게임 컨텍스트 로드
            game_context = load_game_context(
                db=self.db,
                session_id=session_id,
                system_prompt="",  # Phase 1에서는 시스템 프롬프트 불필요
            )

            logger.debug(
                f"Context loaded: {len(game_context.characters)} characters, "
                f"{len(game_context.story_history)} history entries"
            )

            # AI 노드 호출
            analyses = await analyze_and_judge_actions(
                player_actions=player_actions,
                characters=game_context.characters,
                world_context=game_context.world_prompt,
                story_history=game_context.story_history[-1:],
                llm_model=self.llm_model,
                ai_summary=game_context.ai_summary,
            )

            logger.info(f"Phase 1 완료: {len(analyses)}개 행동 분석됨")

            # **NEW: 주사위 미리 굴림**
            judgments = await self._preroll_dice(session_id, analyses)

            # **NEW: 버퍼 생성**
            buffer_manager = get_buffer_manager()
            await buffer_manager.create_buffer(session_id)
            logger.info(f"스트림 버퍼 생성: 세션={session_id}")

            # **NEW: 백그라운드에서 이야기 생성 시작**
            task_manager = get_task_manager()
            await task_manager.start_task(
                session_id,  # For task tracking
                self._generate_narrative_background,
                session_id,  # First positional arg for the coroutine
                judgments,
                game_context,
            )
            logger.info(f"백그라운드 이야기 생성 시작: 세션={session_id}")

            return analyses

        except ContextLoadError as e:
            logger.error(f"컨텍스트 로드 실패: {e}")
            raise ValueError(f"게임 컨텍스트 로드 실패: {e!s}") from e

        except Exception as e:
            logger.error(f"Phase 1 실패: {e}", exc_info=True)
            raise ValueError(f"행동 분석 실패: {e!s}") from e

    async def generate_narrative(self, session_id: int, dice_results: list[DiceResult]) -> NarrativeResult:
        """
        Phase 3: 주사위 결과를 바탕으로 서술을 생성합니다.

        프로세스:
        1. 게임 컨텍스트 로드
        2. 판정 결과 계산 (주사위 + 보정치 vs DC)
        3. AI를 사용하여 서술 생성
        4. 결과를 데이터베이스에 저장

        Args:
            session_id: 게임 세션 ID
            dice_results: 플레이어 주사위 결과 목록

        Returns:
            NarrativeResult: 판정 결과와 서술이 포함된 완전한 결과

        Raises:
            ValueError: 입력 검증 실패 또는 처리 실패 시
        """
        logger.info(f"Phase 3 - 이야기 생성 시작: 세션={session_id}, 주사위 결과={len(dice_results)}개")

        # 입력 검증
        if not dice_results:
            raise ValueError("주사위 결과가 제공되지 않았습니다")

        try:
            # 게임 컨텍스트 로드
            game_context = load_game_context(
                db=self.db,
                session_id=session_id,
                system_prompt="",  # Phase 3에서는 시스템 프롬프트 불필요
            )

            logger.debug(
                f"Context loaded: {len(game_context.characters)} characters, "
                f"{len(game_context.story_history)} history entries"
            )

            # 판정 결과 계산
            judgments = self._judge_dice_results(dice_results)

            logger.debug(f"판정 계산 완료: {len(judgments)}개")

            # AI 노드 호출하여 서술 생성
            # 막 컨텍스트 구성
            act_context = None
            if game_context.current_act:
                act = game_context.current_act
                act_context = f"{act.act_number}막 — {act.title}"
                if act.subtitle:
                    act_context += f": {act.subtitle}"

            director_service = get_story_director_service()
            director_guidance = director_service.build_guidance(
                session_id=session_id,
                world_context=game_context.world_prompt,
                ai_summary=game_context.ai_summary,
                judgments=judgments,
            )

            raw_narrative = await generate_narrative(
                judgments=judgments,
                characters=game_context.characters,
                world_context=game_context.world_prompt,
                story_history=game_context.story_history,
                llm_model=self.llm_model,
                act_context=act_context,
                ai_summary=game_context.ai_summary,
                director_guidance=director_guidance,
            )

            # XML 파싱: clean narrative + metadata 분리
            narrative, metadata = parse_narrative_xml(raw_narrative)

            # Story Director 상태 확정 반영 (tension/arc)
            director_service.commit_after_narrative(
                session_id=session_id,
                world_context=game_context.world_prompt,
                ai_summary=game_context.ai_summary,
                judgments=judgments,
                metadata=metadata,
            )

            logger.debug(f"이야기 생성 완료: {len(narrative)}자")

            # 데이터베이스에 저장
            self._save_results(session_id=session_id, judgments=judgments, narrative=narrative)

            logger.info("Phase 3 완료: 이야기 DB 저장됨")

            # 상태 효과 회복 체크
            self._apply_status_recovery(session_id)

            # 결과 반환
            result = NarrativeResult(
                session_id=session_id,
                judgments=judgments,
                full_narrative=narrative,
                narrative_metadata=metadata,
                is_complete=True,
            )

            return result

        except ContextLoadError as e:
            logger.error(f"컨텍스트 로드 실패: {e}")
            raise ValueError(f"게임 컨텍스트 로드 실패: {e!s}") from e

        except Exception as e:
            logger.error(f"Phase 3 실패: {e}", exc_info=True)
            raise ValueError(f"서술 생성 실패: {e!s}") from e

    async def regenerate_latest_story(self, session_id: int) -> StoryLog:
        """최근 AI 스토리 로그를 같은 행동/판정 결과로 재생성합니다."""
        latest_ai_log = (
            self.db.query(StoryLog)
            .filter(StoryLog.session_id == session_id, StoryLog.role == "AI")
            .order_by(StoryLog.id.desc())
            .first()
        )
        if not latest_ai_log:
            raise ValueError("재생성할 AI 스토리 로그가 없습니다")

        judgment_rows = (
            self.db.query(ActionJudgment)
            .filter(ActionJudgment.session_id == session_id, ActionJudgment.story_log_id == latest_ai_log.id)
            .order_by(ActionJudgment.id.asc())
            .all()
        )
        if not judgment_rows:
            raise ValueError("최근 스토리에 연결된 판정 결과가 없어 재생성할 수 없습니다")

        judgments: list[JudgmentResult] = []
        for row in judgment_rows:
            if row.outcome is None:
                continue
            try:
                outcome = JudgmentOutcome(row.outcome)
            except Exception:
                logger.warning(f"알 수 없는 판정 결과 값 스킵: {row.outcome}")
                continue

            judgments.append(
                JudgmentResult(
                    character_id=row.character_id,
                    action_text=row.action_text,
                    dice_result=row.dice_result if row.dice_result is not None else 1,
                    modifier=row.modifier,
                    final_value=row.final_value if row.final_value is not None else row.modifier,
                    difficulty=row.difficulty,
                    outcome=outcome,
                    outcome_reasoning=row.difficulty_reasoning or "",
                )
            )

        if not judgments:
            raise ValueError("유효한 판정 결과가 없어 재생성할 수 없습니다")

        game_context = load_game_context(
            db=self.db,
            session_id=session_id,
            system_prompt="",
        )

        act_context = None
        if game_context.current_act:
            act = game_context.current_act
            act_context = f"{act.act_number}막 — {act.title}"
            if act.subtitle:
                act_context += f": {act.subtitle}"

        director_service = get_story_director_service()
        director_guidance = director_service.build_guidance(
            session_id=session_id,
            world_context=game_context.world_prompt,
            ai_summary=game_context.ai_summary,
            judgments=judgments,
        )

        raw_narrative = await generate_narrative(
            judgments=judgments,
            characters=game_context.characters,
            world_context=game_context.world_prompt,
            story_history=game_context.story_history,
            llm_model=self.llm_model,
            act_context=act_context,
            ai_summary=game_context.ai_summary,
            director_guidance=director_guidance,
        )

        narrative, metadata = parse_narrative_xml(raw_narrative)

        director_service.commit_after_narrative(
            session_id=session_id,
            world_context=game_context.world_prompt,
            ai_summary=game_context.ai_summary,
            judgments=judgments,
            metadata=metadata,
        )

        latest_ai_log.content = narrative
        if metadata is not None and "event_triggered" in metadata:
            latest_ai_log.event_triggered = bool(metadata.get("event_triggered"))
        self.db.commit()
        self.db.refresh(latest_ai_log)

        return latest_ai_log

    def _judge_dice_results(self, dice_results: list[DiceResult]) -> list[JudgmentResult]:
        """
        주사위 결과를 판정합니다.

        판정 규칙:
        - 주사위 1: 자동 대실패
        - 주사위 20: 자동 대성공
        - 최종값 >= DC: 성공
        - 최종값 < DC: 실패

        Args:
            dice_results: 주사위 결과 목록

        Returns:
            List[JudgmentResult]: 판정 결과 목록
        """
        judgments = []

        for dice_result in dice_results:
            # 최종값 계산
            final_value = dice_result.dice_roll + dice_result.modifier

            # 결과 판정
            outcome = self.dice_system.determine_outcome(
                dice_result=dice_result.dice_roll, modifier=dice_result.modifier, difficulty=dice_result.difficulty
            )

            # 판정 결과 생성
            judgment = JudgmentResult(
                character_id=dice_result.character_id,
                action_text=dice_result.action_text,
                dice_result=dice_result.dice_roll,
                modifier=dice_result.modifier,
                final_value=final_value,
                difficulty=dice_result.difficulty,
                outcome=outcome,
                outcome_reasoning=self._get_outcome_reasoning(
                    dice_result.dice_roll, final_value, dice_result.difficulty, outcome
                ),
            )
            judgments.append(judgment)

            logger.debug(
                f"Character {dice_result.character_id}: "
                f"dice={dice_result.dice_roll}, modifier={dice_result.modifier:+d}, "
                f"final={final_value}, DC={dice_result.difficulty}, "
                f"outcome={outcome.value}"
            )

        return judgments

    def _get_outcome_reasoning(
        self, dice_result: int, final_value: int, difficulty: int, outcome: JudgmentOutcome
    ) -> str:
        """
        판정 결과에 대한 설명을 생성합니다.

        Args:
            dice_result: 주사위 결과
            final_value: 최종값 (주사위 + 보정치)
            difficulty: 난이도
            outcome: 판정 결과

        Returns:
            str: 판정 설명 (한국어)
        """
        if outcome == JudgmentOutcome.CRITICAL_FAILURE:
            if dice_result == 1:
                return "1이 나와 자동으로 대실패했습니다."
            return f"최종 값 {final_value}이(가) 난이도 {difficulty}보다 10 이상 낮아 대실패했습니다."

        if outcome == JudgmentOutcome.FAILURE:
            return f"최종 값 {final_value}이(가) 난이도 {difficulty}에 미치지 못해 실패했습니다."

        if outcome == JudgmentOutcome.SUCCESS:
            return f"최종 값 {final_value}이(가) 난이도 {difficulty}을(를) 넘어 성공했습니다."

        if outcome == JudgmentOutcome.CRITICAL_SUCCESS:
            if dice_result == 20:
                return "20이 나와 자동으로 대성공했습니다!"
            return f"최종 값 {final_value}이(가) 난이도 {difficulty}보다 10 이상 높아 대성공했습니다!"

        return "판정이 완료되었습니다."

    async def _preroll_dice(self, session_id: int, analyses: list[ActionAnalysis]) -> list[JudgmentResult]:
        """
        모든 행동에 대해 주사위를 미리 굴리고 데이터베이스에 저장합니다.

        이 메서드는 Phase 1에서 호출되어 모든 주사위 결과를 사전에 생성합니다.
        생성된 결과는 phase=0으로 저장되어 플레이어에게 아직 공개되지 않은 상태입니다.

        Args:
            session_id: 게임 세션 ID
            analyses: 행동 분석 결과 목록

        Returns:
            List[JudgmentResult]: 사전 굴림된 판정 결과 목록

        Requirements: 1.1, 8.1
        """
        logger.info(f"주사위 사전 굴림: 세션={session_id}, 행동 수={len(analyses)}")

        judgments = []

        try:
            for analysis in analyses:
                if not analysis.requires_roll:
                    # 자동 성공: 주사위 굴림 불필요
                    judgment = JudgmentResult(
                        character_id=analysis.character_id,
                        action_text=analysis.action_text,
                        dice_result=0,
                        modifier=analysis.modifier,
                        final_value=0,
                        difficulty=0,
                        outcome=JudgmentOutcome.AUTO_SUCCESS,
                        outcome_reasoning="위험이나 대립이 없는 행동으로, 자동으로 성공합니다.",
                        requires_roll=False,
                    )
                    judgments.append(judgment)

                    # DB에 phase=0으로 저장 (플레이어 확인 대기)
                    action_judgment = ActionJudgment(
                        session_id=session_id,
                        character_id=analysis.character_id,
                        action_text=analysis.action_text,
                        action_type=analysis.action_type.value,
                        dice_result=0,
                        modifier=analysis.modifier,
                        final_value=0,
                        difficulty=0,
                        difficulty_reasoning=analysis.difficulty_reasoning,
                        outcome="auto_success",
                        phase=0,  # Phase 0: 플레이어 확인 대기 (자동 성공도 확인 필요)
                        created_at=datetime.utcnow(),
                    )
                    self.db.add(action_judgment)

                    logger.debug(f"Auto-success for character {analysis.character_id}: {analysis.action_text}")
                    continue

                # 주사위 굴림 (1-20)
                dice_roll = random.randint(1, 20)

                # 최종값 계산
                final_value = dice_roll + analysis.modifier

                # 결과 판정
                outcome = self.dice_system.determine_outcome(
                    dice_result=dice_roll, modifier=analysis.modifier, difficulty=analysis.difficulty
                )

                # 판정 결과 생성
                judgment = JudgmentResult(
                    character_id=analysis.character_id,
                    action_text=analysis.action_text,
                    dice_result=dice_roll,
                    modifier=analysis.modifier,
                    final_value=final_value,
                    difficulty=analysis.difficulty,
                    outcome=outcome,
                    outcome_reasoning=self._get_outcome_reasoning(dice_roll, final_value, analysis.difficulty, outcome),
                )
                judgments.append(judgment)

                # 데이터베이스에 phase=0으로 저장 (사전 굴림)
                action_judgment = ActionJudgment(
                    session_id=session_id,
                    character_id=analysis.character_id,
                    action_text=analysis.action_text,
                    action_type=analysis.action_type.value,
                    dice_result=dice_roll,
                    modifier=analysis.modifier,
                    final_value=final_value,
                    difficulty=analysis.difficulty,
                    difficulty_reasoning=analysis.difficulty_reasoning,
                    outcome=outcome.value,
                    phase=0,  # Phase 0: 사전 굴림 (플레이어에게 아직 공개 안됨)
                    created_at=datetime.utcnow(),
                )
                self.db.add(action_judgment)

                logger.debug(
                    f"Pre-rolled for character {analysis.character_id}: "
                    f"dice={dice_roll}, modifier={analysis.modifier:+d}, "
                    f"final={final_value}, DC={analysis.difficulty}, "
                    f"outcome={outcome.value}"
                )

            # 커밋
            self.db.commit()

            logger.info(f"주사위 사전 굴림 완료: {len(judgments)}개 결과 저장")

            return judgments

        except Exception as e:
            logger.error(f"주사위 사전 굴림 실패: {e}", exc_info=True)
            self.db.rollback()
            raise

    async def _generate_narrative_background(
        self, session_id: int, judgments: list[JudgmentResult], game_context: GameContext
    ):
        """
        백그라운드에서 이야기를 생성하고 버퍼에 저장합니다.

        이 메서드는 LLM 스트리밍 API를 호출하여 토큰을 하나씩 받아
        StreamBuffer에 저장합니다. 이 작업은 백그라운드 태스크로 실행되며,
        플레이어가 주사위를 확인하는 동안 병렬로 진행됩니다.

        Args:
            session_id: 게임 세션 ID
            judgments: 사전 굴림된 판정 결과 목록
            game_context: 게임 컨텍스트 (캐릭터, 세계관, 히스토리)

        Requirements: 1.2, 1.4
        """
        logger.info(f"백그라운드 이야기 생성 시작: 세션={session_id}")

        # 버퍼 가져오기
        buffer_manager = get_buffer_manager()
        buffer = buffer_manager.get_buffer(session_id)

        if not buffer:
            logger.error(f"버퍼를 찾을 수 없음: 세션={session_id}")
            return

        try:
            # 랜덤 이벤트 확률 판정
            from app.services.event_probability import roll_event_trigger, update_event_probability

            event_triggered = roll_event_trigger(session_id, self.db)

            # 버퍼에 이벤트 발생 여부 저장
            buffer.event_triggered = event_triggered

            # 막 컨텍스트 구성
            act_context = None
            if game_context.current_act:
                act = game_context.current_act
                act_context = f"{act.act_number}막 — {act.title}"
                if act.subtitle:
                    act_context += f": {act.subtitle}"

            director_service = get_story_director_service()
            director_guidance = director_service.build_guidance(
                session_id=session_id,
                world_context=game_context.world_prompt,
                ai_summary=game_context.ai_summary,
                judgments=judgments,
            )

            # LLM 스트리밍 호출
            token_count = 0
            async for token in generate_narrative_streaming(
                judgments=judgments,
                characters=game_context.characters,
                world_context=game_context.world_prompt,
                story_history=game_context.story_history,
                llm_model=self.llm_model,
                act_context=act_context,
                ai_summary=game_context.ai_summary,
                event_triggered=event_triggered,
                director_guidance=director_guidance,
            ):
                # 버퍼에 토큰 추가
                success = await buffer.add_token(token)
                token_count += 1
                logger.debug(f"Added token {token_count} to buffer for session {session_id}")
                if not success:
                    logger.warning(f"버퍼 가득 참: 세션={session_id}, 생성 중단")
                    break

            # XML 파싱: 메타데이터 추출
            raw_text = buffer.get_full_text()
            narrative, metadata = parse_narrative_xml(raw_text)

            # Story Director 상태 확정 반영 (tension/arc)
            director_service.commit_after_narrative(
                session_id=session_id,
                world_context=game_context.world_prompt,
                ai_summary=game_context.ai_summary,
                judgments=judgments,
                metadata=metadata,
            )

            # 메타데이터를 버퍼에 저장 (핸들러에서 참조)
            buffer.set_metadata(metadata)

            # 버퍼 토큰을 clean narrative로 교체
            async with buffer._lock:
                buffer.tokens.clear()
                buffer._total_chars = 0
                if narrative:
                    buffer.tokens.append(narrative)
                    buffer._total_chars = len(narrative)

            # 이벤트 확률 갱신 (발동 시 리셋, 미발동 시 증가)
            update_event_probability(session_id, self.db, event_fired=event_triggered)

            buffer.mark_complete()
            logger.info(f"백그라운드 이야기 생성 완료: 세션={session_id}")

        except asyncio.CancelledError:
            # Timeout/cancel must leave the buffer in a terminal state.
            # Otherwise stream_narrative() can wait forever.
            error_msg = "이야기 생성이 취소되었습니다(타임아웃 또는 중단)."
            logger.warning(f"백그라운드 생성 취소: 세션={session_id}")
            buffer.mark_error(error_msg)
            raise

        except Exception as e:
            error_msg = f"이야기 생성 실패: {str(e)}"
            logger.error(f"백그라운드 생성 에러: 세션={session_id}, {e}", exc_info=True)
            buffer.mark_error(error_msg)

    async def confirm_dice_roll(
        self, session_id: int, character_id: int, judgment_id: int | None = None
    ) -> DiceResult:
        """
        주사위 확인 - 미리 굴린 주사위 값을 반환합니다.

        이 메서드는 Phase 2에서 호출되며, 플레이어가 "주사위 굴리기" 버튼을
        클릭했을 때 실행됩니다. 실제로는 주사위를 굴리지 않고, Phase 1에서
        미리 굴려둔 값(phase=0)을 조회하여 반환합니다.

        Args:
            session_id: 게임 세션 ID
            character_id: 캐릭터 ID

        Returns:
            DiceResult: 사전 굴림된 주사위 결과

        Raises:
            ValueError: 사전 굴림된 주사위를 찾을 수 없을 때

        Requirements: 3.2, 3.4, 8.2
        """
        logger.info(f"주사위 확인: 세션={session_id}, 캐릭터={character_id}, 판정={judgment_id}")

        try:
            judgment = None

            # 신규 클라이언트: judgment_id를 지정해 정확한 판정을 확인
            if judgment_id is not None:
                judgment = (
                    self.db.query(ActionJudgment)
                    .filter(
                        ActionJudgment.id == judgment_id,
                        ActionJudgment.session_id == session_id,
                        ActionJudgment.character_id == character_id,
                    )
                    .first()
                )
                if not judgment:
                    raise ValueError(
                        f"판정을 찾을 수 없습니다: session={session_id}, "
                        f"character={character_id}, judgment={judgment_id}"
                    )

                # 정상 흐름: phase 0 -> 2
                if judgment.phase == 0:
                    judgment.phase = 2
                    self.db.commit()
                # 중복 클릭/재전송: 이미 처리된 판정이면 그대로 성공 처리
                elif judgment.phase in (2, 3):
                    logger.info(
                        "이미 확인된 판정 재요청으로 간주합니다: "
                        f"judgment={judgment.id}, phase={judgment.phase}"
                    )
                else:
                    raise ValueError(
                        f"확인 가능한 판정 단계가 아닙니다: "
                        f"judgment={judgment.id}, phase={judgment.phase}"
                    )
            else:
                # 레거시 클라이언트 호환: judgment_id 없이 가장 최근 phase=0 판정 확인
                judgment = (
                    self.db.query(ActionJudgment)
                    .filter(
                        ActionJudgment.session_id == session_id,
                        ActionJudgment.character_id == character_id,
                        ActionJudgment.phase == 0,
                    )
                    .order_by(ActionJudgment.id.desc())
                    .first()
                )

                if judgment:
                    judgment.phase = 2
                    self.db.commit()
                else:
                    # 레이스/중복 요청 대응: 이미 2/3으로 전환된 가장 최근 판정을 반환
                    judgment = (
                        self.db.query(ActionJudgment)
                        .filter(
                            ActionJudgment.session_id == session_id,
                            ActionJudgment.character_id == character_id,
                            ActionJudgment.phase.in_([2, 3]),
                        )
                        .order_by(ActionJudgment.id.desc())
                        .first()
                    )
                    if not judgment:
                        raise ValueError(
                            f"사전 굴림된 주사위 없음: 세션={session_id}, 캐릭터={character_id}"
                        )
                    logger.info(
                        "phase=0 판정이 없어 최신 확정 판정을 반환합니다: "
                        f"judgment={judgment.id}, phase={judgment.phase}"
                    )

            if judgment is None:
                raise ValueError("판정 조회 실패")

            logger.info(
                f"주사위 확인 완료: 캐릭터={character_id}, "
                f"주사위={judgment.dice_result}, 최종={judgment.final_value}, "
                f"결과={judgment.outcome}"
            )

            # 결과 반환
            raw_dice = judgment.dice_result if judgment.dice_result is not None else 1
            raw_difficulty = judgment.difficulty if judgment.difficulty is not None else 5
            return DiceResult(
                character_id=character_id,
                action_text=judgment.action_text,
                dice_roll=min(max(raw_dice, 1), 20),
                modifier=judgment.modifier,
                difficulty=min(max(raw_difficulty, 5), 30),
            )

        except Exception as e:
            logger.error(f"주사위 확인 실패: {e}", exc_info=True)
            self.db.rollback()
            raise

    async def stream_narrative(self, session_id: int) -> AsyncIterator[str]:
        """
        버퍼에서 이야기를 스트리밍으로 전송합니다.

        Wait-for-Completion 전략:
        백그라운드 생성이 Phase 1에서 시작되고, 클라이언트 소비는 Phase 3에서
        발생하므로 보통 이미 완료 상태입니다. 완료를 기다린 후 clean narrative를
        청크로 스트리밍합니다.

        Args:
            session_id: 게임 세션 ID

        Yields:
            str: 이야기 토큰

        Raises:
            ValueError: 버퍼를 찾을 수 없거나 에러가 발생한 경우
        """
        logger.info(f"이야기 스트리밍 시작: 세션={session_id}")

        # 버퍼 가져오기
        buffer_manager = get_buffer_manager()
        buffer = buffer_manager.get_buffer(session_id)

        if not buffer:
            raise ValueError(f"이야기 버퍼 없음: 세션={session_id}")

        if buffer.error:
            raise ValueError(f"이야기 생성 실패: {buffer.error}")

        # 버퍼 완료 대기 (백그라운드 생성이 끝날 때까지)
        wait_count = 0
        while not buffer.is_complete:
            if buffer.error:
                raise ValueError(f"이야기 생성 실패: {buffer.error}")
            await asyncio.sleep(0.1)
            wait_count += 1
            if wait_count % 100 == 0:
                logger.debug(f"버퍼 완료 대기 중: 세션={session_id}, {wait_count * 0.1:.1f}초 경과")

        if buffer.error:
            raise ValueError(f"이야기 생성 실패: {buffer.error}")

        # clean narrative를 청크로 스트리밍
        full_narrative = buffer.get_full_text()
        chunk_size = 4  # 한국어 기준 자연스러운 타이핑 효과
        token_count = 0

        for i in range(0, len(full_narrative), chunk_size):
            chunk = full_narrative[i:i + chunk_size]
            yield chunk
            token_count += 1
            await asyncio.sleep(0.03)  # 30ms per chunk

        logger.info(f"이야기 스트리밍 완료: 세션={session_id}, 청크={token_count}개")

        # 버퍼에서 이벤트 발생 여부 가져오기
        event_triggered = buffer.event_triggered if buffer else False

        try:
            await self._save_narrative_to_database(session_id, full_narrative, event_triggered=event_triggered)
            logger.info(f"이야기 DB 저장 완료: 세션={session_id}")
            # 상태 효과 회복 체크
            self._apply_status_recovery(session_id)
        except Exception as e:
            logger.error(f"이야기 저장 실패: {e}", exc_info=True)

    async def _save_narrative_to_database(self, session_id: int, narrative: str, event_triggered: bool = False):
        """
        이야기를 데이터베이스에 저장합니다.

        StoryLog를 생성하고 모든 ActionJudgment를 phase=3으로 업데이트합니다.
        단일 트랜잭션으로 처리됩니다.

        Args:
            session_id: 게임 세션 ID
            narrative: 생성된 이야기 전체 텍스트
            event_triggered: 돌발이벤트 발생 여부

        Requirements: 8.4, 8.5
        """
        try:
            current_act = resolve_current_open_act(self.db, session_id)

            # StoryLog 생성
            story_log = StoryLog(
                session_id=session_id,
                role="AI",
                content=narrative,
                act_id=current_act.id if current_act else None,
                event_triggered=event_triggered,
                created_at=datetime.utcnow(),
            )
            self.db.add(story_log)
            self.db.flush()  # story_log.id 획득

            # 모든 phase=2 ActionJudgment를 phase=3으로 업데이트
            judgments = (
                self.db.query(ActionJudgment)
                .filter(ActionJudgment.session_id == session_id, ActionJudgment.phase == 2)
                .all()
            )

            for judgment in judgments:
                judgment.story_log_id = story_log.id
                judgment.phase = 3  # Phase 3: 서술 완료

            # 직전 USER StoryLog에 판정 스냅샷 저장
            if judgments:
                char_ids = {j.character_id for j in judgments}
                char_name_map = {
                    c.id: c.name
                    for c in self.db.query(Character).filter(Character.id.in_(char_ids)).all()
                }

                latest_user_log = (
                    self.db.query(StoryLog)
                    .filter(StoryLog.session_id == session_id, StoryLog.role == "USER")
                    .order_by(StoryLog.created_at.desc())
                    .first()
                )
                if latest_user_log:
                    latest_user_log.judgments_data = [
                        {
                            "id": j.id,
                            "character_id": j.character_id,
                            "character_name": char_name_map.get(
                                j.character_id, f"캐릭터 {j.character_id}"
                            ),
                            "action_text": j.action_text,
                            "action_type": j.action_type,
                            "dice_result": j.dice_result,
                            "modifier": j.modifier,
                            "final_value": j.final_value,
                            "difficulty": j.difficulty,
                            "outcome": j.outcome,
                        }
                        for j in judgments
                    ]

            # 커밋
            self.db.commit()

            logger.info(f"이야기 DB 저장: story_log_id={story_log.id}, {len(judgments)}개 판정 phase=3으로 업데이트")

        except Exception as e:
            logger.error(f"이야기 DB 저장 실패: {e}", exc_info=True)
            self.db.rollback()
            raise

    def _save_results(self, session_id: int, judgments: list[JudgmentResult], narrative: str) -> None:
        """
        판정 결과와 서술을 데이터베이스에 저장합니다.

        Args:
            session_id: 게임 세션 ID
            judgments: 판정 결과 목록
            narrative: 생성된 서술

        Raises:
            Exception: 데이터베이스 저장 실패 시
        """
        try:
            current_act = resolve_current_open_act(self.db, session_id)

            # 서술을 story_logs에 저장
            story_log = StoryLog(
                session_id=session_id,
                role="AI",
                content=narrative,
                act_id=current_act.id if current_act else None,
                created_at=datetime.utcnow(),
            )
            self.db.add(story_log)
            self.db.flush()  # story_log.id 획득

            # 판정 결과를 action_judgments에 저장
            for judgment in judgments:
                action_judgment = ActionJudgment(
                    session_id=session_id,
                    character_id=judgment.character_id,
                    story_log_id=story_log.id,
                    action_text=judgment.action_text,
                    dice_result=judgment.dice_result,
                    modifier=judgment.modifier,
                    final_value=judgment.final_value,
                    difficulty=judgment.difficulty,
                    outcome=judgment.outcome.value,
                    phase=3,  # Phase 3 (서술 완료)
                    created_at=datetime.utcnow(),
                )
                self.db.add(action_judgment)

            # 커밋
            self.db.commit()

            logger.debug(f"DB 저장 완료: 스토리 로그 1개, 판정 {len(judgments)}개")

        except Exception as e:
            logger.error(f"결과 저장 실패: {e}", exc_info=True)
            self.db.rollback()
            raise

    def _apply_status_recovery(self, session_id: int) -> None:
        """
        페이즈 기반 상태 회복을 적용합니다.

        매 내러티브 완료 후 호출됩니다.
        3 페이즈마다 모든 캐릭터의 구조화된 상태 효과의 severity를 1 감소시키고,
        severity가 0이 된 효과는 제거합니다.

        Args:
            session_id: 게임 세션 ID
        """
        state_manager = get_session_state_manager()
        phase = state_manager.increment_phase(session_id)

        if not state_manager.should_apply_recovery(session_id):
            logger.debug(f"Phase {phase}: 회복 미적용 (3페이즈마다 적용)")
            return

        logger.info(f"Phase {phase}: 상태 회복 적용 시작 (세션={session_id})")

        try:
            # 세션에 속한 캐릭터 조회
            characters = self.db.query(Character).filter(Character.session_id == session_id).all()

            for char in characters:
                data = char.data or {}
                status_effects = data.get("status_effects", [])

                if not status_effects:
                    continue

                updated_effects = []
                for effect in status_effects:
                    if isinstance(effect, dict) and "severity" in effect:
                        # 구조화된 효과: severity 감소
                        new_severity = effect["severity"]
                        if new_severity < 0:
                            new_severity = min(new_severity + 1, 0)  # 디버프 회복
                        elif new_severity > 0:
                            new_severity = max(new_severity - 1, 0)  # 버프 감소

                        if new_severity != 0:
                            effect["severity"] = new_severity
                            effect["modifier"] = new_severity  # modifier도 동기화
                            updated_effects.append(effect)
                        else:
                            logger.info(f"캐릭터 {char.id}: 상태 '{effect.get('name', '?')}' 회복 완료")
                    else:
                        # 문자열 효과: 유지 (수동 제거만 가능)
                        updated_effects.append(effect)

                if len(updated_effects) != len(status_effects):
                    data["status_effects"] = updated_effects
                    char.data = data
                    # SQLAlchemy JSON 변경 감지를 위해 flag
                    from sqlalchemy.orm.attributes import flag_modified

                    flag_modified(char, "data")

            self.db.commit()
            logger.info(f"Phase {phase}: 상태 회복 적용 완료 (세션={session_id})")

        except Exception as e:
            logger.error(f"상태 회복 적용 실패: {e}", exc_info=True)
            self.db.rollback()

    async def check_act_transition(self, session_id: int) -> ActTransitionResult | None:
        """서술 완료 후 막 전환을 분석합니다.

        전환이 필요하면:
        1. 현재 막 종료 (ended_at 설정)
        2. 성장 보상 생성 및 적용
        3. 새 막 생성
        4. ActTransitionResult 반환

        전환 불필요 시 None 반환.

        Args:
            session_id: 게임 세션 ID

        Returns:
            ActTransitionResult | None
        """
        from app.services.ai_nodes.act_analysis_node import (
            analyze_act_transition,
            generate_growth_rewards,
        )
        from app.services.ai_nodes.session_summary_node import generate_updated_ai_summary
        from app.services.context_loader import load_act_story_history

        # 현재 막 조회
        current_act_db = resolve_current_open_act(self.db, session_id)

        if not current_act_db:
            logger.debug(f"세션 {session_id}: 현재 막 없음, 전환 스킵")
            return None

        current_act_info = StoryActInfo(
            id=current_act_db.id,
            act_number=current_act_db.act_number,
            title=current_act_db.title,
            subtitle=current_act_db.subtitle,
            started_at=current_act_db.started_at.isoformat(),
        )

        # 게임 컨텍스트 로드
        game_context = load_game_context(db=self.db, session_id=session_id, system_prompt="")

        # 현재 막의 스토리 로드
        act_story = load_act_story_history(self.db, session_id, current_act_db.id)

        # AI 막 전환 분석
        analysis = await analyze_act_transition(
            world_context=game_context.world_prompt,
            current_act=current_act_info,
            story_history=act_story,
            characters=game_context.characters,
            llm_model=self.llm_model,
        )

        if not analysis.should_transition:
            logger.info(
                f"세션 {session_id}: 막 전환 불필요 "
                f"(사건 {analysis.event_count}개, 이유: {analysis.reasoning})"
            )
            return None

        logger.info(
            f"세션 {session_id}: 막 전환 결정! "
            f"'{current_act_info.title}' → '{analysis.new_act_title}'"
        )

        # 성장 보상 생성
        growth_rewards = await generate_growth_rewards(
            world_context=game_context.world_prompt,
            characters=game_context.characters,
            act_story_entries=act_story,
            act_info=current_act_info,
            llm_model=self.llm_model,
        )

        # 성장 보상 적용 + DB 저장
        for reward in growth_rewards:
            self._apply_growth_reward(reward)
        self._persist_growth_rewards(session_id, current_act_db.id, growth_rewards)

        # Act 종료 시점에만 ai_summary 갱신
        session = self.db.query(GameSession).filter(GameSession.id == session_id).first()
        if session:
            try:
                session.ai_summary = await generate_updated_ai_summary(
                    previous_summary=session.ai_summary,
                    completed_act=current_act_info,
                    act_story_entries=act_story,
                    growth_rewards=growth_rewards,
                    llm_model=self.llm_model,
                )
                logger.info(f"세션 {session_id}: ai_summary 갱신 완료")
            except Exception as e:
                logger.error(f"세션 {session_id}: ai_summary 갱신 실패, 기존 요약 유지 ({e})", exc_info=True)

        # 현재 막 종료
        current_act_db.ended_at = datetime.utcnow()
        # 마지막 스토리 로그 ID를 end_story_log_id로 설정
        last_log = (
            self.db.query(StoryLog)
            .filter(StoryLog.session_id == session_id, StoryLog.act_id == current_act_db.id)
            .order_by(StoryLog.created_at.desc())
            .first()
        )
        if last_log:
            current_act_db.end_story_log_id = last_log.id

        # 새 막 생성
        new_act = StoryAct(
            session_id=session_id,
            act_number=current_act_db.act_number + 1,
            title=analysis.new_act_title or f"{current_act_db.act_number + 1}막",
            subtitle=analysis.new_act_subtitle,
            started_at=datetime.utcnow(),
        )
        self.db.add(new_act)
        self.db.commit()
        self.db.refresh(new_act)

        new_act_info = StoryActInfo(
            id=new_act.id,
            act_number=new_act.act_number,
            title=new_act.title,
            subtitle=new_act.subtitle,
            started_at=new_act.started_at.isoformat(),
        )

        completed_act_info = StoryActInfo(
            id=current_act_db.id,
            act_number=current_act_db.act_number,
            title=current_act_db.title,
            subtitle=current_act_db.subtitle,
            started_at=current_act_db.started_at.isoformat(),
        )

        return ActTransitionResult(
            completed_act=completed_act_info,
            new_act=new_act_info,
            growth_rewards=growth_rewards,
        )

    async def execute_act_transition(
        self, session_id: int, new_act_title: str, new_act_subtitle: str | None = None
    ) -> ActTransitionResult | None:
        """메타데이터 기반 막 전환을 실행합니다 (AI 분석 호출 없음).

        내러티브 AI가 act_transition=true로 응답했을 때 호출됩니다.
        AI 막 분석 호출 없이 DB 작업만 수행합니다:
        1. 코드 가드: AI 서술 엔트리 2개 이하면 전환 거부
        2. 성장 보상 생성 (AI 호출)
        3. ai_summary 갱신 (AI 호출)
        4. 현재 막 종료, 새 막 생성

        Args:
            session_id: 게임 세션 ID
            new_act_title: 새 막 제목
            new_act_subtitle: 새 막 부제 (옵션)

        Returns:
            ActTransitionResult | None: 전환 결과 또는 None (거부 시)
        """
        from app.services.ai_nodes.act_analysis_node import generate_growth_rewards
        from app.services.ai_nodes.session_summary_node import generate_updated_ai_summary
        from app.services.context_loader import load_act_story_history

        # 현재 막 조회
        current_act_db = resolve_current_open_act(self.db, session_id)
        if not current_act_db:
            logger.debug(f"세션 {session_id}: 현재 막 없음, 전환 스킵")
            return None

        # 현재 막의 스토리 로드
        act_story = load_act_story_history(self.db, session_id, current_act_db.id)

        # 코드 가드: AI 서술 엔트리 2개 이하면 전환 거부
        ai_entries = [e for e in act_story if e.role == "AI"]
        if len(ai_entries) <= 2:
            logger.warning(
                f"세션 {session_id}: AI 서술 {len(ai_entries)}개, 전환 거부 (최소 3개 필요)"
            )
            return None

        current_act_info = StoryActInfo(
            id=current_act_db.id,
            act_number=current_act_db.act_number,
            title=current_act_db.title,
            subtitle=current_act_db.subtitle,
            started_at=current_act_db.started_at.isoformat(),
        )

        logger.info(
            f"세션 {session_id}: 메타데이터 기반 막 전환! "
            f"'{current_act_info.title}' → '{new_act_title}'"
        )

        # 게임 컨텍스트 로드
        game_context = load_game_context(db=self.db, session_id=session_id, system_prompt="")

        # 성장 보상 생성
        growth_rewards = await generate_growth_rewards(
            world_context=game_context.world_prompt,
            characters=game_context.characters,
            act_story_entries=act_story,
            act_info=current_act_info,
            llm_model=self.llm_model,
        )

        # 성장 보상 적용 + DB 저장
        for reward in growth_rewards:
            self._apply_growth_reward(reward)
        self._persist_growth_rewards(session_id, current_act_db.id, growth_rewards)

        # ai_summary 갱신
        session = self.db.query(GameSession).filter(GameSession.id == session_id).first()
        if session:
            try:
                session.ai_summary = await generate_updated_ai_summary(
                    previous_summary=session.ai_summary,
                    completed_act=current_act_info,
                    act_story_entries=act_story,
                    growth_rewards=growth_rewards,
                    llm_model=self.llm_model,
                )
                logger.info(f"세션 {session_id}: ai_summary 갱신 완료")
            except Exception as e:
                logger.error(
                    f"세션 {session_id}: ai_summary 갱신 실패, 기존 요약 유지 ({e})",
                    exc_info=True,
                )

        # 현재 막 종료
        current_act_db.ended_at = datetime.utcnow()
        last_log = (
            self.db.query(StoryLog)
            .filter(StoryLog.session_id == session_id, StoryLog.act_id == current_act_db.id)
            .order_by(StoryLog.created_at.desc())
            .first()
        )
        if last_log:
            current_act_db.end_story_log_id = last_log.id

        # 새 막 생성
        new_act = StoryAct(
            session_id=session_id,
            act_number=current_act_db.act_number + 1,
            title=new_act_title,
            subtitle=new_act_subtitle,
            started_at=datetime.utcnow(),
        )
        self.db.add(new_act)
        self.db.commit()
        self.db.refresh(new_act)

        new_act_info = StoryActInfo(
            id=new_act.id,
            act_number=new_act.act_number,
            title=new_act.title,
            subtitle=new_act.subtitle,
            started_at=new_act.started_at.isoformat(),
        )

        completed_act_info = StoryActInfo(
            id=current_act_db.id,
            act_number=current_act_db.act_number,
            title=current_act_db.title,
            subtitle=current_act_db.subtitle,
            started_at=current_act_db.started_at.isoformat(),
        )

        return ActTransitionResult(
            completed_act=completed_act_info,
            new_act=new_act_info,
            growth_rewards=growth_rewards,
        )

    def _apply_growth_reward(self, reward: GrowthReward) -> None:
        """성장 보상을 캐릭터 데이터에 적용합니다.

        Args:
            reward: 적용할 성장 보상
        """

        from sqlalchemy.orm.attributes import flag_modified

        character = self.db.query(Character).filter(Character.id == reward.character_id).first()
        if not character:
            logger.warning(f"캐릭터 {reward.character_id} 찾을 수 없음, 보상 스킵")
            return

        data = character.data or {}

        if reward.growth_type == "ability_increase":
            ability = reward.growth_detail.get("ability", "")
            delta = reward.growth_detail.get("delta", 1)
            current = data.get(ability, 10)
            new_value = min(current + delta, 20)  # 최대 20
            data[ability] = new_value
            logger.info(f"캐릭터 {character.name}: {ability} {current} → {new_value}")

        elif reward.growth_type == "new_skill":
            skill_data = reward.growth_detail.get("skill", {})
            skills = data.get("skills", [])
            if isinstance(skills, list):
                skills.append(skill_data)
                data["skills"] = skills
            logger.info(f"캐릭터 {character.name}: 새 스킬 '{skill_data.get('name', '?')}'")

        elif reward.growth_type == "weakness_mitigated":
            weakness_name = reward.growth_detail.get("weakness", "")
            mitigation_delta = reward.growth_detail.get("mitigation_delta", 1)
            weaknesses = data.get("weaknesses", [])
            updated = False

            for i, w in enumerate(weaknesses):
                if isinstance(w, str) and w == weakness_name:
                    # string → 객체로 변환
                    weaknesses[i] = {"name": w, "mitigation": mitigation_delta}
                    updated = True
                    break
                elif isinstance(w, dict) and w.get("name") == weakness_name:
                    w["mitigation"] = w.get("mitigation", 0) + mitigation_delta
                    updated = True
                    break

            if updated:
                data["weaknesses"] = weaknesses
                logger.info(f"캐릭터 {character.name}: 약점 '{weakness_name}' 완화")
            else:
                logger.warning(f"캐릭터 {character.name}: 약점 '{weakness_name}' 찾을 수 없음")

        character.data = data
        flag_modified(character, "data")

    def _persist_growth_rewards(
        self, session_id: int, act_id: int, rewards: list[GrowthReward]
    ) -> None:
        """성장 보상을 CharacterGrowthLog에 저장합니다."""
        for reward in rewards:
            self.db.add(
                CharacterGrowthLog(
                    session_id=session_id,
                    act_id=act_id,
                    character_id=reward.character_id,
                    growth_type=reward.growth_type,
                    growth_detail=reward.growth_detail,
                    narrative_reason=reward.narrative_reason,
                    applied_at=datetime.utcnow(),
                )
            )
        logger.info(f"세션 {session_id}: 성장 보상 {len(rewards)}개 DB 저장")
