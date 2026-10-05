import { createContext, PropsWithChildren, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { AccessibilityInfo, AppState, Modal, StyleSheet, Text, View } from 'react-native';
import { AVPlaybackStatus, ResizeMode, Video } from 'expo-av';
import { BrandMark } from './BrandMark';
import { colors } from '../theme/colors';
import { tokens } from '../theme/tokens';
import { entryPlayback, visibleWait } from '../ux/motionPolicy';

const assets = { entry: require('../../assets/motion/squiggle-flow.mp4'), wait: require('../../assets/motion/car-racing.mp4') };

export function useReducedMotion() {
  const [reduced, setReduced] = useState<boolean | null>(null);
  useEffect(() => {
    let live = true;
    void AccessibilityInfo.isReduceMotionEnabled().then(value => { if (live) setReduced(value); }).catch(() => { if (live) setReduced(true); });
    const listener = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduced);
    return () => { live = false; listener.remove(); };
  }, []);
  return reduced;
}

/** Stable silent single-player lifecycle. Entry completes naturally, never on API completion. */
function BrandFilm({ mode, onComplete }: { mode: 'entry' | 'wait'; onComplete?: () => void }) {
  const player = useRef<Video>(null);
  const completed = useRef(false);
  const mounted = useRef(true);
  const [failed, setFailed] = useState(false);
  const [ready, setReady] = useState(false);
  const [foreground, setForeground] = useState(AppState.currentState === 'active');
  const reduced = useReducedMotion();
  const playback = entryPlayback(reduced, failed, foreground);
  const finish = useCallback(() => { if (mounted.current && !completed.current) { completed.current = true; onComplete?.(); } }, [onComplete]);
  useEffect(() => {
    mounted.current = true;
    const instance = player;
    const listener = AppState.addEventListener('change', value => setForeground(value === 'active'));
    return () => { mounted.current = false; listener.remove(); void instance.current?.unloadAsync().catch(() => {}); };
  }, []);
  useEffect(() => {
    if (mode !== 'entry' || !foreground) return;
    // Static accessible fallback; failed player must never trap navigation.
    if (playback === 'static') { const timer = setTimeout(finish, 600); return () => clearTimeout(timer); }
    if (reduced === null) return;
    const watchdog = setTimeout(() => { setFailed(true); }, 15_000);
    return () => clearTimeout(watchdog);
  }, [mode, reduced, failed, finish, foreground, playback]);
  const status = useCallback((value: AVPlaybackStatus) => {
    if (value.isLoaded && value.didJustFinish && mode === 'entry') finish();
  }, [finish, mode]);
  return <View style={styles.film} accessibilityLiveRegion="polite">
    <View style={styles.staticBrand}><BrandMark /><Text style={styles.caption}>{mode === 'entry' ? 'Your city is opening.' : 'Putting your plans in motion.'}</Text></View>
    {reduced === false && !failed && <Video ref={player} source={assets[mode]} style={[StyleSheet.absoluteFill, { opacity: ready ? 1 : 0 }]} resizeMode={ResizeMode.COVER}
      shouldPlay={foreground} isMuted volume={0} isLooping={false} useNativeControls={false}
      onReadyForDisplay={() => setReady(true)} onPlaybackStatusUpdate={status} onError={() => setFailed(true)} />}
  </View>;
}

export function BACityEntrySequence({ onComplete }: { onComplete: () => void }) {
  return <View style={styles.entry}><BrandFilm mode="entry" onComplete={onComplete} /></View>;
}

const WaitContext = createContext<(id: symbol, label: string | null) => void>(() => {});
export function BACityLoadingProvider({ children, entryActive = false }: PropsWithChildren<{ entryActive?: boolean }>) {
  const [jobs, setJobs] = useState<Map<symbol, string>>(new Map());
  const [visible, setVisible] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const report = useCallback((id: symbol, label: string | null) => {
    setJobs(previous => { const next = new Map(previous); if (label) next.set(id, label); else next.delete(id); return next; });
  }, []);
  const busy = jobs.size > 0;
  const showWait = visibleWait(busy, visible, entryActive, dismissed);
  useEffect(() => {
    if (!busy || entryActive) { setVisible(false); if (!busy) setDismissed(false); return; }
    const timer = setTimeout(() => setVisible(true), tokens.motion.loadingReveal);
    return () => clearTimeout(timer);
  }, [busy, entryActive]);
  return <WaitContext.Provider value={report}>{children}{showWait && <Modal visible transparent animationType="none" onRequestClose={() => setDismissed(true)}>
    <View style={styles.wait}><BrandFilm mode="wait" /><View style={styles.waitLabel}><Text style={styles.waitText}>{Array.from(jobs.values())[0] || 'Preparing your experience'}</Text><Text style={styles.waitHint} onPress={() => setDismissed(true)} accessibilityRole="button">Continue in background</Text></View></View>
  </Modal>}</WaitContext.Provider>;
}

/** Call only for generation/cold substantial work, never for cached refresh or taps. */
export function useBACityWaiting(active: boolean, label: string) {
  const report = useContext(WaitContext);
  const id = useRef(Symbol('bacity-wait')).current;
  useEffect(() => { report(id, active ? label : null); return () => report(id, null); }, [active, label, id, report]);
}

const styles = StyleSheet.create({
  film: { flex: 1, backgroundColor: colors.background }, staticBrand: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 16 },
  caption: { ...tokens.type.metadata, color: colors.textMuted }, entry: { ...StyleSheet.absoluteFillObject, zIndex: 1000, backgroundColor: colors.background },
  wait: { flex: 1, backgroundColor: colors.background }, waitLabel: { position: 'absolute', bottom: 48, left: 24, right: 24, padding: 20, borderRadius: 24, backgroundColor: colors.surface },
  waitText: { ...tokens.type.section, color: colors.text }, waitHint: { ...tokens.type.action, paddingVertical: 16, color: colors.primaryDark },
});
