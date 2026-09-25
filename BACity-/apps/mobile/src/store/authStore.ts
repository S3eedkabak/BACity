import { create } from "zustand";
import { tokenStorage as SecureStore } from "./tokenStorage";
import { apiRequest } from "../api/client";
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
  completeOAuth: (code: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

async function persistSession(accessToken: string, set: (state: Partial<AuthState>) => void) {
  setSessionToken(accessToken);
  await SecureStore.setItemAsync(TOKEN_KEY, accessToken);
  set({ token: accessToken });
  const user = await authApi.getMe();
  set({ user });
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
      setSessionToken(null);
      set({ token: null, user: null });
    } finally {
      set({ isLoading: false });
    }
  },

  login: async (email, password) => {
    const { access_token } = await authApi.login(email, password);
    await persistSession(access_token, set);
  },

  register: async (email, password, displayName) => {
    await authApi.register(email, password, displayName);
    await get().login(email, password);
  },

  completeOAuth: async (code) => {
    const { access_token } = await authApi.exchangeOAuth(code);
    await persistSession(access_token, set);
  },

  logout: async () => {
    try {
      await apiRequest("/auth/logout", { method: "POST", auth: true });
    } catch {
      // Local logout still succeeds if the API is temporarily unavailable.
    }
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
