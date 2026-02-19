"""Story Director service.

Act(행동 판정) 시스템 위에 얹는 경량 연출 레이어입니다.
AI 호출 없이 규칙 기반으로 스토리 방향을 보정합니다.

핵심 목표:
- 메인 목표 정렬 유지 (드리프트 완화)
- 위기 연속 과다 방지 (긴장 곡선 제어)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.schemas import JudgmentOutcome, JudgmentResult

logger = logging.getLogger("ai_gm.story_director")


@dataclass
class StoryDirectorState:
    """세션 단위 스토리 연출 상태."""

    session_id: int
    main_goal: str
    sub_goals: list[str] = field(default_factory=list)
    arc_phase: str = "build"  # intro|build|twist|climax|resolution
    tension: int = 45  # 0~100
    consecutive_crisis: int = 0
    forbidden_drifts: list[str] = field(default_factory=list)
    last_situation: str = ""
    host_instruction: str = ""


class StoryDirectorService:
    """규칙 기반 스토리 연출 서비스 (메모리 상태)."""

    def __init__(self):
        self._states: dict[int, StoryDirectorState] = {}

    def get_or_create_state(self, session_id: int, world_context: str, ai_summary: str | None = None) -> StoryDirectorState:
        state = self._states.get(session_id)
        if state:
            return state

        state = StoryDirectorState(
            session_id=session_id,
            main_goal=self._derive_main_goal(world_context, ai_summary),
            sub_goals=self._derive_sub_goals(world_context),
            forbidden_drifts=self._derive_forbidden_drifts(world_context),
        )
        self._states[session_id] = state
        logger.info(
            f"StoryDirector initialized: session={session_id}, main_goal='{state.main_goal}', arc={state.arc_phase}"
        )
        return state

    def build_guidance(
        self,
        session_id: int,
        world_context: str,
        ai_summary: str | None,
        judgments: list[JudgmentResult],
    ) -> str:
        """현재 상태+판정 결과를 바탕으로 내러티브 가이드를 구성합니다."""
        state = self.get_or_create_state(session_id, world_context, ai_summary)

        pressure_delta = self._estimate_tension_delta(judgments)
        projected_tension = self._clamp(state.tension + pressure_delta, 0, 100)

        crisis_scene = projected_tension >= 75 or state.consecutive_crisis >= 2
        if crisis_scene:
            scene_instruction = (
                "이번 장면은 위기를 더 키우지 말고 완화/정리/회복/정보정리 중심으로 전개하세요. "
                "즉시 전투 확대, 대규모 재난, 연속적인 절망 연출은 피하세요."
            )
        elif projected_tension <= 35:
            scene_instruction = (
                "이번 장면에서는 약한 갈등 또는 미스터리 단서를 추가해 긴장도를 소폭 올릴 수 있습니다. "
                "단, 메인 목표와 인과적으로 연결된 요소만 허용합니다."
            )
        else:
            scene_instruction = (
                "현재 긴장도를 유지하면서 메인 목표를 향해 사건을 한 단계 전진시키세요. "
                "불필요한 분기나 무관한 사건 삽입은 피하세요."
            )

        sub_goal_text = ", ".join(state.sub_goals) if state.sub_goals else "(none)"
        forbidden_text = ", ".join(state.forbidden_drifts) if state.forbidden_drifts else "(none)"
        host_instruction_block = ""
        if state.host_instruction.strip():
            host_instruction_block = (
                "\n### Host Instruction (Persistent Override)\n"
                "- Follow this direction as long as it does not violate safety or core game rules.\n"
                f"- {state.host_instruction.strip()}\n"
            )

        return (
            "## Story Director Guidance (Rules, Non-negotiable)\n\n"
            f"- Main Goal: {state.main_goal}\n"
            f"- Sub Goals: {sub_goal_text}\n"
            f"- Arc Phase: {state.arc_phase}\n"
            f"- Current Tension: {state.tension} (projected: {projected_tension})\n"
            f"- Consecutive Crisis Count: {state.consecutive_crisis}\n"
            f"- Forbidden Drift Keywords: {forbidden_text}\n"
            f"{host_instruction_block}\n"
            "### Direction Constraints\n"
            "1) Keep causal continuity with current scene.\n"
            "2) Do not derail from Main Goal.\n"
            "3) Respect tension control rule below.\n"
            f"4) {scene_instruction}\n"
        )

    def set_host_instruction(
        self,
        session_id: int,
        world_context: str,
        ai_summary: str | None,
        instruction: str,
    ) -> StoryDirectorState:
        state = self.get_or_create_state(session_id, world_context, ai_summary)
        state.host_instruction = instruction.strip()
        logger.info(
            f"StoryDirector host instruction updated: session={session_id}, enabled={bool(state.host_instruction)}"
        )
        return state

    def get_host_instruction(
        self,
        session_id: int,
        world_context: str,
        ai_summary: str | None,
    ) -> str:
        state = self.get_or_create_state(session_id, world_context, ai_summary)
        return state.host_instruction

    def commit_after_narrative(
        self,
        session_id: int,
        world_context: str,
        ai_summary: str | None,
        judgments: list[JudgmentResult],
        metadata: dict | None,
    ) -> StoryDirectorState:
        """내러티브 생성 후 tension/arc/state를 확정 반영합니다."""
        state = self.get_or_create_state(session_id, world_context, ai_summary)

        delta = self._estimate_tension_delta(judgments)
        state.tension = self._clamp(state.tension + delta, 0, 100)

        is_crisis_turn = self._is_crisis_turn(judgments)
        if is_crisis_turn:
            state.consecutive_crisis += 1
        else:
            state.consecutive_crisis = 0

        situation = (metadata or {}).get("situation") if metadata else None
        if isinstance(situation, str):
            state.last_situation = situation.strip()

        if metadata and metadata.get("act_transition"):
            state.arc_phase = self._next_arc_phase(state.arc_phase)
            # 막 전환 시 긴장도 리셋(완전 초기화는 아님)
            state.tension = 45
            state.consecutive_crisis = 0

        logger.info(
            "StoryDirector updated: "
            f"session={session_id}, tension={state.tension}, consecutive_crisis={state.consecutive_crisis}, "
            f"arc={state.arc_phase}, situation='{state.last_situation[:60]}'"
        )
        return state

    @staticmethod
    def _estimate_tension_delta(judgments: list[JudgmentResult]) -> int:
        """판정 결과로 긴장도 변화량 추정 (-15~+15로 clamp 전제)."""
        if not judgments:
            return 0

        score = 0
        for j in judgments:
            if j.outcome == JudgmentOutcome.CRITICAL_FAILURE:
                score += 8
            elif j.outcome == JudgmentOutcome.FAILURE:
                score += 4
            elif j.outcome == JudgmentOutcome.SUCCESS:
                score -= 2
            elif j.outcome == JudgmentOutcome.CRITICAL_SUCCESS:
                score -= 5
            elif j.outcome == JudgmentOutcome.AUTO_SUCCESS:
                score -= 1

        return max(-15, min(15, score))

    @staticmethod
    def _is_crisis_turn(judgments: list[JudgmentResult]) -> bool:
        """이번 턴이 위기 턴인지 판단."""
        if not judgments:
            return False

        failures = sum(1 for j in judgments if j.outcome in {JudgmentOutcome.FAILURE, JudgmentOutcome.CRITICAL_FAILURE})
        critical_failures = sum(1 for j in judgments if j.outcome == JudgmentOutcome.CRITICAL_FAILURE)

        if critical_failures >= 1:
            return True
        return failures >= max(1, len(judgments) // 2)

    @staticmethod
    def _derive_main_goal(world_context: str, ai_summary: str | None) -> str:
        combined = f"{world_context or ''}\n{ai_summary or ''}".strip()
        if not combined:
            return "Advance the main storyline while maintaining party continuity"

        # 첫 문장/첫 줄 기반 간단 추출
        lines = [line.strip() for line in combined.splitlines() if line.strip()]
        for line in lines[:10]:
            if len(line) >= 12:
                return line[:140]

        return lines[0][:140] if lines else "Advance the main storyline"

    @staticmethod
    def _derive_sub_goals(world_context: str) -> list[str]:
        text = world_context or ""
        goals: list[str] = []
        for pattern in [r"목표\s*[:：]\s*(.+)", r"Goal\s*[:：]\s*(.+)"]:
            matches = re.findall(pattern, text, flags=re.IGNORECASE)
            for m in matches:
                item = m.strip()
                if item and item not in goals:
                    goals.append(item[:120])
                if len(goals) >= 3:
                    return goals

        if not goals:
            goals = [
                "Keep story causally connected to current act",
                "Advance one meaningful clue or relationship per turn",
            ]
        return goals[:3]

    @staticmethod
    def _derive_forbidden_drifts(world_context: str) -> list[str]:
        text = (world_context or "").lower()
        forbidden: list[str] = []

        # 기본 금지 방향 (무관한 장르 급변/톤 붕괴)
        base = [
            "sudden sci-fi tech insertion",
            "unrelated slapstick tone break",
            "goal-irrelevant side detour",
        ]
        forbidden.extend(base)

        # world context에 이미 금지/제약이 있으면 일부 반영
        if "dark" in text:
            forbidden.append("abrupt comedic parody")
        if "politic" in text or "kingdom" in text:
            forbidden.append("random dungeon crawl unrelated to factions")

        return forbidden[:5]

    @staticmethod
    def _next_arc_phase(current: str) -> str:
        order = ["intro", "build", "twist", "climax", "resolution"]
        if current not in order:
            return "build"
        idx = order.index(current)
        return order[min(idx + 1, len(order) - 1)]

    @staticmethod
    def _clamp(value: int, min_value: int, max_value: int) -> int:
        return max(min_value, min(max_value, value))


_story_director_service: StoryDirectorService | None = None


def get_story_director_service() -> StoryDirectorService:
    global _story_director_service
    if _story_director_service is None:
        _story_director_service = StoryDirectorService()
    return _story_director_service
