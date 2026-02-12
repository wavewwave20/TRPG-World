"""AI GM 관련 이벤트 핸들러 모듈.

AI GM 판정 및 이야기 생성 이벤트를 처리합니다.
행동 분석 → 주사위 확인 → 이야기 생성 흐름을 담당합니다.
"""

import asyncio
import os
from datetime import datetime

from app.database import SessionLocal
from app.models import ActionJudgment, Character, GameSession, StoryLog
from app.socket.managers.presence_manager import session_presence
from app.socket.server import logger

# Guard against duplicate narrative stream requests for the same session.
_narrative_stream_in_progress: set[int] = set()


async def _generate_opening_narrative(session_id, world_prompt, db, room_name, sio):
    """AI로 오프닝 서술을 스트리밍 생성합니다.

    세계관 프롬프트에 '시작 상황' 섹션이 없을 때 호출됩니다.
    AI가 세계관을 기반으로 모험의 시작 장면을 생성합니다.

    인자:
        session_id: 게임 세션 ID
        world_prompt: 세계관 프롬프트
        db: 데이터베이스 세션
        room_name: 브로드캐스트용 소켓 룸 이름
        sio: Socket.io 서버 인스턴스
    """
    logger.info(f"오프닝 서술 생성 시작: 세션={session_id}")

    await sio.emit("narrative_stream_started", {"session_id": session_id}, room=room_name)

    try:
        from langchain_litellm import ChatLiteLLM
        from langchain_core.prompts import ChatPromptTemplate

        from app.utils.prompt_loader import load_prompt

        llm_model = os.getenv("LLM_MODEL", "gpt-4o")

        # narrative_prompt.md를 시스템 프롬프트로 사용
        system_message = load_prompt("narrative_prompt.md")

        chat_template = ChatPromptTemplate.from_messages([
            system_message,
            ("human", "## 세계관\n\n{world_prompt}\n\n"
                      "위 세계관을 바탕으로 모험의 시작 장면을 서술해주세요. "
                      "모험가들이 어디에 있고, 무엇을 보고 느끼는지 생생하게 묘사해주세요. "
                      "3인칭 서술자 시점으로 장면만 묘사하고, 플레이어에게 질문하지 마세요."),
        ])

        llm = ChatLiteLLM(
            model=llm_model,
            temperature=1.0,
            max_tokens=2000,
        )

        chain = chat_template | llm

        full_narrative = ""
        token_count = 0
        async for chunk in chain.astream({"world_prompt": world_prompt}):
            if hasattr(chunk, "content") and chunk.content:
                token = chunk.content
                full_narrative += token
                await sio.emit(
                    "narrative_token",
                    {"session_id": session_id, "token": token},
                    room=room_name,
                )
                token_count += 1
                await asyncio.sleep(0.05)

        logger.info(f"오프닝 서술 생성 완료: 세션={session_id}, 토큰={token_count}개")

        story_log = StoryLog(
            session_id=session_id,
            role="AI",
            content=full_narrative.strip(),
            created_at=datetime.utcnow(),
        )
        db.add(story_log)
        db.commit()
        db.refresh(story_log)

        await sio.emit("narrative_complete", {"session_id": session_id}, room=room_name)

        logger.info(f"오프닝 서술 DB 저장 완료: 세션={session_id}")

        # Act 1 생성
        await _create_act_1(
            session_id, world_prompt, full_narrative.strip(), story_log.id, db, room_name, sio
        )

    except Exception as e:
        logger.error(f"오프닝 서술 생성 에러: {e}", exc_info=True)
        await sio.emit(
            "narrative_error",
            {"session_id": session_id, "error": f"오프닝 서술 생성 실패: {str(e)}"},
            room=room_name,
        )


