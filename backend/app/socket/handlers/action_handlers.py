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

            # 빈 행동 텍스트 검증
            if not action_text:
                await sio.emit("error", {"message": "행동 텍스트가 비어있습니다"}, room=sid)
                return

            # 액션 추가
            action = add_action(session_id, player_id, character_name, action_text)

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

            logger.info(f"행동 제출: 세션={session_id}, 플레이어={player_id}, 캐릭터={character_name}")

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
                                        action_type=ActionType.DEXTERITY,  # 기본값
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
                                        action_type=ActionType.DEXTERITY,
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
                                    "requires_roll": bool(analysis.requires_roll),
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
                                        "requires_roll": bool(analysis.requires_roll),
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
                                "requires_roll": bool(analysis.requires_roll),
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
