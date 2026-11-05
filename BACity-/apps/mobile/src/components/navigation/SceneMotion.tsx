import { Children, PropsWithChildren, useEffect, useLayoutEffect, useRef } from "react";
import { View } from "react-native";
import Animated, { cancelAnimation, Easing, useAnimatedStyle, useSharedValue, withDelay, withTiming } from "react-native-reanimated";
import { useMotionPreference } from "../interactions/useMotionPreference";

/** The screen frame, navigation and scroll position never translate on focus. */
export function TabScene({ children }: PropsWithChildren) {
  return <View style={{ flex: 1 }}>{children}</View>;
}

/** Short, bounded content arrival. Initial mount only; cached pages stay settled. */
export function ContentEntrance({ children, index = 0 }: PropsWithChildren<{ index?: number }>) {
  const reduced = useMotionPreference();
  const progress = useSharedValue(reduced ? 1 : 0);
  const started = useRef(false);
  useLayoutEffect(() => {
    if (reduced) { cancelAnimation(progress); progress.value = 1; }
    else if (!started.current) {
      progress.value = withDelay(Math.min(index, 4) * 25, withTiming(1, { duration: 260, easing: Easing.out(Easing.cubic) }));
    }
    started.current = true;
    // Preference/app-state changes settle content; they never restart it.
  }, [reduced, index, progress]);
  useEffect(() => () => cancelAnimation(progress), [progress]);
  const style = useAnimatedStyle(() => ({
    opacity: progress.value,
    transform: [{ translateY: reduced ? 0 : 6 * (1 - progress.value) }],
  }));
  return <Animated.View style={style}>{children}</Animated.View>;
}

export function ContentStages({ children }: PropsWithChildren) {
  return <>{Children.toArray(children).map((child, index) =>
    <ContentEntrance key={(child as { key?: string }).key ?? index} index={index}>{child}</ContentEntrance>
  )}</>;
}

/** Only an explicit section identity change can animate an already mounted page. */
export function SectionTransition({ children, identity }: PropsWithChildren<{ identity: string }>) {
  const reduced = useMotionPreference();
  const progress = useSharedValue(1);
  const previous = useRef(identity);
  useLayoutEffect(() => {
    const changed = previous.current !== identity;
    previous.current = identity;
    if (reduced) { cancelAnimation(progress); progress.value = 1; }
    else if (changed) {
      progress.value = 0;
      progress.value = withTiming(1, { duration: 220, easing: Easing.out(Easing.cubic) });
    }
  }, [identity, reduced, progress]);
  useEffect(() => () => cancelAnimation(progress), [progress]);
  const style = useAnimatedStyle(() => ({
    opacity: progress.value,
    transform: [{ translateY: reduced ? 0 : (1 - progress.value) * 6 }],
  }));
  return <Animated.View style={style}>{children}</Animated.View>;
}
