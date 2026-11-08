import { PropsWithChildren, useEffect, useRef } from "react";
import Animated, {
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";
import { useThemeRevision } from "../../theme/appearance";
import { useMotionPreference } from "../interactions/useMotionPreference";
/** Preserve the entire navigation tree and drafts while appearance changes settle. */
export function ThemeScene({ children }: PropsWithChildren) {
  const revision = useThemeRevision(),
    previous = useRef(revision),
    reduced = useMotionPreference(),
    opacity = useSharedValue(1);
  useEffect(() => {
    if (revision !== previous.current) {
      opacity.value = reduced ? 1 : 0.8;
      opacity.value = reduced ? 1 : withTiming(1, { duration: 240 });
      previous.current = revision;
    }
    return () => cancelAnimation(opacity);
  }, [revision, reduced, opacity]);
  const style = useAnimatedStyle(() => ({ flex: 1, opacity: opacity.value }));
  return <Animated.View style={style}>{children}</Animated.View>;
}
