import { create } from 'zustand';
import type { StoryActInfo, GrowthReward, ActGrowthHistory } from '../types/act';

interface ActStore {
  currentAct: StoryActInfo | null;
  isTransitioning: boolean;
  growthRewards: GrowthReward[];
  showGrowthModal: boolean;
  growthHistory: ActGrowthHistory[];
  selectedHistoryActId: number | null;

  setCurrentAct: (act: StoryActInfo | null) => void;
  setTransitioning: (transitioning: boolean) => void;
  setGrowthRewards: (rewards: GrowthReward[]) => void;
  setShowGrowthModal: (show: boolean) => void;
  setGrowthHistory: (history: ActGrowthHistory[]) => void;
  showHistoryRewards: (actId: number) => void;
  clearAct: () => void;
}

export const useActStore = create<ActStore>((set, get) => ({
  currentAct: null,
  isTransitioning: false,
  growthRewards: [],
  showGrowthModal: false,
  growthHistory: [],
  selectedHistoryActId: null,

  setCurrentAct: (act) => set({ currentAct: act }),
  setTransitioning: (transitioning) => set({ isTransitioning: transitioning }),
  setGrowthRewards: (rewards) => set({ growthRewards: rewards }),
  setShowGrowthModal: (show) => set(show ? {} : { showGrowthModal: false, selectedHistoryActId: null }),
  setGrowthHistory: (history) => set({ growthHistory: history }),
  showHistoryRewards: (actId) => {
    const entry = get().growthHistory.find((h) => h.actId === actId);
    if (entry) {
      set({
        growthRewards: entry.rewards,
        selectedHistoryActId: actId,
        showGrowthModal: true,
      });
    }
  },
  clearAct: () => set({
    currentAct: null,
    isTransitioning: false,
    growthRewards: [],
    showGrowthModal: false,
    growthHistory: [],
    selectedHistoryActId: null,
  }),
}));