async def _create_act_1(session_id, world_prompt, narrative_text, story_log_id, db, room_name, sio):
    """Act 1을 생성하고 act_started 이벤트를 emit합니다."""
    from app.models import StoryAct

    try:
        from app.services.ai_nodes.act_analysis_node import generate_act_title

        llm_model = os.getenv("LLM_MODEL", "gpt-4o")
        title_data = await generate_act_title(world_prompt, narrative_text, llm_model)

        act = StoryAct(
            session_id=session_id,
            act_number=1,
            title=title_data.get("title", "서막"),
            subtitle=title_data.get("subtitle"),
            started_at=datetime.utcnow(),
            start_story_log_id=story_log_id,
        )
        db.add(act)

        # 오프닝 StoryLog에 act_id 설정
        story_log = db.query(StoryLog).filter(StoryLog.id == story_log_id).first()
        if story_log:
            story_log.act_id = act.id

        db.commit()
        db.refresh(act)

        act_info = {
            "id": act.id,
            "act_number": act.act_number,
            "title": act.title,
            "subtitle": act.subtitle,
            "started_at": act.started_at.isoformat(),
        }

        await sio.emit(
            "act_started",
            {"session_id": session_id, "act": act_info},
            room=room_name,
        )

        logger.info(f"Act 1 생성 완료: 세션={session_id}, 제목='{act.title}'")

    except Exception as e:
        logger.error(f"Act 1 생성 실패: {e}", exc_info=True)
        # Act 생성 실패해도 게임은 계속 진행 가능


async def _check_act_transition_after_narrative(session_id, db, room_name, sio):
    """Phase 3 서술 완료 후 막 전환을 체크합니다."""
    try:
        llm_model = os.getenv("LLM_MODEL", "gpt-4o")

        from app.services.ai_gm_service_v2 import AIGMServiceV2

        ai_service = AIGMServiceV2(db=db, llm_model=llm_model)
        result = await ai_service.check_act_transition(session_id)

        if result is None:
            return

        # 막 전환 결과 브로드캐스트
        await sio.emit(
            "act_completed",
            {
                "session_id": session_id,
                "completed_act": result.completed_act.model_dump(),
                "new_act": result.new_act.model_dump(),
                "growth_rewards": [r.model_dump() for r in result.growth_rewards],
            },
            room=room_name,
        )

        # 개별 캐릭터 성장 이벤트
        for reward in result.growth_rewards:
            await sio.emit(
                "character_growth_applied",
                {
                    "session_id": session_id,
                    "character_id": reward.character_id,
                    "growth": reward.model_dump(),
                },
                room=room_name,
            )

        logger.info(
            f"막 전환 완료: 세션={session_id}, "
            f"'{result.completed_act.title}' → '{result.new_act.title}', "
            f"성장 보상 {len(result.growth_rewards)}개"
        )

    except Exception as e:
        logger.error(f"막 전환 체크 실패: {e}", exc_info=True)


