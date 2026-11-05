import { useEffect, useState } from "react";
import { ScrollView, Text, View } from "react-native";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withSpring,
} from "react-native-reanimated";
import { AnimatedPressable } from "../motion/Motion";
import { colors } from "../../theme/colors";
import { tokens } from "../../theme/tokens";
import { motion } from "../../navigation/motion";
import { useMotionPreference } from "./useMotionPreference";
import { useThemeRevision } from "../../theme/appearance";
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: readonly { id: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  label: string;
}) {
  useThemeRevision();
  const reduced = useMotionPreference();
  const [cells, setCells] = useState<
    Record<string, { x: number; width: number }>
  >({});
  const x = useSharedValue(0),
    width = useSharedValue(0);
  useEffect(() => {
    const target = cells[value];
    if (!target) return;
    x.value = reduced ? target.x : withSpring(target.x, motion.spring);
    width.value = reduced
      ? target.width
      : withSpring(target.width, motion.spring);
  }, [value, cells, reduced, x, width]);
  const indicator = useAnimatedStyle(() => ({
    transform: [{ translateX: x.value }],
    width: width.value,
  }));
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      accessibilityLabel={label}
      contentContainerStyle={{ flexGrow: 1 }}
    >
      <View
        style={{
          flexDirection: "row",
          flexGrow: 1,
          borderBottomWidth: 1,
          borderBottomColor: colors.border,
        }}
      >
        {options.map((option) => (
          <AnimatedPressable
            key={option.id}
            accessibilityRole="tab"
            accessibilityState={{ selected: value === option.id }}
            aria-selected={value === option.id}
            accessibilityLabel={option.label}
            onPress={() => onChange(option.id)}
            onLayout={(event) => {
              const { x, width } = event.nativeEvent.layout;
              setCells((current) =>
                current[option.id]?.x === x &&
                current[option.id]?.width === width
                  ? current
                  : { ...current, [option.id]: { x, width } },
              );
            }}
            style={{
              minHeight: 48,
              minWidth: 48,
              flexGrow: 1,
              paddingHorizontal: 12,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Text
              style={{
                ...tokens.type.metadata,
                color: value === option.id ? colors.text : colors.textMuted,
                fontWeight: value === option.id ? "700" : "500",
              }}
            >
              {option.label}
            </Text>
          </AnimatedPressable>
        ))}
        <Animated.View
          pointerEvents="none"
          style={[
            {
              position: "absolute",
              height: 2,
              left: 0,
              bottom: -1,
              borderRadius: 1,
              backgroundColor: colors.primaryDark,
            },
            indicator,
          ]}
        />
      </View>
    </ScrollView>
  );
}
