# Playwright MCP 기반 TRPG World 실제 플레이 테스트 계획

> 재사용 가능한 실행 절차/스크립트는 `docs/e2e-methodology.md`를 참고하세요.

## Context

TRPG World 앱에는 현재 백엔드 단위 테스트만 존재하고, E2E/플레이 테스트가 없습니다. Playwright MCP 도구를 활용하여 실제 브라우저에서 전체 게임 플로우를 수동/반자동으로 테스트하는 계획입니다. 목표는 로그인부터 멀티플레이어 게임 세션까지 전체 사용자 여정을 검증하는 것입니다.

---

## 사전 준비

### 서버 시작
```bash
# Terminal 1 - Backend
cd D:\Dev\trpg-world\backend
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# Terminal 2 - Frontend
cd D:\Dev\trpg-world\frontend
npm run dev   # http://localhost:5173
```

### 필요 환경변수
- `OPENAI_API_KEY` 또는 `GEMINI_API_KEY` (AI GM용)
- `REGISTRATION_CODE` (회원가입 테스트용)

### 테스트 계정
- `user1` / `1234`, `user2` / `1234` (기존 계정)

---

## 테스트 시나리오

### Phase 1: 인증 테스트

| # | 시나리오 | 핵심 단계 | 검증 포인트 |
|---|---------|----------|------------|
| 1.1 | 로그인 성공 | navigate → snapshot → type username/password → click 로그인 → wait_for "캐릭터 관리" | 캐릭터 관리 페이지 로드, "환영합니다, user1님!" 표시 |
| 1.2 | 로그인 실패 | 잘못된 credentials 입력 → click 로그인 | 에러 메시지 표시, 로그인 폼 유지 |
| 1.3 | 회원가입 모드 전환 | "계정이 없으신가요?" 클릭 | 인증 코드 필드 추가, 버튼 텍스트 "회원가입"으로 변경 |
| 1.4 | 로그아웃 | 로그인 → 로그아웃 클릭 | 로그인 페이지로 복귀 |

#### 상세 절차 - 1.1 로그인 성공

```
1. browser_navigate → http://localhost:5173
2. browser_evaluate → () => localStorage.clear()  // 클린 상태 보장
3. browser_navigate → http://localhost:5173
4. browser_snapshot → 로그인 폼 확인 (TRPG World 제목, 입력 필드 2개, 로그인 버튼)
5. browser_type → username 필드에 "user1"
6. browser_type → password 필드에 "1234"
7. browser_click → "로그인" 버튼
8. browser_wait_for → text "캐릭터 관리" (timeout 5s)
9. browser_snapshot → "환영합니다, user1님!" 확인
```

#### 상세 절차 - 1.2 로그인 실패

```
1. 클린 상태에서 시작
2. browser_type → username "wronguser", password "wrongpass"
3. browser_click → "로그인"
4. browser_wait_for → 에러 메시지 표시
5. browser_snapshot → 빨간 에러 박스 + 로그인 폼 유지 확인
```

---

### Phase 2: 캐릭터 관리 테스트

| # | 시나리오 | 핵심 단계 | 검증 포인트 |
|---|---------|----------|------------|
| 2.1 | 캐릭터 생성 | "+ 새 캐릭터 생성" → 이름/나이/종족/컨셉 입력 → 능력치(STR~CHA) 설정 → 스킬 추가 → 약점 추가 → "생성" 클릭 | 캐릭터 카드에 이름, 스탯, 스킬, 약점 표시 |
| 2.2 | 캐릭터 수정 | "수정" 클릭 → 이름 변경 → "수정" 제출 | 변경된 이름 반영 |
| 2.3 | 캐릭터 삭제 | "삭제" 클릭 → confirm 다이얼로그 수락 | 목록에서 제거됨 |
| 2.4 | 캐릭터 선택 → 로비 진입 | "선택" 클릭 | 로비 페이지 로드, "어서 오세요, [캐릭터명]님" |

#### 상세 절차 - 2.1 캐릭터 생성

