import {
  createContext,
  PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { Text, View } from "react-native";
import Animated, {
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors } from "../../theme/colors";
import { tokens } from "../../theme/tokens";
import { useThemeRevision } from "../../theme/appearance";
import { useMotionPreference } from "./useMotionPreference";
import { DrawCheck } from "./MotionParts";
const FeedbackContext = createContext<(message: string) => void>(() => {});
export const useActionFeedback = () => useContext(FeedbackContext);
/** Neutral completion survives secure logout/cache teardown; it stores no account data. */
export function ActionFeedbackProvider({ children }: PropsWithChildren) {
  useThemeRevision();
  const [notice, setNotice] = useState<{ message: string } | null>(null),
    reduced = useMotionPreference(),
    insets = useSafeAreaInsets(),
    progress = useSharedValue(0);
  const show = useCallback((message: string) => setNotice({ message }), []);
  useEffect(() => {
    if (!notice) return;
    progress.value = reduced ? 1 : 0;
    progress.value = reduced ? 1 : withTiming(1, { duration: 180 });
    const timer = setTimeout(() => setNotice(null), 2400);
    return () => {
      clearTimeout(timer);
      cancelAnimation(progress);
    };
  }, [notice, reduced, progress]);
  const style = useAnimatedStyle(() => ({
    opacity: progress.value,
    transform: [{ translateY: reduced ? 0 : 8 * (1 - progress.value) }],
  }));
  return (
    <FeedbackContext.Provider value={show}>
      {children}
      {notice && (
        <Animated.View
          pointerEvents="none"
          accessibilityRole="alert"
          accessibilityLiveRegion="polite"
          style={[
            {
              position: "absolute",
              bottom: Math.max(insets.bottom, 12) + 12,
              left: 18,
              right: 18,
              padding: 16,
              borderRadius: 16,
              backgroundColor: colors.successSurface,
              flexDirection: "row",
              alignItems: "center",
              gap: 12,
            },
            style,
          ]}
        >
          <DrawCheck visible color={colors.free} duration={250} />
          <Text style={{ ...tokens.type.action, color: colors.text, flex: 1 }}>
            {notice.message}
          </Text>
        </Animated.View>
      )}
    </FeedbackContext.Provider>
  );
}
