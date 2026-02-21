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
    if (get().isTransitioning) return; // 중복 실행 방지

    set({ isTransitioning: true, transitionCompletedTitle: null });

    const startedAt = Date.now();

    const revealTitle = () => {
      const data = get().pendingTransition;
      if (!data) return;
      const title = `${data.newAct.actNumber}막\n${data.newAct.title}${data.newAct.subtitle ? `\n${data.newAct.subtitle}` : ''}`;
      set({ transitionCompletedTitle: title });

      // 타이틀 표시 후 적용/종료
      setTimeout(() => {
        const final = get().pendingTransition || data;
        set({
          currentAct: final.newAct,
          growthRewards: final.rewards,
          showGrowthModal: final.rewards.length > 0,
          pendingTransition: null,
          isTransitioning: false,
          transitionCompletedTitle: null,
        });
      }, 2500);
    };

    // 데이터(act_completed) 도착 대기 + 최소 2200ms 로딩 보장
    const waitForData = () => {
      const pending = get().pendingTransition;
      if (pending && pending.newAct.id !== -1) {
        const remaining = Math.max(0, 2200 - (Date.now() - startedAt));
        setTimeout(revealTitle, remaining);
        return;
      }
      // 60초 타임아웃
      if (Date.now() - startedAt > 60_000) {
        set({ isTransitioning: false, transitionCompletedTitle: null });
        return;
      }
      setTimeout(waitForData, 200);
    };

    waitForData();
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
