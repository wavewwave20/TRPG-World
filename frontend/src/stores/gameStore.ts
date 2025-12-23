import { create } from 'zustand';
import type { Character } from '../types/character';

interface GameSession {
  id: number;
  title: string;
  hostUserId: number;
}

interface Participant {
  user_id: number;
  character_id: number;
  character_name: string;
  character?: Character;
}

interface Notification {
  id: string;
  type: 'user_joined' | 'user_left' | 'system' | 'action_submitted' | 'story_committed' | 'error' | 'alert';
  message: string;
  timestamp: Date;
  sessionId?: number;
  userId?: number;
  characterName?: string;
  autoHide?: boolean;
  duration?: number;
}

interface GameStore {
  currentSession: GameSession | null;
  currentCharacter: Character | null;
  participants: Participant[];
  selectedParticipant: Participant | null;
  notifications: Notification[];
  isJudgmentModalOpen: boolean;
  setSession: (session: GameSession | null) => void;
  setCharacter: (character: Character | null) => void;
  setParticipants: (participants: Participant[]) => void;
  setSelectedParticipant: (participant: Participant | null) => void;
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp'>) => void;
  addError: (message: string, duration?: number) => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;
  setJudgmentModalOpen: (open: boolean) => void;
}

export const useGameStore = create<GameStore>((set) => ({
  currentSession: null,
  currentCharacter: null,
  participants: [],
  selectedParticipant: null,
  notifications: [],
  isJudgmentModalOpen: false,
  setSession: (session) => set({ currentSession: session, participants: [], selectedParticipant: null }),
  setCharacter: (character) => set({ currentCharacter: character }),
  setParticipants: (participants) => set({ participants }),
  setSelectedParticipant: (participant) => set({ selectedParticipant: participant }),
  addNotification: (notification) => set((state) => ({
    notifications: [
      ...state.notifications,
      {
        ...notification,
        id: `${Date.now()}-${Math.random()}`,
        timestamp: new Date()
      }
    ]
  })),
  addError: (message: string, duration: number = 5000) => {
    const id = `${Date.now()}-${Math.random()}`;
    set((state) => ({
      notifications: [
        ...state.notifications,
        {
          id,
          type: 'error',
          message,
          timestamp: new Date(),
          autoHide: true,
          duration
        }
      ]
    }));
    
    // Set timeout to auto-dismiss the error notification
    setTimeout(() => {
      set((state) => ({
        notifications: state.notifications.filter(n => n.id !== id)
      }));
    }, duration);
  },
  removeNotification: (id: string) => set((state) => ({
    notifications: state.notifications.filter(n => n.id !== id)
  })),
  clearNotifications: () => set({ notifications: [] }),
  setJudgmentModalOpen: (open: boolean) => set({ isJudgmentModalOpen: open })
}));
