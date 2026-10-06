import { router } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Animated, {
  cancelAnimation,
  runOnJS,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withTiming,
} from 'react-native-reanimated';
import { AppIcon, AppIconName } from '../src/components/AppIcon';
import { AnimatedPressable as Pressable } from '../src/components/motion/Motion';
import { useMajorTransition } from '../src/components/loading/LoadingExperience';
import { PlusGateAction } from '../src/plus/usePlusGate';
import type { PlusFeature } from '../src/plus/policy';
import { useRecommendationLocation } from '../src/recommendations/useRecommendationLocation';
import { useAuthStore } from '../src/store/authStore';
import { colors } from '../src/theme/colors';
import { fonts } from '../src/theme/fonts';

type StoryPage = {
  eyebrow: string;
  title: string;
  copy: string;
  icon: AppIconName;
  feature?: PlusFeature;
  action: string;
  route?: '/tonight' | '/evening-plan' | '/weekend-plan' | '/groups' | '/area-watches' | '/(tabs)/explore';
  note?: string;
};

const PAGES: StoryPage[] = [
  { eyebrow: 'BACITÝ+', title: 'Your city,\ncomposed for you.', copy: 'Less searching. More living. Move through the tools BACITÝ can use to build a real plan around you.', icon: 'sparkles', action: 'See what BACITÝ+ can do' },
  { eyebrow: 'TONIGHT / RIGHT NOW', title: 'A good night\nstarts here.', copy: 'A small, realistic set of events happening now, starting soon, or still worth making tonight.', icon: 'moon', feature: 'tonight', action: 'See tonight', route: '/tonight' },
  { eyebrow: 'BUILD MY EVENING', title: 'Tell us the mood.\nWe’ll build the night.', copy: 'Choose your time and interests. BACITÝ combines real events into practical, ordered alternatives.', icon: 'sparkles-outline', feature: 'build_my_evening', action: 'Build my evening', route: '/evening-plan' },
  { eyebrow: 'WEEKEND GENERATOR', title: 'An empty weekend\nis an opportunity.', copy: 'Create a relaxed, culture-heavy, or unexpected weekend using real Bratislava events.', icon: 'sunny-outline', feature: 'weekend_generator', action: 'Generate my weekend', route: '/weekend-plan' },
  { eyebrow: 'EVENT CHAINS', title: 'One event.\nA whole evening.', copy: 'Start from an event you already like and discover what safely fits before and after it.', icon: 'git-network-outline', feature: 'event_chains', action: 'Choose an event', route: '/(tabs)/explore', note: 'Open an event and choose “Build around this event”.' },
  { eyebrow: 'GROUP MATCH', title: 'Stop debating.\nStart deciding.', copy: 'Create a group match with BACITÝ+, then invite anyone to join and vote—even friends without Plus.', icon: 'people-outline', action: 'Open groups', route: '/groups' },
  { eyebrow: 'AREA WATCH', title: 'Keep an eye\non your corner.', copy: 'Choose an area and see newly discovered activity without repeatedly searching for it.', icon: 'radio-outline', feature: 'area_watch', action: 'Open Area Watch', route: '/area-watches' },
  { eyebrow: 'DISCOVERY AROUND YOU', title: 'Better plans from\nwhere you start.', copy: 'Location is optional, approximate, foreground-only, and never stored as history. BACITÝ stays useful without it.', icon: 'navigate-outline', action: 'Done' },
];

function StoryProgress({ state }: { state: 'past' | 'current' | 'future' }) {
  const reduced = useReducedMotion();
  const value = useSharedValue(state === 'past' ? 1 : 0);
  useEffect(() => {
    value.value = state === 'past' ? 1 : state === 'future' ? 0 : withTiming(1, { duration: reduced ? 0 : 430 });
    return () => cancelAnimation(value);
  }, [reduced, state, value]);
  const fill = useAnimatedStyle(() => ({ opacity: state === 'future' ? 0 : .45 + value.value * .55, transform: [{ scaleX: value.value }] }));
  return <View style={styles.segment}><Animated.View style={[styles.segmentFill, fill]} /></View>;
}

