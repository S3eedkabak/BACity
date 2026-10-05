import { create } from "zustand";
import { tokenStorage as SecureStore } from "./tokenStorage";
import { apiRequest } from "../api/client";
import * as authApi from "../api/auth";
import { setSessionToken, getSessionRevision } from "./tokenSession";
import { NativeModules, Platform } from "react-native";

const TOKEN_KEY = "bratislava_events_token";
let storageMutation: Promise<void> = Promise.resolve();

function persistStoredToken(token: string | null): Promise<void> {
  const write = storageMutation.catch(() => {}).then(() => token
    ? SecureStore.setItemAsync(TOKEN_KEY, token)
    : SecureStore.deleteItemAsync(TOKEN_KEY));
  storageMutation = write;
  return write;
}

interface AuthState {
  token: string | null;
  user: authApi.UserOut | null;
  isLoading: boolean;
  hydrate: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  completeOAuth: (code: string) => Promise<void>;
  completeNativeOAuth: (provider: "google" | "apple", identityToken: string, authorizationCode?: string | null, displayName?: string | null) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

async function persistSession(accessToken: string, set: (state: Partial<AuthState>) => void) {
  setSessionToken(accessToken);
  const revision = getSessionRevision();
  set({ token: accessToken, user: null });
  await persistStoredToken(accessToken);
  if (revision !== getSessionRevision()) return;
  const user = await authApi.getMe();
  if (revision === getSessionRevision()) set({ user });
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  user: null,
  isLoading: true,

  hydrate: async () => {
    const startingRevision = getSessionRevision();
    let hydratedRevision = startingRevision;
    try {
      await storageMutation.catch(() => {});
      const token = await SecureStore.getItemAsync(TOKEN_KEY);
      if (!token || startingRevision !== getSessionRevision()) return;
      setSessionToken(token);
      hydratedRevision = getSessionRevision();
      set({ token });
      try {
        const user = await authApi.getMe();
        if (hydratedRevision === getSessionRevision()) set({ user });
      } catch {
        if (hydratedRevision !== getSessionRevision()) return;
        await persistStoredToken(null);
        if (hydratedRevision !== getSessionRevision()) return;
        setSessionToken(null);
        set({ token: null, user: null });
      }
    } catch {
      if (hydratedRevision === getSessionRevision()) {
        setSessionToken(null);
        set({ token: null, user: null });
      }
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

  completeNativeOAuth: async (provider, identityToken, authorizationCode, displayName) => {
    const { access_token } = await authApi.nativeOAuth(provider, identityToken, authorizationCode, displayName);
    await persistSession(access_token, set);
  },

  logout: async () => {
    // Capture the old bearer, then clear local identity immediately.
    const logoutRequest = apiRequest("/auth/logout", { method: "POST", auth: true }).catch(() => {});
    setSessionToken(null);
    const logoutRevision = getSessionRevision();
    set({ token: null, user: null });
    try { await persistStoredToken(null); } finally { await logoutRequest; }
    if (logoutRevision === getSessionRevision() && Platform.OS !== "web" && NativeModules.RNGoogleSignin) {
      try { await require("@react-native-google-signin/google-signin").GoogleSignin.signOut(); } catch { /* BACity logout remains authoritative. */ }
    }
  },

  refreshUser: async () => {
    if (!get().token) return;
    const user = await authApi.getMe();
    set({ user });
  },
}));
