"""액션 관련 이벤트 핸들러 모듈.

플레이어 행동 제출, 큐 조회, 수정, 삭제, 재정렬, 커밋 이벤트를 처리합니다.
"""

import os

from app.database import SessionLocal
from app.models import ActionJudgment, Character, SessionParticipant, StoryLog
from app.services.act_resolver import resolve_current_open_act
from app.socket.managers.action_queue_manager import (
    add_action,
    clear_queue,
    delete_action,
    edit_action,
    get_queue,
    reorder_actions,
)
from app.socket.managers.presence_manager import session_presence
from app.socket.managers.session_manager import verify_host_authorization
from app.socket.server import logger
from app.utils.timezone import to_kst_iso


def _coerce_requires_roll(value) -> bool:
    """requires_roll 값을 불리언으로 안전하게 변환합니다."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"false", "0", "no", "off", "n"}:
            return False
        if normalized in {"true", "1", "yes", "on", "y"}:
            return True
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)


def register_handlers(sio):
    """액션 관련 이벤트 핸들러를 등록합니다.

    인자:
        sio: Socket.io 서버 인스턴스
    """

    @sio.event
    async def submit_action(sid, data):
        """플레이어 행동 제출을 처리합니다.

        행동을 인메모리 큐에 추가하고 세션 내 모든 참가자에게 알립니다.

        인자:
            sid: 소켓 세션 ID
            data: 행동 데이터
                - session_id: 게임 세션 ID
                - player_id: 플레이어(사용자) ID
                - character_name: 캐릭터 이름
                - action_text: 행동 텍스트
        """
        try:
            session_id = data.get("session_id")
            player_id = data.get("player_id")
            character_name = data.get("character_name")
            action_text = data.get("action_text", "").strip()
            action_mode = (data.get("action_mode") or "normal").strip().lower()
            skill_name = (data.get("skill_name") or "").strip() or None

            # 빈 행동 텍스트 검증
            if not action_text:
                await sio.emit("error", {"message": "행동 텍스트가 비어있습니다"}, room=sid)
                return

            if action_mode not in {"normal", "skill"}:
                await sio.emit("error", {"message": "action_mode 값이 올바르지 않습니다"}, room=sid)
                return

            skill_ability = None

            db = SessionLocal()
            try:
                if action_mode == "skill":
                    if not skill_name:
                        await sio.emit("error", {"message": "스킬 사용 모드에서는 스킬 선택이 필요합니다"}, room=sid)
                        return

                    participant = (
                        db.query(SessionParticipant)
                        .filter(
                            SessionParticipant.session_id == session_id,
                            SessionParticipant.user_id == player_id,
                        )
                        .first()
                    )
                    if not participant:
                        await sio.emit("error", {"message": "세션 참가 캐릭터를 찾을 수 없습니다"}, room=sid)
                        return

                    character = db.query(Character).filter(Character.id == participant.character_id).first()
                    if not character:
                        await sio.emit("error", {"message": "캐릭터를 찾을 수 없습니다"}, room=sid)
                        return

                    skills = character.data.get("skills", []) if isinstance(character.data, dict) else []
                    active_skill = None
                    for s in skills:
                        if not isinstance(s, dict):
                            continue
                        if (s.get("name") or "").strip() != skill_name:
                            continue
                        if (s.get("type") or "").strip().lower() != "active":
                            continue
                        active_skill = s
                        break

                    if not active_skill:
                        await sio.emit("error", {"message": "사용 가능한 액티브 스킬을 찾을 수 없습니다"}, room=sid)
                        return

                    skill_ability = (active_skill.get("ability") or "dexterity").strip().lower()
                    if skill_ability not in {
                        "strength",
                        "dexterity",
                        "constitution",
                        "intelligence",
                        "wisdom",
                        "charisma",
                    }:
                        skill_ability = "dexterity"

                    cooldown_actions = active_skill.get("cooldown_actions", active_skill.get("cooldown", 3))
                    try:
                        cooldown_actions = int(3 if cooldown_actions is None else cooldown_actions)
                    except (TypeError, ValueError):
                        cooldown_actions = 3
                    cooldown_actions = max(0, cooldown_actions)

                    current_narrative_turn = (
                        db.query(StoryLog)
                        .filter(StoryLog.session_id == session_id, StoryLog.role == "AI")
                        .count()
                    )

                    char_data = character.data if isinstance(character.data, dict) else {}
                    cooldown_map = char_data.get("skill_cooldowns", {})
                    if not isinstance(cooldown_map, dict):
                        cooldown_map = {}

                    ready_turn = int(cooldown_map.get(skill_name, 0) or 0)
                    if current_narrative_turn < ready_turn:
                        remaining = ready_turn - current_narrative_turn
                        await sio.emit(
                            "error",
                            {
                                "message": f"{skill_name} 쿨타임 중입니다. 남은 스토리 진행 {remaining}회",
                            },
                            room=sid,
                        )
                        return

                    next_ready_turn = current_narrative_turn + cooldown_actions
                    cooldown_map[skill_name] = next_ready_turn
                    char_data["skill_cooldowns"] = cooldown_map
                    # JSON 필드 dirty 감지를 확실히 하기 위해 새 dict 객체로 재할당
                    character.data = {**char_data}
                    db.commit()

                    await sio.emit(
                        "skill_cooldown_updated",
                        {
                            "session_id": session_id,
                            "character_id": character.id,
                            "skill_name": skill_name,
                            "ready_turn": next_ready_turn,
                            "current_turn": current_narrative_turn,
                            "remaining": max(0, next_ready_turn - current_narrative_turn),
                        },
                        room=f"session_{session_id}",
                    )

                # 액션 추가
                action = add_action(
                    session_id,
                    player_id,
                    character_name,
                    action_text,
                    action_mode=action_mode,
                    skill_name=skill_name,
                    skill_ability=skill_ability,
                )

                # action_submitted 이벤트 브로드캐스트
                room_name = f"session_{session_id}"
                queue = get_queue(session_id)
                await sio.emit(
                    "action_submitted",
                    {
                        "session_id": session_id,
                        "action": action,
                        "queue_count": len(queue),
                    },
                    room=room_name,
                )

                logger.info(
                    f"행동 제출: 세션={session_id}, 플레이어={player_id}, 캐릭터={character_name}, 모드={action_mode}, 스킬={skill_name}"
                )
            finally:
                db.close()

        except Exception as e:
            print(f"submit_action 에러: {e}")
            await sio.emit("error", {"message": "행동 제출 실패"}, room=sid)

    @sio.event
    async def get_queue_handler(sid, data):
        """세션의 액션 큐를 조회합니다.

        인자:
            sid: 소켓 세션 ID
            data: 요청 데이터
                - session_id: 게임 세션 ID
        """
        try:
            session_id = data.get("session_id")
            queue = get_queue(session_id)

            await sio.emit("queue_data", {"actions": queue}, room=sid)

            print(f"큐 조회: session={session_id}, count={len(queue)}")

        except Exception as e:
            print(f"get_queue 에러: {e}")
            await sio.emit("error", {"message": "큐 조회 실패"}, room=sid)

    # get_queue 이벤트 이름으로 등록
    sio.on("get_queue", get_queue_handler)

    @sio.event
    async def edit_action_handler(sid, data):
        """액션 텍스트를 수정합니다.

        호스트만 수정할 수 있습니다.

        인자:
            sid: 소켓 세션 ID
            data: 수정 데이터
                - session_id: 게임 세션 ID
                - action_id: 수정할 액션 ID
                - new_text: 새로운 행동 텍스트
                - user_id: 요청 사용자 ID
        """
        try:
            session_id = data.get("session_id")
            action_id = data.get("action_id")
            new_text = data.get("new_text", "").strip()
            user_id = data.get("user_id")

            # 호스트 권한 확인
            db = SessionLocal()
            try:
                is_authorized, error_message = await verify_host_authorization(session_id, user_id, db)
                if not is_authorized:
                    await sio.emit("error", {"message": error_message}, room=sid)
                    return
            finally:
                db.close()

            # 빈 텍스트 검증
            if not new_text:
                await sio.emit("error", {"message": "행동 텍스트가 비어있습니다"}, room=sid)
                return

            # 액션 수정
            edit_action(session_id, action_id, new_text)

            # queue_updated 이벤트 브로드캐스트
            room_name = f"session_{session_id}"
            queue = get_queue(session_id)
            await sio.emit("queue_updated", {"actions": queue}, room=room_name)

            print(f"액션 수정: session={session_id}, action_id={action_id}")

        except Exception as e:
            print(f"edit_action 에러: {e}")
            await sio.emit("error", {"message": "액션 수정 실패"}, room=sid)

    # edit_action 이벤트 이름으로 등록
    sio.on("edit_action", edit_action_handler)

    @sio.event
    async def reorder_actions_handler(sid, data):
        """액션 순서를 재정렬합니다.

        호스트만 재정렬할 수 있습니다.

        인자:
            sid: 소켓 세션 ID
            data: 재정렬 데이터
                - session_id: 게임 세션 ID
                - action_ids: 새로운 순서의 액션 ID 목록
                - user_id: 요청 사용자 ID
        """
        try:
            session_id = data.get("session_id")
            action_ids = data.get("action_ids", [])
            user_id = data.get("user_id")

            # 호스트 권한 확인
            db = SessionLocal()
            try:
                is_authorized, error_message = await verify_host_authorization(session_id, user_id, db)
                if not is_authorized:
                    await sio.emit("error", {"message": error_message}, room=sid)
                    return
            finally:
                db.close()

            # 액션 재정렬
            reorder_actions(session_id, action_ids)

            # queue_updated 이벤트 브로드캐스트
            room_name = f"session_{session_id}"
            queue = get_queue(session_id)
            await sio.emit("queue_updated", {"actions": queue}, room=room_name)

            print(f"액션 재정렬: session={session_id}, new_order={action_ids}")

        except Exception as e:
            print(f"reorder_actions 에러: {e}")
            await sio.emit("error", {"message": "액션 재정렬 실패"}, room=sid)

    # reorder_actions 이벤트 이름으로 등록
    sio.on("reorder_actions", reorder_actions_handler)

    @sio.event
    async def delete_action_handler(sid, data):
        """액션을 큐에서 삭제합니다.

        호스트만 삭제할 수 있습니다.

        인자:
            sid: 소켓 세션 ID
            data: 삭제 데이터
                - session_id: 게임 세션 ID
                - action_id: 삭제할 액션 ID
                - user_id: 요청 사용자 ID
        """
        try:
            session_id = data.get("session_id")
            action_id = data.get("action_id")
            user_id = data.get("user_id")

            # 호스트 권한 확인
            db = SessionLocal()
            try:
                is_authorized, error_message = await verify_host_authorization(session_id, user_id, db)
                if not is_authorized:
                    await sio.emit("error", {"message": error_message}, room=sid)
                    return
            finally:
                db.close()

            # 액션 삭제
            delete_action(session_id, action_id)

            # queue_updated 이벤트 브로드캐스트
            room_name = f"session_{session_id}"
            queue = get_queue(session_id)
            await sio.emit(
                "queue_updated",
                {"actions": queue, "queue_count": len(queue)},
                room=room_name,
            )

            print(f"액션 삭제: session={session_id}, action_id={action_id}")

        except Exception as e:
            print(f"delete_action 에러: {e}")
            await sio.emit("error", {"message": "액션 삭제 실패"}, room=sid)

    # delete_action 이벤트 이름으로 등록
    sio.on("delete_action", delete_action_handler)

    @sio.event
    async def commit_actions(sid, data):
        """모든 액션을 StoryLog에 커밋하고 AI 생성을 트리거합니다.

        호스트만 커밋할 수 있습니다.
        커밋 시:
        1. 플레이어 행동을 데이터베이스에 저장
        2. AI 판정 생성 (Phase 1)
        3. 결과를 실시간으로 스트리밍

        인자:
            sid: 소켓 세션 ID
            data: 커밋 데이터
                - session_id: 게임 세션 ID
                - user_id: 요청 사용자 ID
        """
        try:
            session_id = data.get("session_id")
            user_id = data.get("user_id")

            db = SessionLocal()
            try:
                # 호스트 권한 확인
                is_authorized, error_message = await verify_host_authorization(session_id, user_id, db)
                if not is_authorized:
                    await sio.emit("error", {"message": error_message}, room=sid)
                    return

                # 큐가 비어있는지 확인
                queue = get_queue(session_id)
                if not queue:
                    await sio.emit("error", {"message": "커밋할 행동이 없습니다"}, room=sid)
                    return

                # 액션을 order 기준으로 정렬하여 가져오고 큐 비우기
                actions = clear_queue(session_id)

                # 행동 텍스트를 내러티브 형식으로 결합
                narrative_parts = [f"{action['character_name']}: {action['action_text']}" for action in actions]
                combined_narrative = "\n".join(narrative_parts)

                current_act = resolve_current_open_act(db, session_id)

                # StoryLog에 저장 (role='USER')
                story_entry = StoryLog(
                    session_id=session_id,
                    role="USER",
                    content=combined_narrative,
                    act_id=current_act.id if current_act else None,
                )
                db.add(story_entry)
                db.commit()
                db.refresh(story_entry)

                # story_committed 이벤트 브로드캐스트
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

                # queue_updated 이벤트 (큐 비움)
                await sio.emit("queue_updated", {"actions": [], "queue_count": 0}, room=room_name)

                logger.info(f"행동 커밋: 세션={session_id}, 행동 수={len(actions)}")

                # ===== AI 생성 워크플로우 =====
                # ai_generation_started 이벤트 (Phase 1: 판정)
                await sio.emit(
                    "ai_generation_started",
                    {"session_id": session_id, "phase": "judgment"},
                    room=room_name,
                )

                try:
                    # AI 서비스 import
                    from app.schemas import ActionType, PlayerAction
                    from app.services.ai_gm_service_v2 import AIGMServiceV2

                    # 액션을 PlayerAction으로 변환
                    player_actions = []
                    for action in actions:
                        action_type_value = (action.get("skill_ability") or "dexterity").lower()
                        action_type_enum = {
                            "strength": ActionType.STRENGTH,
                            "dexterity": ActionType.DEXTERITY,
                            "constitution": ActionType.CONSTITUTION,
                            "intelligence": ActionType.INTELLIGENCE,
                            "wisdom": ActionType.WISDOM,
                            "charisma": ActionType.CHARISMA,
                        }.get(action_type_value, ActionType.DEXTERITY)

                        # SessionParticipant에서 캐릭터 찾기
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
                                        action_type=action_type_enum,
                                    )
                                )
                                logger.info(f"행동 매핑: 유저 {action['player_id']} -> 캐릭터 {char.id} ({char.name})")
                            else:
                                logger.warning(
                                    f"캐릭터 없음: user_id={action['player_id']}, "
                                    f"character_id={participant.character_id}"
                                )
                        else:
                            # 폴백: 캐릭터 이름으로 찾기
                            char = db.query(Character).filter(Character.name == action["character_name"]).first()
                            if char:
                                player_actions.append(
                                    PlayerAction(
                                        character_id=char.id,
                                        action_text=action["action_text"],
                                        action_type=action_type_enum,
                                    )
                                )
                                logger.info(f"캐릭터명으로 매핑: {action['character_name']} -> {char.id}")
                            else:
                                logger.warning(
                                    f"캐릭터 찾기 실패: player_id={action['player_id']}, "
                                    f"character_name={action['character_name']}"
                                )

                    if not player_actions:
                        raise ValueError(f"캐릭터에 매핑된 행동이 없습니다. Actions: {actions}")

                    # AI GM 서비스 초기화
                    from app.services.llm_config_resolver import get_active_llm_model

                    llm_model = get_active_llm_model()
                    ai_service = AIGMServiceV2(db=db, llm_model=llm_model)

                    # Phase 1: 행동 분석 및 DC 결정
                    analyses = await ai_service.analyze_actions(session_id=session_id, player_actions=player_actions)

                    if not analyses:
                        raise ValueError("AI에서 분석 결과가 반환되지 않았습니다")

                    # judgments_ready 이벤트 브로드캐스트
                    await sio.emit(
                        "judgments_ready",
                        {
                            "session_id": session_id,
                            "analyses": [
                                {
                                    "character_id": analysis.character_id,
                                    "action_text": analysis.action_text,
                                    "action_type": analysis.action_type.value,
                                    "modifier": analysis.modifier,
                                    "difficulty": analysis.difficulty,
                                    "difficulty_reasoning": analysis.difficulty_reasoning,
                                    "requires_roll": _coerce_requires_roll(analysis.requires_roll),
                                }
                                for analysis in analyses
                            ],
                        },
                        room=room_name,
                    )
                    logger.info(f"judgments_ready 이벤트 전송: 세션={session_id}")

                    # 각 플레이어에게 judgment_ready 전송
                    for analysis in analyses:
                        character = db.query(Character).filter(Character.id == analysis.character_id).first()

                        if not character:
                            continue

                        # 사전 굴림 판정 조회 (phase=0)
                        action_judgment = (
                            db.query(ActionJudgment)
                            .filter(
                                ActionJudgment.session_id == session_id,
                                ActionJudgment.character_id == analysis.character_id,
                                ActionJudgment.phase == 0,
                            )
                            .order_by(ActionJudgment.id.desc())
                            .first()
                        )

                        if not action_judgment:
                            logger.warning(f"사전 굴림 판정 없음: 캐릭터={analysis.character_id}")
                            continue

                        # 플레이어의 소켓 ID 찾기
                        participant = (
                            db.query(SessionParticipant)
                            .filter(
                                SessionParticipant.session_id == session_id,
                                SessionParticipant.character_id == analysis.character_id,
                            )
                            .first()
                        )

                        if participant:
                            # 해당 사용자의 소켓 ID 찾기
                            player_sid = None
                            for s_id, info in session_presence.items():
                                if info.get("session_id") == session_id and info.get("user_id") == participant.user_id:
                                    player_sid = s_id
                                    break

                            if player_sid:
                                # 해당 플레이어에게 judgment_ready 전송
                                await sio.emit(
                                    "judgment_ready",
                                    {
                                        "session_id": session_id,
                                        "character_id": analysis.character_id,
                                        "judgment_id": action_judgment.id,
                                        "action_text": analysis.action_text,
                                        "action_type": analysis.action_type.value,
                                        "modifier": analysis.modifier,
                                        "difficulty": analysis.difficulty,
                                        "difficulty_reasoning": analysis.difficulty_reasoning,
                                        "requires_roll": _coerce_requires_roll(analysis.requires_roll),
                                    },
                                    to=player_sid,
                                )

                        # 다른 플레이어들에게 player_action_analyzed 브로드캐스트
                        await sio.emit(
                            "player_action_analyzed",
                            {
                                "session_id": session_id,
                                "character_id": analysis.character_id,
                                "character_name": character.name,
                                "judgment_id": action_judgment.id,
                                "action_text": analysis.action_text,
                                "action_type": analysis.action_type.value,
                                "modifier": analysis.modifier,
                                "difficulty": analysis.difficulty,
                                "difficulty_reasoning": analysis.difficulty_reasoning,
                                "requires_roll": _coerce_requires_roll(analysis.requires_roll),
                            },
                            room=room_name,
                            skip_sid=player_sid if participant else None,
                        )

                    logger.info(f"Phase 1 완료: 세션={session_id}, {len(analyses)}개 행동 분석됨")

                except Exception as ai_error:
                    # AI 생성 에러는 호스트에게만 전송
                    print(f"AI 생성 에러: {ai_error}")
                    await sio.emit(
                        "ai_generation_error",
                        {"session_id": session_id, "error": str(ai_error)},
                        to=sid,
                    )

            except Exception as e:
                # 데이터베이스 에러 (큐는 비우지 않음)
                print(f"commit_actions 데이터베이스 에러: {e}")
                await sio.emit("error", {"message": "행동 커밋 실패"}, room=sid)
            finally:
                db.close()

        except Exception as e:
            print(f"commit_actions 에러: {e}")
            await sio.emit("error", {"message": "행동 커밋 실패"}, room=sid)