```
1. 로그인 완료 상태
2. browser_click → "+ 새 캐릭터 생성" 버튼
3. browser_snapshot → 생성 폼 확인
4. browser_type → 이름: "용사 아르테미스"
5. browser_type → 나이: "28"
6. browser_type → 종족: "엘프"
7. browser_type → 컨셉: "숲에서 자란 궁수"
8. 능력치 설정 (각 필드에 값 입력):
   - STR: 14, DEX: 18, CON: 12, INT: 10, WIS: 16, CHA: 10
9. 스킬 추가:
   - 타입: "Active (액티브)" 선택
   - 능력치: DEX 선택
   - 이름: "정밀 사격"
   - 설명: "활을 사용한 정밀한 사격"
   - "+ 스킬 추가" 클릭
10. 약점 추가:
    - "물에 대한 공포" 입력 → "추가" 클릭
11. browser_click → "생성" 버튼
12. browser_wait_for → "용사 아르테미스" (캐릭터 목록에 나타남)
13. browser_snapshot → 캐릭터 카드 정보 확인
```

#### 상세 절차 - 2.4 캐릭터 선택 → 로비

```
1. browser_click → "선택" 버튼
2. browser_wait_for → "어서 오세요" (로비 페이지)
3. browser_snapshot → 3개 카드 확인: "새 세션", "세션 참가", "내 세션"
   - 헤더에 "시스템 온라인" (소켓 연결 상태) 확인
```

---

### Phase 3: 세션 관리 테스트

| # | 시나리오 | 핵심 단계 | 검증 포인트 |
|---|---------|----------|------------|
| 3.1 | 세션 생성 | 제목 + 월드 프롬프트 입력 → "세션 생성" | 게임 레이아웃(3분할) 로드, "스토리북" 표시 |
| 3.2 | 세션 참가 | 세션 목록에서 "참가" 클릭 | 게임 레이아웃 로드, 참여 알림 |
| 3.3 | 세션 종료/재시작/삭제 | "내 세션"에서 관리 | 상태 변경 반영 |
| 3.4 | 빈 제목/프롬프트 오류 | 빈 필드로 생성 시도 | 에러 메시지 표시 |
| 3.5 | 호스트 세션 관리 즉시 반영(회귀) | "내 세션"에서 수정/종료/재시작/스토리 편집 실행 | 전체 목록 재조회 없이 카드/로그 수 즉시 반영(복제는 예외) |

#### 상세 절차 - 3.1 세션 생성

```
1. 로비 상태에서 "새 세션" 카드 찾기
2. browser_type → 세션 제목 (id="session-title"): "테스트 모험 세계"
3. browser_type → 월드 프롬프트 (id="world-prompt"):
   "이것은 중세 판타지 세계입니다. 마법과 검이 공존하는 세계에서 모험가들이 던전을 탐험합니다."
4. browser_click → "세션 생성"
5. browser_wait_for → "스토리북" (게임 레이아웃)
6. browser_snapshot → 3분할 레이아웃 확인:
   - 좌: 캐릭터 상태
   - 중: 스토리북 ("스토리북이 비어있습니다")
   - 우: 채팅
   - 호스트 전용: "게임 시작", "행동 결정" 버튼
```

#### 상세 절차 - 3.5 호스트 세션 관리 즉시 반영(회귀)

> 목적: `HostSessionsManager` 액션 이후 불필요한 `GET /api/sessions/host/{user_id}` 호출이 줄어들었는지 확인

