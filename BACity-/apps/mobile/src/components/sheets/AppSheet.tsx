import { tokens } from "../../theme/tokens";
import { StatusBar } from "expo-status-bar";
import { getColorMode } from "../../theme/colors";
import { PropsWithChildren, useEffect, useRef, useState } from "react";
import {
  AccessibilityInfo,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  Text,
  useWindowDimensions,
  View,
} from "react-native";
import {
  Gesture,
  GestureDetector,
  GestureHandlerRootView,
} from "react-native-gesture-handler";
import Animated, {
  cancelAnimation,
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
} from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { colors } from "../../theme/colors";
import { motion, sheetTarget } from "../../navigation/motion";
import { useThemeRevision } from "../../theme/appearance";
import { useMotionPreference } from "../interactions/useMotionPreference";
import { AppIcon } from "../AppIcon";

export function AppSheet({
  visible,
  title,
  onClose,
  children,
}: PropsWithChildren<{
  visible: boolean;
  title: string;
  onClose: () => void;
}>) {
  useThemeRevision();
  const reduced = useMotionPreference();
  const insets = useSafeAreaInsets();
  const { height, width } = useWindowDimensions();
  const [mounted, setMounted] = useState(visible);
  const maxHeight = Math.min(height * 0.88, 760);
  const offset = useSharedValue(maxHeight);
  const measuredHeight = useSharedValue(maxHeight);
  const start = useSharedValue(0);
  const backdrop = useSharedValue(0);
  const close = () => onClose();
  const previouslyVisible = useRef(false);
  useEffect(() => {
    const opening = visible && !previouslyVisible.current;
    previouslyVisible.current = visible;
    if (visible) {
      setMounted(true);
      if (opening) offset.value = reduced ? 0 : maxHeight;
      const destination = opening
        ? 0
        : sheetTarget(offset.value, 0, [
            0,
            Math.max(0, measuredHeight.value - 160),
          ]);
      offset.value = reduced
        ? destination
        : withSpring(destination, motion.sheet);
      backdrop.value = withTiming(1, { duration: reduced ? 0 : 220 });
    } else {
      offset.value = withTiming(maxHeight, { duration: reduced ? 0 : 220 });
      backdrop.value = withTiming(0, { duration: reduced ? 0 : 220 });
      const timer = setTimeout(() => setMounted(false), reduced ? 0 : 230);
      return () => clearTimeout(timer);
    }
    return () => {
      cancelAnimation(offset);
      cancelAnimation(backdrop);
    };
  }, [visible, reduced, maxHeight, offset, backdrop]);
  const snap = (target: number) => {
    "worklet";
    offset.value = reduced ? target : withSpring(target, motion.sheet);
  };
  const gesture = Gesture.Pan()
    .activeOffsetY([-6, 6])
    .failOffsetX([-24, 24])
    .onBegin(() => {
      cancelAnimation(offset);
      start.value = offset.value;
    })
    .onUpdate((event) => {
      offset.value = Math.max(
        0,
        Math.min(measuredHeight.value, start.value + event.translationY),
      );
    })
    .onEnd((event) => {
      const h = measuredHeight.value;
      const destination = sheetTarget(offset.value, event.velocityY, [
        0,
        Math.max(0, h - 160),
        h,
      ]);
      if (destination === h) runOnJS(close)();
      else snap(destination);
    })
    .onFinalize((event, success) => {
      if (!success)
        snap(
          sheetTarget(offset.value, 0, [
            0,
            Math.max(0, measuredHeight.value - 160),
          ]),
        );
    });
  const panelStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: offset.value }],
  }));
  const shade = useAnimatedStyle(() => ({ opacity: backdrop.value }));
  if (!mounted) return null;
  return (
    <Modal
      visible
      transparent
      animationType="none"
      onRequestClose={onClose}
      statusBarTranslucent
      onShow={() => AccessibilityInfo.announceForAccessibility(title)}
    >
      <StatusBar style={getColorMode() === "dark" ? "light" : "dark"} />
      <GestureHandlerRootView style={{ flex: 1 }}>
        <KeyboardAvoidingView
          style={{ flex: 1 }}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
        >
          <Animated.View
            style={[
              {
                position: "absolute",
                top: 0,
                right: 0,
                bottom: 0,
                left: 0,
                backgroundColor: colors.overlay,
              },
              shade,
            ]}
          >
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Dismiss ${title}`}
              style={{ flex: 1 }}
              onPress={onClose}
            />
          </Animated.View>
          <Animated.View
            onLayout={(event) => {
              measuredHeight.value = event.nativeEvent.layout.height;
            }}
            accessibilityViewIsModal
            style={[
              {
                position: "absolute",
                bottom: 0,
                width: Math.min(width, 760),
                alignSelf: "center",
                maxHeight,
                backgroundColor: colors.background,
                borderTopLeftRadius: 24,
                borderTopRightRadius: 24,
                paddingBottom: Math.max(12, insets.bottom),
              },
              panelStyle,
            ]}
          >
            <GestureDetector gesture={gesture}>
              <Animated.View style={{ paddingHorizontal: 20 }}>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={`Expand or collapse ${title}`}
                  accessibilityActions={[
                    { name: "increment", label: "Expand" },
                    { name: "decrement", label: "Collapse" },
                  ]}
                  onAccessibilityAction={(event) => {
                    offset.value = reduced
                      ? event.nativeEvent.actionName === "increment"
                        ? 0
                        : Math.max(0, measuredHeight.value - 160)
                      : withSpring(
                          event.nativeEvent.actionName === "increment"
                            ? 0
                            : Math.max(0, measuredHeight.value - 160),
                          motion.sheet,
                        );
                  }}
                  onPress={() => {
                    offset.value = reduced
                      ? offset.value > 10
                        ? 0
                        : Math.max(0, measuredHeight.value - 160)
                      : withSpring(
                          offset.value > 10
                            ? 0
                            : Math.max(0, measuredHeight.value - 160),
                          motion.sheet,
                        );
                  }}
                  style={{
                    alignSelf: "center",
                    minHeight: 48,
                    paddingHorizontal: 48,
                    justifyContent: "center",
                  }}
                >
                  <View
                    style={{
                      alignSelf: "center",
                      width: 36,
                      height: 4,
                      backgroundColor: colors.border,
                      borderRadius: 2,
                      marginTop: 8,
                    }}
                  />
                </Pressable>
                <View
                  style={{
                    flexDirection: "row",
                    alignItems: "center",
                    minHeight: 52,
                    gap: 12,
                  }}
                >
                  <Text
                    accessibilityRole="header"
                    style={{
                      ...tokens.type.action,
                      color: colors.text,
                      flex: 1,
                    }}
                  >
                    {title}
                  </Text>
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel="Close menu"
                    onPress={onClose}
                    style={{
                      width: 48,
                      height: 48,
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <AppIcon name="close" size={20} color={colors.textMuted} />
                  </Pressable>
                </View>
              </Animated.View>
            </GestureDetector>
            <ScrollView
              keyboardShouldPersistTaps="handled"
              contentContainerStyle={{
                paddingHorizontal: 20,
                paddingBottom: 20,
                gap: 12,
              }}
              showsVerticalScrollIndicator={false}
            >
              {children}
            </ScrollView>
          </Animated.View>
        </KeyboardAvoidingView>
      </GestureHandlerRootView>
    </Modal>
  );
}
