import { create } from 'zustand';

// Type definitions for judgment data
export type AbilityScore = 'str' | 'dex' | 'con' | 'int' | 'wis' | 'cha';
export type JudgmentStatus = 'waiting' | 'active' | 'rolling' | 'complete';
export type Outcome = 'critical_failure' | 'failure' | 'success' | 'critical_success';

export interface JudgmentSetup {
  action_id: number;
  character_id: number;
  character_name: string;
  action_text: string;
  ability_score: AbilityScore;
  modifier: number;
  difficulty: number;       // DC
  difficulty_reasoning: string;
  status: JudgmentStatus;
  order: number;            // Sequence order
}

export interface JudgmentResult extends JudgmentSetup {
  dice_result: number;      // 1-20
  final_value: number;      // dice_result + modifier
  outcome: Outcome;
  outcome_reasoning: string;
}

interface AIStore {
  // State
  isGenerating: boolean;
  judgments: (JudgmentSetup | JudgmentResult)[];
  currentJudgmentIndex: number;
  currentNarrative: string;
  judgmentHistory: Map<number, JudgmentResult[]>;  // storyLogId -> judgments
  lastDiceRolledAt: number | null; // timestamp to gate next transition
  ackRequiredForActionId: number | null; // require user confirm before moving on (for local player)
  pendingNextIndex: number | null; // store server-sent next index until confirmed
  
  // Actions
  setGenerating: (isGenerating: boolean) => void;
  setJudgmentSetups: (setups: JudgmentSetup[]) => void;
  setCurrentJudgmentIndex: (index: number) => void;
  updateJudgmentResult: (actionId: number, result: Partial<JudgmentResult>) => void;
  setJudgmentRolling: (actionId: number) => void;
  appendNarrativeToken: (token: string) => void;
  clearCurrentNarrative: () => void;
  saveJudgmentsToHistory: (storyLogId: number, judgments: JudgmentResult[]) => void;
  clearJudgments: () => void;
  setLastDiceRolledAt: (ts: number) => void;
  setAckRequired: (actionId: number | null) => void;
  setPendingNextIndex: (idx: number | null) => void;
}

export const useAIStore = create<AIStore>((set) => ({
  // Initial state
  isGenerating: false,
  judgments: [],
  currentJudgmentIndex: 0,
  currentNarrative: '',
  judgmentHistory: new Map(),
  lastDiceRolledAt: null,
  ackRequiredForActionId: null,
  pendingNextIndex: null,
  
  // Actions
  setGenerating: (isGenerating) => set({ isGenerating }),
  
  setJudgmentSetups: (setups) => set({ 
    judgments: setups,
    currentJudgmentIndex: 0
  }),
  
  setCurrentJudgmentIndex: (index) => set({ currentJudgmentIndex: index }),
  
  updateJudgmentResult: (actionId, result) => set((state) => ({
    judgments: state.judgments.map(judgment => 
      judgment.action_id === actionId 
        ? { ...judgment, ...result } as JudgmentResult
        : judgment
    )
  })),
  
  setJudgmentRolling: (actionId) => set((state) => ({
    judgments: state.judgments.map(judgment =>
      judgment.action_id === actionId
        ? { ...judgment, status: 'rolling' as JudgmentStatus }
        : judgment
    )
  })),
  
  appendNarrativeToken: (token) => set((state) => ({
    currentNarrative: state.currentNarrative + token
  })),
  
  clearCurrentNarrative: () => set({ currentNarrative: '' }),
  
  saveJudgmentsToHistory: (storyLogId, judgments) => set((state) => {
    const newHistory = new Map(state.judgmentHistory);
    newHistory.set(storyLogId, judgments);
    return { judgmentHistory: newHistory };
  }),
  
  clearJudgments: () => set({ 
    judgments: [],
    currentJudgmentIndex: 0,
    currentNarrative: '',
    judgmentHistory: new Map(),
    lastDiceRolledAt: null,
    ackRequiredForActionId: null,
    pendingNextIndex: null
  }),

  setLastDiceRolledAt: (ts) => set({ lastDiceRolledAt: ts }),
  setAckRequired: (actionId) => set({ ackRequiredForActionId: actionId }),
  setPendingNextIndex: (idx) => set({ pendingNextIndex: idx })
}));
