# TRPG World — LLM 호출 전체 점검 보고서 (한글)

작성일: 2026-02-20  
범위: 백엔드 LLM 호출 경로, 트리거 조건, 프롬프트 점검, 리스크, 최적화 우선순위

---

## 1) 현재 LLM 호출 지점 전체 목록

### A. 코어 게임 루프

1. **Phase 1 판정 분석**
- 파일: `backend/app/services/ai_nodes/judgment_node.py`
- 호출: `chain.ainvoke({"context": context_text})`
- 프롬프트: `backend/app/prompts/judgment_prompt.md`
- 트리거: 호스트가 행동 커밋할 때
- 빈도: **커밋 1회당 1콜**

2. **Phase 3 서사 생성(비스트리밍)**
- 파일: `backend/app/services/ai_nodes/narrative_node.py`
- 호출: `chain.ainvoke({"context": context_text})`
- 프롬프트: `backend/app/prompts/narrative_prompt.md`
- 트리거: 비스트리밍 서사 생성 경로
- 빈도: **서사 1회당 1콜**

3. **Phase 3 서사 생성(스트리밍)**
- 파일: `backend/app/services/ai_nodes/narrative_node.py`
- 호출: `chain.astream({"context": context_text})`
- 프롬프트: `backend/app/prompts/narrative_prompt.md`
- 트리거: 소켓 스트리밍 서사 경로
- 빈도: **서사 1회당 1 스트리밍 콜**

---

### B. Act/요약 메타 파이프라인

4. **Act 전환 분석**
- 파일: `backend/app/services/ai_nodes/act_analysis_node.py`
- 호출: `chain.ainvoke({"context": context_text})`
- 프롬프트: `backend/app/prompts/act_analysis_prompt.md`
- 트리거: `check_act_transition()` 분석 기반 전환 경로

5. **Act 1 제목/부제 생성**
- 파일: `backend/app/services/ai_nodes/act_analysis_node.py`
- 호출: `chain.ainvoke({"world_context":..., "narrative":...})`
- 프롬프트: 코드 내 인라인 시스템 프롬프트
- 트리거: 오프닝/초기 Act 생성 시

6. **성장 보상 생성**
- 파일: `backend/app/services/ai_nodes/act_analysis_node.py`
- 호출: `chain.ainvoke({"context": context_text})`
- 프롬프트: `backend/app/prompts/growth_reward_prompt.md`
- 트리거: Act 전환 실행 시

7. **장기 요약(ai_summary) 갱신**
- 파일: `backend/app/services/ai_nodes/session_summary_node.py`
- 호출: `chain.ainvoke({"context": context})`
- 프롬프트: 코드 내 인라인 시스템 프롬프트
- 트리거: Act 전환 완료 시

---

### C. 오프닝 생성 경로

8. **오프닝 서술 생성(스트리밍)**
- 파일: `backend/app/socket/handlers/ai_gm_handlers.py`
- 호출: `chain.astream({"world_prompt": world_prompt})`
- 프롬프트: `backend/app/prompts/narrative_prompt.md`
- 트리거: 세계관 프롬프트에 시작 상황이 없을 때

---

## 2) 턴당 실제 호출 수 구조

### 일반 행동 커밋 1회
- Phase1 판정: 1콜
- Phase3 서사: 1콜
- **합계: 2콜**

### Act 전환이 함께 발생하는 경우(메타데이터 전환 경로)
- 기본 2콜 + 성장 보상 1콜 + 요약 갱신 1콜
- **합계: 4콜**

### 분석 기반 전환 경로까지 타는 경우
- 기본 2콜 + 전환 분석 1콜 + 성장 보상 1콜 + 요약 갱신 1콜
- **합계: 5콜**

### 최근 스토리 재생성 버튼
- 내러티브 재생성 1콜 추가
- (전환 조건 만족 시 전환 관련 추가 콜 가능)

---

## 3) 프롬프트별 상태 점검

### `judgment_prompt.md` (Phase1)
- 상태: 영어 시스템 프롬프트 중심으로 변경
- 강제 규칙: JSON 전용 출력, `difficulty_reasoning`은 한글
- 추가 규칙: 입력 action_type은 임시값일 수 있고, 최종 action_type은 모델이 행동 의미 기반으로 결정

### `narrative_prompt.md` (Phase3)
- 서사 규칙이 매우 풍부하고 길다
- XML 출력 계약(`<story>`, `<summary>`), 이벤트/Act 전환 지시 포함

### `act_analysis_prompt.md`
- 사건 수 카운트 + 전환 여부 판단 계약 명확

### `growth_reward_prompt.md`
- 성장 보상 생성 규칙
- 액티브 스킬만 허용 정책 반영됨
- 주의: 샘플 JSON에 passive 예시가 남아 있으면 정책과 충돌할 수 있어 추가 정리 권장

---

## 4) 최근 반영된 아키텍처 변경 확인

1. **Phase1 입력 경량화**
- Phase1에서 세계관 원문 제거
- Phase1에서 장기요약(ai_summary) 제거
- 현재 막 정보 + 최근 스토리 중심 입력으로 변경

2. **Phase1 최근 스토리 윈도우 확대**
- `story_history[-1:]` → 최근 다건(`[-6:]`)으로 확대

3. **action_type 결정권 보정**
- 프롬프트/컨텍스트 모두에서 입력 action_type은 참고값임을 명시
- 모델이 최종 action_type을 직접 판단하도록 유도

4. **스킬 모드 + 쿨타임**
- 일반행동/스킬사용 모드 분리
- 액티브 스킬 ability를 판정 action_type 입력으로 연결
- 내러티브 턴 기준 쿨타임 적용

5. **Act 보상 스킬 정책 고정**
- new_skill 보상은 최종적으로 active만 허용되도록 파서/적용 단계에서 강제
- cooldown 기본값 보정

---

## 5) 리스크 및 버그 포인트

1. **서사 중복 생성 잠재 리스크**
- 자동 백그라운드 생성 경로 + 수동 트리거 경로가 타이밍에 따라 겹칠 수 있음
- 일부 가드가 있으나, 단일 상태락 통합이 더 안전

2. **성장 보상 프롬프트 샘플 불일치 가능성**
- 정책은 active-only인데 샘플이 passive를 보여주면 모델 드리프트 위험

3. **Phase1 지연은 모델/컨텍스트 영향이 큼**
- 호출 수보다 "콜당 입력 길이"와 모델 응답속도 영향이 큼

---

## 6) 즉시 권장 조치 (작고 효과 큰 순서)

1. `growth_reward_prompt.md` 샘플 JSON도 active-only로 완전 통일
2. `phase3_status` 단일 상태락(`idle|generating|ready|streaming|done`) 도입해 중복 생성 완전 차단
3. Phase1은 현재처럼 "현재 막 + 최근 스토리" 최소 컨텍스트 유지

---

## 7) 빠른 참조 경로

- 판정 호출: `services/ai_nodes/judgment_node.py`
- 서사 호출: `services/ai_nodes/narrative_node.py`
- 오프닝 스트리밍: `socket/handlers/ai_gm_handlers.py`
- 전환/보상 오케스트레이션: `services/ai_gm_service_v2.py`
- 전환/보상 모델 호출: `services/ai_nodes/act_analysis_node.py`
- 요약 갱신 호출: `services/ai_nodes/session_summary_node.py`
- 프롬프트 디렉토리: `backend/app/prompts/`
