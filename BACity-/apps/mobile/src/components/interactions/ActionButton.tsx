import { useEffect, useState } from "react";
import {
  useWindowDimensions,
  StyleProp,
  Text,
  View,
  ViewStyle,
} from "react-native";
import Svg, { Circle } from "react-native-svg";
import Animated, {
  cancelAnimation,
  Easing,
  interpolateColor,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withSpring,
  withTiming,
} from "react-native-reanimated";
import { AnimatedPressable } from "../motion/Motion";
import { AppIcon, type AppIconName } from "../AppIcon";
import { colors } from "../../theme/colors";
import { tokens } from "../../theme/tokens";
import { useThemeRevision } from "../../theme/appearance";
import type { ActionState } from "../../interactions/policy";
import { motion } from "../../navigation/motion";
import { useMotionPreference } from "./useMotionPreference";
import { DrawCheck, RollingLabel } from "./MotionParts";
export function MorphActionButton({
  title,
  onPress,
  state = "idle",
  disabled = false,
  variant = "primary",
  successLabel = "Saved",
  icon,
  style,
  stretch = false,
}: {
  title: string;
  onPress: () => void;
  state?: ActionState;
  disabled?: boolean;
  variant?: "primary" | "secondary" | "danger";
  successLabel?: string;
  icon?: AppIconName;
  style?: StyleProp<ViewStyle>;
  stretch?: boolean;
}) {
  useThemeRevision();
  const reduced = useMotionPreference();
  const [available, setAvailable] = useState(320);
  const busy = state === "loading",
    unavailable = disabled || busy || state === "success";
  const label = busy
    ? `${title}…`
    : state === "success"
      ? successLabel
      : state === "error"
        ? `Retry · ${title}`
        : title;
  const { fontScale: scale } = useWindowDimensions();
  const idleWidth = stretch
    ? available
    : Math.min(available, title.length * 8 * scale + 72);
  const target = busy
    ? 52
    : state === "idle"
      ? idleWidth
      : Math.min(available, label.length * 8 * scale + 72);
  const width = useSharedValue(target),
    progress = useSharedValue(Number(state === "success")),
    shake = useSharedValue(0),
    rotation = useSharedValue(0),
    press = useSharedValue(1);
  useEffect(() => {
    width.value = reduced ? target : withSpring(target, motion.spring);
    progress.value = withTiming(Number(state === "success"), {
      duration: reduced ? 0 : motion.label,
    });
    if (state === "error" && !reduced)
      shake.value = withSequence(
        ...[-1.5, 1.5, 0].map((value) =>
          withTiming(value, { duration: 60 }),
        ),
      );
    rotation.value = 0;
    if (busy && !reduced)
      rotation.value = withRepeat(
        withTiming(360, { duration: 800, easing: Easing.linear }),
        -1,
      );
    return () => {
      cancelAnimation(width);
      cancelAnimation(progress);
      cancelAnimation(shake);
      cancelAnimation(rotation);
    };
  }, [state, target, reduced, busy, width, progress, shake, rotation]);
  const background =
    variant === "primary"
      ? colors.primary
      : variant === "danger"
        ? colors.dangerSurface
        : busy
          ? colors.surfaceAlt
          : "transparent";
  const ink =
    variant === "primary"
      ? colors.white
      : variant === "danger"
        ? colors.danger
        : colors.primaryDark;
  const successBackground = colors.successSurface;
  const morph = useAnimatedStyle(() => ({
    width: width.value,
    borderRadius: 26,
    backgroundColor: interpolateColor(
      progress.value,
      [0, 1],
      [background, successBackground],
    ),
    transform: [{ translateX: shake.value }, { scale: press.value }],
  }));
  const spin = useAnimatedStyle(() => ({
    transform: [{ rotate: `${rotation.value}deg` }],
  }));
  return (
    <View
      onLayout={(event) => setAvailable(event.nativeEvent.layout.width)}
      style={[
        { minHeight: 52, alignSelf: "stretch", justifyContent: "center" },
        style,
      ]}
    >
      <AnimatedPressable
        feedbackEnabled={false}
        onPressIn={() => {
          if (!reduced) press.value = withTiming(0.96, { duration: 100 });
        }}
        onPressOut={() => {
          press.value = reduced ? 1 : withSpring(1, motion.spring);
        }}
        accessibilityRole="button"
        accessibilityLabel={label}
        aria-busy={busy}
        accessibilityState={{ disabled: unavailable, busy }}
        disabled={unavailable}
        onPress={onPress}
        style={[
          {
            minHeight: 52,
            paddingVertical: 12,
            paddingHorizontal: 16,
            alignItems: "center",
            justifyContent: "center",
            opacity: disabled ? 0.5 : 1,
          },
          morph,
        ]}
      >
        <View
          style={{
            flexDirection: "row",
            gap: busy ? 0 : 8,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {busy ? (
            <Animated.View style={spin}>
              <Svg width={20} height={20} viewBox="0 0 24 24">
                <Circle
                  cx={12}
                  cy={12}
                  r={9}
                  fill="none"
                  stroke={ink}
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeDasharray="42 57"
                />
              </Svg>
            </Animated.View>
          ) : state === "success" ? (
            <DrawCheck visible color={colors.free} duration={250} delay={0} />
          ) : (
            <AppIcon
              name={state === "error" ? "close" : (icon ?? "arrow-forward")}
              color={ink}
              size={20}
            />
          )}
          {!busy && (
            <View style={{ flexShrink: 1 }}>
              <RollingLabel
                label={label}
                style={{
                  ...tokens.type.action,
                  color: state === "success" ? colors.free : ink,
                  textAlign: "center",
                }}
              />
            </View>
          )}
        </View>
      </AnimatedPressable>
    </View>
  );
}