```
사전 조건:
- 종료된 세션 1개 이상 존재
- 해당 세션에 스토리 로그 1개 이상 존재(스토리 관리 테스트용)

1) browser_snapshot → 로비의 "내 세션" 카드 확인
2) 테스트 대상 세션 1개 선택

3) 세션/프롬프트 수정
   - "세션/프롬프트 수정" 클릭 → 제목 또는 프롬프트 변경 → "저장"
   - 기대 UI: 해당 카드 텍스트가 즉시 변경
   - 기대 네트워크: `PUT /api/sessions/{id}` 이후 host list GET 없음

4) 세션 종료 / 재시작
   - 활성 세션이면 "종료", 종료된 세션이면 "재시작"
   - 기대 UI: 상태 배지(활성/종료됨) 즉시 변경
   - 기대 네트워크:
     - 종료: `POST /api/sessions/{id}/end` 이후 host list GET 없음
     - 재시작: `POST /restart` + `POST /join` 이후 host list GET 없음

5) 스토리 관리 → 메시지 추가/수정/삭제
   - "스토리 관리" 열기
   - 추가: role/content 입력 후 "추가"
   - 수정: 기존 메시지 "수정" → 내용 변경 → "저장"
   - 삭제: 기존 메시지 "삭제" → confirm 수락
   - 기대 UI:
     - 메시지 리스트 즉시 갱신
     - 세션 카드의 "스토리 로그 N개" 카운트가 즉시 갱신
   - 기대 네트워크:
     - 추가: `POST /api/story_logs/{id}/entries` + `GET /api/story_logs/{id}`
     - 수정: `PUT /api/story_logs/entry/{log_id}` + `GET /api/story_logs/{id}`
     - 삭제: `DELETE /api/story_logs/entry/{log_id}` + `GET /api/story_logs/{id}`
     - 공통: host list GET 없음

6) 복제(예외 경로)
   - "복제" 클릭
   - 기대 UI: notice 표시 + 새 세션 카드 목록 반영
   - 기대 네트워크: `POST /duplicate` 후 `GET /api/sessions/host/{user_id}` 1회 발생 가능(의도된 동작)
```

---

### Phase 4: 싱글 플레이어 전체 게임 루프 ⭐ 핵심 테스트

> ⚠️ AI 응답 대기 필요 - 넉넉한 타임아웃 설정 (30~60초)

#### 4.1 게임 시작 (오프닝 내러티브)

```
1. 세션 생성 후 게임 레이아웃 진입
2. browser_snapshot → "게임 시작" 버튼 확인
3. browser_click → "게임 시작"
4. browser_wait_for → text "던전 마스터" (timeout 30s)
   - AI가 월드 프롬프트 기반으로 오프닝 내러티브 생성
   - 토큰 단위로 스트리밍됨
5. browser_snapshot → 스토리북에 "던전 마스터" 라벨 + AI 내러티브 표시 확인
```

#### 4.2 행동 제출

```
1. 내러티브 완료 후 행동 입력 활성화 확인
2. browser_type → 행동 입력 (placeholder "행동을 설명하세요..."):
   "주변을 살펴보며 위험한 것이 없는지 확인한다"
3. browser_click → "행동" 버튼
4. browser_snapshot → 시스템 알림에 행동 제출 확인, 입력 필드 초기화
```

#### 4.3 호스트 행동 결정 (모더레이션)

```
1. browser_click → "행동 결정" 버튼 (중앙 패널 헤더)
2. browser_snapshot → 모더레이션 모달 확인:
   - "행동 결정 (1개 제출 됨)" 제목
   - 행동 카드: 캐릭터 이름 + 행동 텍스트
   - "수정", "삭제" 버튼 (호스트용)
   - "닫기", "제출하기" 버튼
3. browser_click → "제출하기" (행동 커밋)
4. 모달 닫힘
```

#### 4.4 판정 Phase (AI 분석 + 주사위 굴리기)

```
1. browser_wait_for → 판정 모달 자동 열림 (timeout 30s)
   - AI가 행동 분석 → 보정값(modifier) + 난이도(DC) 결정
   - 서버에서 d20 미리 굴림
2. browser_snapshot → 판정 모달 확인:
   - 캐릭터 이름 + 아바타
   - "판정 진행 중" 부제목
   - 행동 텍스트
   - 능력치 보정값 카드 (예: +2)
   - 난이도(DC) 카드 (예: DC 12)
   - 난이도 판단 이유
   - "주사위 굴리기" 버튼 (또는 자동 성공 시 "확인")
3. browser_click → "주사위 굴리기" (또는 "확인")
4. browser_wait_for → 판정 결과 표시
5. browser_snapshot → 결과 확인:
   - 주사위 결과 (1~20)
   - 최종값 = 주사위 + 보정값
   - 판정: 성공/실패/대성공/대실패/자동 성공
   - "이야기 진행" 버튼 (마지막 판정인 경우)
```

#### 4.5 내러티브 생성 (AI 스토리)

```
1. browser_click → "이야기 진행" 버튼
2. 판정 모달 자동 닫힘
3. browser_wait_for → 내러티브 스트리밍 완료 (timeout 60s)
   - AI가 주사위 결과를 반영한 스토리 생성
   - 토큰 단위 스트리밍
4. browser_snapshot → 확인:
   - 스토리북에 USER 행동 + AI 내러티브 모두 표시
   - "던전 마스터" 라벨로 AI 내러티브 구분
   - 행동 입력 재활성화
```

