import { useEffect } from 'react';
import { Appearance, StyleSheet } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { setColorMode, getColorMode } from './colors';
export type AppearanceMode = 'system' | 'light' | 'dark';
const KEY = 'bacity.appearance.v1';
let revision = 0;
let storageWrites: Promise<void> = Promise.resolve();
export const useAppearance = create<{ mode: AppearanceMode; version: number; error: string; setMode: (mode: AppearanceMode) => void }>(set => ({
  mode: 'system', version: 0, error: '',
  setMode: mode => {
    revision += 1; setColorMode(mode === 'system' ? Appearance.getColorScheme() === 'light' ? 'light' : 'dark' : mode);
    set(state => ({ mode, version: state.version + 1, error: '' }));
    storageWrites = storageWrites.catch(() => {}).then(() => AsyncStorage.setItem(KEY, mode)).catch(() => { set({ error: 'Appearance changed for this session. Could not save the preference; choose it again to retry.' }); });
  },
}));
setColorMode(Appearance.getColorScheme() === 'light' ? 'light' : 'dark');
export function useAppearanceLifecycle() {
  useEffect(() => {
    const initialRevision = revision; let active = true;
    void AsyncStorage.getItem(KEY).then(value => {
      if (!active || initialRevision !== revision) return;
      if (value === 'light' || value === 'dark' || value === 'system') {
        setColorMode(value === 'system' ? Appearance.getColorScheme() === 'light' ? 'light' : 'dark' : value);
        useAppearance.setState(state => ({ mode: value, version: state.version + 1 }));
      }
    }).catch(() => {});
    const listener = Appearance.addChangeListener(({ colorScheme }) => {
      if (useAppearance.getState().mode !== 'system') return;
      setColorMode(colorScheme === 'light' ? 'light' : 'dark');
      useAppearance.setState(state => ({ version: state.version + 1 }));
    });
    return () => { active = false; listener.remove(); };
  }, []);
}
export function useThemeRevision() { return useAppearance(state => state.version); }
/** Existing module-level sheets become lazy per-theme sheets, without remounting
 * routes or resetting drafts, navigation, query state, scroll, or map gestures. */
export function themedStyles<T extends StyleSheet.NamedStyles<T>>(factory: () => T): T {
  const cache: Partial<Record<'light' | 'dark', T>> = {};
  return new Proxy({} as T, { get(_target, property) {
    const mode = getColorMode();
    const sheet = cache[mode] ?? (cache[mode] = StyleSheet.create(factory()));
    return sheet[property as keyof T];
  } });
}
