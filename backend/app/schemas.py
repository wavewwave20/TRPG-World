"""AI 게임 마스터 시스템을 위한 Pydantic 스키마."""

from collections.abc import AsyncIterator
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ActionType(str, Enum):
    """
    D&D 능력치에 매핑된 행동 유형.

    각 행동 유형은 보정치 계산에 사용되는 특정 능력치에 대응됩니다.
    """

    STRENGTH = "strength"  # STR: 물리적 힘, 들어올리기
    DEXTERITY = "dexterity"  # DEX: 민첩성, 사격, 손재주
    CONSTITUTION = "constitution"  # CON: 지구력, 독 저항
    INTELLIGENCE = "intelligence"  # INT: 지식, 마법 이해
    WISDOM = "wisdom"  # WIS: 직관, 지각, 의지력
    CHARISMA = "charisma"  # CHA: 설득, 사교 기술, 속임수


class JudgmentOutcome(str, Enum):
    """
    행동 판정의 가능한 결과.

    D20 시스템 규칙 기반:
    - 대실패: 주사위 1 또는 final_value << DC
    - 실패: final_value < DC
    - 성공: final_value >= DC
    - 대성공: 주사위 20 또는 final_value >> DC
    """

    CRITICAL_FAILURE = "critical_failure"  # 대실패
    FAILURE = "failure"  # 실패
    SUCCESS = "success"  # 성공
    CRITICAL_SUCCESS = "critical_success"  # 대성공


class PlayerAction(BaseModel):
    """
    판정할 플레이어의 행동을 나타냅니다.

    Attributes:
        character_id: 행동을 수행하는 캐릭터의 ID
        action_text: 플레이어가 하고자 하는 행동의 설명
        action_type: 행동 유형 (사용할 능력치 결정)
    """

    character_id: int = Field(..., description="행동을 수행하는 캐릭터의 ID")
    action_text: str = Field(..., description="플레이어의 행동 설명")
    action_type: ActionType = Field(..., description="능력치 매핑을 위한 행동 유형")


class ActionAnalysis(BaseModel):
    """
    1단계 결과: 보정치와 난이도가 포함된 행동 분석.

    AI가 플레이어의 행동을 분석한 후, 플레이어가 주사위를 굴리기 전에 반환됩니다.

    Attributes:
        character_id: 행동을 수행하는 캐릭터의 ID
        action_text: 분석된 행동
        action_type: 행동 유형 (사용할 능력치 결정)
        modifier: 능력치, 스킬, 상태 효과로부터 계산된 보정치
        difficulty: LLM이 결정한 DC (난이도 등급) (5-30)
        difficulty_reasoning: DC에 대한 LLM의 설명
    """

    character_id: int = Field(..., description="행동을 수행하는 캐릭터의 ID")
    action_text: str = Field(..., description="분석된 행동")
    action_type: ActionType = Field(..., description="능력치 매핑을 위한 행동 유형")
    modifier: int = Field(..., description="능력치, 스킬, 상태 효과로부터의 총 보정치")
    difficulty: int = Field(..., ge=5, le=30, description="LLM이 결정한 난이도 등급 (DC)")
    difficulty_reasoning: str = Field(..., description="DC에 대한 LLM의 추론")


class DiceResult(BaseModel):
    """
    2단계 입력: 플레이어의 주사위 굴림 결과.

    ActionAnalysis를 받은 후 플레이어가 제출하며,
    이전에 계산된 값들과 함께 d20 굴림 결과를 포함합니다.

    Attributes:
        character_id: 행동을 수행하는 캐릭터의 ID
        action_text: 판정 중인 행동
        dice_roll: d20 굴림 결과 (1-20)
        modifier: 1단계(ActionAnalysis)의 보정치
        difficulty: 1단계(ActionAnalysis)의 DC
    """

    character_id: int = Field(..., description="행동을 수행하는 캐릭터의 ID")
    action_text: str = Field(..., description="판정 중인 행동")
    dice_roll: int = Field(..., ge=1, le=20, description="플레이어의 d20 굴림 결과")
    modifier: int = Field(..., description="1단계 분석의 보정치")
    difficulty: int = Field(..., ge=5, le=30, description="1단계 분석의 DC")


