"""TRPG 행동 판정을 위한 D20 주사위 시스템."""

import random
from enum import Enum

from app.models import Character
from app.schemas import JudgmentOutcome


class ActionType(str, Enum):
    """D&D 능력치에 매핑된 행동 유형."""

    STRENGTH = "strength"  # 근력 (STR): 물리적 힘, 짐 들기
    DEXTERITY = "dexterity"  # 민첩 (DEX): 회피, 사격, 손재주
    CONSTITUTION = "constitution"  # 건강 (CON): 체력, 독 저항
    INTELLIGENCE = "intelligence"  # 지능 (INT): 지식, 마법 이해도
    WISDOM = "wisdom"  # 지혜 (WIS): 직관, 감각, 의지력
    CHARISMA = "charisma"  # 매력 (CHA): 설득, 사교, 거짓말


def calculate_total_modifier(
    ability_score: int,
    action_type_value: str,
    skills: list,
    status_effects: list,
) -> int:
    """
    보정치 통합 계산 함수.

    능력치 보정치, 스킬 숙련 보너스, 상태 효과를 모두 합산합니다.
    judgment_node._calculate_modifier와 DiceSystem.calculate_modifier가
    이 함수를 공유하여 로직 중복을 방지합니다.

    Args:
        ability_score: 능력치 값 (1-30)
        action_type_value: 행동 유형 문자열 (예: "strength", "dexterity")
        skills: 스킬 목록 (list of dict, 각 dict에 "ability" 키 가능)
        status_effects: 상태 효과 목록 (str 또는 dict)

    Returns:
        int: 최종 보정치
    """
    # 1. 능력치 보정치
    modifier = (ability_score - 10) // 2

    # 2. 스킬 숙련 보너스 (+2, 한 번만 적용)
    SKILL_PROFICIENCY_BONUS = 2
    for skill in skills:
        skill_ability = skill.get("ability") if isinstance(skill, dict) else getattr(skill, "ability", None)
        if skill_ability and skill_ability == action_type_value:
            modifier += SKILL_PROFICIENCY_BONUS
            break

    # 3. 상태 효과 보정치
    for effect in status_effects:
        if isinstance(effect, dict):
            effect_modifier = effect.get("modifier", 0)
            if isinstance(effect_modifier, int):
                modifier += effect_modifier

    return modifier


class DiceSystem:
    """
    행동 판정을 위한 D20 주사위 시스템.

    표준 D&D 스타일 메커니즘 구현:
    - d20 굴림 (1-20)
    - 능력치 보정치 계산: (ability_score - 10) / 2
    - 스킬 보너스 및 상태 효과 적용
    - 행동 판정을 위한 최종 보정치 결정
    """

    @staticmethod
    def roll_d20() -> int:
        """
        표준 d20 주사위를 굴립니다.

        Returns:
            int: 1에서 20 사이의 무작위 값 (포함)
        """
        return random.randint(1, 20)

    @staticmethod
    def calculate_ability_modifier(ability_score: int) -> int:
        """
        능력치를 보정치로 변환합니다.

        공식: (ability_score - 10) / 2 (내림 나눗셈)

        Args:
            ability_score: 능력치 값 (일반적으로 1-20+)

        Returns:
            int: 보정치 값 (일반적으로 -5에서 +5 이상)

        Examples:
            - 10 (평균) -> 0
            - 14 (숙련) -> +2
            - 18 (천재) -> +4
            - 8 (평균 이하) -> -1
        """
        return (ability_score - 10) // 2

    @staticmethod
    def get_ability_score(character: Character, action_type: ActionType) -> int:
        """
        캐릭터 데이터에서 주어진 행동 유형에 대한 능력치를 추출합니다.

        Args:
            character: 능력치를 포함하는 data 필드가 있는 Character 객체
            action_type: 행동 유형 (능력치에 매핑됨)

        Returns:
            int: 능력치 값 (찾을 수 없으면 기본값 10)
        """
        # action_type.value는 이미 올바른 키 이름을 포함합니다
        # (예: "strength", "dexterity" 등)
        ability_score = character.data.get(action_type.value, 10)
        return ability_score

    @staticmethod
    def apply_status_effects(base_modifier: int, character: Character) -> int:
        """
        기본 보정치에 상태 효과를 적용합니다.

        상태 효과는 행동에 보너스 또는 페널티를 제공할 수 있습니다.

        Args:
            base_modifier: 상태 효과 적용 전 기본 보정치
            character: data에 상태 효과가 있는 Character 객체

        Returns:
            int: 상태 효과 적용 후 수정된 값
        """
        status_effects = character.data.get("status_effects", [])

        total_modifier = base_modifier

        for effect in status_effects:
            if isinstance(effect, dict):
                # 각 효과는 'modifier' 필드를 가질 수 있습니다
                effect_modifier = effect.get("modifier", 0)
                total_modifier += effect_modifier

        return total_modifier

    @staticmethod
    def calculate_modifier(character: Character, action_type: ActionType) -> int:
        """
        행동에 대한 총 보정치를 계산합니다.

        calculate_total_modifier에 위임하여 judgment_node와 동일한 로직을 사용합니다.

        Args:
            character: Character 객체
            action_type: 수행 중인 행동의 유형

        Returns:
            int: 주사위 굴림에 추가할 총 보정치
        """
        ability_score = DiceSystem.get_ability_score(character, action_type)
        skills = character.data.get("skills", [])
        status_effects = character.data.get("status_effects", [])

        return calculate_total_modifier(
            ability_score=ability_score,
            action_type_value=action_type.value,
            skills=skills if isinstance(skills, list) else [],
            status_effects=status_effects if isinstance(status_effects, list) else [],
        )

    @staticmethod
    def determine_outcome(dice_result: int, modifier: int, difficulty: int) -> JudgmentOutcome:
        """
        주사위 굴림, 보정치, DC를 기반으로 행동의 결과를 결정합니다.

        2단계에서 플레이어의 주사위 굴림 결과를 판정하는 데 사용됩니다.

        Args:
            dice_result: d20 굴림 결과 (1-20)
            modifier: 능력치, 스킬, 상태 효과로부터의 총 보정치
            difficulty: LLM이 결정한 DC (난이도 등급)

        Returns:
            JudgmentOutcome: 판정 결과

        규칙:
            - 주사위 1: 자동 대실패 (DC와 무관)
            - 주사위 20: 자동 대성공 (DC와 무관)
            - final_value >= DC: 성공
            - final_value < DC: 실패

        참고:
            극단적인 차이(DC +/- 10)로 인한 대성공/대실패는
            설계상 주사위 1/20만 크리티컬로 지정되어 여기서 구현되지 않습니다.
        """
        # 규칙: 주사위 1은 자동 대실패
        if dice_result == 1:
            return JudgmentOutcome.CRITICAL_FAILURE

        # 규칙: 주사위 20은 자동 대성공
        if dice_result == 20:
            return JudgmentOutcome.CRITICAL_SUCCESS

        # 최종 값 계산
        final_value = dice_result + modifier

        # DC와 비교
        if final_value >= difficulty:
            return JudgmentOutcome.SUCCESS
        return JudgmentOutcome.FAILURE
