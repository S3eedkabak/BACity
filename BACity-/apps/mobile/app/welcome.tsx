import { router } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Alert, Linking, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';
import { BrandMark } from '../src/components/BrandMark';
import { AppIcon } from '../src/components/AppIcon';
import { CharacterMood } from '../src/components/illustrations/CharacterScene';
import { OnboardingVideo } from '../src/components/OnboardingVideo';
import Animated, { useAnimatedStyle, useSharedValue, withTiming, useReducedMotion } from 'react-native-reanimated';
import { AnimatedPressable as Pressable, Reveal } from '../src/components/motion/Motion';
import { API_URL } from '../src/api/client';
import * as authApi from '../src/api/auth';
import { colors } from '../src/theme/colors';
import { tokens } from '../src/theme/tokens';

type Provider = 'google' | 'apple';
function ProgressTrack({ active }: { active: boolean }) {
  const reduced = useReducedMotion();
  const progress = useSharedValue(active ? 1 : 0);
  useEffect(() => { progress.value = withTiming(active ? 1 : 0, { duration: reduced ? 0 : 180 }); }, [active, progress, reduced]);
  const fill = useAnimatedStyle(() => ({ opacity: progress.value }));
  return <View style={styles.progressTrack}><Animated.View style={[StyleSheet.absoluteFill, styles.progressActive, fill]} /></View>;
}
function CinematicScrim() {
  return <View pointerEvents="none" style={StyleSheet.absoluteFill} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
    <Svg width="100%" height="100%">
      <Defs><LinearGradient id="onboarding-scrim" x1="0%" y1="0%" x2="0%" y2="100%">
        <Stop offset="0%" stopColor="#100E12" stopOpacity=".12" />
        <Stop offset="20%" stopColor="#100E12" stopOpacity=".06" />
        <Stop offset="45%" stopColor="#100E12" stopOpacity=".10" />
        <Stop offset="60%" stopColor="#100E12" stopOpacity=".32" />
        <Stop offset="75%" stopColor="#100E12" stopOpacity=".72" />
        <Stop offset="90%" stopColor="#100E12" stopOpacity=".96" />
        <Stop offset="100%" stopColor="#2A0F20" stopOpacity="1" />
      </LinearGradient></Defs>
      <Rect width="100%" height="100%" fill="url(#onboarding-scrim)" />
    </Svg>
  </View>;
}
const pages: { title: string; copy: string; mood: CharacterMood; label: string }[] = [
  { title: 'Your city.\nNot another quiet night.', copy: 'Discover real events in Bratislava. A concert, a gallery, a new corner of the city.', mood: 'intro', label: 'DISCOVER' },
  { title: 'Find your kind\nof going out.', copy: 'Music, culture, community. Your interests help BACity surface the things you care about.', mood: 'saved', label: 'MAKE IT YOURS' },
  { title: 'The city is\ncloser than you think.', copy: 'Explore the map or stay citywide. Location is always optional, and only used with your permission.', mood: 'city', label: 'EXPLORE' },
  { title: 'Something is happening.\nCome outside.', copy: 'Save a possibility. Share a plan. Find something worth leaving home for.', mood: 'ready', label: 'YOU’RE READY' },
];

