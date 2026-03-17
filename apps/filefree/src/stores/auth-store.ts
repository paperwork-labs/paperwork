import { create } from "zustand";
import type { User } from "@/types";

interface AuthState {
  user: User | null;
  csrfToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  setUser: (user: User, csrfToken?: string) => void;
  setCsrfToken: (token: string) => void;
  clearAuth: () => void;
  setLoading: (loading: boolean) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  csrfToken: null,
  isAuthenticated: false,
  isLoading: true,

  setUser: (user, csrfToken) =>
    set((state) => ({
      user,
      isAuthenticated: true,
      isLoading: false,
      csrfToken: csrfToken ?? state.csrfToken,
    })),

  setCsrfToken: (token) => set({ csrfToken: token }),

  clearAuth: () =>
    set({
      user: null,
      csrfToken: null,
      isAuthenticated: false,
      isLoading: false,
    }),

  setLoading: (loading) => set({ isLoading: loading }),
}));
