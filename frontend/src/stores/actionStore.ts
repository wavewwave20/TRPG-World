import { create } from 'zustand';

interface Action {
  id: number;
  player_id: number;
  character_name: string;
  action_text: string;
  order: number;
}

interface ActionStore {
  pendingActions: Action[];
  actionInputDisabled: boolean;
  queueCount: number;
  
  setPendingActions: (actions: Action[]) => void;
  setActionInputDisabled: (disabled: boolean) => void;
  setQueueCount: (count: number) => void;
  clearQueue: () => void;
}

export const useActionStore = create<ActionStore>((set) => ({
  pendingActions: [],
  actionInputDisabled: false,
  queueCount: 0,
  
  setPendingActions: (actions) => set({ pendingActions: actions }),
  setActionInputDisabled: (disabled) => set({ actionInputDisabled: disabled }),
  setQueueCount: (count) => set({ queueCount: count }),
  clearQueue: () => set({ pendingActions: [], queueCount: 0 })
}));
