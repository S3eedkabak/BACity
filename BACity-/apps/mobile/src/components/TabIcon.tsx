import { useEffect } from 'react';
import { StyleSheet } from 'react-native';
import Animated, { useAnimatedStyle, useReducedMotion, useSharedValue, withTiming } from 'react-native-reanimated';
import { AppIcon, AppIconName } from './AppIcon';
import { colors } from '../theme/colors';
import { tokens } from '../theme/tokens';

export function TabIcon({ name, color, size, focused }: { name: AppIconName; color: string; size: number; focused: boolean }) {
  const reduced = useReducedMotion();
  const selection = useSharedValue(focused ? 1 : 0);
  useEffect(() => { selection.value = withTiming(focused ? 1 : 0, { duration: reduced ? 0 : tokens.motion.fast }); }, [focused, reduced, selection]);
  const indicator = useAnimatedStyle(() => ({ opacity: selection.value }));
  return <Animated.View style={styles.wrap}>
    <AppIcon name={name} color={color} size={size} strokeWidth={focused ? 2 : 1.7} />
    <Animated.View style={[styles.indicator, indicator]} />
  </Animated.View>;
}
const styles = StyleSheet.create({ wrap: { alignItems: 'center' }, indicator: { position: 'absolute', bottom: -5, height: 3, width: 12, borderRadius: 2, backgroundColor: colors.primaryDark } });
