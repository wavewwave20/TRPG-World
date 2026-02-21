"""TRPG World의 SQLAlchemy ORM 모델."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text

from app.database import Base


class User(Base):
    """
    등록된 사용자를 나타내는 User 모델.

    속성:
        id: 고유 사용자 식별자
        username: 로그인용 고유 사용자명
        password: 해시된 비밀번호
        created_at: 사용자 생성 시각
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class GameSession(Base):
    """
    TRPG 게임 방을 나타내는 GameSession 모델.

    속성:
        id: 고유 세션 식별자
        host_user_id: 세션을 생성/호스팅하는 사용자 ID
        title: 세션 제목/이름
        world_prompt: 게임 세계를 정의하는 AI 시스템 프롬프트
        ai_summary: 장기 기억용 AI 생성 요약 (선택사항)
        created_at: 세션 생성 시각
        is_active: 활성 상태 플래그 (호스트 연결 해제 시 비활성화되지만 삭제되지 않음)
    """

    __tablename__ = "game_sessions"

    id = Column(Integer, primary_key=True, index=True)
    host_user_id = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    world_prompt = Column(Text, nullable=False)
    ai_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    event_probability = Column(Float, default=0.00, nullable=False, server_default="0.00")
    host_instruction = Column(Text, nullable=False, default="", server_default="")
    host_story_controls = Column(JSON, nullable=False, default=dict, server_default="{}")


class Character(Base):
    """
    플레이어의 캐릭터를 나타내는 Character 모델.

    속성:
        id: 고유 캐릭터 식별자
        user_id: 이 캐릭터를 소유한 사용자 ID
        name: 캐릭터 이름
        data: 캐릭터 스탯을 포함하는 JSON 객체 (HP, MP, inventory 등)
        created_at: 캐릭터 생성 시각
    """

    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CharacterShareCode(Base):
    """
    캐릭터 공유 코드를 나타내는 모델.

    속성:
        id: 고유 공유코드 식별자
        code: 공유에 사용하는 9자리 숫자 코드
        source_character_id: 공유 원본 캐릭터 ID
        source_user_id: 공유를 생성한 사용자 ID
        redeemed_by_user_id: 코드를 사용한 사용자 ID (미사용 시 NULL)
        created_at: 공유코드 생성 시각
        redeemed_at: 공유코드 사용 시각 (미사용 시 NULL)
    """

    __tablename__ = "character_share_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(9), unique=True, nullable=False, index=True)
    source_character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    source_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    redeemed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    redeemed_at = Column(DateTime, nullable=True)


