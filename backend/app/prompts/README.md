# AI Prompts Directory

이 디렉토리는 백엔드 AI 노드가 사용하는 시스템 프롬프트를 보관합니다.

## Prompt Files

| 파일 | 주요 사용처 | 역할 |
|---|---|---|
| `judgment_prompt.md` | `services/ai_nodes/judgment_node.py` | 플레이어 행동 난이도/판정 분석 |
| `narrative_prompt.md` | `services/ai_nodes/narrative_node.py`, `socket/handlers/ai_gm_handlers.py` | 내러티브 생성 및 스트리밍 |
| `act_analysis_prompt.md` | `services/ai_nodes/act_analysis_node.py` | 막 전환 분석 |
| `growth_reward_prompt.md` | `services/ai_nodes/act_analysis_node.py` | 막 전환 보상 생성 |
| `state_update_prompt.md` | `services/ai_nodes/state_update_node.py` | 캐릭터 상태/인벤토리 업데이트 추론 |
| `image_concept_prompt.md` | `services/session_image_concept_service.py` | 세션 세계관 기반 이미지 컨셉 추출 |
| `story_image_generation_prompt.md` | `services/image_generation_service.py` | 턴 스토리 기반 장면 이미지 생성 지시 |

## Loading Mechanism

- 기본 로더: `app/utils/prompt_loader.py`
- 핵심 API: `load_prompt(filename)` 또는 `PromptLoader`
- 기본 프롬프트 디렉토리: `app/prompts`

예시:

```python
from app.utils.prompt_loader import load_prompt

system_message = load_prompt("narrative_prompt.md")
```

## Legacy Config Note

- `SYSTEM_PROMPT_PATH` 환경 변수는 하위 호환용 레거시 값입니다.
- 실제 런타임에서는 각 노드가 필요한 프롬프트 파일(`*.md`)을 직접 로드합니다.

## Edit Checklist

1. 출력 형식(JSON/XML/텍스트)을 바꾸는 경우, 해당 노드의 파싱 로직을 함께 수정합니다.
2. 프롬프트 변수(플레이스홀더)를 추가/변경한 경우, 호출 코드의 입력 컨텍스트를 맞춥니다.
3. 수정 후 최소한 아래를 확인합니다.

```bash
cd backend
uv run ruff check app/services app/socket app/utils
uv run pytest tests/test_socket_refactoring.py
```

## Related Files

- `app/utils/prompt_loader.py`
- `app/services/ai_nodes/judgment_node.py`
- `app/services/ai_nodes/narrative_node.py`
- `app/services/ai_nodes/act_analysis_node.py`
- `app/services/ai_nodes/state_update_node.py`
