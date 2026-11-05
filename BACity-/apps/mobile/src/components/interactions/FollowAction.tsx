import { useEffect, useRef, useState } from "react";
import { useWindowDimensions, Text, View } from "react-native";
import { router } from "expo-router";
import { useIsMutating } from "@tanstack/react-query";
import Animated, {
  cancelAnimation,
  interpolateColor,
  useAnimatedStyle,
  useSharedValue,
  withSequence,
  withSpring,
  withTiming,
} from "react-native-reanimated";
import { useFollowAction } from "../../hooks/useSocialActions";
import { AnimatedPressable } from "../motion/Motion";
import { AppIcon } from "../AppIcon";
import { DrawCheck, RollingLabel } from "./MotionParts";
import { useMotionPreference } from "./useMotionPreference";
import { selectionHaptic } from "./haptics";
import { useThemeRevision } from "../../theme/appearance";
import { motion } from "../../navigation/motion";
import { colors } from "../../theme/colors";
import { tokens } from "../../theme/tokens";
export function FollowAction({ type, id }: { type: string; id: string }) {
  useThemeRevision();
  const reduced = useMotionPreference();
  const { fontScale } = useWindowDimensions();
  const { state, mutation, signedIn, toggle } = useFollowAction(type, id);
  const following = !!state.data?.following;
  const [intent, setIntent] = useState(false);
  const previous = useRef(following);
  const busy = useIsMutating({ mutationKey: ["follow-action", type, id] }) > 0;
  const disabled = busy || (signedIn && (state.isPending || state.isError));
  const label = following ? (intent ? "Unfollow" : "Following") : "Follow";
  const progress = useSharedValue(Number(following)),
    width = useSharedValue(92),
    dip = useSharedValue(1),
    intentProgress = useSharedValue(0);
  useEffect(() => {
    progress.value = reduced
      ? Number(following)
      : withTiming(Number(following), { duration: 150 });
    width.value = reduced
      ? label.length * 7.5 * fontScale + 48
      : withSpring(label.length * 7.5 * fontScale + 48, motion.surfaceSpring);
    if (previous.current && !following && !reduced)
      dip.value = withSequence(
        withTiming(0.95, { duration: 100 }),
        withSpring(1, motion.spring),
      );
    previous.current = following;
    return () => {
      cancelAnimation(progress);
      cancelAnimation(width);
      cancelAnimation(dip);
    };
  }, [following, label, fontScale, reduced, progress, width, dip]);
  useEffect(() => {
    intentProgress.value = withTiming(Number(intent), {
      duration: reduced ? 0 : 120,
    });
    return () => cancelAnimation(intentProgress);
  }, [intent, reduced, intentProgress]);
  const checkStyle = useAnimatedStyle(() => ({
    opacity: 1 - intentProgress.value,
  }));
  const crossStyle = useAnimatedStyle(() => ({
    opacity: intentProgress.value,
  }));
  const primary = colors.primary,
    surface = colors.background,
    border = colors.border;
  const morph = useAnimatedStyle(() => ({
    width: width.value,
    transform: [{ scale: dip.value }],
    backgroundColor: interpolateColor(
      progress.value,
      [0, 1],
      [primary, surface],
    ),
    borderColor: interpolateColor(progress.value, [0, 1], [primary, border]),
  }));
  const plus = useAnimatedStyle(() => ({
    opacity: 1 - progress.value,
    transform: [
      { rotate: `${progress.value * 30}deg` },
      { scale: 1 - progress.value * 0.4 },
    ],
  }));
  return (
    <View style={{ minWidth: 124, gap: 4 }}>
      <AnimatedPressable
        feedbackEnabled={false}
        accessibilityRole="button"
        accessibilityLabel={
          state.isError
            ? "Reload follow status"
            : following
              ? "Following · Unfollow"
              : "Follow"
        }
        aria-pressed={following}
        accessibilityState={{
          checked: following,
          busy,
          disabled: busy || (signedIn && state.isPending),
        }}
        disabled={busy || (signedIn && state.isPending)}
        onFocus={() => setIntent(true)}
        onBlur={() => setIntent(false)}
        onHoverIn={() => setIntent(true)}
        onHoverOut={() => setIntent(false)}
        onPressIn={() => {
          if (following) setIntent(true);
          if (!reduced) dip.value = withTiming(0.97, { duration: 100 });
        }}
        onPressOut={() => {
          setIntent(false);
          dip.value = reduced ? 1 : withSpring(1, motion.spring);
        }}
        onPress={() => {
          if (state.isError) {
            void state.refetch();
            return;
          }
          selectionHaptic(reduced);
          setIntent(false);
          signedIn ? toggle() : router.push("/auth");
        }}
        style={[
          {
            minHeight: 48,
            paddingVertical: 12,
            paddingHorizontal: 14,
            borderRadius: 24,
            borderWidth: 1,
            opacity: disabled && !busy ? 0.5 : 1,
          },
          morph,
        ]}
      >
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <View style={{ width: 18, height: 18 }}>
            <Animated.View style={[{ position: "absolute" }, plus]}>
              <AppIcon name="add" size={18} color={colors.white} />
            </Animated.View>
            {following && (
              <>
                <Animated.View style={[{ position: "absolute" }, checkStyle]}>
                  <DrawCheck visible color={colors.text} size={18} />
                </Animated.View>
                <Animated.View style={[{ position: "absolute" }, crossStyle]}>
                  <AppIcon name="close" color={colors.danger} size={18} />
                </Animated.View>
              </>
            )}
          </View>
          <RollingLabel
            duration={intent ? 120 : 300}
            distance={intent ? 0 : 8}
            label={label}
            style={{
              ...tokens.type.metadata,
              color: following
                ? intent
                  ? colors.danger
                  : colors.text
                : colors.white,
            }}
          />
        </View>
      </AnimatedPressable>
      {mutation.isError && (
        <Text
          accessibilityRole="alert"
          style={{ ...tokens.type.caption, color: colors.danger }}
        >
          {mutation.error.message}
        </Text>
      )}
    </View>
  );
}
