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

        다음을 결합합니다:
        - 능력치 보정치 (능력치에서)
        - 스킬 보너스 (캐릭터 스킬에서) - TODO: 스킬 기반 보너스 구현
        - 상태 효과 (버프/디버프)

        Args:
            character: Character 객체
            action_type: 수행 중인 행동의 유형

        Returns:
            int: 주사위 굴림에 추가할 총 보정치
        """
        # 능력치를 가져와서 기본 보정치 계산
        ability_score = DiceSystem.get_ability_score(character, action_type)
        ability_modifier = DiceSystem.calculate_ability_modifier(ability_score)

        # TODO: 스킬 기반 보너스 구현
        # 현재 스킬은 이름/설명이 있는 스킬 객체 목록으로 저장됩니다
        # 향후 보너스를 위해 스킬을 행동 유형에 매핑할 수 있습니다
        # 지금은 능력치 보정치만 사용합니다
        skill_bonus = 0

        # 능력치 보정치와 스킬 보너스 결합
        base_modifier = ability_modifier + skill_bonus

        # 상태 효과 적용
        final_modifier = DiceSystem.apply_status_effects(base_modifier, character)

        return final_modifier

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
