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

from app.models import ActionJudgment, StoryLog
from app.schemas import (
    ActionAnalysis,
    DiceResult,
    JudgmentOutcome,
    JudgmentResult,
    NarrativeResult,
    PlayerAction,
)
from app.services.ai_nodes import analyze_and_judge_actions, generate_narrative, generate_narrative_streaming
from app.services.background_task_manager import get_task_manager
from app.services.context_loader import ContextLoadError, GameContext, load_game_context
from app.services.dice_system import DiceSystem
from app.services.stream_buffer import get_buffer_manager

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
                story_history=game_context.story_history,
                llm_model=self.llm_model
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
                game_context
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
            narrative = await generate_narrative(
                judgments=judgments,
                characters=game_context.characters,
                world_context=game_context.world_prompt,
                story_history=game_context.story_history,
                llm_model=self.llm_model
            )

            logger.debug(f"이야기 생성 완료: {len(narrative)}자")

            # 데이터베이스에 저장
            self._save_results(session_id=session_id, judgments=judgments, narrative=narrative)

            logger.info("Phase 3 완료: 이야기 DB 저장됨")

            # 결과 반환
            result = NarrativeResult(
                session_id=session_id,
                judgments=judgments,
                full_narrative=narrative,
                is_complete=True,
            )

            return result

        except ContextLoadError as e:
            logger.error(f"컨텍스트 로드 실패: {e}")
            raise ValueError(f"게임 컨텍스트 로드 실패: {e!s}") from e

        except Exception as e:
            logger.error(f"Phase 3 실패: {e}", exc_info=True)
            raise ValueError(f"서술 생성 실패: {e!s}") from e

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
                return "자연적 1이 나와 자동으로 대실패했습니다."
            return f"최종 값 {final_value}이(가) 난이도 {difficulty}보다 10 이상 낮아 대실패했습니다."

        if outcome == JudgmentOutcome.FAILURE:
            return f"최종 값 {final_value}이(가) 난이도 {difficulty}에 미치지 못해 실패했습니다."

        if outcome == JudgmentOutcome.SUCCESS:
            return f"최종 값 {final_value}이(가) 난이도 {difficulty}을(를) 넘어 성공했습니다."

        if outcome == JudgmentOutcome.CRITICAL_SUCCESS:
            if dice_result == 20:
                return "자연적 20이 나와 자동으로 대성공했습니다!"
            return f"최종 값 {final_value}이(가) 난이도 {difficulty}보다 10 이상 높아 대성공했습니다!"

        return "판정이 완료되었습니다."
    
    async def _preroll_dice(
        self,
        session_id: int,
        analyses: list[ActionAnalysis]
    ) -> list[JudgmentResult]:
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
                # 주사위 굴림 (1-20)
                dice_roll = random.randint(1, 20)
                
                # 최종값 계산
                final_value = dice_roll + analysis.modifier
                
                # 결과 판정
                outcome = self.dice_system.determine_outcome(
                    dice_result=dice_roll,
                    modifier=analysis.modifier,
                    difficulty=analysis.difficulty
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
                    outcome_reasoning=self._get_outcome_reasoning(
                        dice_roll, final_value, analysis.difficulty, outcome
                    )
                )
                judgments.append(judgment)
                
                # 데이터베이스에 phase=0으로 저장 (사전 굴림)
                action_judgment = ActionJudgment(
                    session_id=session_id,
                    character_id=analysis.character_id,
                    action_text=analysis.action_text,
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
            
            logger.info(f"주사위 사전 굴림 완료: {len(judgments)}개 결과 저장 (phase=0)")
            
            return judgments
            
        except Exception as e:
            logger.error(f"주사위 사전 굴림 실패: {e}", exc_info=True)
            self.db.rollback()
            raise
    
    async def _generate_narrative_background(
        self,
        session_id: int,
        judgments: list[JudgmentResult],
        game_context: GameContext
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
            # LLM 스트리밍 호출
            token_count = 0
            async for token in generate_narrative_streaming(
                judgments=judgments,
                characters=game_context.characters,
                world_context=game_context.world_prompt,
                story_history=game_context.story_history,
                llm_model=self.llm_model
            ):
                # 버퍼에 토큰 추가
                success = await buffer.add_token(token)
                token_count += 1
                logger.debug(f"Added token {token_count} to buffer for session {session_id}")
                if not success:
                    logger.warning(f"버퍼 가득 참: 세션={session_id}, 생성 중단")
                    break
            
            buffer.mark_complete()
            logger.info(f"백그라운드 이야기 생성 완료: 세션={session_id}")
            
        except Exception as e:
            error_msg = f"이야기 생성 실패: {str(e)}"
            logger.error(f"백그라운드 생성 에러: 세션={session_id}, {e}", exc_info=True)
            buffer.mark_error(error_msg)
    
    async def confirm_dice_roll(
        self,
        session_id: int,
        character_id: int
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
        logger.info(f"주사위 확인: 세션={session_id}, 캐릭터={character_id}")

        try:
            # phase=0인 가장 최근 판정 조회 (사전 굴림)
            judgment = self.db.query(ActionJudgment).filter(
                ActionJudgment.session_id == session_id,
                ActionJudgment.character_id == character_id,
                ActionJudgment.phase == 0
            ).order_by(ActionJudgment.id.desc()).first()

            if not judgment:
                raise ValueError(
                    f"사전 굴림된 주사위 없음: 세션={session_id}, 캐릭터={character_id}"
                )

            # phase를 2로 변경 (플레이어 확인 완료)
            judgment.phase = 2
            self.db.commit()

            logger.info(
                f"주사위 확인 완료: 캐릭터={character_id}, "
                f"주사위={judgment.dice_result}, 최종={judgment.final_value}, "
                f"결과={judgment.outcome}"
            )
            
            # 결과 반환
            return DiceResult(
                character_id=character_id,
                action_text=judgment.action_text,
                dice_roll=judgment.dice_result,
                modifier=judgment.modifier,
                difficulty=judgment.difficulty
            )
            
        except Exception as e:
            logger.error(f"주사위 확인 실패: {e}", exc_info=True)
            self.db.rollback()
            raise
    
    async def stream_narrative(self, session_id: int) -> AsyncIterator[str]:
        """
        버퍼에서 이야기를 스트리밍으로 전송합니다.
        
        이 메서드는 Phase 3에서 호출되며, 백그라운드에서 생성된 이야기를
        클라이언트로 스트리밍합니다. 버퍼가 아직 완료되지 않았다면 새 토큰을
        기다리면서 스트리밍하고, 완료되면 모든 토큰을 전송한 후 데이터베이스에
        저장합니다.
        
        Args:
            session_id: 게임 세션 ID
            
        Yields:
            str: 이야기 토큰
            
        Raises:
            ValueError: 버퍼를 찾을 수 없거나 에러가 발생한 경우
            
        Requirements: 1.3, 1.5, 10.1, 10.2, 10.3, 10.4
        """
        logger.info(f"이야기 스트리밍 시작: 세션={session_id}")
        
        # 버퍼 가져오기
        buffer_manager = get_buffer_manager()
        buffer = buffer_manager.get_buffer(session_id)
        
        if not buffer:
            raise ValueError(f"이야기 버퍼 없음: 세션={session_id}")
        
        if buffer.error:
            raise ValueError(f"이야기 생성 실패: {buffer.error}")
        
        # 토큰 스트리밍
        index = 0
        token_count = 0
        
        while True:
            # 버퍼에서 토큰 가져오기
            tokens = buffer.get_tokens(start_index=index)
            
            logger.debug(f"Got {len(tokens)} tokens from buffer (index={index}, complete={buffer.is_complete})")
            
            # 토큰 전송 (50ms 간격으로 타이핑 효과)
            for token in tokens:
                logger.debug(f"Yielding token: {token[:20]}..." if len(token) > 20 else f"Yielding token: {token}")
                yield token
                index += 1
                token_count += 1
                await asyncio.sleep(0.05)  # 50ms = 20 tokens/second
            
            if buffer.is_complete:
                logger.info(f"이야기 스트리밍 완료: 세션={session_id}, 토큰={token_count}개")
                break
            
            # 새 토큰 대기
            await asyncio.sleep(0.1)
        
        try:
            full_narrative = buffer.get_full_text()
            await self._save_narrative_to_database(session_id, full_narrative)
            logger.info(f"이야기 DB 저장 완료: 세션={session_id}")
        except Exception as e:
            logger.error(f"이야기 저장 실패: {e}", exc_info=True)
    
    async def _save_narrative_to_database(self, session_id: int, narrative: str):
        """
        이야기를 데이터베이스에 저장합니다.
        
        StoryLog를 생성하고 모든 ActionJudgment를 phase=3으로 업데이트합니다.
        단일 트랜잭션으로 처리됩니다.
        
        Args:
            session_id: 게임 세션 ID
            narrative: 생성된 이야기 전체 텍스트
            
        Requirements: 8.4, 8.5
        """
        try:
            # StoryLog 생성
            story_log = StoryLog(
                session_id=session_id,
                role="AI",
                content=narrative,
                created_at=datetime.utcnow(),
            )
            self.db.add(story_log)
            self.db.flush()  # story_log.id 획득
            
            # 모든 phase=2 ActionJudgment를 phase=3으로 업데이트
            judgments = self.db.query(ActionJudgment).filter(
                ActionJudgment.session_id == session_id,
                ActionJudgment.phase == 2
            ).all()
            
            for judgment in judgments:
                judgment.story_log_id = story_log.id
                judgment.phase = 3  # Phase 3: 서술 완료
            
            # 커밋
            self.db.commit()
            
            logger.info(
                f"이야기 DB 저장: story_log_id={story_log.id}, "
                f"{len(judgments)}개 판정 phase=3으로 업데이트"
            )
            
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
            # 서술을 story_logs에 저장
            story_log = StoryLog(
                session_id=session_id,
                role="AI",
                content=narrative,
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
