# Act 전환 및 보상 시스템 보고서

## 1. 전체 흐름 개요

```
플레이어 행동 제출
    │
    ▼
Phase 1: 행동 분석 + 주사위 사전 굴림 + 백그라운드 내러티브 생성 시작
    │
    ▼
Phase 2: 플레이어가 주사위 결과 확인 (이미 굴려져 있음)
    │
    ▼
Phase 3: 내러티브 스트리밍 → DB 저장 → 막 전환 체크 → (전환 시) 보상 생성
    │
    ▼
프론트엔드: 보상 모달 표시 + 성장 기록 갱신
```

---

## 2. Phase 1: 행동 분석 및 백그라운드 생성

### 트리거

플레이어가 `submit_action`으로 행동 큐를 제출하고, 방장이 `commit_actions`로 큐를 확정하면 Phase 1이 시작된다.

### 처리 흐름 (`AIGMServiceV2.analyze_actions()`)

1. **게임 컨텍스트 로드**: 세션, 캐릭터, 스토리 히스토리
2. **AI 행동 분석**: `analyze_and_judge_actions()` → 각 행동의 보정치(modifier) + 난이도(DC) 결정
3. **주사위 사전 굴림** (`_preroll_dice()`):
   - 모든 행동에 대해 d20 굴림
   - `ActionJudgment` 레코드를 **phase=0**으로 DB 저장
   - `requires_roll=false`인 행동은 `auto_success` 처리
4. **스트림 버퍼 생성**: `buffer_manager.create_buffer(session_id)`
5. **백그라운드 내러티브 생성 시작** (`_generate_narrative_background()`):
   - 별도 비동기 태스크로 LLM 스트리밍 호출
   - 토큰을 하나씩 받아 버퍼에 저장
   - 돌발 이벤트 확률 판정
   - 완료 시 XML 파싱 → clean narrative + metadata 분리 후 버퍼에 저장

### 핵심 포인트

- Phase 1에서 이미 **내러티브 생성이 시작**됨 (플레이어가 주사위 확인하는 동안 병렬 처리)
- 버퍼에 metadata가 저장되어 나중에 막 전환 판단에 사용

---

## 3. Phase 2: 주사위 확인

### 트리거

플레이어가 "주사위 굴리기" 버튼 클릭 → `roll_dice` 소켓 이벤트.

### 처리 흐름 (`AIGMServiceV2.confirm_dice_roll()`)

1. phase=0인 `ActionJudgment` 조회
2. **phase=0 → phase=2**로 업데이트 (확인됨)
3. 사전 굴림된 주사위 값 반환 (실제로 새로 굴리지 않음)
4. 모든 플레이어 확인 완료 시 `all_dice_rolled` 이벤트 브로드캐스트

---

## 4. Phase 3: 내러티브 스트리밍 및 저장

### 트리거

방장이 "스토리 진행" 클릭 → `request_narrative_stream` 소켓 이벤트.

### 처리 흐름

#### A. 정상 경로 (버퍼 있음)

```
request_narrative_stream
    │
    ├─ 버퍼 존재 확인
    │
    ├─ narrative_stream_started 이벤트 발송
    │
    ├─ ai_service.stream_narrative() 호출
    │   ├─ 버퍼 완료 대기 (백그라운드 생성이 아직 진행 중이면)
    │   ├─ clean narrative를 4글자 청크로 스트리밍
    │   ├─ DB 저장: StoryLog(role=AI) 생성
    │   ├─ phase=2 → phase=3 업데이트
    │   └─ 상태 효과 회복 체크
    │
    ├─ narrative_complete 이벤트 발송
    │
    └─ 메타데이터 기반 막 전환 체크
        └─ buffer.metadata에서 act_transition 확인
```

#### B. 폴백 경로 (버퍼 없음 - 재접속 등)

```
request_narrative_stream
    │
    ├─ 버퍼 없음 감지
    │
    └─ _trigger_story_generation_internal() 호출
        ├─ phase=2 판정 수집
        ├─ narrative_stream_started 이벤트 발송
        ├─ ai_service.generate_narrative() (동기식 생성)
        ├─ 청크 스트리밍 (50글자 단위)
        ├─ DB 저장
        ├─ narrative_complete 이벤트 발송
        └─ 메타데이터 있으면 → 메타데이터 기반 전환
           메타데이터 없으면 → AI 분석 기반 전환 (레거시)
```