def register_handlers(sio):
    """AI GM 관련 이벤트 핸들러를 등록합니다.

    인자:
        sio: Socket.io 서버 인스턴스
    """

    @sio.event
    async def submit_player_action(sid, data):
        """플레이어 행동 제출을 처리합니다 (Phase 1).

        행동을 분석하고 DC를 결정합니다:
        1. 플레이어 행동 수신
        2. AI로 행동 분석 및 DC 결정
        3. 캐릭터 스탯에서 보정치 계산
        4. judgment_ready 이벤트로 보정치 + DC 반환

        인자:
            sid: 소켓 세션 ID
            data: 행동 데이터
                - session_id: 게임 세션 ID
                - character_id: 캐릭터 ID
                - action_text: 행동 텍스트
                - action_type: 행동 유형 (strength, dexterity 등)
        """
        try:
            session_id = data.get("session_id")
            character_id = data.get("character_id")
            action_text = data.get("action_text", "").strip()
            action_type = data.get("action_type", "dexterity").lower()

            logger.info(f"Phase 1 - 행동 제출: 세션={session_id}, 캐릭터={character_id}")

            # 필수 필드 검증
            if not session_id or not character_id:
                await sio.emit(
                    "action_analysis_error",
                    {"session_id": session_id, "error": "session_id와 character_id가 필요합니다"},
                    to=sid,
                )
                return

            if not action_text:
                await sio.emit(
                    "action_analysis_error",
                    {"session_id": session_id, "error": "행동 텍스트가 비어있습니다"},
                    to=sid,
                )
                return

            db = SessionLocal()
            try:
                # 세션 존재 및 활성 상태 확인
                session = db.query(GameSession).filter(GameSession.id == session_id).first()
                if not session:
                    await sio.emit(
                        "action_analysis_error",
                        {"session_id": session_id, "error": "세션을 찾을 수 없습니다"},
                        to=sid,
                    )
                    return

                if not session.is_active:
                    await sio.emit(
                        "action_analysis_error",
                        {"session_id": session_id, "error": "세션이 활성 상태가 아닙니다"},
                        to=sid,
                    )
                    return

                # 캐릭터 존재 확인
                character = db.query(Character).filter(Character.id == character_id).first()
                if not character:
                    await sio.emit(
                        "action_analysis_error",
                        {"session_id": session_id, "error": "캐릭터를 찾을 수 없습니다"},
                        to=sid,
                    )
                    return

                # AI 서비스 import
                from app.schemas import ActionType, PlayerAction
                from app.services.ai_gm_service_v2 import AIGMServiceV2

                # action_type 문자열을 ActionType enum으로 변환
                action_type_map = {
                    "strength": ActionType.STRENGTH,
                    "dexterity": ActionType.DEXTERITY,
                    "constitution": ActionType.CONSTITUTION,
                    "intelligence": ActionType.INTELLIGENCE,
                    "wisdom": ActionType.WISDOM,
                    "charisma": ActionType.CHARISMA,
                }
                action_type_enum = action_type_map.get(action_type, ActionType.DEXTERITY)

                # PlayerAction 생성
                player_action = PlayerAction(
                    character_id=character_id,
                    action_text=action_text,
                    action_type=action_type_enum,
                )

                # AI GM 서비스 초기화
                llm_model = os.getenv("LLM_MODEL", "gpt-4o")
                ai_service = AIGMServiceV2(db=db, llm_model=llm_model)

                # Phase 1: 행동 분석
                analyses = await ai_service.analyze_actions(session_id=session_id, player_actions=[player_action])

                if not analyses:
                    raise ValueError("분석 결과가 반환되지 않았습니다")

                analysis = analyses[0]

                # Phase 1 결과를 데이터베이스에 저장
                action_judgment = ActionJudgment(
                    session_id=session_id,
                    character_id=character_id,
                    action_text=action_text,
                    action_type=action_type,
                    modifier=analysis.modifier,
                    difficulty=analysis.difficulty,
                    difficulty_reasoning=analysis.difficulty_reasoning,
                    phase=1,  # Phase 1: 분석 완료
                )
                db.add(action_judgment)
                db.commit()
                db.refresh(action_judgment)

                logger.info(
                    f"Phase 1 완료: 캐릭터={character_id}, 보정치={analysis.modifier:+d}, DC={analysis.difficulty}"
                )

                # 플레이어에게 judgment_ready 이벤트 전송
                await sio.emit(
                    "judgment_ready",
                    {
                        "session_id": session_id,
                        "character_id": character_id,
                        "judgment_id": action_judgment.id,
                        "action_text": action_text,
                        "action_type": analysis.action_type.value,
                        "modifier": analysis.modifier,
                        "difficulty": analysis.difficulty,
                        "difficulty_reasoning": analysis.difficulty_reasoning,
                        "requires_roll": bool(analysis.requires_roll),
                    },
                    to=sid,
                )

                # 다른 플레이어들에게 브로드캐스트
                room_name = f"session_{session_id}"
                await sio.emit(
                    "player_action_analyzed",
                    {
                        "session_id": session_id,
                        "character_id": character_id,
                        "character_name": character.name,
                        "judgment_id": action_judgment.id,
                        "action_text": action_text,
                        "action_type": analysis.action_type.value,
                        "modifier": analysis.modifier,
                        "difficulty": analysis.difficulty,
                        "difficulty_reasoning": analysis.difficulty_reasoning,
                        "requires_roll": bool(analysis.requires_roll),
                    },
                    room=room_name,
                    skip_sid=sid,
                )

            except Exception as e:
                logger.error(f"Phase 1 에러: {e}", exc_info=True)
                await sio.emit(
                    "action_analysis_error",
                    {"session_id": session_id, "character_id": character_id, "error": str(e)},
                    to=sid,
                )
            finally:
                db.close()

        except Exception as e:
            logger.error(f"submit_player_action 에러: {e}", exc_info=True)
            await sio.emit(
                "action_analysis_error",
                {"session_id": data.get("session_id"), "error": "행동 분석 실패"},
                to=sid,
            )

    @sio.event
    async def roll_dice(sid, data):
        """주사위 굴림 확인을 처리합니다 (Phase 2).

        사전 굴림된 주사위 값을 확인합니다:
        1. 플레이어의 주사위 확인 수신 (dice_result는 무시됨)
        2. 데이터베이스에서 사전 굴림 주사위 조회 (phase=0)
        3. ActionJudgment를 phase=2로 업데이트 (확인됨)
        4. 모든 참가자에게 dice_rolled 이벤트 브로드캐스트
        5. 모든 플레이어가 확인했는지 체크

        인자:
            sid: 소켓 세션 ID
            data: 주사위 데이터
                - session_id: 게임 세션 ID
                - character_id: 캐릭터 ID
                - judgment_id: 판정 ID (judgment_ready 이벤트에서 받음)
                - dice_result: 주사위 결과 (무시됨 - 하위 호환성용)
        """
        try:
            session_id = data.get("session_id")
            character_id = data.get("character_id")

            logger.info(f"Phase 2 - 주사위 확인: 세션={session_id}, 캐릭터={character_id}")

            # 필수 필드 검증
            if not session_id or not character_id:
                await sio.emit(
                    "dice_roll_error",
                    {"session_id": session_id, "error": "session_id와 character_id가 필요합니다"},
                    to=sid,
                )
                return

            db = SessionLocal()
            try:
                # AIGMServiceV2로 주사위 확인
                from app.services.ai_gm_service_v2 import AIGMServiceV2

                ai_service = AIGMServiceV2(db=db)
                await ai_service.confirm_dice_roll(session_id=session_id, character_id=character_id)

                # 확인된 판정 조회
                judgment = (
                    db.query(ActionJudgment)
                    .filter(
                        ActionJudgment.session_id == session_id,
                        ActionJudgment.character_id == character_id,
                        ActionJudgment.phase == 2,
                    )
                    .order_by(ActionJudgment.id.desc())
                    .first()
                )

                if not judgment:
                    await sio.emit(
                        "dice_roll_error",
                        {"session_id": session_id, "error": "판정을 찾을 수 없습니다"},
                        to=sid,
                    )
                    return

                # 캐릭터 이름 조회
                character = db.query(Character).filter(Character.id == character_id).first()
                character_name = character.name if character else f"캐릭터 {character_id}"

                logger.info(
                    f"Phase 2 완료: 캐릭터={character_id}, "
                    f"주사위={judgment.dice_result}, 보정치={judgment.modifier:+d}, "
                    f"최종={judgment.final_value}, DC={judgment.difficulty}, 결과={judgment.outcome}"
                )

                # 모든 참가자에게 dice_rolled 이벤트 브로드캐스트
                room_name = f"session_{session_id}"
                await sio.emit(
                    "dice_rolled",
                    {
                        "session_id": session_id,
                        "character_id": character_id,
                        "character_name": character_name,
                        "judgment_id": judgment.id,
                        "dice_result": judgment.dice_result,
                        "modifier": judgment.modifier,
                        "final_value": judgment.final_value,
                        "difficulty": judgment.difficulty,
                        "outcome": judgment.outcome,
                    },
                    room=room_name,
                )

                # 모든 플레이어가 확인했는지 체크 (phase=0은 아직 확인 안 됨)
                pending_judgments = (
                    db.query(ActionJudgment)
                    .filter(
                        ActionJudgment.session_id == session_id,
                        ActionJudgment.phase == 0,
                    )
                    .count()
                )

                if pending_judgments == 0:
                    logger.info(f"모든 주사위 확인 완료: 세션={session_id}")
                    await sio.emit("all_dice_rolled", {"session_id": session_id}, room=room_name)

            except Exception as e:
                logger.error(f"Phase 2 에러: {e}", exc_info=True)
                db.rollback()
                await sio.emit(
                    "dice_roll_error",
                    {"session_id": session_id, "character_id": character_id, "error": str(e)},
                    to=sid,
                )
            finally:
                db.close()

        except Exception as e:
            logger.error(f"roll_dice 에러: {e}", exc_info=True)
            await sio.emit(
                "dice_roll_error",
                {"session_id": data.get("session_id"), "error": "주사위 처리 실패"},
                to=sid,
            )

    @sio.event
    async def next_judgment(sid, data):
        """다음 판정으로 이동합니다.

        플레이어가 주사위 굴림을 완료하고 "다음" 버튼을 클릭했을 때 호출됩니다.

        인자:
            sid: 소켓 세션 ID
            data: 이동 데이터
                - session_id: 게임 세션 ID
                - current_index: 현재 판정 인덱스
        """
        try:
            session_id = data.get("session_id")
            current_index = data.get("current_index", 0)

            if not session_id:
                await sio.emit("error", {"message": "session_id가 필요합니다"}, room=sid)
                return

            # 모든 참가자에게 next_judgment 이벤트 브로드캐스트
            room_name = f"session_{session_id}"
            await sio.emit("next_judgment", {"judgment_index": current_index + 1}, room=room_name)

            logger.info(f"다음 판정으로 이동: 세션={session_id}, 인덱스={current_index + 1}")

        except Exception as e:
            logger.error(f"next_judgment 에러: {e}", exc_info=True)
            await sio.emit("error", {"message": "다음 판정 이동 실패"}, room=sid)

    @sio.event
    async def confirm_action(sid, data):
        """자동 성공 행동의 확인을 처리합니다.

        requires_roll=false인 행동에 대해 플레이어가 "확인" 버튼을 눌렀을 때 호출됩니다.
        phase=0으로 저장된 자동 성공 판정을 phase=2로 업데이트하고
        dice_rolled 이벤트를 브로드캐스트합니다.

        인자:
            sid: 소켓 세션 ID
            data: 확인 데이터
                - session_id: 게임 세션 ID
                - character_id: 캐릭터 ID
                - judgment_id: 판정 ID
        """
        try:
            session_id = data.get("session_id")
            character_id = data.get("character_id")

            logger.info(f"자동 성공 확인: 세션={session_id}, 캐릭터={character_id}")

            if not session_id or not character_id:
                await sio.emit(
                    "dice_roll_error",
                    {"session_id": session_id, "error": "session_id와 character_id가 필요합니다"},
                    to=sid,
                )
                return

            db = SessionLocal()
            try:
                # auto_success + phase=0 판정 조회 (플레이어 확인 대기 중)
                judgment = (
                    db.query(ActionJudgment)
                    .filter(
                        ActionJudgment.session_id == session_id,
                        ActionJudgment.character_id == character_id,
                        ActionJudgment.outcome == "auto_success",
                        ActionJudgment.phase == 0,
                    )
                    .order_by(ActionJudgment.id.desc())
                    .first()
                )

                if not judgment:
                    await sio.emit(
                        "dice_roll_error",
                        {"session_id": session_id, "error": "자동 성공 판정을 찾을 수 없습니다"},
                        to=sid,
                    )
                    return

                # phase=2로 업데이트 (플레이어가 확인함)
                judgment.phase = 2
                db.commit()

                character = db.query(Character).filter(Character.id == character_id).first()
                character_name = character.name if character else f"캐릭터 {character_id}"

                logger.info(f"자동 성공 확인 완료: 캐릭터={character_id}")

                # 모든 참가자에게 dice_rolled 이벤트 브로드캐스트
                room_name = f"session_{session_id}"
                await sio.emit(
                    "dice_rolled",
                    {
                        "session_id": session_id,
                        "character_id": character_id,
                        "character_name": character_name,
                        "judgment_id": judgment.id,
                        "dice_result": 0,
                        "modifier": judgment.modifier,
                        "final_value": 0,
                        "difficulty": 0,
                        "outcome": "auto_success",
                        "requires_roll": False,
                    },
                    room=room_name,
                )

                # 모든 플레이어가 확인했는지 체크
                pending_judgments = (
                    db.query(ActionJudgment)
                    .filter(
                        ActionJudgment.session_id == session_id,
                        ActionJudgment.phase == 0,
                    )
                    .count()
                )

                if pending_judgments == 0:
                    logger.info(f"모든 주사위 확인 완료: 세션={session_id}")
                    await sio.emit("all_dice_rolled", {"session_id": session_id}, room=room_name)

            except Exception as e:
                logger.error(f"confirm_action 에러: {e}", exc_info=True)
                db.rollback()
                await sio.emit(
                    "dice_roll_error",
                    {"session_id": session_id, "character_id": character_id, "error": str(e)},
                    to=sid,
                )
            finally:
                db.close()

        except Exception as e:
            logger.error(f"confirm_action 에러: {e}", exc_info=True)
            await sio.emit(
                "dice_roll_error",
                {"session_id": data.get("session_id"), "error": "자동 성공 확인 처리 실패"},
                to=sid,
            )

    @sio.event
    async def start_game(sid, data):
        """게임 시작 - 첫 번째 이야기를 생성하거나 시작 상황을 전송합니다.

        호스트만 호출할 수 있습니다. 스토리 로그가 비어있을 때만 동작합니다.
        세계관 프롬프트에 '시작 상황' 섹션이 있으면 해당 텍스트를 직접 저장하고,
        없으면 AI가 오프닝 서술을 스트리밍으로 생성합니다.

        인자:
            sid: 소켓 세션 ID
            data: 요청 데이터
                - session_id: 게임 세션 ID
        """
        try:
            session_id = data.get("session_id")
            if not session_id:
                await sio.emit("error", {"message": "session_id가 필요합니다"}, to=sid)
                return

            # 호스트 검증: presence에서 user_id 조회
            presence = session_presence.get(sid)
            if not presence:
                await sio.emit("error", {"message": "세션에 참가하지 않은 상태입니다"}, to=sid)
                return
            user_id = presence.get("user_id")

            db = SessionLocal()
            try:
                # 세션 조회 및 호스트 검증
                session = db.query(GameSession).filter(GameSession.id == session_id).first()
                if not session:
                    await sio.emit("error", {"message": "세션을 찾을 수 없습니다"}, to=sid)
                    return

                if session.host_user_id != user_id:
                    await sio.emit(
                        "start_game_error",
                        {"session_id": session_id, "error": "호스트만 게임을 시작할 수 있습니다"},
                        to=sid,
                    )
                    return

                # 이미 스토리가 있는지 확인
                existing_logs = db.query(StoryLog).filter(StoryLog.session_id == session_id).count()
                if existing_logs > 0:
                    await sio.emit(
                        "start_game_error",
                        {"session_id": session_id, "error": "이미 게임이 시작되었습니다"},
                        to=sid,
                    )
                    return

                room_name = f"session_{session_id}"

                # 시작 상황 추출
                from app.services.context_loader import extract_starting_situation

                starting_text = extract_starting_situation(session.world_prompt or "")

                if starting_text:
                    # Path A: 시작 상황 텍스트를 직접 저장
                    story_log = StoryLog(
                        session_id=session_id,
                        role="AI",
                        content=starting_text,
                        created_at=datetime.utcnow(),
                    )
                    db.add(story_log)
                    db.commit()
                    db.refresh(story_log)

                    logger.info(f"게임 시작 (시작 상황): 세션={session_id}, story_log_id={story_log.id}")

                    await sio.emit(
                        "story_committed",
                        {
                            "story_entry": {
                                "id": story_log.id,
                                "role": "AI",
                                "content": starting_text,
                                "created_at": story_log.created_at.isoformat(),
                            }
                        },
                        room=room_name,
                    )

                    # Path A: Act 1 생성
                    await _create_act_1(
                        session_id, session.world_prompt or "", starting_text,
                        story_log.id, db, room_name, sio
                    )
                else:
                    # Path B: AI로 오프닝 서술 생성 (스트리밍)
                    await _generate_opening_narrative(
                        session_id, session.world_prompt or "", db, room_name, sio
                    )

            except Exception as e:
                logger.error(f"start_game 에러: {e}", exc_info=True)
                db.rollback()
                await sio.emit(
                    "start_game_error",
                    {"session_id": session_id, "error": str(e)},
                    to=sid,
                )
            finally:
                db.close()

        except Exception as e:
            logger.error(f"start_game 외부 에러: {e}", exc_info=True)
            await sio.emit("error", {"message": "게임 시작 실패"}, to=sid)

    @sio.event
    async def request_narrative_stream(sid, data):
        """이야기 스트림을 요청합니다.

        Phase 1에서 백그라운드로 생성된 이야기를 버퍼에서 스트리밍합니다.
        타이핑 효과 딜레이와 함께 토큰을 재생합니다.

        인자:
            sid: 소켓 세션 ID
            data: 요청 데이터
                - session_id: 게임 세션 ID
        """
        try:
            session_id = data.get("session_id")

            if not session_id:
                await sio.emit("error", {"message": "session_id가 필요합니다"}, room=sid)
                return

            if session_id in _narrative_stream_in_progress:
                logger.info(f"중복 이야기 스트림 요청 무시: 세션={session_id}")
                return

            _narrative_stream_in_progress.add(session_id)
            logger.info(f"이야기 스트림 요청: 세션={session_id}")

            db = SessionLocal()
            try:
                room_name = f"session_{session_id}"

                # 스트림 시작 이벤트
                await sio.emit("narrative_stream_started", {"session_id": session_id}, room=room_name)

                # AIGMServiceV2로 이야기 스트리밍
                from app.services.ai_gm_service_v2 import AIGMServiceV2

                ai_service = AIGMServiceV2(db=db)

                # 토큰 스트리밍
                token_count = 0
                async for token in ai_service.stream_narrative(session_id):
                    await sio.emit(
                        "narrative_token",
                        {"session_id": session_id, "token": token},
                        room=room_name,
                    )
                    token_count += 1

                logger.info(f"이야기 토큰 {token_count}개 전송: room={room_name}")

                # 완료 이벤트
                await sio.emit("narrative_complete", {"session_id": session_id}, room=room_name)

                logger.info(f"이야기 스트림 완료: 세션={session_id}")

            except ValueError as e:
                logger.error(f"이야기 스트림 에러: 세션={session_id}, {e}")
                await sio.emit(
                    "narrative_error",
                    {"session_id": session_id, "error": str(e)},
                    room=f"session_{session_id}",
                )
            finally:
                db.close()
                _narrative_stream_in_progress.discard(session_id)

        except Exception as e:
            logger.error(f"request_narrative_stream 에러: {e}", exc_info=True)
            session_id = data.get("session_id")
            if session_id:
                _narrative_stream_in_progress.discard(session_id)
            await sio.emit("error", {"message": "이야기 스트리밍 실패"}, room=sid)

    @sio.event
    async def trigger_story_generation(sid, data):
        """이야기 생성을 수동으로 트리거합니다.

        마지막 플레이어가 주사위 굴림을 완료하고 "이야기 진행" 버튼을 클릭했을 때 호출됩니다.

        인자:
            sid: 소켓 세션 ID
            data: 요청 데이터
                - session_id: 게임 세션 ID
        """
        try:
            session_id = data.get("session_id")

            if not session_id:
                await sio.emit("error", {"message": "session_id가 필요합니다"}, room=sid)
                return

            logger.info(f"수동 이야기 생성 트리거: 세션={session_id}")

            db = SessionLocal()
            try:
                room_name = f"session_{session_id}"
                await _trigger_story_generation_internal(session_id, db, room_name, sio)
            finally:
                db.close()

        except Exception as e:
            logger.error(f"trigger_story_generation 에러: {e}", exc_info=True)
            await sio.emit("error", {"message": "이야기 생성 트리거 실패"}, room=sid)


