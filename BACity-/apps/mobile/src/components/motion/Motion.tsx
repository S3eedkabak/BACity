import { PropsWithChildren, useEffect, useState } from 'react';
import { AppState, Pressable, PressableProps, StyleProp, ViewStyle } from 'react-native';
import Animated, { cancelAnimation, useAnimatedStyle, useReducedMotion, useSharedValue, withDelay, withRepeat, withSpring, withTiming } from 'react-native-reanimated';
import { tokens } from '../../theme/tokens';

const NativePressable = Animated.createAnimatedComponent(Pressable);

/** One press grammar. Nested controls retain their own events/stopPropagation. */
export function AnimatedPressable({ style, onPressIn, onPressOut, disabled, ...props }: PressableProps) {
  const reduced = useReducedMotion();
  const [pressed, setPressed] = useState(false);
  const scale = useSharedValue(1);
  const feedback = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  useEffect(() => { if (disabled || reduced) { scale.value = 1; setPressed(false); } }, [disabled, reduced, scale]);
  return <NativePressable {...props} disabled={disabled}
    onPressIn={event => { setPressed(true); if (!disabled && !reduced) scale.value = withTiming(.975, { duration: tokens.motion.press }); onPressIn?.(event); }}
    onPressOut={event => { setPressed(false); scale.value = reduced ? 1 : withSpring(1, tokens.motion.spring); onPressOut?.(event); }}
    style={[typeof style === 'function' ? style({ pressed }) : style, feedback]} />;
}

/** Bound initial entrance only; never add this to every recycled FlatList row. */
export function Reveal({ children, delay = 0, style }: PropsWithChildren<{ delay?: number; style?: StyleProp<ViewStyle> }>) {
  const reduced = useReducedMotion();
  const progress = useSharedValue(reduced ? 1 : 0);
  useEffect(() => {
    progress.value = reduced ? 1 : withDelay(Math.min(delay, tokens.motion.transition), withTiming(1, { duration: tokens.motion.transition }));
    return () => cancelAnimation(progress);
  }, [delay, reduced, progress]);
  const motion = useAnimatedStyle(() => ({ opacity: progress.value, transform: [{ translateY: reduced ? 0 : (1 - progress.value) * 12 }] }));
  return <Animated.View style={[style, motion]}>{children}</Animated.View>;
}

export function SkeletonPulse({ children, style }: PropsWithChildren<{ style?: StyleProp<ViewStyle> }>) {
  const reduced = useReducedMotion();
  const opacity = useSharedValue(1);
  useEffect(() => {
    const update = (active: boolean) => {
      cancelAnimation(opacity);
      opacity.value = active && !reduced ? tokens.opacity.skeletonLow : 1;
      if (active && !reduced) opacity.value = withRepeat(withTiming(tokens.opacity.skeletonHigh, { duration: tokens.motion.pulse }), -1, true);
    };
    update(AppState.currentState === 'active');
    const listener = AppState.addEventListener('change', state => update(state === 'active'));
    return () => { listener.remove(); cancelAnimation(opacity); };
  }, [reduced, opacity]);
  const pulse = useAnimatedStyle(() => ({ opacity: opacity.value }));
  return <Animated.View style={[style, pulse]} accessibilityLabel="Loading" accessibilityRole="progressbar">{children}</Animated.View>;
}
