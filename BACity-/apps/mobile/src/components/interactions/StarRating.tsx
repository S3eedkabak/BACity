import { useEffect, useRef, useState } from "react";
import { Platform, Text, View } from "react-native";
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
import { Burst } from "./MotionParts";
import { colors } from "../../theme/colors";
import { tokens } from "../../theme/tokens";
import { motion } from "../../navigation/motion";
import { useThemeRevision } from "../../theme/appearance";
import { useMotionPreference } from "./useMotionPreference";
import { selectionHaptic } from "./haptics";
function RatingStar({
  rating,
  value,
  preview,
  setPreview,
  onChange,
  disabled,
  label,
}: {
  rating: number;
  value: number;
  preview: number;
  setPreview: (n: number) => void;
  onChange: (n: number) => void;
  disabled: boolean;
  label: string;
}) {
  const reduced = useMotionPreference(),
    selected = rating <= (preview || value);
  const previous = useRef(rating <= value);
  const fill = useSharedValue(Number(selected)),
    scale = useSharedValue(1);
  const [burst, setBurst] = useState(0);
  useEffect(() => {
    fill.value = reduced
      ? Number(selected)
      : selected
        ? withSpring(1, { ...motion.spring, overshootClamping: true })
        : withTiming(0, { duration: 150 });
    if (rating <= value && !previous.current && !reduced) {
      scale.value = withSequence(
        withTiming(0.94, { duration: 70 }),
        withTiming(1.04, { duration: 100 }),
        withTiming(1, { duration: 130 }),
      );
      setBurst((n) => n + 1);
    } else
      scale.value = reduced
        ? 1
        : withSpring(
            preview === rating
              ? 1.05
              : Math.abs(preview - rating) === 1
                ? 1.02
                : 1,
            motion.spring,
          );
    previous.current = rating <= value;
    return () => {
      cancelAnimation(fill);
      cancelAnimation(scale);
    };
  }, [value, selected, preview, rating, reduced, fill, scale]);
  const pop = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  const ink = useAnimatedStyle(() => ({
    opacity: fill.value,
    transform: [{ scale: fill.value }],
  }));
  return (
    <AnimatedPressable
      accessibilityRole={Platform.OS === "web" ? "radio" : "button"}
      aria-checked={value === rating}
      accessibilityLabel={`${label}, ${rating} out of 5`}
      accessibilityState={{
        checked: value === rating,
        selected: value === rating,
        disabled,
      }}
      disabled={disabled}
      onHoverIn={() => setPreview(rating)}
      onHoverOut={() => setPreview(0)}
      onFocus={() => setPreview(rating)}
      onBlur={() => setPreview(0)}
      onPress={() => {
        selectionHaptic(reduced);
        onChange(rating);
      }}
      style={{
        width: 48,
        height: 48,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Burst trigger={burst} color={colors.primaryDark} particles={5} />
      <Animated.View style={pop}>
        <AppIcon name="star-outline" size={26} color={colors.textMuted} />
        <Animated.View style={[{ position: "absolute", top: 0, left: 0 }, ink]}>
          <AppIcon name="star" size={26} color={colors.primaryDark} />
        </Animated.View>
      </Animated.View>
    </AnimatedPressable>
  );
}
export function StarRating({
  value,
  onChange,
  label,
  disabled = false,
}: {
  value: number;
  onChange?: (value: number) => void;
  label: string;
  disabled?: boolean;
}) {
  useThemeRevision();
  const [preview, setPreview] = useState(0);
  if (!onChange)
    return (
      <View
        accessible
        accessibilityLabel={`${label}, ${value.toLocaleString(undefined, { maximumFractionDigits: 1 })} out of 5`}
        style={{ flexDirection: "row", alignItems: "center", gap: 4 }}
      >
        <View
          accessible={false}
          accessibilityElementsHidden
          importantForAccessibility="no-hide-descendants"
          style={{ flexDirection: "row" }}
        >
          {[1, 2, 3, 4, 5].map((star) => (
            <View key={star} style={{ width: 18, height: 18 }}>
              <AppIcon name="star-outline" size={18} color={colors.textMuted} />
              <View
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: Math.min(1, Math.max(0, value - star + 1)) * 18,
                  overflow: "hidden",
                }}
              >
                <AppIcon name="star" size={18} color={colors.primaryDark} />
              </View>
            </View>
          ))}
        </View>
        <Text style={{ ...tokens.type.metadata, color: colors.primaryDark }}>
          {value.toLocaleString(undefined, { maximumFractionDigits: 1 })} / 5
        </Text>
      </View>
    );
  return (
    <View style={{ gap: 4 }}>
      <Text style={{ ...tokens.type.metadata, color: colors.text }}>
        {label}
      </Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap" }}>
        {[1, 2, 3, 4, 5].map((rating) => (
          <RatingStar
            key={rating}
            {...{
              rating,
              value,
              preview,
              setPreview,
              onChange,
              disabled,
              label,
            }}
          />
        ))}
      </View>
    </View>
  );
}