---

## 5. 내러티브 XML 구조

LLM은 다음 XML 형식으로 응답:

```xml
<story>
[순수 서술 텍스트 - 플레이어에게 보여지는 이야기]
</story>
<summary>
<situation>현재 상황 한줄 요약</situation>
<act_transition>true 또는 false</act_transition>
<new_act_title>새 막 제목 (전환 시만)</new_act_title>
<new_act_subtitle>새 막 부제 (전환 시만)</new_act_subtitle>
</summary>
```

- `<story>` 내용만 플레이어에게 스트리밍
- `<summary>`는 시스템용 메타데이터 (막 전환 판단에 사용)
- `parse_narrative_xml()`이 분리 처리

---

## 6. Act 전환 메커니즘

### 두 가지 경로

| | 메타데이터 기반 (주 경로) | AI 분석 기반 (레거시 폴백) |
|---|---|---|
| **트리거** | 내러티브 XML에 `act_transition=true` | 메타데이터 없을 때 |
| **AI 호출** | 내러티브 AI가 이미 판단 완료 | 별도 `analyze_act_transition()` AI 호출 |
| **함수** | `execute_act_transition()` | `check_act_transition()` |
| **비용** | 추가 LLM 호출 없음 (성장 보상만) | 분석 LLM 호출 1회 추가 |

### 메타데이터 기반 전환 (`_handle_act_transition_from_metadata`)

1. `metadata["act_transition"] == true` 확인
2. `new_act_title` 존재 확인 (없으면 스킵)
3. `execute_act_transition()` 호출

### AI 분석 기반 전환 (`_check_act_transition_after_narrative`)

1. 현재 막의 스토리 전체 로드
2. `analyze_act_transition()` AI 호출 → 사건 식별, 전환 필요성 판단
3. `should_transition == true`이면 전환 실행

### 전환 실행 공통 로직

```
코드 가드: AI 서술 3개 미만이면 전환 거부
    │
    ▼
성장 보상 생성 (AI 호출: generate_growth_rewards)
    │
    ▼
보상 적용 (_apply_growth_reward → 캐릭터 데이터 수정)
    │
    ▼
보상 DB 저장 (_persist_growth_rewards → CharacterGrowthLog)
    │
    ▼
AI Summary 갱신 (AI 호출: generate_updated_ai_summary)
    │
    ▼
현재 막 종료 (ended_at 설정, end_story_log_id 설정)
    │
    ▼
새 막 생성 (StoryAct 레코드, act_number + 1)
    │
    ▼
결과 반환 → 소켓 이벤트 브로드캐스트
```

### 전환 시 소켓 이벤트

1. **`act_completed`**: 전체 보상 + 완료된 막/새 막 정보
2. **`character_growth_applied`**: 캐릭터별 개별 성장 이벤트 (캐릭터 시트 갱신용)

---

## 7. 성장 보상 시스템

### 보상 생성 (`generate_growth_rewards`)

- 프롬프트: `growth_reward_prompt.md`
- 입력: 세계관, 캐릭터 정보(능력치/스킬/약점), 막의 전체 스토리
- 출력: JSON 배열 (캐릭터당 1~3개 보상)

### 보상 규칙

| 보상 유형 | 필수/선택 | 조건 |
|---|---|---|
| `ability_increase` (기본) | **필수** (캐릭터당 1개) | 가장 활약한 능력치 +1 |
| `ability_increase` (추가) | 선택 | 높은 기여도 시 다른 능력치 +1 |
| `new_skill` | 선택 | 반복 행동/극적 경험 시 |
| `weakness_mitigated` | 선택 | 약점 관련 상황 극복 시 |

### 파서 안전장치 (`_parse_growth_rewards`)

- 잘못된 `character_id`, `growth_type` 필터링
- **Fallback**: AI가 `ability_increase`를 빠뜨린 캐릭터에 자동으로 constitution +1 추가

### 보상 적용 (`_apply_growth_reward`)

| 유형 | 적용 방식 |
|---|---|
| `ability_increase` | `character.data[ability] += delta` (최대 20) |
| `new_skill` | `character.data["skills"].append(skill_data)` |
| `weakness_mitigated` | `weakness.mitigation += delta` (3 이상이면 극복) |

### 보상 DB 저장 (`_persist_growth_rewards`)

