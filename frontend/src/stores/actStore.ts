import { create } from 'zustand';
import type { StoryActInfo, GrowthReward, ActGrowthHistory } from '../types/act';

interface PendingTransition {
  newAct: StoryActInfo;
  rewards: GrowthReward[];
}

interface ActStore {
  currentAct: StoryActInfo | null;
  isTransitioning: boolean;
  transitionCompletedTitle: string | null;
  pendingTransition: PendingTransition | null;
  growthRewards: GrowthReward[];
  showGrowthModal: boolean;
  growthHistory: ActGrowthHistory[];
  selectedHistoryActId: number | null;

  setCurrentAct: (act: StoryActInfo | null) => void;
  setTransitioning: (transitioning: boolean) => void;
  setTransitionCompletedTitle: (title: string | null) => void;
  setPendingTransition: (transition: PendingTransition | null) => void;
  runPendingTransition: () => void;
  setGrowthRewards: (rewards: GrowthReward[]) => void;
  setShowGrowthModal: (show: boolean) => void;
  setGrowthHistory: (history: ActGrowthHistory[]) => void;
  showHistoryRewards: (actId: number) => void;
  clearAct: () => void;
}

export const useActStore = create<ActStore>((set, get) => ({
  currentAct: null,
  isTransitioning: false,
  transitionCompletedTitle: null,
  pendingTransition: null,
  growthRewards: [],
  showGrowthModal: false,
  growthHistory: [],
  selectedHistoryActId: null,

  setCurrentAct: (act) => set({ currentAct: act }),
  setTransitioning: (transitioning) => set({ isTransitioning: transitioning }),
  setTransitionCompletedTitle: (title) => set({ transitionCompletedTitle: title }),
  setPendingTransition: (transition) => set({ pendingTransition: transition }),
  runPendingTransition: () => {
    const pending = get().pendingTransition;
    if (!pending) return;

    const title = `${pending.newAct.actNumber}막 · ${pending.newAct.title}${pending.newAct.subtitle ? ` ${pending.newAct.subtitle}` : ''}`;
    set({
      isTransitioning: true,
      transitionCompletedTitle: null,
    });

    // 로딩 연출 후 타이틀 표시
    setTimeout(() => {
      set({ transitionCompletedTitle: title });
    }, 2200);

    // 타이틀 표시 후 적용/종료
    setTimeout(() => {
      set({
        currentAct: pending.newAct,
        growthRewards: pending.rewards,
        showGrowthModal: pending.rewards.length > 0,
        pendingTransition: null,
        isTransitioning: false,
        transitionCompletedTitle: null,
      });
    }, 4700);
  },
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
    transitionCompletedTitle: null,
    pendingTransition: null,
    growthRewards: [],
    showGrowthModal: false,
    growthHistory: [],
    selectedHistoryActId: null,
  }),
}));
