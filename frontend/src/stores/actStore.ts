import { create } from 'zustand';
import type { StoryActInfo, GrowthReward } from '../types/act';

interface ActStore {
  currentAct: StoryActInfo | null;
  isTransitioning: boolean;
  growthRewards: GrowthReward[];
  showGrowthModal: boolean;

  setCurrentAct: (act: StoryActInfo | null) => void;
  setTransitioning: (transitioning: boolean) => void;
  setGrowthRewards: (rewards: GrowthReward[]) => void;
  setShowGrowthModal: (show: boolean) => void;
  clearAct: () => void;
}

export const useActStore = create<ActStore>((set) => ({
  currentAct: null,
  isTransitioning: false,
  growthRewards: [],
  showGrowthModal: false,

  setCurrentAct: (act) => set({ currentAct: act }),
  setTransitioning: (transitioning) => set({ isTransitioning: transitioning }),
  setGrowthRewards: (rewards) => set({ growthRewards: rewards }),
  setShowGrowthModal: (show) => set({ showGrowthModal: show }),
  clearAct: () => set({ currentAct: null, isTransitioning: false, growthRewards: [], showGrowthModal: false }),
}));
