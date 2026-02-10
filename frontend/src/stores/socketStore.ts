import { create } from 'zustand';
import { io, Socket } from 'socket.io-client';
import { useGameStore } from './gameStore';
import { useAuthStore } from './authStore';
import { registerAllSocketHandlers } from './socket-handlers';

interface SocketStore {
  socket: Socket | null;
  connected: boolean;
  error: string | null;
  connect: () => void;
  disconnect: () => void;
  emit: (event: string, data: any) => void;
  on: (event: string, handler: (data: any) => void) => void;
  off: (event: string, handler?: (data: any) => void) => void;
  joinSession: (sessionId: number, userId: number, characterId: number) => void;
  leaveSession: (sessionId: number, userId: number) => void;
}

export const useSocketStore = create<SocketStore>((set, get) => ({
  socket: null,
  connected: false,
  error: null,

  connect: () => {
    const socketUrl = import.meta.env.VITE_SOCKET_URL || window.location.origin;
    const socket = io(socketUrl, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5,
    });

    // Connection lifecycle events
    socket.on('connect', () => {
      console.log('Socket connected');
      set({ connected: true, error: null });

      // Auto rejoin current session on reconnect
      const session = useGameStore.getState().currentSession;
      const userId = useAuthStore.getState().userId;
      const character = useGameStore.getState().currentCharacter;
      if (session && userId && character) {
        try {
          get().emit('join_session', {
            session_id: session.id,
            user_id: userId,
            character_id: character.id,
          });
        } catch (e) {
          console.warn('Failed to auto rejoin session:', e);
        }
      }
    });

    socket.on('disconnect', (reason) => {
      console.log('Socket disconnected:', reason);
      set({ connected: false });
    });

    socket.on('connect_error', (error) => {
      console.error('Socket connection error:', error);
      set({ connected: false, error: `Connection failed: ${error.message}` });
    });

    socket.on('error', (error) => {
      console.error('Socket error:', error);
      const errorMessage = typeof error === 'string' ? error : error.message || 'An error occurred';
      set({ error: `Socket error: ${errorMessage}` });
      useGameStore.getState().addError(errorMessage);
    });

    // Register all domain-specific event handlers
    registerAllSocketHandlers(socket);

    set({ socket });
  },

  disconnect: () => {
    const { socket } = get();
    if (socket) {
      socket.disconnect();
      set({ socket: null, connected: false, error: null });
    }
  },

  emit: (event: string, data: any) => {
    const { socket } = get();
    if (socket && socket.connected) {
      socket.emit(event, data);
    } else {
      console.warn(`Cannot emit event "${event}": socket not connected`);
    }
  },

  on: (event: string, handler: (data: any) => void) => {
    const { socket } = get();
    if (socket) {
      socket.on(event, handler);
    }
  },

  off: (event: string, handler?: (data: any) => void) => {
    const { socket } = get();
    if (socket) {
      if (handler) {
        socket.off(event, handler);
      } else {
        socket.off(event);
      }
    }
  },

  joinSession: (sessionId: number, userId: number, characterId: number) => {
    const { emit } = get();
    emit('join_session', {
      session_id: sessionId,
      user_id: userId,
      character_id: characterId,
    });
  },

  leaveSession: (sessionId: number, userId: number) => {
    const { emit } = get();
    emit('leave_session', { session_id: sessionId, user_id: userId });
  },
}));
