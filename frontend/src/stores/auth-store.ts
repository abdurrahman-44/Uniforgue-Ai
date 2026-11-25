"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/types/api";

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  theme: "dark" | "light";
  activeProjectId: string | null;
  setAuth: (user: User, accessToken: string, refreshToken?: string | null) => void;
  setUser: (user: User | null) => void;
  setTheme: (theme: "dark" | "light") => void;
  setActiveProjectId: (projectId: string | null) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      theme: "dark",
      activeProjectId: null,
      setAuth: (user, accessToken, refreshToken = null) =>
        set({ user, accessToken, refreshToken }),
      setUser: (user) => set({ user }),
      setTheme: (theme) => set({ theme }),
      setActiveProjectId: (activeProjectId) => set({ activeProjectId }),
      clearAuth: () =>
        set({ user: null, accessToken: null, refreshToken: null, activeProjectId: null }),
    }),
    {
      name: "uniforge-auth",
    }
  )
);