class SessionParticipant(Base):
    """
    어떤 캐릭터가 어떤 세션에 있는지 추적하는 SessionParticipant 모델.

    속성:
        id: 고유 참가자 식별자
        session_id: 게임 세션 ID
        user_id: 사용자 ID
        character_id: 사용 중인 캐릭터 ID
        joined_at: 사용자가 참여한 시각
    """

    __tablename__ = "session_participants"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class StoryLog(Base):
    """
    게임 세션의 서술 이벤트를 나타내는 StoryLog 모델.

    속성:
        id: 고유 로그 항목 식별자
        session_id: 이 로그가 속한 게임 세션 ID
        role: 메시지 발신자 역할 ("USER" 또는 "AI")
        content: 실제 스토리/메시지 내용
        created_at: 로그 생성 시각
    """

    __tablename__ = "story_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False)
    act_id = Column(Integer, ForeignKey("story_acts.id"), nullable=True)
    role = Column(String(10), nullable=False)  # "USER" 또는 "AI"
    content = Column(Text, nullable=False)
    judgments_data = Column(JSON, nullable=True)  # 판정 결과 스냅샷 (USER 메시지 전용)
    event_triggered = Column(Boolean, default=False, nullable=False)  # 돌발이벤트 발생 여부
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class StoryFlowMetric(Base):
    """스토리 흐름 품질 계측 로그.

    LLM 추가 호출 없이 턴 단위 핵심 지표를 저장합니다.
    """

    __tablename__ = "story_flow_metrics"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False, index=True)
    story_log_id = Column(Integer, ForeignKey("story_logs.id"), nullable=True, index=True)
    act_id = Column(Integer, ForeignKey("story_acts.id"), nullable=True, index=True)
    source = Column(String(32), nullable=False)  # phase3|stream|regenerate

    tension = Column(Integer, nullable=False, default=45)
    consecutive_crisis = Column(Integer, nullable=False, default=0)

    judgments_count = Column(Integer, nullable=False, default=0)
    failure_count = Column(Integer, nullable=False, default=0)
    critical_failure_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    critical_success_count = Column(Integer, nullable=False, default=0)
    auto_success_count = Column(Integer, nullable=False, default=0)

    host_instruction_enabled = Column(Boolean, nullable=False, default=False)
    host_instruction_length = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class StoryAct(Base):
    """
    스토리 막(Act)을 나타내는 모델.
    AI GM이 스토리 진행 상황에 따라 자동으로 막 전환을 결정합니다.

    속성:
        id: 고유 Act 식별자
        session_id: 이 Act가 속한 게임 세션 ID
        act_number: 막 번호 (1부터 시작)
        title: AI가 생성한 막 제목 (e.g., "어둠의 전조")
        subtitle: AI가 생성한 막 부제 (e.g., "폐광산의 비밀")
        started_at: 막 시작 시각
        ended_at: 막 종료 시각 (NULL이면 현재 진행 중)
        start_story_log_id: 이 막이 시작되는 StoryLog의 ID
        end_story_log_id: 이 막이 종료되는 StoryLog의 ID
    """

    __tablename__ = "story_acts"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False)
    act_number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    subtitle = Column(String(200), nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    start_story_log_id = Column(Integer, ForeignKey("story_logs.id"), nullable=True)
    end_story_log_id = Column(Integer, ForeignKey("story_logs.id"), nullable=True)


class CharacterGrowthLog(Base):
    """
    캐릭터 성장 기록을 나타내는 모델.
    막 종료 시 AI가 제안한 성장 보상을 기록합니다.

    속성:
        id: 고유 성장 로그 식별자
        session_id: 세션 ID
        act_id: 어떤 Act의 완료로 인한 성장인지
        character_id: 성장 대상 캐릭터
        growth_type: 성장 유형 (ability_increase, new_skill, weakness_mitigated)
        growth_detail: 성장 상세 내용 JSON
        narrative_reason: AI가 생성한 성장 이유 (서사적 설명)
        applied_at: 적용 시각
    """

    __tablename__ = "character_growth_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False)
    act_id = Column(Integer, ForeignKey("story_acts.id"), nullable=False)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    growth_type = Column(String(50), nullable=False)
    growth_detail = Column(JSON, nullable=False)
    narrative_reason = Column(Text, nullable=False)
    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ActionJudgment(Base):
    """
    AI가 판정한 플레이어 행동을 나타내는 ActionJudgment 모델.

    3단계 판정 프로세스의 결과를 저장:
    - Phase 1: 행동 분석 (보정치 + DC)
    - Phase 2: 주사위 굴림 및 판정
    - Phase 3: story_log_id를 통해 서술과 연결

    속성:
        id: 고유 판정 식별자
        session_id: 게임 세션 ID
        character_id: 행동을 수행하는 캐릭터 ID
        story_log_id: 연관된 서술 스토리 로그 ID (Phase 3)
        action_text: 플레이어의 행동 설명
        action_type: 행동 유형 (strength, dexterity 등)
        dice_result: d20 주사위 결과 (1-20)
        modifier: 캐릭터 스탯에서 계산된 보정치
        final_value: dice_result + modifier
        difficulty: LLM이 결정한 DC (난이도)
        difficulty_reasoning: 난이도에 대한 LLM의 설명
        outcome: 판정 결과 (critical_failure, failure, success, critical_success)
        phase: 현재 판정 단계 (1=분석, 2=주사위_굴림, 3=서술됨)
        created_at: 판정 생성 시각
    """

    __tablename__ = "action_judgments"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False)
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    story_log_id = Column(Integer, ForeignKey("story_logs.id"), nullable=True)

    action_text = Column(Text, nullable=False)
    action_mode = Column(String(20), nullable=False, default="normal", server_default="normal")
    skill_name = Column(String(120), nullable=True)
    skill_description = Column(Text, nullable=True)
    action_type = Column(String(50), nullable=True)  # strength, dexterity 등
    dice_result = Column(Integer, nullable=True)  # Phase 2까지 null
    modifier = Column(Integer, nullable=False)
    final_value = Column(Integer, nullable=True)  # Phase 2까지 null
    difficulty = Column(Integer, nullable=False)
    difficulty_reasoning = Column(Text, nullable=True)
    outcome = Column(String(50), nullable=True)  # Phase 2까지 null
    phase = Column(Integer, default=1, nullable=False)  # 1=분석, 2=주사위_굴림, 3=서술됨

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DiceRollState(Base):
    """
    세션 라운드별 플레이어 주사위 굴림을 추적하는 DiceRollState 모델.

    현재 라운드에서 어떤 플레이어가 주사위를 굴렸는지 추적하여,
    모든 플레이어가 굴림을 완료했을 때 Phase 3 (스토리 생성)을
    트리거할 수 있도록 합니다.

    속성:
        id: 고유 상태 식별자
        session_id: 게임 세션 ID
        round_id: 현재 라운드 식별자 (턴마다 증가)
        character_id: 주사위를 굴린 캐릭터 ID
        judgment_id: 연관된 ActionJudgment ID
        dice_result: d20 굴림 결과
        has_rolled: 이 캐릭터가 이번 라운드에 굴렸는지 여부
        created_at: 굴림이 기록된 시각
    """

    __tablename__ = "dice_roll_states"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False)
    round_id = Column(Integer, nullable=False)  # 턴마다 증가
    character_id = Column(Integer, ForeignKey("characters.id"), nullable=False)
    judgment_id = Column(Integer, ForeignKey("action_judgments.id"), nullable=True)
    dice_result = Column(Integer, nullable=True)
    has_rolled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class LLMApiKey(Base):
    """
    프로바이더별 API 키를 저장하는 모델.

    속성:
        id: 고유 식별자
        provider: 프로바이더 식별자 (openai, gemini, anthropic)
        provider_display: 표시명 (OpenAI, Google Gemini, Anthropic)
        api_key_encrypted: Fernet으로 암호화된 API 키
        created_at: 생성 시각
        updated_at: 수정 시각
    """

    __tablename__ = "llm_api_keys"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), unique=True, nullable=False)
    provider_display = Column(String(100), nullable=False)
    api_key_encrypted = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class LLMModel(Base):
    """
    등록된 LLM 모델을 나타내는 모델.

    속성:
        id: 고유 식별자
        provider: 프로바이더 식별자 (llm_api_keys.provider 참조)
        model_id: LiteLLM 형식 모델 식별자 (예: "gpt-4o", "gemini/gemini-2.5-flash")
        display_name: 사용자 표시명
        is_active: 현재 활성 모델 여부 (한 번에 하나만 활성)
        created_at: 생성 시각
    """

    __tablename__ = "llm_models"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False)
    model_id = Column(String(200), nullable=False, unique=True)
    display_name = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
