import { create } from 'zustand';

export type StoryImageStatus = 'loading' | 'ready' | 'error';

export interface StoryImageState {
  status: StoryImageStatus;
  imageUrl?: string;
  error?: string;
  modelId?: string;
}

interface StoryImageStore {
  byStoryLogId: Record<number, StoryImageState>;
  startGeneration: (storyLogId: number) => void;
  setGenerated: (storyLogId: number, imageUrl: string, modelId?: string) => void;
  setError: (storyLogId: number, error: string) => void;
  clear: () => void;
}

export const useStoryImageStore = create<StoryImageStore>((set) => ({
  byStoryLogId: {},

  startGeneration: (storyLogId) =>
    set((state) => ({
      byStoryLogId: {
        ...state.byStoryLogId,
        [storyLogId]: { status: 'loading' },
      },
    })),

  setGenerated: (storyLogId, imageUrl, modelId) =>
    set((state) => ({
      byStoryLogId: {
        ...state.byStoryLogId,
        [storyLogId]: { status: 'ready', imageUrl, modelId },
      },
    })),

  setError: (storyLogId, error) =>
    set((state) => ({
      byStoryLogId: {
        ...state.byStoryLogId,
        [storyLogId]: { status: 'error', error },
      },
    })),

  clear: () => set({ byStoryLogId: {} }),
}));
