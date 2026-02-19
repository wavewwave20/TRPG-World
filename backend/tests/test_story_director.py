from app.schemas import JudgmentOutcome, JudgmentResult
from app.services.story_director import StoryDirectorService


def _j(outcome: JudgmentOutcome) -> JudgmentResult:
    return JudgmentResult(
        character_id=1,
        action_text="test",
        dice_result=10,
        modifier=0,
        final_value=10,
        difficulty=10,
        outcome=outcome,
        outcome_reasoning="",
    )


def test_story_director_build_guidance_relief_when_crisis_is_high():
    service = StoryDirectorService()

    # 1턴차: 위기 누적
    judgments = [_j(JudgmentOutcome.CRITICAL_FAILURE), _j(JudgmentOutcome.FAILURE)]
    service.commit_after_narrative(
        session_id=100,
        world_context="왕국 붕괴를 막아야 한다.",
        ai_summary=None,
        judgments=judgments,
        metadata={"situation": "성문이 무너진다", "act_transition": False},
    )

    # 2턴차: 다시 위기 -> 연속 위기 >=2가 되면 완화 지시가 나와야 함
    service.commit_after_narrative(
        session_id=100,
        world_context="왕국 붕괴를 막아야 한다.",
        ai_summary=None,
        judgments=judgments,
        metadata={"situation": "후퇴 중", "act_transition": False},
    )

    guidance = service.build_guidance(
        session_id=100,
        world_context="왕국 붕괴를 막아야 한다.",
        ai_summary=None,
        judgments=judgments,
    )

    assert "완화/정리/회복" in guidance


def test_story_director_commit_resets_on_act_transition():
    service = StoryDirectorService()
    session_id = 200

    service.commit_after_narrative(
        session_id=session_id,
        world_context="고대 봉인을 지켜라.",
        ai_summary=None,
        judgments=[_j(JudgmentOutcome.FAILURE)],
        metadata={"situation": "균열이 커진다", "act_transition": False},
    )

    state_before = service.get_or_create_state(session_id, "고대 봉인을 지켜라.")
    assert state_before.tension >= 45

    service.commit_after_narrative(
        session_id=session_id,
        world_context="고대 봉인을 지켜라.",
        ai_summary=None,
        judgments=[_j(JudgmentOutcome.SUCCESS)],
        metadata={"situation": "새 단서를 발견", "act_transition": True},
    )

    state_after = service.get_or_create_state(session_id, "고대 봉인을 지켜라.")
    assert state_after.arc_phase in {"twist", "climax", "resolution", "build", "intro"}
    assert state_after.tension == 45
    assert state_after.consecutive_crisis == 0
