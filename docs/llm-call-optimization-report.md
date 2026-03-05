# LLM 콜 현황 및 최적화 분석 보고서

## 1. 전체 LLM 콜 맵

| # | 함수 | 파일 | 프롬프트 | 모델 기본값 | Temp | Max Tokens | 호출방식 | 출력 |
|---|------|------|----------|-------------|------|------------|----------|------|
| 1 | `_determine_difficulty_with_ai` | `judgment_node.py:309` | `judgment_prompt.md` | gemini-3-pro | 1.0 | 4000 | `ainvoke` | JSON 배열 |
| 2 | `generate_narrative` | `narrative_node.py:253` | `narrative_prompt.md` | gpt-4o | 1.0 | 4000 | `ainvoke` | XML |
| 3 | `generate_narrative_streaming` | `narrative_node.py:408` | `narrative_prompt.md` | gemini-3-pro | 1.0 | 4000 | `astream` | XML |
| 4 | `analyze_act_transition` | `act_analysis_node.py:101` | `act_analysis_prompt.md` | gpt-4o | 0.3 | 1000 | `ainvoke` | JSON |
| 5 | `generate_act_title` | `act_analysis_node.py:174` | 인라인 | gpt-4o | 0.7 | 200 | `ainvoke` | JSON |
| 6 | `generate_growth_rewards` | `act_analysis_node.py:277` | `growth_reward_prompt.md` | gpt-4o | 0.7 | 2000 | `ainvoke` | JSON 배열 |
| 7 | `generate_updated_ai_summary` | `session_summary_node.py:108` | 인라인 | gpt-4o | 0.2 | 2000 | `ainvoke` | 평문 |
| 8 | `_generate_opening_narrative` | `ai_gm_handlers.py:83` | `narrative_prompt.md` | 런타임 | 1.0 | 2000 | `astream` | XML |

---

## 2. 정상 플로우별 LLM 콜 횟수

### 게임 시작 (1회)
| 조건 | LLM 콜 |
|------|--------|
| "시작 상황:" 있음 | **#5** (Act 타이틀) = **1회** |
| "시작 상황:" 없음 | **#8** (오프닝 서술) + **#5** (Act 타이틀) = **2회** |

### 매 턴 (메인 루프)
| 단계 | LLM 콜 |
|------|--------|
| Phase 1: 행동 분석 | **#1** (난이도 판정) = **1회** |
| Phase 3: 서술 생성 | **#3** (스트리밍 서술) = **1회** |
| **턴당 합계** | **2회** |

### 막 전환 시 (추가)
| 단계 | LLM 콜 |
|------|--------|
| 성장 보상 | **#6** = **1회** |
| 누적 요약 갱신 | **#7** = **1회** |
| **막 전환 추가** | **2회** |

---

## 3. 낭비/비효율 분석

### 문제 1: `generate_narrative` (비스트리밍)가 사실상 데드코드

