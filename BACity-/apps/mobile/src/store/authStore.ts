import { create } from "zustand";
import { tokenStorage as SecureStore } from './tokenStorage';
import { apiRequest } from '../api/client';
import * as authApi from "../api/auth";
import { setSessionToken } from "./tokenSession";

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
    try {
      const token = await SecureStore.getItemAsync(TOKEN_KEY);
      if (!token) return;
      setSessionToken(token);
      set({ token });
      try {
        const user = await authApi.getMe();
        set({ user });
      } catch {
        await SecureStore.deleteItemAsync(TOKEN_KEY);
        setSessionToken(null);
        set({ token: null, user: null });
      }
    } catch {
      // SecureStore can fail before the network request; still release startup.
      setSessionToken(null);
      set({ token: null, user: null });
    } finally {
      set({ isLoading: false });
    }
  },

  login: async (email, password) => {
    const { access_token } = await authApi.login(email, password);
    setSessionToken(access_token);
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
    try { await apiRequest('/auth/logout', { method: 'POST', auth: true }); } catch { /* Always clear this device's session, including expired tokens. */ }
    await SecureStore.deleteItemAsync(TOKEN_KEY);
    setSessionToken(null);
    set({ token: null, user: null });
  },

  refreshUser: async () => {
    if (!get().token) return;
    const user = await authApi.getMe();
    set({ user });
  },
}));