class JudgmentResult(BaseModel):
    """
    2단계 결과: 주사위 굴림 후 최종 판정.

    주사위 굴림, 보정치, 난이도, 최종 결과에 대한 모든 정보를 포함합니다.
    플레이어가 2단계에서 주사위를 굴린 후 계산됩니다.

    Attributes:
        character_id: 캐릭터의 ID
        action_text: 판정된 행동
        dice_result: d20 굴림 (1-20)
        modifier: 능력치, 스킬, 상태 효과로부터의 총 보정치
        final_value: dice_result + modifier
        difficulty: 1단계에서 LLM이 결정한 DC (난이도 등급)
        difficulty_reasoning: DC에 대한 LLM의 설명 (1단계에서)
        outcome: 최종 판정 (critical_failure/failure/success/critical_success)
        outcome_reasoning: 판정 결과에 대한 설명

    판정 규칙:
        - 주사위 1: 자동 대실패 (DC와 무관)
        - 주사위 20: 자동 대성공 (DC와 무관)
        - final_value >= DC: 성공
        - final_value < DC: 실패
    """

    character_id: int = Field(..., description="캐릭터의 ID")
    action_text: str = Field(..., description="판정된 행동")
    dice_result: int = Field(..., ge=1, le=20, description="D20 굴림 결과")
    modifier: int = Field(..., description="굴림에 적용된 총 보정치")
    final_value: int = Field(..., description="dice_result + modifier")
    difficulty: int = Field(..., ge=5, le=30, description="난이도 등급 (DC)")
    difficulty_reasoning: str | None = Field(None, description="DC에 대한 LLM의 추론")
    outcome: JudgmentOutcome = Field(..., description="최종 판정 결과")
    outcome_reasoning: str | None = Field(None, description="판정 결과에 대한 추론")


class NarrativeResult(BaseModel):
    """
    3단계 결과: 스토리 서술 생성 결과.

    모든 판정 결과와 생성된 서술을 포함한 3단계 AI 생성 프로세스의 완전한 결과를 포함합니다.

    Attributes:
        session_id: 게임 세션의 ID
        judgments: 2단계의 모든 행동에 대한 판정 결과 목록
        full_narrative: 완전히 생성된 서술 텍스트
        narrative_stream: 스트리밍 토큰을 위한 선택적 비동기 이터레이터
        is_complete: 서술 생성이 성공적으로 완료되었는지 여부
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: int = Field(..., description="게임 세션의 ID")
    judgments: list[JudgmentResult] = Field(..., description="2단계의 모든 판정 결과")
    full_narrative: str = Field(default="", description="완전히 생성된 서술 텍스트")
    narrative_stream: AsyncIterator[str] | None = Field(None, exclude=True)
    is_complete: bool = Field(default=False, description="서술 생성 완료 여부")


class CharacterSheet(BaseModel):
    """
    AI 컨텍스트를 위한 간소화된 캐릭터 시트.

    Character.data JSON 필드에서 추출됩니다.
    """

    id: int
    name: str
    age: int | None = None
    race: str | None = None
    concept: str | None = None

    # 능력치 (D&D 스타일)
    strength: int = Field(10, ge=1, le=30)
    dexterity: int = Field(10, ge=1, le=30)
    constitution: int = Field(10, ge=1, le=30)
    intelligence: int = Field(10, ge=1, le=30)
    wisdom: int = Field(10, ge=1, le=30)
    charisma: int = Field(10, ge=1, le=30)

    # 스킬과 보정치
    skills: list[dict[str, Any]] = Field(default_factory=list, description="유형, 이름, 설명이 포함된 스킬 목록")
    weaknesses: list[str] = Field(default_factory=list)
    status_effects: list[str] = Field(default_factory=list)


class StoryLogEntry(BaseModel):
    """
    스토리 히스토리의 단일 항목.

    Attributes:
        role: "USER" 또는 "AI"
        content: 스토리 텍스트 또는 플레이어 행동
        created_at: 이 항목이 생성된 시간
    """

    role: str = Field(..., pattern="^(USER|AI)$")
    content: str
    created_at: datetime


class GameContext(BaseModel):
    """
    AI 프롬프트 구성을 위한 완전한 게임 컨텍스트.

    AI 응답 생성에 필요한 모든 정보를 포함합니다:
    - 세션 세부사항 및 세계관 설정
    - 모든 활성 캐릭터
    - 최근 스토리 히스토리
    - 시스템 프롬프트

    Attributes:
        session_id: 게임 세션의 ID
        world_prompt: 세계관 설정 및 규칙
        system_prompt: 마크다운 파일의 TRPG 시스템 규칙
        characters: 세션의 모든 캐릭터
        story_history: 최근 스토리 로그 (최대 20개)
        ai_summary: 긴 세션을 위한 선택적 압축 컨텍스트
    """

    session_id: int
    world_prompt: str
    system_prompt: str
    characters: list[CharacterSheet]
    story_history: list[StoryLogEntry] = Field(default_factory=list, max_length=20)
    ai_summary: str | None = None
