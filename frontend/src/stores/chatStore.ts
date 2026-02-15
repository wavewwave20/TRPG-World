import { create } from 'zustand';

export interface ChatMessage {
  id: string;
  session_id: number;
  user_id: number | null;
  username?: string;
  character_name?: string;
  message: string;
  timestamp: Date;
}

interface ChatStore {
  messages: ChatMessage[];
  addMessage: (msg: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
  clear: () => void;
  clearForSession: (sessionId: number) => void;
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  addMessage: (msg) => set((state) => ({ 
    messages: [...state.messages, { ...msg, id: `${Date.now()}-${Math.random()}`, timestamp: new Date() }] 
  })),
  clear: () => set({ messages: [] }),
  clearForSession: (sessionId) => set((state) => ({
    messages: state.messages.filter(m => m.session_id !== sessionId)
  })),
}));