export default function WelcomeScreen() {
  const [page, setPage] = useState(0);
  const [providerBusy, setProviderBusy] = useState<Provider | null>(null);
  const [providers, setProviders] = useState<authApi.OAuthStatus | null>(null);
  const { height } = useWindowDimensions();
  useEffect(() => { authApi.oauthStatus().then(setProviders).catch(() => setProviders(null)); }, []);

  async function continueWith(provider: Provider) {
    setProviderBusy(provider);
    try {
      const status = providers ?? (await authApi.oauthStatus());
      setProviders(status);
      if (!status[provider]) {
        Alert.alert(provider === 'google' ? 'Google sign in needs setup' : 'Apple sign in needs setup',
          'The BACity server is ready for this provider, but its OAuth credentials have not been configured yet.');
        return;
      }
      await Linking.openURL(`${API_URL}/auth/oauth/${provider}/start`);
    } catch (error) {
      Alert.alert('Could not start sign in', error instanceof Error ? error.message : 'Check that the BACity API is running.');
    } finally { setProviderBusy(null); }
  }

  const current = pages[page];
  const last = page === pages.length - 1;
  return <View style={styles.root}>
    <OnboardingVideo />
    <CinematicScrim />
    <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
    <StatusBar style="light" translucent backgroundColor="transparent" />
    <View style={styles.top}><BrandMark compact />
      <Pressable accessibilityRole="button" onPress={() => router.push({ pathname: '/auth', params: { mode: 'login' } })} style={styles.link}><Text style={styles.linkText}>Log in</Text></Pressable>
    </View>
    <View style={styles.progress} accessibilityLabel={`Introduction, step ${page + 1} of ${pages.length}`}>
      {pages.map((_, index) => <ProgressTrack key={index} active={index <= page} />)}
    </View>
    <ScrollView contentContainerStyle={[styles.story, height < 700 && styles.compactStory]} showsVerticalScrollIndicator={false}>
      <Reveal key={`text-${page}`} delay={tokens.motion.stagger}>
        <Text style={styles.eyebrow}>{current.label}</Text>
        <Text style={[styles.title, height < 700 && styles.compactTitle]}>{current.title}</Text>
        <Text style={[styles.copy, height < 700 && styles.compactCopy]}>{current.copy}</Text>
      </Reveal>
    </ScrollView>
    <View style={styles.actions}>
      <Pressable accessibilityRole="button" onPress={() => last ? router.push({ pathname: '/auth', params: { mode: 'register' } }) : setPage(value => value + 1)} style={styles.primary}>
        <Text style={styles.primaryText}>{last ? 'Get started' : 'Continue'}</Text><AppIcon name="arrow-forward" color={colors.white} />
      </Pressable>
      {last && <View style={styles.providers}>{(['google', 'apple'] as const).map(provider => <Pressable key={provider} accessibilityRole="button" accessibilityLabel={`Continue with ${provider === 'google' ? 'Google' : 'Apple'}`} disabled={providerBusy !== null} onPress={() => void continueWith(provider)} style={styles.social}>
        {providerBusy === provider ? <ActivityIndicator color={colors.text} /> : <Text style={styles.socialText}>{provider === 'google' ? 'Google' : 'Apple'}</Text>}
      </Pressable>)}</View>}
      <View style={styles.bottomRow}>
        {page > 0 ? <Pressable accessibilityRole="button" accessibilityLabel="Previous introduction page" onPress={() => setPage(value => value - 1)} style={styles.link}><Text style={styles.linkText}>Back</Text></Pressable> : <View />}
        <Pressable accessibilityRole="button" onPress={() => router.replace('/(tabs)/discover')} style={styles.link}><Text style={styles.muted}>{last ? 'Explore without an account' : 'Skip for now'}</Text></Pressable>
      </View>
    </View>
    </SafeAreaView>
  </View>;
}
const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  safe: { flex: 1, backgroundColor: 'transparent' },
  top: { paddingHorizontal: tokens.layout.gutter, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  progress: { flexDirection: 'row', gap: tokens.space.sm, paddingHorizontal: tokens.layout.gutter, marginTop: tokens.space.md },
  progressTrack: { height: 3, flex: 1, borderRadius: 2, backgroundColor: colors.border },
  progressActive: { backgroundColor: colors.primaryDark },
  story: { flexGrow: 1, justifyContent: 'flex-end', paddingHorizontal: tokens.space.xl, paddingTop: 180, paddingBottom: tokens.space.md, width: '100%', maxWidth: tokens.layout.maxWidth, alignSelf: 'center' },
  compactStory: { paddingHorizontal: 20, paddingTop: 100, paddingBottom: 8 },
  compactTitle: { fontSize: 27, lineHeight: 30 },
  compactCopy: { fontSize: 14, lineHeight: 20, marginTop: 8 },
  eyebrow: { ...tokens.type.caption, letterSpacing: 2, color: colors.primaryDark, marginBottom: tokens.space.md },
  title: { ...tokens.type.hero, color: colors.text },
  copy: { ...tokens.type.body, color: colors.textMuted, marginTop: tokens.space.md },
  actions: { paddingHorizontal: tokens.layout.gutter, paddingTop: tokens.space.md, paddingBottom: tokens.space.sm, gap: tokens.space.md, maxWidth: tokens.layout.maxWidth, width: '100%', alignSelf: 'center' },
  primary: { minHeight: 56, paddingHorizontal: tokens.space.lg, borderRadius: tokens.radius.md, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: colors.primary },
  primaryText: { ...tokens.type.action, color: colors.white },
  providers: { flexDirection: 'row', gap: tokens.space.md },
  social: { flex: 1, minHeight: tokens.icon.touch, backgroundColor: colors.surfaceAlt, alignItems: 'center', justifyContent: 'center', borderRadius: tokens.radius.sm },
  socialText: { ...tokens.type.action, color: colors.text },
  bottomRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  link: { minHeight: tokens.icon.touch, justifyContent: 'center', paddingHorizontal: tokens.space.sm },
  linkText: { ...tokens.type.action, color: colors.text },
  muted: { ...tokens.type.metadata, color: colors.textMuted },
});