#### 4.6 2라운드 반복

```
1. 새 행동 제출: "보물 상자를 열어본다"
2. 행동 결정 → 커밋
3. 판정 → 주사위 → 내러티브 (4.3~4.5 반복)
4. browser_snapshot → 스토리북에 2라운드 누적 로그 확인
```

---

### Phase 5: 멀티 플레이어 테스트 (브라우저 탭 활용)

> `browser_tabs`로 탭 2개 운용, localStorage 격리 필수

#### 5.1 두 플레이어 셋업

```
=== Tab 1 (user1 - 호스트) ===
1. browser_navigate → http://localhost:5173
2. user1 로그인 → 캐릭터 "전사 가렌" 선택
3. 세션 생성: "멀티플레이 테스트"
4. 게임 레이아웃 진입

=== Tab 2 (user2 - 참가자) ===
5. browser_tabs → action "new" (새 탭)
6. browser_evaluate → () => localStorage.clear()
7. browser_navigate → http://localhost:5173
8. user2 로그인 → 캐릭터 "마법사 엘리사" 선택
9. 세션 목록에서 "멀티플레이 테스트" 찾기 → "참가" 클릭
10. browser_wait_for → "스토리북"

=== 검증 ===
11. browser_tabs → action "select", index 0 (Tab 1으로 전환)
12. browser_snapshot → user2 참여 시스템 알림 확인
```

#### 5.2 게임 시작 & 동시 수신

```
=== Tab 1 (호스트) ===
1. browser_click → "게임 시작"
2. browser_wait_for → "던전 마스터" (timeout 30s)
3. browser_snapshot → 내러티브 확인

=== Tab 2 (참가자) ===
4. browser_tabs → action "select", index 1
5. browser_wait_for → "던전 마스터" (WebSocket으로 동시 수신, timeout 5s)
6. browser_snapshot → 동일 내러티브 표시 확인
```

#### 5.3 양측 행동 제출

```
=== Tab 1 (user1) ===
1. browser_type → "검을 뽑아 적에게 돌격한다"
2. browser_click → "행동"

=== Tab 2 (user2) ===
3. browser_tabs → select index 1
4. browser_type → "화염 마법을 시전한다"
5. browser_click → "행동"

=== Tab 1 (호스트 - 행동 결정) ===
6. browser_tabs → select index 0
7. browser_click → "행동 결정"
8. browser_snapshot → 모더레이션 모달에 2개 행동 확인
9. browser_click → "제출하기"
```

#### 5.4 멀티 판정

```
1. 각 탭에서 자기 캐릭터의 판정 처리:
   - Tab 1: user1의 판정 → "주사위 굴리기"
   - Tab 2: user2의 판정 → "주사위 굴리기"
2. 상대방 판정 결과도 실시간 수신 확인 (dice_rolled 이벤트)
3. 모든 판정 완료 후 마지막 플레이어가 "이야기 진행" 클릭
4. 양쪽 탭에서 AI 내러티브 스트리밍 수신 확인
```

#### 5.5 채팅 테스트

```
1. Tab 1: 채팅 입력 (placeholder "메시지 전송..."): "안녕하세요!"
2. Tab 1: browser_click → "전송"
3. Tab 2: browser_tabs → select index 1
4. browser_snapshot → "일반 채팅" 섹션에 메시지 수신 확인
```

---

## 에러/엣지 케이스 테스트

| # | 시나리오 | 테스트 방법 | 기대 결과 |
|---|---------|-----------|----------|
| E.1 | 빈 행동 제출 | 행동 입력 비워둔 채 "행동" 클릭 | 버튼 비활성화 (disabled) |
| E.2 | 빈 제목 세션 생성 | 제목 비운 채 "세션 생성" 클릭 | 에러 메시지 |
| E.3 | 존재하지 않는 세션 참가 | ID "99999"로 참가 시도 | "세션을 찾을 수 없습니다" |
| E.4 | 이름 없는 캐릭터 생성 | 이름 비운 채 "생성" 클릭 | HTML5 required 검증 |
| E.5 | 호스트 퇴장 시 세션 종료 | 호스트가 뒤로가기 → 참가자 탭 확인 | 참가자 화면이 로비로 복귀되고 해당 세션이 목록에서 제거됨 |

