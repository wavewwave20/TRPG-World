import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthState {
  userId: number | null;
  username: string | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  login: (userId: number, username: string) => void;
  logout: () => void;
  checkAdmin: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      userId: null,
      username: null,
      isAuthenticated: false,
      isAdmin: false,
      login: (userId: number, username: string) => {
        set({ userId, username, isAuthenticated: true });
        get().checkAdmin();
      },
      logout: () => {
        set({ userId: null, username: null, isAuthenticated: false, isAdmin: false });
      },
      checkAdmin: async () => {
        const { userId } = get();
        if (!userId) {
          set({ isAdmin: false });
          return;
        }
        try {
          const API_BASE_URL = import.meta.env.VITE_API_URL || '';
          const res = await fetch(`${API_BASE_URL}/api/auth/check-admin?user_id=${userId}`);
          if (res.ok) {
            const data = await res.json();
            set({ isAdmin: data.is_admin });
          }
        } catch {
          set({ isAdmin: false });
        }
      },
    }),
    {
      name: 'auth-storage',
    }
  )
);
