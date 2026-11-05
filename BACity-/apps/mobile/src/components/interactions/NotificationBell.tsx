import { useEffect, useRef } from "react";
import { View } from "react-native";
import { router } from "expo-router";
import Svg, { Path } from "react-native-svg";
import Animated, {
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withSequence,
  withSpring,
  withTiming,
} from "react-native-reanimated";
import { useNotificationSummary } from "../../hooks/useNotifications";
import { AnimatedPressable } from "../motion/Motion";
import { NumberTicker } from "./NumberTicker";
import { colors } from "../../theme/colors";
import { motion } from "../../navigation/motion";
import { useMotionPreference } from "./useMotionPreference";
import { useThemeRevision } from "../../theme/appearance";
const times = [90, 120, 110, 100];
export function NotificationBell() {
  useThemeRevision();
  const query = useNotificationSummary();
  const count = query.data?.unread;
  const previous = useRef<number>();
  const reduced = useMotionPreference();
  const angle = useSharedValue(0),
    clapper = useSharedValue(0),
    badge = useSharedValue(count ? 1 : 0),
    ping = useSharedValue(1);
  function ring() {
    if (reduced) return;
    angle.value = withSequence(
      ...[5, -3, 1, 0].map((v, i) =>
        withTiming(v, { duration: times[i] }),
      ),
    );
    clapper.value = withSequence(
      ...[-6, 3, -1, 0].map((v, i) =>
        withTiming(v, { duration: times[i] }),
      ),
    );
  }
  useEffect(() => {
    if (reduced) {
      angle.value = 0;
      clapper.value = 0;
      ping.value = 1;
    }
    badge.value = reduced
      ? Number(!!count)
      : withSpring(Number(!!count), motion.badgeSpring);
    if (
      count !== undefined &&
      previous.current !== undefined &&
      count > previous.current
    ) {
      ring();
      ping.value = 0;
      ping.value = withTiming(1, { duration: reduced ? 0 : motion.bell });
    }
    previous.current = count;
    return () => {
      cancelAnimation(angle);
      cancelAnimation(clapper);
      cancelAnimation(badge);
      cancelAnimation(ping);
    };
  }, [count, reduced]);
  // Translating around the top hinge also works on RN versions without transformOrigin.
  const dome = useAnimatedStyle(() => ({
    transform: [
      { translateY: -8 },
      { rotate: `${angle.value}deg` },
      { translateY: 8 },
    ],
  }));
  const pendulum = useAnimatedStyle(() => ({
    transform: [
      { translateY: -7 },
      { rotate: `${clapper.value}deg` },
      { translateY: 7 },
    ],
  }));
  const badgeStyle = useAnimatedStyle(() => ({
    transform: [{ scale: badge.value }],
    opacity: badge.value,
  }));
  const pingStyle = useAnimatedStyle(() => ({
    opacity: reduced ? 0 : 1 - ping.value,
    transform: [{ scale: 1 + ping.value }],
  }));
  return (
    <AnimatedPressable
      accessibilityRole="button"
      accessibilityLabel={
        query.isError
          ? "Notifications, unread count unavailable"
          : count === undefined
            ? "Notifications"
            : `Notifications, ${count} unread`
      }
      onPress={() => {
        ring();
        router.push("/notifications");
      }}
      style={{
        width: 48,
        height: 48,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Animated.View style={dome}>
        <Svg width={24} height={24} viewBox="0 0 24 24">
          <Path
            d="M4 18h16c-2-2-2-4-2-7a6 6 0 0 0-12 0c0 3 0 5-2 7ZM11 3V2h2v1"
            fill="none"
            stroke={colors.text}
            strokeWidth={1.7}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </Svg>
      </Animated.View>
      <Animated.View style={[{ position: "absolute" }, pendulum]}>
        <Svg width={24} height={24} viewBox="0 0 24 24">
          <Path
            d="M10 21a2.2 2.2 0 0 0 4 0"
            fill="none"
            stroke={colors.text}
            strokeWidth={1.7}
            strokeLinecap="round"
          />
        </Svg>
      </Animated.View>
      {!!count && (
        <Animated.View
          pointerEvents="none"
          style={[
            {
              position: "absolute",
              right: 0,
              top: 0,
              minWidth: 20,
              minHeight: 20,
              paddingHorizontal: 3,
              borderRadius: 12,
              backgroundColor: colors.primary,
              alignItems: "center",
              justifyContent: "center",
            },
            badgeStyle,
          ]}
        >
          <Animated.View
            style={[
              {
                position: "absolute",
                top: 0,
                right: 0,
                bottom: 0,
                left: 0,
                borderRadius: 12,
                borderColor: colors.primary,
                borderWidth: 1,
              },
              pingStyle,
            ]}
          />
          <NumberTicker
            value={count}
            label="unread"
            style={{ fontSize: 10, color: colors.white }}
          />
        </Animated.View>
      )}
    </AnimatedPressable>
  );
}
