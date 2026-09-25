import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

// Native credentials use OS-backed storage. Web tokens expire with the tab session.
export const tokenStorage = {
  getItemAsync: async (key: string) => Platform.OS === 'web' ? (typeof window === 'undefined' ? null : window.sessionStorage.getItem(key)) : SecureStore.getItemAsync(key),
  setItemAsync: async (key: string, value: string) => { if (Platform.OS === 'web') window.sessionStorage.setItem(key, value); else await SecureStore.setItemAsync(key, value); },
  deleteItemAsync: async (key: string) => { if (Platform.OS === 'web') { if (typeof window !== 'undefined') window.sessionStorage.removeItem(key); } else await SecureStore.deleteItemAsync(key); },
};