export default function PlusExperienceScreen() {
  const { width } = useWindowDimensions();
  const reduced = useReducedMotion();
  const transition = useSharedValue(1);
  const direction = useSharedValue(1);
  const [page, setPage] = useState(0);
  const [outgoing, setOutgoing] = useState<number | null>(null);
  const token = useAuthStore(state => state.token);
  const location = useRecommendationLocation(!!token);
  const major = useMajorTransition();

  useEffect(() => {
    const timer = setTimeout(() => major.finish('bacity-plus'), 0);
    return () => { clearTimeout(timer); major.finish('bacity-plus'); };
  }, [major]);
  useEffect(() => () => cancelAnimation(transition), [transition]);

  const incomingStyle = useAnimatedStyle(() => ({
    opacity: reduced ? 1 : .35 + transition.value * .65,
    transform: [{ translateX: reduced ? 0 : direction.value * (1 - transition.value) * Math.min(width * .28, 120) }, { scale: reduced ? 1 : .97 + transition.value * .03 }],
  }));
  const outgoingStyle = useAnimatedStyle(() => ({
    opacity: reduced ? 0 : 1 - transition.value,
    transform: [{ translateX: reduced ? 0 : -direction.value * transition.value * Math.min(width * .2, 90) }, { scale: reduced ? 1 : 1 - transition.value * .035 }],
  }));
  const atmosphere = useAnimatedStyle(() => ({ transform: [{ translateX: reduced ? 0 : direction.value * (1 - transition.value) * 36 }, { rotate: `${page * 17}deg` }] }));

  function go(next: number) {
    if (next < 0 || next >= PAGES.length || next === page) return;
    direction.value = next > page ? 1 : -1;
    setOutgoing(page);
    setPage(next);
    transition.value = reduced ? 1 : 0;
    transition.value = withTiming(1, { duration: reduced ? 0 : 430 }, finished => {
      if (finished) runOnJS(setOutgoing)(null);
    });
  }

  function open(route?: StoryPage['route']) {
    if (!route) {
      if (page === PAGES.length - 1) router.back();
      else go(page + 1);
      return;
    }
    router.push(route);
  }

  const current = PAGES[page];
  const locationLabel = useMemo(() => {
    if (!token) return 'Sign in to use optional location';
    if (location.status === 'granted') return 'Approximate location is enabled';
    if (location.status === 'blocked') return 'Open settings to allow location';
    if (location.enabled) return 'Retry approximate location';
    return 'Enable optional location';
  }, [location.enabled, location.status, token]);

  const renderPage = (item: StoryPage, index: number) => <View style={styles.pageContent}>
    <View style={[styles.visual, index % 2 === 1 && styles.visualAlt]}>
      <View style={styles.visualRing} />
      <View style={styles.iconDisc}><AppIcon name={item.icon} size={58} color={colors.white} strokeWidth={1.35} /></View>
      <Text style={styles.visualIndex}>{String(index + 1).padStart(2, '0')}</Text>
    </View>
    <View style={styles.copyBlock}>
      <Text style={styles.eyebrow}>{item.eyebrow}</Text>
      <Text style={styles.title}>{item.title}</Text>
      <Text style={styles.copy}>{item.copy}</Text>
      {item.note ? <Text style={styles.note}>{item.note}</Text> : null}
    </View>
  </View>;

  const action = current.feature ? <PlusGateAction feature={current.feature} onAllowed={() => open(current.route)}>
    {({ onPress, loading }) => <Pressable disabled={loading} accessibilityRole="button" onPress={onPress} style={styles.cta}>
      <Text style={styles.ctaText}>{loading ? 'Checking access…' : current.action}</Text><AppIcon name="arrow-forward" color={colors.white} />
    </Pressable>}
  </PlusGateAction> : page === PAGES.length - 1 ? <>
    <Pressable accessibilityRole="button" onPress={() => {
      if (!token) router.push({ pathname: '/auth', params: { mode: 'login' } });
      else if (location.status === 'blocked') void location.openSettings();
      else void (location.enabled ? location.retry() : location.enable());
    }} style={styles.locationAction}><AppIcon name={location.status === 'granted' ? 'navigate' : 'navigate-outline'} size={18} color={colors.primaryDark} /><Text style={styles.locationText}>{locationLabel}</Text></Pressable>
    <Pressable accessibilityRole="button" onPress={() => router.back()} style={styles.cta}><Text style={styles.ctaText}>Return to BACITÝ</Text><AppIcon name="arrow-forward" color={colors.white} /></Pressable>
  </> : <Pressable accessibilityRole="button" onPress={() => open(current.route)} style={styles.cta}>
    <Text style={styles.ctaText}>{current.action}</Text><AppIcon name="arrow-forward" color={colors.white} />
  </Pressable>;

  return <View style={styles.root}>
    <Animated.View pointerEvents="none" style={[styles.atmosphere, atmosphere]} />
    <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
      <View style={styles.progress} accessibilityLabel={`BACity Plus story, page ${page + 1} of ${PAGES.length}`}>
        {PAGES.map((_, index) => <StoryProgress key={index} state={index < page ? 'past' : index === page ? 'current' : 'future'} />)}
      </View>
      <View style={styles.header}><Text style={styles.brand}>BACITÝ+</Text><Pressable accessibilityRole="button" accessibilityLabel="Exit BACity Plus" onPress={() => router.back()} style={styles.close}><AppIcon name="close" size={24} /></Pressable></View>
      <View style={styles.story}>
        <Pressable accessibilityRole="button" accessibilityLabel="Previous BACity Plus page" onPress={() => go(page - 1)} disabled={page === 0} style={styles.leftZone} />
        <Pressable accessibilityRole="button" accessibilityLabel="Next BACity Plus page" onPress={() => go(page + 1)} disabled={page === PAGES.length - 1} style={styles.rightZone} />
        {outgoing != null ? <Animated.View pointerEvents="none" style={[styles.pageLayer, outgoingStyle]}>{renderPage(PAGES[outgoing], outgoing)}</Animated.View> : null}
        <Animated.View pointerEvents="none" style={[styles.pageLayer, incomingStyle]}>{renderPage(current, page)}</Animated.View>
      </View>
      <View style={styles.footer}>{action}<Text style={styles.hint}>{page > 0 ? 'Tap left to go back' : 'Tap right to continue'} · {page + 1}/{PAGES.length}</Text></View>
    </SafeAreaView>
  </View>;
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background, overflow: 'hidden' }, safe: { flex: 1 },
  atmosphere: { position: 'absolute', width: 460, height: 460, borderRadius: 230, backgroundColor: '#4A1530', opacity: .5, top: -170, right: -190 },
  progress: { flexDirection: 'row', gap: 5, paddingHorizontal: 18, paddingTop: 8 }, segment: { flex: 1, height: 3, borderRadius: 2, overflow: 'hidden', backgroundColor: colors.border }, segmentFill: { width: '100%', height: '100%', backgroundColor: colors.primaryDark },
  header: { minHeight: 58, paddingHorizontal: 18, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }, brand: { color: colors.text, fontFamily: fonts.black, fontWeight: '800', fontSize: 17, letterSpacing: 1 }, close: { width: 48, height: 48, alignItems: 'center', justifyContent: 'center' },
  story: { flex: 1, position: 'relative' }, leftZone: { position: 'absolute', zIndex: 3, left: 0, top: 0, bottom: 0, width: '28%' }, rightZone: { position: 'absolute', zIndex: 3, right: 0, top: 0, bottom: 0, width: '28%' }, pageLayer: { ...StyleSheet.absoluteFillObject, zIndex: 2, paddingHorizontal: 24 }, pageContent: { flex: 1, justifyContent: 'space-around', paddingBottom: 8 },
  visual: { alignSelf: 'center', width: 224, height: 224, borderRadius: 72, backgroundColor: colors.primary, transform: [{ rotate: '-5deg' }], alignItems: 'center', justifyContent: 'center', shadowColor: '#000', shadowOpacity: .36, shadowRadius: 24, shadowOffset: { width: 0, height: 14 }, elevation: 12 }, visualAlt: { borderRadius: 112, transform: [{ rotate: '4deg' }], backgroundColor: '#702449' }, visualRing: { position: 'absolute', width: 172, height: 172, borderRadius: 86, borderWidth: 1, borderColor: 'rgba(255,255,255,.28)' }, iconDisc: { width: 110, height: 110, borderRadius: 40, backgroundColor: 'rgba(16,14,18,.3)', alignItems: 'center', justifyContent: 'center' }, visualIndex: { position: 'absolute', right: 20, bottom: 14, color: 'rgba(255,255,255,.55)', fontFamily: fonts.black, fontWeight: '800', fontSize: 24 },
  copyBlock: { maxWidth: 560, width: '100%', alignSelf: 'center' }, eyebrow: { color: colors.primaryDark, fontFamily: fonts.black, fontWeight: '800', fontSize: 11, letterSpacing: 2 }, title: { color: colors.text, fontFamily: fonts.black, fontWeight: '800', fontSize: 37, lineHeight: 39, letterSpacing: -1.5, marginTop: 9 }, copy: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 15, lineHeight: 22, marginTop: 12, maxWidth: 480 }, note: { color: colors.primaryDark, fontFamily: fonts.medium, fontSize: 12, lineHeight: 18, marginTop: 10 },
  footer: { paddingHorizontal: 20, paddingBottom: 8, gap: 9 }, cta: { minHeight: 56, borderRadius: 19, backgroundColor: colors.primary, paddingHorizontal: 19, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }, ctaText: { color: colors.white, fontFamily: fonts.black, fontWeight: '800', fontSize: 14 }, hint: { color: colors.textMuted, textAlign: 'center', fontFamily: fonts.medium, fontSize: 11 }, locationAction: { minHeight: 48, borderRadius: 16, backgroundColor: colors.primarySoft, paddingHorizontal: 16, flexDirection: 'row', alignItems: 'center', gap: 10 }, locationText: { flex: 1, color: colors.text, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 13 },
});