---

## 주요 기술적 고려사항

### localStorage 격리 (멀티탭)
authStore가 `auth-storage` 키로 localStorage에 persist됨. 새 탭에서 다른 유저로 로그인하려면:
```js
browser_evaluate(() => localStorage.clear())
browser_navigate("http://localhost:5173")
```

### AI 응답 대기 전략
- Phase 1 (판정 분석): timeout **30초**
- Phase 3 (내러티브 생성): timeout **60초**
- `browser_wait_for`로 특정 텍스트 대기
- `browser_console_messages`로 소켓 이벤트 모니터링 가능

### 세션 목록 갱신 정책 (SessionList)
- 가시 상태 탭: 약 15초 주기 폴링
- 백그라운드 탭: 약 60초 주기 폴링
- 탭 포커스/가시성 복귀 시 즉시 1회 갱신
- 수동 "새로고침" 버튼 클릭 시 즉시 갱신 + 로딩 스피너
- 네트워크 검증 시 기존(5초 고정 폴링) 대비 `GET /api/sessions/` 호출 빈도가 줄어야 함

### 한국어 UI 핵심 텍스트 매핑

| 한국어 | 의미 | 사용처 |
|-------|------|-------|
| 캐릭터 관리 | Character Management | 로그인 후 첫 화면 |
| 어서 오세요 | Welcome | 로비 진입 |
| 게임 시작 | Start Game | 호스트 전용 버튼 |
| 행동 결정 | Action Moderation | 호스트 전용 버튼 |
| 주사위 굴리기 | Roll Dice | 판정 모달 |
| 이야기 진행 | Progress Story | 마지막 판정 후 |
| 던전 마스터 | Dungeon Master | AI 내러티브 라벨 |
| 시스템 온라인 | System Online | 소켓 연결 상태 |
| 제출하기 | Submit | 모더레이션 모달 |
| 전송 | Send | 채팅 전송 버튼 |

### confirm() 다이얼로그
캐릭터 삭제, 세션 삭제 시 `window.confirm()` 사용 → `browser_handle_dialog(accept: true)`

### 소켓 이벤트 디버깅
```
browser_console_messages(level: "info")  → 소켓 이벤트 로그
browser_network_requests(includeStatic: false)  → API 호출 확인
```

---

## 권장 실행 순서

```
1. 인증 (1.1 → 1.2 → 1.3)
2. 캐릭터 (2.1 → 2.2 → 2.4)
3. 세션 관리 (3.1 → 3.5)
4. 싱글 게임 루프 (4.1 → 4.2 → 4.3 → 4.4 → 4.5 → 4.6) ← 핵심
5. 멀티 플레이어 (5.1 → 5.2 → 5.3 → 5.4 → 5.5)    ← 가장 복잡
6. 에러/엣지 케이스 (E.1 ~ E.5)
7. 정리 (로그아웃, 테스트 데이터 삭제)
```

---

## 핵심 파일 참조

| 파일 | 설명 |
|------|------|
| `frontend/src/App.tsx` | 앱 라우팅 (로그인 → 캐릭터 → 로비 → 게임) |
| `frontend/src/stores/socketStore.ts` | 소켓 이벤트 전체 핸들링 |
| `frontend/src/components/CenterPane.tsx` | 게임 중앙 패널 (스토리, 행동 입력) |
| `frontend/src/components/JudgmentModal.tsx` | 판정 모달 (주사위, 결과) |
| `frontend/src/components/LoginForm.tsx` | 로그인/회원가입 UI |
| `frontend/src/components/CharacterManagement.tsx` | 캐릭터 CRUD |
| `frontend/src/components/SessionList.tsx` | 세션 목록/참가 |
| `frontend/src/components/HostSessionsManager.tsx` | 호스트 세션 관리 |
| `backend/app/socket/handlers/ai_gm_handlers.py` | AI 판정/내러티브 소켓 핸들러 |
| `backend/app/services/ai_gm_service_v2.py` | AI GM 서비스 (LangChain) |
