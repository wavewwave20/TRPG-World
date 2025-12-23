import { create } from 'zustand';
import type { JudgmentSummary } from '../services/api';

interface StoryEntry {
  id: number;
  role: 'USER' | 'AI';
  content: string;
  created_at: string;
  judgments?: JudgmentSummary[] | null;
}

interface StoryStore {
  entries: StoryEntry[];
  
  setEntries: (entries: StoryEntry[]) => void;
  addEntry: (entry: StoryEntry) => void;
  clearEntries: () => void;
}

export const useStoryStore = create<StoryStore>((set) => ({
  entries: [],
  
  setEntries: (entries) => set({ entries }),
  addEntry: (entry) => set((state) => ({
    entries: [...state.entries, entry]
  })),
  clearEntries: () => set({ entries: [] })
}));