**위치:** `narrative_node.py:136-263` (Call #2)

**현상:**
- `generate_narrative_streaming` (#3)이 메인 경로에서 항상 사용됨
- `generate_narrative` (#2)는 `ai_gm_service_v2.py:225`의 `generate_narrative()` 메서드에서만 호출
- 이 메서드는 `request_narrative_stream`의 내부 폴백 헬퍼 `_trigger_story_generation_internal`에서만 호출됨

**영향:**
- 레거시 폴백이 실행되면 **동일한 프롬프트로 비스트리밍 LLM 콜**이 발생
- 스트리밍 버전과 프롬프트 조합 로직이 **완전히 중복** (~120줄 복붙)
- 유지보수 시 양쪽을 동기화해야 하는 부담

**개선안:** 레거시 경로도 `generate_narrative_streaming`을 사용하도록 통합. 비스트리밍 `generate_narrative` 함수 제거.

---

### 문제 2: `analyze_act_transition` (#4)이 사실상 데드코드

**위치:** `act_analysis_node.py:21-124` (Call #4)

**현상:**
- 메인 경로에서는 내러티브 AI가 `<summary>` XML 안에 `<act_transition>true/false</act_transition>`을 직접 출력
- `_handle_act_transition_from_metadata()` → `execute_act_transition()`으로 처리
- `analyze_act_transition` (#4)은 `check_act_transition()`에서만 호출되는데, 이는 `_check_act_transition_after_narrative` (레거시 폴백)에서만 호출됨
- 레거시 폴백 로직은 `_trigger_story_generation_internal` 내부에서 메타데이터가 없을 때만 실행

**영향:**
- 정상 경로에서는 **절대 호출되지 않는** LLM 콜
- 프롬프트 파일(`act_analysis_prompt.md`)과 관련 코드가 유지보수 대상으로 남아있음
- 만약 레거시 경로가 실행되면 **불필요한 추가 LLM 콜 1회** 발생

**개선안:** 레거시 폴백에서도 내러티브 메타데이터 기반 전환을 사용하도록 통합. `analyze_act_transition` 및 `act_analysis_prompt.md` 제거.

---

### 문제 3: `load_game_context` 중복 호출

**위치:** `ai_gm_service_v2.py` 내 `execute_act_transition` (line 1152)

**현상:**
- `analyze_actions()` (line 120)에서 `load_game_context` 호출 → `game_context`를 `_generate_narrative_background()`에 전달
- 서술 완료 후 막 전환 시 `execute_act_transition()` (line 1152)에서 **다시 `load_game_context` 호출**
- 같은 턴 안에서 DB 쿼리(세션, 캐릭터, 스토리, Act)가 **동일하게 2번** 실행됨

**영향:**
- LLM 콜은 아니지만 **DB 쿼리 낭비** (세션 + 캐릭터 + 스토리 로그 + Act 전부 재조회)
- 특히 스토리 로그가 길어지면 조회 비용 증가

**개선안:** `game_context`를 버퍼에 함께 저장하거나, 핸들러에서 막 전환 함수로 전달.

---

### 문제 4: Judgment 노드에서 `story_history[-1:]`만 전달

**위치:** `ai_gm_service_v2.py:136`

```python
story_history=game_context.story_history[-1:],
```

**현상:**
- `load_game_context`에서 현재 막의 **전체** 스토리 로그를 DB에서 로드
- 그런데 judgment 노드에는 **마지막 1개만** 전달
- 전체 스토리를 로드하는 DB 비용을 지불하고도 대부분 버림

**영향:**
- DB에서 현재 막의 전체 스토리를 불러온 후 1개만 사용 → DB 쿼리 낭비
- 단, judgment에는 최소한의 컨텍스트만 필요하므로 LLM 토큰 절약은 의도적일 수 있음

**개선안:**
- A) judgment용 별도 경량 컨텍스트 로더 생성 (story_history 없이 로드)
- B) 현재 방식 유지하되, 이미 로드된 `game_context`를 narrative에 재사용하므로 실질 손실은 적음 → **우선순위 낮음**

---

### 문제 5: 코드 중복 — 유틸 함수가 두 파일에 복붙됨

**위치:**
- `judgment_node.py:21-49`: `_select_recent_story_entries`, `_format_story_entry`
- `narrative_node.py:20-49`: 동일한 함수 복붙

**영향:**
- LLM 비용과 직접 관련은 없지만, 프롬프트 조합 로직이 분산되어 **불일치 위험** 존재
- 실제로 narrative_node의 `_format_story_entry`와 session_summary_node의 것이 미세하게 다름

**개선안:** 공통 유틸로 추출하여 단일화.

---

### 문제 6: Judgment 노드 max_tokens=4000 과다

**위치:** `judgment_node.py:303`

**현상:**
- Judgment 결과는 캐릭터당 ~100토큰 수준의 간단한 JSON 배열
- 4명의 캐릭터 기준 약 400-600토큰이면 충분
- `max_tokens=4000`은 실제 필요량의 **6-10배**

**영향:**
- 직접적인 비용 낭비는 아님 (실제 생성된 토큰만 과금)
- 하지만 모델이 불필요하게 장황한 응답을 생성할 여지를 줌 → 파싱 에러 위험 증가

**개선안:** `max_tokens=1500` 정도로 줄이는 것이 적절.

---

## 4. 종합 개선 우선순위

| 우선순위 | 문제 | 유형 | 절감 효과 |
|----------|------|------|-----------|
| **높음** | #1: 비스트리밍 narrative 제거 | 코드 정리 | 중복 코드 120줄 제거, 유지보수 비용 감소 |
| **높음** | #2: analyze_act_transition 제거 | 데드코드 제거 | 레거시 경로에서 LLM 콜 1회 절약, 코드 ~100줄 + 프롬프트 1개 제거 |
| **중간** | #3: load_game_context 중복 제거 | DB 쿼리 최적화 | 막 전환 시 DB 쿼리 1세트 절약 |
| **낮음** | #4: judgment용 story_history 최적화 | DB 쿼리 최적화 | 미미한 DB 쿼리 절약 |
| **낮음** | #5: 유틸 함수 중복 제거 | 코드 품질 | 불일치 위험 제거 |
| **낮음** | #6: judgment max_tokens 조정 | LLM 파라미터 | 파싱 안정성 향상 |

---

## 5. 결론

**현재 정상 경로의 LLM 콜은 효율적으로 설계되어 있음.**
- 턴당 2회 (판정 + 서술)로 최소화
- 막 전환 판단을 별도 LLM 콜 없이 서술 메타데이터로 통합한 것은 좋은 설계

**주요 낭비는 레거시 폴백 경로에 집중:**
- 비스트리밍 narrative (#2)와 analyze_act_transition (#4)은 정상 흐름에서 사용되지 않는 데드코드
- 이들을 제거하면 코드 ~220줄 + 프롬프트 파일 1개가 정리되고, 레거시 폴백 시 불필요한 LLM 콜 1회가 절약됨
