import { createContext, PropsWithChildren, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { AppState, StyleSheet, Text, View } from 'react-native';
import { useIsFocused } from '@react-navigation/native';
import { router } from 'expo-router';
import Animated, { cancelAnimation, useAnimatedStyle, useReducedMotion, useSharedValue, withTiming } from 'react-native-reanimated';
import { LoadingContext, loadingRegistry } from '../../loading/registry';
import { LoadingPresentation, LOADING_EXIT_MS } from '../../loading/policy';
import { colors } from '../../theme/colors';
import { BrandMark } from '../BrandMark';
import { AnimatedPressable, SkeletonPulse } from '../motion/Motion';
import { RiveCharacter } from './RiveCharacter';

type Entry = { id: symbol; context: LoadingContext };
const Context = createContext<{ add: (entry: Entry) => () => void } | null>(null);
/** One owner across session cache remounts. Explicit pending-without-data only. */
export function LoadingExperienceProvider({ children }: PropsWithChildren) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [visible, setVisible] = useState<Entry>();
  const [active, setActive] = useState(AppState.currentState === 'active');
  const [failed, setFailed] = useState(false);
  const reduced = useReducedMotion();
  const opacity = useSharedValue(0);
  const presentation = useRef<LoadingPresentation>();
  const lastContext = useRef<LoadingContext>();
  const selected = entries.at(-1);
  const add = useCallback((entry: Entry) => {
    setEntries(values => [...values.filter(value => value.id !== entry.id), entry]);
    return () => setEntries(values => values.filter(value => value.id !== entry.id));
  }, []);
  const value = useMemo(() => ({ add }), [add]);
  const fail = useCallback(() => { setFailed(true); if (__DEV__) console.warn('[LoadingExperience] Rive unavailable; using branded fallback'); }, []);
  useEffect(() => {
    const listener = AppState.addEventListener('change', state => setActive(state === 'active'));
    return () => listener.remove();
  }, []);
  useEffect(() => {
    if (!active) { presentation.current?.dispose(); presentation.current = undefined; setVisible(undefined); opacity.value = 0; return; }
    if (selected) {
      lastContext.current = selected.context;
      presentation.current?.dispose(); setVisible(undefined); opacity.value = 0;
      presentation.current = new LoadingPresentation(() => {
        setFailed(false); setVisible(selected);
        opacity.value = withTiming(1, { duration: reduced ? 0 : LOADING_EXIT_MS });
        if (__DEV__) console.debug('[LoadingExperience]', selected.context, 'thresholdPassed=true', loadingRegistry[selected.context].animation);
      }, () => { opacity.value = withTiming(0, { duration: reduced ? 0 : LOADING_EXIT_MS }); }, () => setVisible(undefined), undefined, reduced ? 0 : LOADING_EXIT_MS);
      presentation.current.start();
      return;
    }
    if (__DEV__ && presentation.current) console.debug('[LoadingExperience]', lastContext.current, 'requestComplete=true');
    presentation.current?.complete();
  }, [selected?.id, selected?.context, active, reduced, opacity]);
  useEffect(() => () => { presentation.current?.dispose(); cancelAnimation(opacity); }, [opacity]);
  const stage = useAnimatedStyle(() => ({ opacity: opacity.value, transform: [{ translateY: reduced ? 0 : (1 - opacity.value) * 10 }] }));
  return <Context.Provider value={value}>{children}
    {visible && active && <Animated.View pointerEvents="box-none" style={[styles.overlay, stage]}>
      <View pointerEvents="none" style={styles.stage}>
        <BrandMark compact />
        {failed || reduced ? <SkeletonPulse><View style={styles.fallback} /></SkeletonPulse> : <RiveCharacter animation={loadingRegistry[visible.context].animation} onFailure={fail} />}
        <Text accessibilityRole="text" accessibilityLiveRegion="polite" style={styles.copy}>{loadingRegistry[visible.context].copy}</Text>
      </View>
      {visible.context !== 'startup' && <AnimatedPressable accessibilityRole="button" accessibilityLabel="Go back" style={styles.back} onPress={() => router.canGoBack() ? router.back() : router.replace('/(tabs)/discover')}><Text style={styles.copy}>Back</Text></AnimatedPressable>}
    </Animated.View>}
  </Context.Provider>;
}
export function useMeaningfulLoading(context: LoadingContext, pendingWithoutData: boolean) {
  const provider = useContext(Context);
  const focused = useIsFocused();
  const id = useRef(Symbol(context));
  useEffect(() => {
    if (pendingWithoutData && focused) return provider?.add({ id: id.current, context });
  }, [provider, context, pendingWithoutData, focused]);
}
// Root startup is outside navigation focus; use the same centralized presentation.
export function useStartupLoading(pending: boolean) {
  const provider = useContext(Context);
  const id = useRef(Symbol('startup'));
  useEffect(() => { if (pending) return provider?.add({ id: id.current, context: 'startup' }); }, [pending, provider]);
}
const styles = StyleSheet.create({
  overlay: { ...StyleSheet.absoluteFillObject, backgroundColor: colors.background, zIndex: 100 },
  stage: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 24 },
  copy: { color: colors.textMuted, fontSize: 16, textAlign: 'center' },
  back: { position: 'absolute', top: 64, left: 20, minHeight: 48, minWidth: 64, justifyContent: 'center' },
  fallback: { width: 96, height: 4, borderRadius: 2, backgroundColor: colors.primaryDark },
});
