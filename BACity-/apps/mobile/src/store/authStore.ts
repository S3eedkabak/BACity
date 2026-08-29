/**
 * Auth state (spec section 37). Zustand for the in-memory store, Expo
 * SecureStore so the JWT survives an app restart. Deliberately minimal —
 * no refresh tokens yet, matching the backend's single-token JWT flow
 * (services/api/app/core/security.py).
 */
import { create } from "zustand";
import * as SecureStore from "expo-secure-store";
import * as authApi from "../api/auth";

const TOKEN_KEY = "bratislava_events_token";

interface AuthState {
  token: string | null;
  user: authApi.UserOut | null;
  isLoading: boolean;
  hydrate: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  user: null,
  isLoading: true,

  hydrate: async () => {
    const token = await SecureStore.getItemAsync(TOKEN_KEY);
    if (token) {
      set({ token });
      try {
        const user = await authApi.getMe();
        set({ user });
      } catch {
        // stored token is invalid/expired — drop it
        await SecureStore.deleteItemAsync(TOKEN_KEY);
        set({ token: null, user: null });
      }
    }
    set({ isLoading: false });
  },

  login: async (email, password) => {
    const { access_token } = await authApi.login(email, password);
    await SecureStore.setItemAsync(TOKEN_KEY, access_token);
    set({ token: access_token });
    const user = await authApi.getMe();
    set({ user });
  },

  register: async (email, password, displayName) => {
    await authApi.register(email, password, displayName);
    await get().login(email, password);
  },

  logout: async () => {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
    set({ token: null, user: null });
  },

  refreshUser: async () => {
    if (!get().token) return;
    const user = await authApi.getMe();
    set({ user });
  },
}));