- `CharacterGrowthLog` 테이블에 기록
- 필드: `session_id`, `act_id`, `character_id`, `growth_type`, `growth_detail`, `narrative_reason`, `applied_at`

### 보상 기록 조회 API

- `GET /api/sessions/{session_id}/growth-history`
- act별 그룹화, 캐릭터 이름 resolve
- 프론트엔드에서 세션 진입 시 + act 완료 시 호출

---

## 8. 프론트엔드 보상 표시 흐름

```
act_completed 소켓 이벤트 수신
    │
    ├─ actStore에 보상 저장
    ├─ GrowthRewardModal 표시 (보상 카드 UI)
    └─ getGrowthHistory() API 호출 → growthHistory 갱신

사용자가 모달 닫음
    │
    └─ 이후 "성장 기록" 드롭다운에서 재확인 가능
        ├─ act별 보상 목록 드롭다운
        └─ 클릭 시 해당 act의 보상 모달 다시 표시
```

### 관련 컴포넌트

| 컴포넌트 | 역할 |
|---|---|
| `GrowthRewardModal` | 보상 카드 모달 (능력치/스킬/약점 유형별 UI) |
| `GrowthHistoryDropdown` | 스토리북 헤더의 "성장 기록" 버튼 + 드롭다운 |
| `CenterPane` | 드롭다운 배치 + 세션 진입 시 기록 로드 |

---

## 9. 전체 이벤트 시퀀스 (타임라인)

```
T+0   submit_action (플레이어별 큐 제출/수정)
        → queue_updated 이벤트 (반복)

T+0+  commit_actions (방장 커밋)
        → Phase 1 분석
        → 주사위 사전 굴림 (phase=0)
        → 스트림 버퍼 생성
        → 백그라운드 내러티브 생성 시작
        → judgment_ready 이벤트 발송

T+1   roll_dice (각 플레이어)
        → phase=0 → phase=2
        → dice_rolled 이벤트

T+2   all_dice_rolled (모든 플레이어 확인 완료)

T+3   request_narrative_stream (방장 클릭 또는 자동)
        → narrative_stream_started
        → narrative_token (n회 반복)
        → DB 저장 (StoryLog, phase=2→3)
        → narrative_complete

T+4   (막 전환 발생 시)
        → 성장 보상 AI 생성 (LLM 호출)
        → 보상 적용 (캐릭터 데이터 수정)
        → 보상 DB 저장 (CharacterGrowthLog)
        → AI Summary 갱신 (LLM 호출)
        → 현재 막 종료 + 새 막 생성
        → act_completed 이벤트
        → character_growth_applied 이벤트 (캐릭터별)

T+5   프론트엔드
        → 보상 모달 표시
        → 성장 기록 API 호출 → 드롭다운 갱신
```

---

## 10. 관련 파일 맵

### Backend

| 파일 | 역할 |
|---|---|
| `socket/handlers/ai_gm_handlers.py` | 소켓 이벤트 오케스트레이션 |
| `services/ai_gm_service_v2.py` | 핵심 비즈니스 로직 (분석, 생성, 전환, 보상) |
| `services/ai_nodes/act_analysis_node.py` | 막 전환 분석 + 보상 생성 AI 노드 |
| `services/ai_nodes/narrative_node.py` | 내러티브 XML 파싱 |
| `services/stream_buffer.py` | 토큰 버퍼링 (백그라운드 생성 ↔ 스트리밍) |
| `prompts/narrative_prompt.md` | 내러티브 + 메타데이터 XML 형식 지정 |
| `prompts/growth_reward_prompt.md` | 보상 생성 규칙 + 출력 형식 |
| `routes/sessions.py` | 성장 기록 API 엔드포인트 |

### Frontend

| 파일 | 역할 |
|---|---|
| `stores/actStore.ts` | Act 상태 + 보상 기록 관리 |
| `stores/socket-handlers/actHandlers.ts` | act_completed/act_started 이벤트 처리 |
| `components/GrowthRewardModal.tsx` | 보상 카드 모달 UI |
| `components/GrowthHistoryDropdown.tsx` | 성장 기록 드롭다운 |
| `components/CenterPane.tsx` | 드롭다운 배치 + 기록 로드 |
| `services/api.ts` | `getGrowthHistory()` API 함수 |
| `types/act.ts` | 타입 정의 |
