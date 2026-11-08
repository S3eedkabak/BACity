import { themedStyles, useThemeRevision } from '../../theme/appearance';
import { PropsWithChildren, ReactNode, useCallback, useEffect, useRef, useState } from 'react';
import { AccessibilityInfo, ActivityIndicator, AppState, LayoutChangeEvent, Platform, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { useIsFocused } from '@react-navigation/native';
import Animated, { cancelAnimation, Easing, LinearTransition, runOnJS, useAnimatedStyle, useReducedMotion, useSharedValue, withTiming } from 'react-native-reanimated';
import Svg, { Circle, Defs, Path, Pattern, Rect } from 'react-native-svg';
import { AnimatedPressable as Pressable } from '../motion/Motion';
import { colors } from '../../theme/colors';
import { feedPosition, printDuration, receiptIsComplete } from '../../receipts/presentation';

export const receiptInk = '#29232D';
export const receiptPaper = '#FCF5E9';
export const receiptMono = Platform.OS === 'ios' ? 'Menlo' : 'monospace';
export type ReceiptStage = 'processing' | 'printing' | 'complete';
type Props = PropsWithChildren<{
  title: string; pending: boolean; resultKey: string | null; summary: string;
  processingLabel: string; completeLabel: string; fallback?: ReactNode; onShare?: () => void;
  feedMotion?: 'stepped' | 'smooth';
}>;

function PaperTexture() {
  useThemeRevision();
  return <Svg pointerEvents="none" style={StyleSheet.absoluteFill} width="100%" height="100%" accessibilityElementsHidden>
    <Defs><Pattern id="receipt-grain" width="13" height="11" patternUnits="userSpaceOnUse"><Circle cx="2" cy="3" r=".45" fill="#776650" opacity=".13" /><Path d="M8 8h2" stroke="#776650" opacity=".09" strokeWidth=".5" /></Pattern></Defs>
    <Rect width="100%" height="100%" fill="url(#receipt-grain)" />
  </Svg>;
}
function TearEdge() {
  useThemeRevision();
  const points = Array.from({ length: 29 }, (_, i) => `${i * 12},${i % 2 ? 0 : 6}`).join(' L');
  return <Svg height={7} width="100%" viewBox="0 0 336 7" preserveAspectRatio="none" accessibilityElementsHidden><Path d={`M0 0 L${points} L336 0 Z`} fill={receiptPaper} /></Svg>;
}

/** Inline, data-only printer. It cannot generate plans, fetch events or verify payments. */
export function ReceiptPrinterView({ title, pending, resultKey, summary, processingLabel, completeLabel, children, fallback, onShare, feedMotion = 'stepped' }: Props) {
  useThemeRevision();
  const focused = useIsFocused();
  const systemReduced = useReducedMotion();
  const [reduced, setReduced] = useState(systemReduced);
  const [phase, setPhase] = useState<{ key: string | null; stage: ReceiptStage }>({ key: null, stage: 'processing' });
  const [dismissed, setDismissed] = useState(false);
  const [measurement, setMeasurement] = useState({ key: '', height: 0 });
  const [active, setActive] = useState(AppState.currentState === 'active');
  const { height: screenHeight } = useWindowDimensions();
  const feed = useSharedValue(0);
  const entrance = useSharedValue(0);
  const printed = useRef(new Set<string>());
  const currentKey = useRef(resultKey);
  currentKey.current = resultKey;
  const ready = !pending && !!resultKey;
  const height = measurement.key === resultKey ? measurement.height : 0;
  const cap = Math.max(180, Math.min(520, screenHeight * .58));

  const finish = useCallback((key: string) => {
    if (currentKey.current !== key) return;
    printed.current.add(key);
    if (printed.current.size > 32) printed.current.delete(printed.current.values().next().value!);
    setPhase({ key, stage: 'complete' });
  }, []);
  useEffect(() => {
    let mounted = true;
    void AccessibilityInfo.isReduceMotionEnabled().then(value => { if (mounted) setReduced(value); }).catch(() => {});
    const reduce = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduced);
    const app = AppState.addEventListener('change', value => setActive(value === 'active'));
    return () => { mounted = false; reduce.remove(); app.remove(); };
  }, []);
  useEffect(() => {
    entrance.value = reduced ? 1 : withTiming(1, { duration: 220 });
    return () => cancelAnimation(entrance);
  }, [reduced, entrance]);
  useEffect(() => {
    if (pending) { setDismissed(false); setPhase({ key: null, stage: 'processing' }); feed.value = 0; return; }
    if (!resultKey || !height) return;
    cancelAnimation(feed);
    if (reduced || !active || !focused || printed.current.has(resultKey) || dismissed) {
      feed.value = 1; finish(resultKey); return;
    }
    feed.value = 0;
    setPhase({ key: resultKey, stage: 'printing' });
    feed.value = withTiming(1, { duration: printDuration(height), easing: Easing.linear }, done => { if (done) runOnJS(finish)(resultKey); });
    return () => cancelAnimation(feed);
  }, [pending, resultKey, height, reduced, active, focused, dismissed, feed, finish]);
  useEffect(() => () => { cancelAnimation(feed); currentKey.current = null; }, [feed]);

  const machineMotion = useAnimatedStyle(() => ({ opacity: entrance.value, transform: [{ translateY: reduced ? 0 : (1 - entrance.value) * 8 }] }));
  const paperMotion = useAnimatedStyle(() => ({ opacity: height > 0 ? 1 : 0, transform: [{ translateY: reduced ? 0 : -(1 - feedPosition(feed.value, feedMotion === 'stepped')) * Math.max(0, height - 2) }] }));
  const complete = receiptIsComplete(pending, resultKey, phase.stage === 'complete' ? phase.key : null);
  const label = !ready ? processingLabel : complete ? completeLabel : 'Printing your result';
  const measured = (event: LayoutChangeEvent) => {
    const next = Math.ceil(event.nativeEvent.layout.height);
    if (resultKey && next > 0) {
      if (measurement.key !== resultKey) {
        cancelAnimation(feed);
        feed.value = reduced || !active || !focused || printed.current.has(resultKey) ? 1 : 0;
      }
      setMeasurement(previous => previous.key === resultKey && previous.height === next ? previous : { key: resultKey, height: next });
    }
  };
  function skip() { if (resultKey) { cancelAnimation(feed); feed.value = 1; finish(resultKey); } }

  if (dismissed && !pending && fallback) return <View style={styles.host}>
    <Pressable accessibilityRole="button" onPress={() => setDismissed(false)} style={styles.reopen}><Text style={styles.actionText}>Show printed result</Text><Text style={styles.actionText}>↗</Text></Pressable>
    {fallback}
  </View>;

  return <Animated.View layout={LinearTransition.duration(reduced ? 0 : 220)} style={[styles.host, machineMotion]} testID="receipt-printer">
    <View style={styles.machine}>
      <View style={styles.header}><Text style={styles.brand}>BACity<Text style={styles.plus}>+</Text></Text><Text style={styles.machineLabel}>CITY, COMPOSED</Text>
        {ready && fallback && <Pressable accessibilityRole="button" accessibilityLabel="Show original event cards" onPress={() => setDismissed(true)} style={styles.close}><Text style={styles.closeText}>×</Text></Pressable>}
      </View>
      <View style={styles.screen}>
        <Text style={styles.screenTitle}>{title}</Text>
        <Text style={styles.screenSummary}>{pending ? 'Working with real Bratislava events' : summary}</Text>
        <View style={styles.status} accessibilityLiveRegion="polite" accessibilityLabel={label}>
          {complete ? <View style={styles.doneDot}><Text style={styles.check}>✓</Text></View> : <ActivityIndicator color={colors.primaryDark} size="small" />}
          <Text style={styles.statusText}>{label}</Text>
        </View>
      </View>
      <View style={styles.vents} accessibilityElementsHidden>{Array.from({ length: 7 }, (_, i) => <View key={i} style={styles.vent} />)}</View>
      <View style={styles.slot} accessibilityElementsHidden />
    </View>
    {ready && <View style={styles.output}>
      <View style={[styles.aperture, { height: height ? Math.min(height + 7, cap) : 180 }]}>
        <ScrollView nestedScrollEnabled scrollEnabled={complete && height > cap} showsVerticalScrollIndicator={height > cap} accessibilityLabel="Printed result" style={styles.paperScroll}>
          <Animated.View key={resultKey} onLayout={measured} style={paperMotion} pointerEvents={complete ? 'auto' : 'none'} aria-hidden={!complete} accessibilityElementsHidden={!complete} importantForAccessibility={complete ? 'auto' : 'no-hide-descendants'}>
            <View style={styles.paper}><PaperTexture />{children}</View><TearEdge />
          </Animated.View>
        </ScrollView>
      </View>
      <View pointerEvents="none" style={styles.slotShadow} />
      <View style={styles.actions}>
        {!complete ? <Pressable accessibilityRole="button" onPress={skip} style={styles.action}><Text style={styles.actionText}>Show results now</Text></Pressable> : <>
          {onShare && <Pressable accessibilityRole="button" onPress={onShare} style={styles.action}><Text style={styles.actionText}>Share result ↗</Text></Pressable>}
          {fallback && <Pressable accessibilityRole="button" onPress={() => setDismissed(true)} style={styles.action}><Text style={styles.actionText}>Event cards</Text></Pressable>}
        </>}
      </View>
      {complete && height > cap && <Text style={styles.scrollHint}>Scroll the paper to see the whole result.</Text>}
    </View>}
  </Animated.View>;
}

