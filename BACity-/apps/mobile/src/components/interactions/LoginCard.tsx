import { Children, PropsWithChildren, useEffect, useRef } from "react";
import { Text, View } from "react-native";
import Animated, {
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withTiming,
  LinearTransition,
} from "react-native-reanimated";
import { colors } from "../../theme/colors";
import { tokens } from "../../theme/tokens";
import { useThemeRevision } from "../../theme/appearance";
import { useMotionPreference } from "./useMotionPreference";
function Stage({
  index,
  children,
  identity,
}: PropsWithChildren<{ index: number; identity: string }>) {
  const reduced = useMotionPreference();
  const progress = useSharedValue(reduced ? 1 : 0);
  const previousIdentity = useRef(identity);
  useEffect(() => {
    if (previousIdentity.current !== identity) progress.value = reduced ? 1 : 0;
    previousIdentity.current = identity;
    progress.value = reduced
      ? 1
      : withDelay(Math.min(index, 5) * 100, withTiming(1, { duration: 600 }));
    return () => cancelAnimation(progress);
  }, [identity, reduced, index, progress]);
  const style = useAnimatedStyle(() => ({
    opacity: progress.value,
    transform: [{ translateY: reduced ? 0 : 20 * (1 - progress.value) }],
  }));
  return <Animated.View style={style}>{children}</Animated.View>;
}
/** Presentation only; credentials, sessions, OAuth and error handling stay with the auth flow. */
export function LoginCard({
  title,
  subtitle,
  children,
}: PropsWithChildren<{ title: string; subtitle: string }>) {
  useThemeRevision();
  const reduced = useMotionPreference(),
    entrance = useSharedValue(reduced ? 1 : 0);
  useEffect(() => {
    entrance.value = reduced ? 1 : withTiming(1, { duration: 800 });
    return () => cancelAnimation(entrance);
  }, [reduced, entrance]);
  const entering = useAnimatedStyle(() => ({
    opacity: entrance.value,
    transform: [{ translateY: reduced ? 0 : 20 * (1 - entrance.value) }],
  }));
  return (
    <Animated.View
      layout={reduced ? undefined : LinearTransition.duration(300)}
      style={[
        {
          width: "100%",
          maxWidth: 520,
          alignSelf: "center",
          gap: 20,
          padding: 20,
          marginTop: 20,
          borderRadius: 28,
          backgroundColor: colors.surface,
        },
        entering,
      ]}
    >
      <Stage index={0} identity={title}>
        <View style={{ gap: 8 }}>
          <Text
            accessibilityRole="header"
            style={{
              ...tokens.type.section,
              fontSize: 30,
              lineHeight: 36,
              fontWeight: "400",
              color: colors.text,
            }}
          >
            {title}
          </Text>
          <Text style={{ ...tokens.type.metadata, color: colors.textMuted }}>
            {subtitle}
          </Text>
        </View>
      </Stage>
      <View style={{ gap: 16 }}>
        {Children.toArray(children).map((child, index) => (
          <Stage key={index} index={index + 1} identity={title}>
            {child}
          </Stage>
        ))}
      </View>
    </Animated.View>
  );
}
