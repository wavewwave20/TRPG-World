import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthState {
  userId: number | null;
  username: string | null;
  isAuthenticated: boolean;
  login: (userId: number, username: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      userId: null,
      username: null,
      isAuthenticated: false,
      login: (userId: number, username: string) => {
        set({ userId, username, isAuthenticated: true });
      },
      logout: () => {
        set({ userId: null, username: null, isAuthenticated: false });
      },
    }),
    {
      name: 'auth-storage',
    }
  )
);
