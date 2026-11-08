import {
  Children,
  createContext,
  PropsWithChildren,
  useContext,
  useRef,
} from "react";
import { LayoutChangeEvent, Text, View } from "react-native";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
} from "react-native-reanimated";
import { colors } from "../../theme/colors";
import { tokens } from "../../theme/tokens";
import { motion } from "../../navigation/motion";
import { useThemeRevision } from "../../theme/appearance";
import { useMotionPreference } from "./useMotionPreference";
const NavHighlight = createContext<
  ((y: number, height: number, visible: boolean) => void) | null
>(null);
export function useNavRow() {
  const highlight = useContext(NavHighlight),
    box = useRef({ y: 0, height: 48 });
  return {
    onLayout: (event: LayoutChangeEvent) => {
      box.current = {
        y: event.nativeEvent.layout.y,
        height: event.nativeEvent.layout.height,
      };
    },
    onHoverIn: () => highlight?.(box.current.y, box.current.height, true),
    onHoverOut: () => highlight?.(0, 0, false),
    onFocus: () => highlight?.(box.current.y, box.current.height, true),
    onBlur: () => highlight?.(0, 0, false),
    onPressIn: () => highlight?.(box.current.y, box.current.height, true),
    onPressOut: () => highlight?.(0, 0, false),
  };
}
/** One highlight glides between rows, matching the reference's shared hover/focus surface. */
export function SettingsNavList({
  title,
  children,
}: PropsWithChildren<{ title: string }>) {
  useThemeRevision();
  const reduced = useMotionPreference();
  const y = useSharedValue(0),
    height = useSharedValue(48),
    opacity = useSharedValue(0);
  const update = (nextY: number, nextHeight: number, visible: boolean) => {
    if (visible) {
      y.value = reduced ? nextY : withSpring(nextY, motion.surfaceSpring);
      height.value = reduced
        ? nextHeight
        : withSpring(nextHeight, motion.surfaceSpring);
    }
    opacity.value = withTiming(Number(visible), {
      duration: reduced ? 0 : 120,
    });
  };
  const style = useAnimatedStyle(() => ({
    transform: [{ translateY: y.value }],
    height: height.value,
    opacity: opacity.value,
  }));
  if (!Children.toArray(children).length) return null;
  return (
    <View style={{ gap: 6, marginVertical: 8 }}>
      <Text
        accessibilityRole="header"
        style={{ ...tokens.type.metadata, color: colors.textMuted }}
      >
        {title}
      </Text>
      <NavHighlight.Provider value={update}>
        <View style={{ position: "relative", paddingHorizontal: 8 }}>
          <Animated.View
            pointerEvents="none"
            style={[
              {
                position: "absolute",
                left: 0,
                right: 0,
                top: 0,
                borderRadius: 12,
                backgroundColor: colors.surfaceAlt,
              },
              style,
            ]}
          />
          {children}
        </View>
      </NavHighlight.Provider>
    </View>
  );
}
