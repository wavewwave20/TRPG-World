<p align="center">
  <img src="docs/assets/readme-hero-fantasy.png" alt="TRPG World Hero" width="100%" />
</p>

<h1 align="center">TRPG World 🎲</h1>
<p align="center"><b>멀티플레이 텍스트 TRPG를 위한 실시간 AI 게임마스터 플랫폼</b></p>

<p align="center">
  <img src="https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Frontend-React%20%2B%20TypeScript-61DAFB?style=flat-square" alt="React TS" />
  <img src="https://img.shields.io/badge/Realtime-Socket.IO-010101?style=flat-square" alt="Socket.IO" />
  <img src="https://img.shields.io/badge/State-Zustand-764ABC?style=flat-square" alt="Zustand" />
  <img src="https://img.shields.io/badge/Deploy-Docker-2496ED?style=flat-square" alt="Docker" />
</p>

---

## 왜 TRPG World인가?

기존 TRPG 도구는 채팅 중심이라 라이브 진행에서 중재가 느려지기 쉽습니다.
**TRPG World**는 실시간 세션 운영에 맞춰 설계했습니다.

- 플레이어는 행동을 병렬로 제출하고,
- 호스트는 대기열을 정리해 장면을 확정하며,
- AI GM은 결과를 스트리밍으로 서술하고,
- 스토리 로그는 영구 저장됩니다.

즉, 단순 챗봇이 아니라 **실제 세션 테이블 감각**을 목표로 합니다.

---

## 핵심 기능

- **호스트 중심 행동 대기열 중재**
  - 여러 플레이어 행동 동시 접수
  - 호스트가 순서 조정/편집 후 한 턴으로 확정

- **3단계 AI GM 파이프라인**
  - **판정(Judgment):** 난이도/보정치 계산
  - **주사위(Dice):** d20 기반 결과 처리
  - **서술(Narrative):** 결과 반영 스토리 생성

- **Socket.IO 기반 실시간 멀티플레이 동기화**
  - 세션 이벤트, UI 전환, 로그를 전원에게 브로드캐스트

- **영구 스토리 로그 + 휘발성 사이드 채팅 분리**
  - 메인 서사는 DB 저장
  - 잡담/시스템 채팅은 가볍게 처리

- **캐릭터 시트 + 유연한 JSON 스탯 구조**
  - HP/MP/능력치/인벤토리 확장 가능

- **AI 응답 스트리밍 + TTS 대응 구조**
  - 타이핑 효과 기반 실시간 몰입감
  - 음성 출력 연동 가능한 아키텍처

- **Docker 중심 개발/배포 워크플로우**
  - compose로 빠른 실행
  - 서버 시작 시 마이그레이션 자동 적용

---

## 기능 중심 스크린샷 (데스크톱 + 모바일)

### 1) 세션 대시보드 (생성 / 참가 / 관리)
**데스크톱**
<p>
  <img src="docs/assets/readme-session-dashboard-desktop.png" alt="세션 대시보드 데스크톱" width="100%" />
</p>

**모바일**
<p align="center">
  <img src="docs/assets/readme-session-dashboard-mobile.png" alt="세션 대시보드 모바일" width="360" />
</p>

### 2) 캐릭터 관리 (시트/스킬/약점)
**데스크톱**
<p>
  <img src="docs/assets/readme-character-management-desktop.png" alt="캐릭터 관리 데스크톱" width="100%" />
</p>

**모바일**
<p align="center">
  <img src="docs/assets/readme-character-management-mobile.png" alt="캐릭터 관리 모바일" width="360" />
</p>

### 3) 스토리 플레이 UI (실시간 서사 + 행동 입력)
**데스크톱**
<p>
  <img src="docs/assets/readme-story-play-desktop.png" alt="스토리 플레이 데스크톱" width="100%" />
</p>

**모바일**
<p align="center">
  <img src="docs/assets/readme-story-play-mobile.png" alt="스토리 플레이 모바일" width="360" />
</p>

---

## 기술 스택

- **Backend:** FastAPI, SQLAlchemy, Alembic, LangGraph, LiteLLM, Socket.IO
- **Frontend:** React 19, TypeScript, Zustand, Tailwind CSS, Socket.IO Client
- **DB:** SQLite(개발), PostgreSQL 대응(운영)
- **Infra:** Docker Compose, Nginx 연동 배포

---

## 빠른 시작

### 1) Docker 실행 (권장)

```bash
docker compose up -d --build
```

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- Health: `http://localhost:8000/health`

### 2) 종료

```bash
docker compose down
```

---

## 주요 API

- `POST /api/auth/register` – 회원가입
- `POST /api/auth/login` – 로그인
- `GET /api/sessions/` – 세션 목록
- `POST /api/sessions/` – 세션 생성
- `POST /api/characters` – 캐릭터 생성
- `GET /api/characters/{id}` – 캐릭터 조회
- `GET /health` – 서버 상태

---

## 프로젝트 구조

```text
trpg-world/
├── backend/         # FastAPI 서버 + AI 오케스트레이션 + Socket 핸들러
├── frontend/        # React 앱 + Zustand 스토어 + 실시간 UI
├── docs/            # 명세/리포트/에셋
└── docker-compose.yml
```

---

## 언어 버전

- English: `README.md`
- 한국어: `README.ko.md`

---

## 상태

현재 활발히 개발 중입니다.
이슈 제보, 플레이테스트 피드백, 기여 모두 환영합니다.
