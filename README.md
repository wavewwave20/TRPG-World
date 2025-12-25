# TRPG World

웹 기반 TRPG(테이블탑 롤플레잉 게임) 플랫폼입니다. AI 게임 마스터가 플레이어의 행동을 판정하고 스토리를 생성합니다.

## 프로젝트 구조

```
trpg-world/
├── backend/          # FastAPI 백엔드 서버
├── frontend/         # React 프론트엔드
└── README.md         # 이 파일
```

## 주요 기능

### 🎲 3단계 AI 게임 마스터 시스템

1. **Phase 1: 행동 분석**
   - 플레이어가 행동을 제출
   - AI가 난이도(DC)를 결정
   - 캐릭터 스탯에서 보정치 계산

2. **Phase 2: 주사위 굴림**
   - 플레이어가 직접 주사위 굴림 (d20)
   - 실시간으로 다른 플레이어에게 공유

3. **Phase 3: 스토리 생성**
   - AI가 모든 판정 결과를 통합
   - 몰입감 있는 서술 생성
   - 실시간으로 모든 플레이어에게 전달

### 🌐 실시간 멀티플레이어

- WebSocket 기반 실시간 통신
- 세션 참가자 관리
- 호스트 권한 시스템
- 자동 세션 정리

### 🎭 캐릭터 시스템

- D&D 5e 기반 능력치 (STR, DEX, CON, INT, WIS, CHA)
- 캐릭터 생성 및 관리
- 레벨 및 클래스 시스템

## 빠른 시작

### 필수 요구사항

- Python 3.11+
- Node.js 18+
- uv (Python 패키지 관리자)
- npm 또는 yarn

### 설치 및 실행

#### 1. 백엔드 실행

```bash
cd backend

# 의존성 설치
uv sync

# 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 OPENAI_API_KEY 등을 설정

# 데이터베이스 마이그레이션
uv run alembic upgrade head

# 개발 서버 실행
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 2. 프론트엔드 실행

```bash
cd frontend

# 의존성 설치
npm install

# 개발 서버 실행
npm run dev
```

#### 3. 브라우저에서 접속

- 프론트엔드: http://localhost:5173
- 백엔드 API: http://localhost:8000
- API 문서: http://localhost:8000/docs

## 기술 스택

### 백엔드

- **FastAPI**: 고성능 Python 웹 프레임워크
- **SQLAlchemy**: ORM
- **Socket.IO**: 실시간 통신
- **LangChain + LiteLLM**: AI 통합
- **Alembic**: 데이터베이스 마이그레이션

### 프론트엔드

- **React 18**: UI 라이브러리
- **TypeScript**: 타입 안전성
- **Vite**: 빌드 도구
- **Tailwind CSS**: 스타일링
- **Zustand**: 상태 관리
- **Socket.IO Client**: 실시간 통신

## 개발 가이드

### 코드 스타일

- **백엔드**: Ruff (린팅 + 포맷팅)
- **프론트엔드**: ESLint + Prettier

```bash
# 백엔드 린트
cd backend
uv run ruff check --fix .
uv run ruff format .

# 프론트엔드 린트
cd frontend
npm run lint
```

### 테스트

```bash
# 백엔드 테스트
cd backend
uv run pytest

# 프론트엔드 테스트
cd frontend
npm run test
```

## 환경 변수

### 백엔드 (.env)

```env
# 데이터베이스
DATABASE_URL=sqlite:///./trpg_world.db

# AI 설정
OPENAI_API_KEY=your-api-key-here
LLM_MODEL=gpt-4o

# CORS
CORS_ORIGINS=http://localhost:5173

# JWT
SECRET_KEY=your-secret-key-here
```

### 프론트엔드 (.env)

```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=http://localhost:8000
```

## 프로젝트 문서

- [백엔드 README](./backend/README.md) - 백엔드 상세 문서
- [프론트엔드 README](./frontend/README.md) - 프론트엔드 상세 문서
- [리팩토링 가이드](./backend/REFACTORING_GUIDE.md) - AI 서비스 리팩토링 문서


## 실행
cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
cd frontend && npm run dev
