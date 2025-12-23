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

import logging
from datetime import datetime

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
from app.services.ai_nodes import analyze_and_judge_actions, generate_narrative
from app.services.context_loader import ContextLoadError, load_game_context
from app.services.dice_system import DiceSystem

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

        logger.info(f"Initialized AIGMServiceV2 with model: {llm_model}")

    async def analyze_actions(self, session_id: int, player_actions: list[PlayerAction]) -> list[ActionAnalysis]:
        """
        Phase 1: 플레이어 행동을 분석하고 보정치 + DC를 반환합니다.

        프로세스:
        1. 게임 컨텍스트 로드 (세션, 캐릭터, 히스토리)
        2. 캐릭터 스탯에서 보정치 계산
        3. AI를 사용하여 난이도(DC) 결정

        Args:
            session_id: 게임 세션 ID
            player_actions: 분석할 플레이어 행동 목록

        Returns:
            List[ActionAnalysis]: 각 행동에 대한 보정치와 DC

        Raises:
            ValueError: 입력 검증 실패 또는 컨텍스트 로드 실패 시
        """
        logger.info(f"Phase 1 - Analyzing actions for session {session_id}: {len(player_actions)} actions")

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
                llm_model=self.llm_model,
                temperature=0.3,  # 일관된 판정을 위해 낮게 설정
            )

            logger.info(f"Phase 1 completed: {len(analyses)} actions analyzed")

            return analyses

        except ContextLoadError as e:
            logger.error(f"Failed to load context: {e}")
            raise ValueError(f"게임 컨텍스트 로드 실패: {e!s}") from e

        except Exception as e:
            logger.error(f"Phase 1 failed: {e}", exc_info=True)
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
        logger.info(f"Phase 3 - Generating narrative for session {session_id}: {len(dice_results)} dice results")

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

            logger.debug(f"Judgments calculated: {len(judgments)} results")

            # AI 노드 호출하여 서술 생성
            narrative = await generate_narrative(
                judgments=judgments,
                characters=game_context.characters,
                world_context=game_context.world_prompt,
                story_history=game_context.story_history,
                llm_model=self.llm_model,
                temperature=0.8,  # 창의적인 서술을 위해 높게 설정
            )

            logger.debug(f"Narrative generated: {len(narrative)} characters")

            # 데이터베이스에 저장
            self._save_results(session_id=session_id, judgments=judgments, narrative=narrative)

            logger.info("Phase 3 completed: narrative saved to database")

            # 결과 반환
            result = NarrativeResult(
                session_id=session_id,
                judgments=judgments,
                full_narrative=narrative,
                is_complete=True,
            )

            return result

        except ContextLoadError as e:
            logger.error(f"Failed to load context: {e}")
            raise ValueError(f"게임 컨텍스트 로드 실패: {e!s}") from e

        except Exception as e:
            logger.error(f"Phase 3 failed: {e}", exc_info=True)
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

            logger.debug(f"Saved to database: 1 story log, {len(judgments)} judgments")

        except Exception as e:
            logger.error(f"Failed to save results: {e}", exc_info=True)
            self.db.rollback()
            raise