async def _trigger_story_generation_internal(session_id: int, db, room_name: str, sio):
    """이야기 생성을 내부적으로 트리거합니다 (Phase 3).

    모든 플레이어가 주사위를 굴린 후 이야기를 생성합니다:
    1. 모든 Phase 2 판정 수집 (주사위 굴림 완료)
    2. AI로 이야기 생성
    3. 이야기 토큰을 모든 참가자에게 스트리밍
    4. 결과를 데이터베이스에 저장
    5. 완료 이벤트 브로드캐스트

    인자:
        session_id: 게임 세션 ID
        db: 데이터베이스 세션
        room_name: 브로드캐스트용 소켓 룸 이름
        sio: Socket.io 서버 인스턴스
    """
    logger.info(f"Phase 3 - 이야기 생성 시작: 세션={session_id}")

    # story_generation_started 이벤트 브로드캐스트
    await sio.emit("story_generation_started", {"session_id": session_id}, room=room_name)

    try:
        # 모든 Phase 2 판정 조회 (주사위 굴림 완료, 아직 이야기 생성 안 됨)
        judgments = (
            db.query(ActionJudgment).filter(ActionJudgment.session_id == session_id, ActionJudgment.phase == 2).all()
        )

        if not judgments:
            raise ValueError("이야기 생성을 위한 판정이 없습니다")

        # AI 서비스 import
        from app.schemas import DiceResult
        from app.services.ai_gm_service_v2 import AIGMServiceV2

        # 판정을 DiceResult 객체로 변환
        dice_results = []
        for j in judgments:
            dice_result = DiceResult(
                character_id=j.character_id,
                action_text=j.action_text,
                dice_roll=j.dice_result,
                modifier=j.modifier,
                difficulty=j.difficulty,
            )
            dice_results.append(dice_result)

        # AI GM 서비스 초기화
        llm_model = os.getenv("LLM_MODEL", "gpt-4o")
        ai_service = AIGMServiceV2(db=db, llm_model=llm_model)

        # Phase 3: 이야기 생성
        result = await ai_service.generate_narrative(session_id=session_id, dice_results=dice_results)

        # 이야기 토큰 스트리밍
        narrative = result.full_narrative
        chunk_size = 50  # 청크당 문자 수

        for i in range(0, len(narrative), chunk_size):
            chunk = narrative[i : i + chunk_size]
            await sio.emit("narrative_token", {"session_id": session_id, "token": chunk}, room=room_name)
            # 스트리밍 시뮬레이션을 위한 작은 딜레이
            await asyncio.sleep(0.03)

        # 모든 판정을 Phase 3으로 업데이트
        for j in judgments:
            j.phase = 3
        db.commit()

        # 판정을 직렬화 가능한 형식으로 변환
        judgments_data = [
            {
                "character_id": j.character_id,
                "action_text": j.action_text,
                "dice_result": j.dice_result,
                "modifier": j.modifier,
                "final_value": j.final_value,
                "difficulty": j.difficulty,
                "difficulty_reasoning": j.difficulty_reasoning,
                "outcome": j.outcome,
            }
            for j in result.judgments
        ]

        # story_generation_complete 이벤트 브로드캐스트
        await sio.emit(
            "story_generation_complete",
            {
                "session_id": session_id,
                "narrative": result.full_narrative,
                "judgments": judgments_data,
            },
            room=room_name,
        )

        logger.info(f"Phase 3 완료: 세션={session_id}, 이야기 길이={len(narrative)}")

        # 막 전환 체크 (Phase 3 완료 후)
        await _check_act_transition_after_narrative(session_id, db, room_name, sio)

    except Exception as e:
        logger.error(f"Phase 3 에러: {e}", exc_info=True)

        # 호스트의 소켓 ID를 찾아 에러 전송
        session = db.query(GameSession).filter(GameSession.id == session_id).first()
        if session:
            # presence 추적에서 호스트의 소켓 ID 찾기
            host_sid = None
            for sid, info in session_presence.items():
                if info.get("session_id") == session_id and info.get("user_id") == session.host_user_id:
                    host_sid = sid
                    break

            if host_sid:
                await sio.emit(
                    "story_generation_error",
                    {"session_id": session_id, "error": str(e)},
                    to=host_sid,
                )
            else:
                # 폴백: 룸에 브로드캐스트
                await sio.emit(
                    "story_generation_error",
                    {"session_id": session_id, "error": str(e)},
                    room=room_name,
                )
