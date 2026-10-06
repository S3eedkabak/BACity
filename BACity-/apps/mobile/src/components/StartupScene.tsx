import { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { useStartupLoading } from './loading/LoadingExperience';
import { AnimatedPressable } from './motion/Motion';
import { colors } from '../theme/colors';
import { tokens } from '../theme/tokens';
/** No intro/minimum startup duration. Routing/cache readiness remains authoritative. */
export function StartupScene({ ready, onRetry }: { ready: boolean; onRetry: () => void }) {
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useStartupLoading(!ready && !failed);
  useEffect(() => {
    if (ready) { setFailed(false); return; }
    const timer = setTimeout(() => setFailed(true), tokens.motion.startupTimeout);
    return () => clearTimeout(timer);
  }, [ready, attempt]);
  if (!failed || ready) return null;
  return <View style={styles.error}><Text style={styles.text}>BACity could not finish opening.</Text>
    <AnimatedPressable accessibilityRole="button" onPress={() => { setFailed(false); setAttempt(value => value + 1); onRetry(); }} style={styles.retry}><Text style={styles.text}>Try again</Text></AnimatedPressable>
  </View>;
}
const styles = StyleSheet.create({ error: { ...StyleSheet.absoluteFillObject, backgroundColor: colors.background, justifyContent: 'center', alignItems: 'center', gap: 20, zIndex: 90 }, text: { color: colors.text }, retry: { backgroundColor: colors.primary, borderRadius: 12, padding: 20, minHeight: 48 } });
