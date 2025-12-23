# TRPG World - 백엔드

FastAPI 기반의 TRPG 게임 백엔드 서버입니다.

## 목차

- [프로젝트 구조](#프로젝트-구조)
- [설치 및 실행](#설치-및-실행)
- [API 문서](#api-문서)
- [데이터베이스](#데이터베이스)
- [AI 시스템](#ai-시스템)
- [WebSocket 이벤트](#websocket-이벤트)
- [개발 가이드](#개발-가이드)

## 프로젝트 구조

```
backend/
├── app/
│   ├── models.py              # 데이터베이스 모델
│   ├── schemas.py             # Pydantic 스키마
│   ├── database.py            # 데이터베이스 설정
│   ├── main.py                # FastAPI 앱 진입점
│   ├── socket_server.py       # Socket.IO 서버
│   │
│   ├── routes/                # API 라우트
│   │   ├── auth.py
│   │   ├── sessions.py
│   │   ├── characters.py
│   │   └── ...
│   │
│   ├── services/              # 비즈니스 로직
│   │   ├── ai_gm_service_v2.py      # AI GM 서비스 (리팩토링 버전)
│   │   ├── ai_nodes/                # AI 처리 노드
│   │   │   ├── judgment_node.py     # Phase 1: 행동 판정
│   │   │   └── narrative_node.py    # Phase 3: 서술 생성
│   │   ├── dice_system.py           # 주사위 시스템
│   │   └── context_loader.py        # 게임 컨텍스트 로더
│   │
│   ├── prompts/               # AI 프롬프트 템플릿
│   │   ├── judgment_prompt.md       # 행동 판정 프롬프트
│   │   └── narrative_prompt.md      # 서술 생성 프롬프트
│   │
│   └── utils/                 # 유틸리티
│       └── prompt_loader.py         # 프롬프트 로더
│
├── alembic/                   # 데이터베이스 마이그레이션
├── scripts/                   # 유틸리티 스크립트
├── tests/                     # 테스트
├── pyproject.toml             # 프로젝트 설정
└── README.md                  # 이 파일
```

## 설치 및 실행

### 1. 의존성 설치

```bash
# uv를 사용한 설치 (권장)
uv sync

# 또는 pip 사용
pip install -e .
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어 다음 값들을 설정하세요:

```env
# 데이터베이스
DATABASE_URL=sqlite:///./trpg_world.db

# AI 설정
OPENAI_API_KEY=your-openai-api-key
LLM_MODEL=gpt-4o

# CORS
CORS_ORIGINS=http://localhost:5173

# JWT
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 3. 데이터베이스 초기화

```bash
# 마이그레이션 실행
uv run alembic upgrade head

# 테스트 데이터 생성 (선택사항)
uv run python scripts/seed_users.py
uv run python scripts/reset_characters.py
```

### 4. 서버 실행

```bash
# 개발 모드 (자동 재시작)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 프로덕션 모드
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

서버가 실행되면:
- API: http://localhost:8000
- API 문서: http://localhost:8000/docs
- WebSocket: ws://localhost:8000/socket.io

## API 문서

FastAPI는 자동으로 API 문서를 생성합니다:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 주요 엔드포인트

#### 인증

- `POST /auth/register` - 회원가입
- `POST /auth/login` - 로그인
- `GET /auth/me` - 현재 사용자 정보

#### 세션

- `GET /sessions` - 세션 목록
- `POST /sessions` - 세션 생성
- `GET /sessions/{id}` - 세션 상세
- `PUT /sessions/{id}` - 세션 수정
- `DELETE /sessions/{id}` - 세션 삭제

#### 캐릭터

- `GET /characters` - 캐릭터 목록
- `POST /characters` - 캐릭터 생성
- `GET /characters/{id}` - 캐릭터 상세
- `PUT /characters/{id}` - 캐릭터 수정
- `DELETE /characters/{id}` - 캐릭터 삭제

## 데이터베이스

### 모델

- **User**: 사용자
- **GameSession**: 게임 세션
- **Character**: 캐릭터
- **SessionParticipant**: 세션 참가자
- **StoryLog**: 스토리 로그
- **ActionJudgment**: 행동 판정 기록

### 마이그레이션

```bash
# 새 마이그레이션 생성
uv run alembic revision --autogenerate -m "설명"

# 마이그레이션 적용
uv run alembic upgrade head

# 마이그레이션 롤백
uv run alembic downgrade -1
```

## AI 시스템

### 아키텍처

새로 리팩토링된 AI 시스템은 명확한 구조를 가지고 있습니다:

```
AIGMServiceV2
├── Phase 1: analyze_actions()
│   └── judgment_node.py
│       ├── PromptLoader("judgment_prompt.md")
│       ├── ChatLiteLLM (AI 호출)
│       └── 보정치 계산 + DC 결정
│
└── Phase 3: generate_narrative()
    └── narrative_node.py
        ├── PromptLoader("narrative_prompt.md")
        ├── ChatLiteLLM (AI 호출)
        └── 서술 생성 + DB 저장
```

### 사용 예시

```python
from app.services.ai_gm_service_v2 import AIGMServiceV2
from app.schemas import PlayerAction, ActionType

# 서비스 초기화
service = AIGMServiceV2(db=db, llm_model="gpt-4o")

# Phase 1: 행동 분석
analyses = await service.analyze_actions(
    session_id=1,
    player_actions=[
        PlayerAction(
            character_id=1,
            action_text="문을 조심스럽게 연다",
            action_type=ActionType.DEXTERITY
        )
    ]
)

# Phase 2: 플레이어가 주사위 굴림 (프론트엔드)

# Phase 3: 서술 생성
result = await service.generate_narrative(
    session_id=1,
    dice_results=[...]
)
```

### 프롬프트 커스터마이징

프롬프트는 `app/prompts/` 디렉토리의 마크다운 파일로 관리됩니다:

- `judgment_prompt.md`: 행동 판정 프롬프트
- `narrative_prompt.md`: 서술 생성 프롬프트

프롬프트를 수정하려면 해당 파일을 직접 편집하면 됩니다.

## WebSocket 이벤트

### 클라이언트 → 서버

#### 세션 관리

- `join_session` - 세션 참가
  ```json
  {
    "session_id": 1,
    "user_id": 1,
    "character_id": 1
  }
  ```

- `leave_session` - 세션 나가기
  ```json
  {
    "session_id": 1,
    "user_id": 1
  }
  ```

#### 게임 플레이

- `submit_player_action` - 행동 제출 (Phase 1)
  ```json
  {
    "session_id": 1,
    "character_id": 1,
    "action_text": "문을 연다",
    "action_type": "dexterity"
  }
  ```

- `roll_dice` - 주사위 굴림 (Phase 2)
  ```json
  {
    "session_id": 1,
    "character_id": 1,
    "judgment_id": 1,
    "dice_result": 15
  }
  ```

### 서버 → 클라이언트

#### Phase 1 이벤트

- `judgment_ready` - 판정 준비 완료
  ```json
  {
    "session_id": 1,
    "character_id": 1,
    "judgment_id": 1,
    "modifier": 3,
    "difficulty": 15,
    "difficulty_reasoning": "..."
  }
  ```

#### Phase 2 이벤트

- `dice_rolled` - 주사위 굴림 완료
  ```json
  {
    "session_id": 1,
    "character_id": 1,
    "dice_result": 15,
    "final_value": 18,
    "outcome": "success"
  }
  ```

#### Phase 3 이벤트

- `story_generation_started` - 서술 생성 시작
- `story_generation_complete` - 서술 생성 완료
  ```json
  {
    "session_id": 1,
    "narrative": "당신은 문을 조심스럽게 연다...",
    "judgments": [...]
  }
  ```

## 개발 가이드

### 코드 스타일

Ruff를 사용하여 코드 스타일을 관리합니다:

```bash
# 린트 체크
uv run ruff check .

# 자동 수정
uv run ruff check --fix .

# 포맷팅
uv run ruff format .
```

### 테스트

```bash
# 전체 테스트 실행
uv run pytest

# 특정 테스트 파일 실행
uv run pytest tests/test_ai_gm_service.py

# 커버리지 포함
uv run pytest --cov=app --cov-report=html
```

### 유틸리티 스크립트

```bash
# 데이터베이스 초기화
uv run python scripts/reset_sessions.py

# 캐릭터 재생성
uv run python scripts/reset_characters.py

# AI 문제 진단
uv run python scripts/diagnose_ai_issue.py
```

### 디버깅

로그 레벨을 조정하려면 `.env` 파일에 추가:

```env
LOG_LEVEL=DEBUG
```

## 트러블슈팅

### "No module named 'app'" 오류

backend 디렉토리에서 실행하세요:

```bash
cd backend
uv run python scripts/script_name.py
```

### "Database is locked" 오류

백엔드 서버를 중지하고 다시 시도하세요:

```bash
# Ctrl+C로 서버 중지
uv run python scripts/script_name.py
```

### AI 응답이 없음

1. OPENAI_API_KEY가 설정되어 있는지 확인
2. API 키가 유효한지 확인
3. 로그에서 에러 메시지 확인

```bash
# 진단 스크립트 실행
uv run python scripts/diagnose_ai_issue.py
```

## 성능 최적화

### 데이터베이스

- 인덱스 추가
- 쿼리 최적화
- 연결 풀 설정

### AI 호출

- 프롬프트 길이 최적화
- 캐싱 활용
- 배치 처리

## 보안

- JWT 토큰 기반 인증
- CORS 설정
- SQL Injection 방지 (SQLAlchemy ORM)
- XSS 방지 (Pydantic 검증)

## 라이선스

MIT License
