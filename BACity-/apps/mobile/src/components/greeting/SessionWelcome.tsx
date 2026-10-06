import { useEffect } from 'react';
import { AppState, StyleSheet, Text } from 'react-native';
import Animated, { useAnimatedStyle, useReducedMotion, useSharedValue, withTiming } from 'react-native-reanimated';
import type { Greeting } from '../../greeting/session';
import { colors } from '../../theme/colors';
export function SessionWelcome({ greeting, onComplete }: { greeting: Greeting; onComplete: () => void }) {
  const reduced = useReducedMotion();
  const opacity = useSharedValue(1);
  useEffect(() => {
    const remaining = Math.max(0, greeting.deadline - Date.now());
    const exit = setTimeout(() => { opacity.value = withTiming(0, { duration: reduced ? 0 : 220 }); }, Math.max(0, remaining - 220));
    const deadline = setTimeout(onComplete, remaining);
    const listener = AppState.addEventListener('change', state => { if (state !== 'active') onComplete(); });
    return () => { clearTimeout(exit); clearTimeout(deadline); listener.remove(); };
  }, [greeting.deadline, onComplete, opacity, reduced]);
  const style = useAnimatedStyle(() => ({ opacity: opacity.value, transform: [{ translateY: (1 - opacity.value) * -12 }] }));
  return <Animated.View accessibilityViewIsModal accessibilityLiveRegion="polite" style={[styles.overlay, style]}>
    {/* Neither community asset has a transparent stage. Never show demo art;
        retain the safe greeting until a clean Hello export is supplied. */}
    <Text style={styles.brand}>BACITÝ</Text>
    <Text style={styles.title}>{greeting.kind === 'new' ? 'Welcome to BACITÝ' : 'Welcome back'}</Text>
    {greeting.kind === 'new' && <Text style={styles.subtitle}>Your city awaits.</Text>}
  </Animated.View>;
}
const styles = StyleSheet.create({
  overlay: { ...StyleSheet.absoluteFillObject, zIndex: 10000, backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center', gap: 28, padding: 24 },
  title: { color: colors.text, fontSize: 28, fontWeight: '700', textAlign: 'center' },
  subtitle: { color: colors.textMuted, fontSize: 16 },
  brand: { color: colors.primaryDark, fontSize: 48, fontWeight: '800' },
});
