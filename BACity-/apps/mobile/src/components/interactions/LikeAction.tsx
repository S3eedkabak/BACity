import { useEffect, useRef, useState } from "react";
import { View } from "react-native";
import Animated, {
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withSequence,
  withSpring,
  withTiming,
} from "react-native-reanimated";
import { AnimatedPressable } from "../motion/Motion";
import { AppIcon } from "../AppIcon";
import { colors } from "../../theme/colors";
import { useThemeRevision } from "../../theme/appearance";
import { motion } from "../../navigation/motion";
import { useMotionPreference } from "./useMotionPreference";
import { selectionHaptic } from "./haptics";
import { Burst } from "./MotionParts";
export function LikeAction({
  active,
  busy = false,
  disabled = false,
  onPress,
  kind = "save",
  label,
}: {
  active: boolean;
  busy?: boolean;
  disabled?: boolean;
  onPress: () => void;
  kind?: "save" | "like";
  label?: string;
}) {
  useThemeRevision();
  const reduced = useMotionPreference();
  const previous = useRef(active);
  const [burst, setBurst] = useState(0);
  const scale = useSharedValue(1),
    fill = useSharedValue(Number(active));
  useEffect(() => {
    fill.value = reduced
      ? Number(active)
      : active
        ? withSpring(1, motion.spring)
        : withTiming(0, { duration: 150 });
    if (active !== previous.current && !reduced) {
      if (active) {
        setBurst((value) => value + 1);
        scale.value = withSequence(
          withTiming(0.94, { duration: 70 }),
          withTiming(1.04, { duration: 100 }),
          withTiming(1, { duration: 130 }),
        );
      } else
        scale.value = withSequence(
          withTiming(0.97, { duration: 100 }),
          withSpring(1, motion.spring),
        );
    }
    if (reduced) scale.value = 1;
    previous.current = active;
    return () => {
      cancelAnimation(scale);
      cancelAnimation(fill);
    };
  }, [active, reduced, scale, fill]);
  const pop = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  const selected = useAnimatedStyle(() => ({
    opacity: fill.value,
    transform: [{ scale: fill.value }],
  }));
  const outline = kind === "save" ? "bookmark-outline" : "heart-outline";
  const solid = kind === "save" ? "bookmark" : "heart";
  return (
    <AnimatedPressable
      accessibilityRole="button"
      accessibilityLabel={
        label ??
        (kind === "save"
          ? active
            ? "Remove from saved events"
            : "Save event"
          : active
            ? "Unlike"
            : "Like")
      }
      aria-pressed={active}
      aria-busy={busy}
      accessibilityState={{ checked: active, busy, disabled: disabled || busy }}
      disabled={disabled || busy}
      onPress={(event) => {
        event.stopPropagation();
        selectionHaptic(reduced);
        onPress();
      }}
      style={{
        width: 48,
        height: 48,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Burst trigger={burst} color={colors.primaryDark} />
      <Animated.View style={pop}>
        <AppIcon name={outline} size={23} color={colors.textMuted} />
        <Animated.View
          style={[{ position: "absolute", top: 0, left: 0 }, selected]}
        >
          <AppIcon name={solid} size={23} color={colors.primaryDark} />
        </Animated.View>
      </Animated.View>
    </AnimatedPressable>
  );
}
