import { create } from 'zustand';
import type { JudgmentSummary } from '../services/api';

interface StoryEntry {
  id: number;
  role: 'USER' | 'AI';
  content: string;
  created_at: string;
  judgments?: JudgmentSummary[] | null;
  event_triggered?: boolean;
}

interface StoryStore {
  entries: StoryEntry[];

  setEntries: (entries: StoryEntry[]) => void;
  addEntry: (entry: StoryEntry) => void;
  updateEntry: (entryId: number, patch: Partial<StoryEntry>) => void;
  removeEntry: (entryId: number) => void;
  clearEntries: () => void;
}

export const useStoryStore = create<StoryStore>((set) => ({
  entries: [],
  
  setEntries: (entries) => set({ entries }),
  addEntry: (entry) => set((state) => ({
    entries: [...state.entries, entry]
  })),
  updateEntry: (entryId, patch) => set((state) => ({
    entries: state.entries.map((e) => (e.id === entryId ? { ...e, ...patch } : e)),
  })),
  removeEntry: (entryId) => set((state) => ({
    entries: state.entries.filter((e) => e.id !== entryId),
  })),
  clearEntries: () => set({ entries: [] })
}));
