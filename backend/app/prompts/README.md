# AI Prompts Directory

이 디렉토리에는 AI 게임 마스터가 사용하는 프롬프트 파일들이 포함되어 있습니다.

## 파일 목록

### `judgment_prompt.md` (Phase 1: 행동 분석)
**목적**: 플레이어 행동을 분석하고 난이도(DC)를 결정

**사용 시점**: Phase 1 - 플레이어가 행동을 제출했을 때

**포함 내용**:
- TRPG 규칙 명세
- D20 능력치 시스템
- 난이도 결정 기준 (창의성, 상황, 배경, 환경)
- DC 등급 설명 (5-30)
- JSON 응답 형식

**응답 형식**:
```json
[
  {
    "character_id": 1,
    "difficulty": 15,
    "reasoning": "난이도 결정 이유"
  }
]
```

---

### `narrative_prompt.md` (Phase 3: 스토리 생성)
**목적**: 판정 결과를 기반으로 몰입감 있는 서술 생성

**사용 시점**: Phase 3 - 모든 플레이어가 주사위를 굴린 후

**포함 내용**:
- 서술 스타일 가이드라인
- 판정 결과 반영 방법
- 캐릭터 행동 통합 방법
- 다음 행동으로의 연결

**응답 형식**: 순수 텍스트 (JSON이나 마크다운 없이)

---

## 사용 방법

### 초기화

```python
from app.services.prompt_builder import PromptBuilder

# system_prompt_path는 레거시 파라미터
# 실제로는 해당 디렉토리에서 judgment_prompt.md와 narrative_prompt.md를 로드
prompt_builder = PromptBuilder(
    system_prompt_path="app/prompts/system_prompt.md"  # 디렉토리 경로만 사용
)
```

### Phase 1: 행동 분석 프롬프트 생성

```python
prompt = prompt_builder.build_action_analysis_prompt(
    actions=player_actions,
    characters=all_characters,
    world_context=session.world_prompt,
    story_history=recent_logs
)
```

### Phase 3: 서술 생성 프롬프트 생성

```python
prompt = prompt_builder.build_narration_prompt(
    judgments=judgment_results,
    characters=all_characters,
    story_history=recent_logs,
    world_context=session.world_prompt
)
```

---

## 프롬프트 작성 가이드

### 마크다운 형식
모든 프롬프트는 마크다운 형식으로 작성되어야 합니다.

### 구조화
- 명확한 섹션 구분 (##, ###)
- 예시 포함
- 규칙 명시

### 일관성
- 용어 통일 (능력치, 보정치, DC 등)
- 한국어 사용
- 명확한 지시사항

---

## 환경 변수

프롬프트 파일 경로는 환경 변수로 설정할 수 있습니다:

```bash
# .env
SYSTEM_PROMPT_PATH=app/prompts/system_prompt.md
```

**참고**: `SYSTEM_PROMPT_PATH`는 레거시 변수명입니다. 실제로는 해당 경로의 디렉토리에서 `judgment_prompt.md`와 `narrative_prompt.md`를 찾습니다.

---

## 프롬프트 수정 시 주의사항

1. **JSON 형식 유지**: `judgment_prompt.md`의 응답 형식은 반드시 JSON 배열이어야 합니다.

2. **텍스트 형식 유지**: `narrative_prompt.md`의 응답은 순수 텍스트여야 합니다 (JSON이나 마크다운 없이).

3. **인코딩**: 모든 파일은 UTF-8 인코딩을 사용해야 합니다.

4. **테스트**: 프롬프트 수정 후 반드시 테스트하세요:
   ```bash
   cd backend
   uv run python scripts/diagnose_ai_issue.py
   ```

---

## 관련 문서

- [PROJECT_DOCUMENTATION.md](../../../PROJECT_DOCUMENTATION.md) - 전체 프로젝트 문서
- [backend/app/services/prompt_builder.py](../services/prompt_builder.py) - 프롬프트 빌더 구현
- [.kiro/specs/ai-game-master/design.md](../../../.kiro/specs/ai-game-master/design.md) - AI 시스템 설계