const styles = themedStyles(() => ({
  host: { width: '100%', maxWidth: 460, alignSelf: 'center', marginTop: 16, marginBottom: 12 },
  machine: { zIndex: 1, borderRadius: 26, borderWidth: 1, borderColor: '#514653', padding: 14, paddingBottom: 30, backgroundColor: '#2D2831', shadowColor: '#000', shadowOpacity: .3, shadowRadius: 18, shadowOffset: { width: 0, height: 10 }, elevation: 5 },
  header: { minHeight: 40, flexDirection: 'row', gap: 8, alignItems: 'center', paddingHorizontal: 3, marginBottom: 12 },
  brand: { color: colors.white, fontWeight: '800', fontSize: 19, letterSpacing: -.8 }, plus: { color: colors.primaryDark },
  machineLabel: { color: colors.textMuted, fontFamily: receiptMono, letterSpacing: 1.4, fontSize: 8, flex: 1, textAlign: 'right' },
  close: { minHeight: 44, minWidth: 44, alignItems: 'center', justifyContent: 'center' }, closeText: { color: colors.textMuted, fontSize: 25 },
  screen: { backgroundColor: '#131015', borderRadius: 14, padding: 19, borderWidth: 1, borderColor: '#09070B', gap: 7 },
  screenTitle: { color: colors.text, fontSize: 17, fontWeight: '700', letterSpacing: -.3 }, screenSummary: { color: colors.textMuted, fontSize: 12, lineHeight: 18 },
  status: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 30, marginTop: 7 }, statusText: { color: colors.primaryDark, fontSize: 12, flex: 1 },
  doneDot: { width: 20, height: 20, borderRadius: 10, backgroundColor: colors.successSurface, alignItems: 'center', justifyContent: 'center' }, check: { color: colors.free, fontSize: 13 },
  vents: { flexDirection: 'row', gap: 4, marginTop: 11, marginLeft: 5 }, vent: { width: 13, height: 2, backgroundColor: '#100C12', borderRadius: 2 },
  slot: { position: 'absolute', left: '7%', right: '7%', bottom: 8, height: 9, backgroundColor: '#070609', borderRadius: 4, borderTopWidth: 2, borderTopColor: '#17121A' },
  output: { zIndex: 2, width: '84%', alignSelf: 'center', marginTop: -12 }, aperture: { overflow: 'hidden' }, paperScroll: { flex: 1 },
  paper: { backgroundColor: receiptPaper, padding: 21, paddingTop: 29, paddingBottom: 25 }, slotShadow: { position: 'absolute', top: 0, left: 0, right: 0, height: 7, backgroundColor: 'rgba(6,4,8,.25)' },
  actions: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 4, marginTop: 12 }, action: { minHeight: 48, paddingHorizontal: 12, justifyContent: 'center' },
  actionText: { color: colors.primaryDark, fontSize: 12, fontWeight: '600' }, reopen: { minHeight: 48, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', borderBottomWidth: 1, borderColor: colors.border, marginBottom: 12 },
  scrollHint: { fontSize: 11, lineHeight: 17, color: colors.textMuted, textAlign: 'center', paddingBottom: 4 },
}));
