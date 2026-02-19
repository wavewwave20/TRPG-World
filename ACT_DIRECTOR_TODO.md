# Act System Extension TODO (Story Director)

## Goal
Stabilize story flow without introducing a separate quest system.

## Design
- [x] Add rule-based Story Director layer on top of existing act pipeline
- [x] Keep AI calls unchanged in count (no additional LLM calls)
- [x] Control drift + tension via deterministic state machine

## Implementation
- [x] `backend/app/services/story_director.py`
  - [x] Session state (`main_goal`, `sub_goals`, `arc_phase`, `tension`, `consecutive_crisis`, `forbidden_drifts`)
  - [x] Guidance generation for narrative prompt
  - [x] Post-narrative state commit logic
- [x] `backend/app/services/ai_nodes/narrative_node.py`
  - [x] Add `director_guidance` parameter (normal + streaming)
  - [x] Inject director guidance into narrative context
- [x] `backend/app/services/ai_gm_service_v2.py`
  - [x] Build director guidance before narrative generation
  - [x] Commit director state after XML metadata parsing

## Tests
- [x] Add unit tests: `backend/tests/test_story_director.py`
  - [x] Crisis overrun => relief guidance
  - [x] Act transition => tension/consecutive crisis reset
- [ ] Run test suite in runtime (blocked: exec approval required)

## Validation Checklist
- [ ] Trigger 2+ continuous crisis turns and verify relief direction appears
- [ ] Trigger act transition metadata and verify director state reset
- [ ] Confirm no extra LLM call introduced in logs
