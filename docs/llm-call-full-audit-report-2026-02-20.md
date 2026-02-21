# TRPG World — Full LLM Call Audit Report

Date: 2026-02-20
Scope: Backend LLM call paths, trigger conditions, prompt inventory, risk notes, optimization priorities

---

## 1) LLM Call Inventory (All current call sites)

### A. Core gameplay loop

1. **Phase 1 Judgment**
- File: `backend/app/services/ai_nodes/judgment_node.py`
- Call: `chain.ainvoke({"context": context_text})`
- Prompt: `backend/app/prompts/judgment_prompt.md`
- Trigger: host action commit flow
- Frequency: **1 call per commit**

2. **Phase 3 Narrative (non-streaming)**
- File: `backend/app/services/ai_nodes/narrative_node.py`
- Call: `chain.ainvoke({"context": context_text})`
- Prompt: `backend/app/prompts/narrative_prompt.md`
- Trigger: direct narrative generation path
- Frequency: **1 call per narrative generation**

3. **Phase 3 Narrative (streaming)**
- File: `backend/app/services/ai_nodes/narrative_node.py`
- Call: `chain.astream({"context": context_text})`
- Prompt: `backend/app/prompts/narrative_prompt.md`
- Trigger: socket streaming narrative path
- Frequency: **1 streaming call per narrative generation**

---

### B. Act/summary meta pipeline

4. **Act transition analysis**
- File: `backend/app/services/ai_nodes/act_analysis_node.py`
- Call: `chain.ainvoke({"context": context_text})`
- Prompt: `backend/app/prompts/act_analysis_prompt.md`
- Trigger: `check_act_transition()` path (analysis-based transition)

5. **Act 1 title/subtitle generation**
- File: `backend/app/services/ai_nodes/act_analysis_node.py`
- Call: `chain.ainvoke({"world_context":..., "narrative":...})`
- Prompt: inline system prompt in code
- Trigger: initial opening/act creation flow

6. **Growth reward generation**
- File: `backend/app/services/ai_nodes/act_analysis_node.py`
- Call: `chain.ainvoke({"context": context_text})`
- Prompt: `backend/app/prompts/growth_reward_prompt.md`
- Trigger: act transition execution

7. **Session long summary update**
- File: `backend/app/services/ai_nodes/session_summary_node.py`
- Call: `chain.ainvoke({"context": context})`
- Prompt: inline system prompt in code
- Trigger: act transition completion

---

### C. Opening narrative path

8. **Opening scene generation (streaming)**
- File: `backend/app/socket/handlers/ai_gm_handlers.py`
- Call: `chain.astream({"world_prompt": world_prompt})`
- Prompt: `backend/app/prompts/narrative_prompt.md`
- Trigger: when world prompt has no "start situation" section

---

## 2) Real call count model per turn

## Normal action commit turn
- Phase1 judgment: 1
- Phase3 narrative: 1
- **Total: 2 calls**

## When act transition is triggered (metadata path)
- Base 2 + growth reward 1 + summary update 1
- **Total: 4 calls**

## If analysis-based transition path is used
- Base 2 + transition analysis 1 + growth reward 1 + summary update 1
- **Total: 5 calls**

## Story regenerate button
- Narrative regenerate: +1
- (and possible transition extras if transition is triggered)

---

## 3) Prompt-by-prompt status

### judgment_prompt.md (Phase1)
- Current status: switched to English system guidance
- Enforced: JSON-only output, `difficulty_reasoning` in Korean
- Added: explicit rule that input action_type may be temporary and model should decide final action_type

### narrative_prompt.md (Phase3)
- Large and comprehensive narrative style/continuity rules
- Includes XML output contract (`<story>`, `<summary>`) and event/act-transition directives

### act_analysis_prompt.md
- Event counting and transition decision prompt
- `event_count` and `should_transition` output contract

### growth_reward_prompt.md
- Growth reward generation rules
- Note: file now says active-only policy, but sample JSON block still contains `"type":"passive"` in examples (inconsistent with policy)

---

## 4) Recent architecture changes verified

1. **Phase1 context slimming**
- world long context removed from Phase1 input
- ai_summary removed from Phase1 input
- now uses short current-act text + recent story slice

2. **Phase1 story context window widened**
- from `story_history[-1:]` to recent multiple entries (`[-6:]`)

3. **Action type authority fixed**
- prompt + context labeling now clarifies action_type input can be provisional
- model expected to infer final action_type from action semantics

4. **Skill mode + cooldown**
- action mode normal/skill implemented
- active skill ability mapping feeds judgment type input
- cooldown based on narrative turn count

5. **Act reward skill policy hardening**
- new_skill rewards are forced to `active` in parser and apply stages
- cooldown default attached when missing

---

## 5) Risk/bug notes

1. **Potential narrative duplicate generation race (design risk)**
- automatic background generation + manual trigger path can overlap depending on timing
- existing stream-in-progress guard blocks some duplicates, but state lock unification is still recommended

2. **growth_reward_prompt example inconsistency**
- policy says active-only, but sample JSON still includes passive skill type
- should be corrected to avoid model drift

3. **Phase1 latency remains model-dependent**
- call count is stable, but prompt size and model latency still affect response time

---

## 6) Recommended immediate cleanup (small, high impact)

1. Fix `growth_reward_prompt.md` sample JSON to active-only
2. Add unified `phase3_status` lock (`idle|generating|ready|streaming|done`) to fully prevent duplicate narrative generation
3. Keep Phase1 context lightweight (current act + recent story only) and avoid reintroducing world/summary bulk

---

## 7) Quick reference map

- Judgment call path: `services/ai_nodes/judgment_node.py`
- Narrative call path: `services/ai_nodes/narrative_node.py`
- Opening stream path: `socket/handlers/ai_gm_handlers.py`
- Transition + rewards orchestration: `services/ai_gm_service_v2.py`
- Transition/reward model calls: `services/ai_nodes/act_analysis_node.py`
- Long summary update call: `services/ai_nodes/session_summary_node.py`
- Prompt directory: `backend/app/prompts/`
