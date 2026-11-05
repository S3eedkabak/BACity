import { useEffect, useRef } from "react";
import {
  useWindowDimensions,
  StyleSheet,
  StyleProp,
  Text,
  TextStyle,
  View,
} from "react-native";
import Animated, {
  cancelAnimation,
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withTiming,
} from "react-native-reanimated";
import { formatCount } from "../../interactions/policy";
import { tokens } from "../../theme/tokens";
import { colors } from "../../theme/colors";
import { useThemeRevision } from "../../theme/appearance";
import { useMotionPreference } from "./useMotionPreference";
function Reel({
  digit,
  style,
  delay,
  reduced,
}: {
  digit: number;
  style?: StyleProp<TextStyle>;
  delay: number;
  reduced: boolean;
}) {
  const { fontScale } = useWindowDimensions();
  const fontSize =
    StyleSheet.flatten(style)?.fontSize ?? tokens.type.section.fontSize;
  const logicalHeight = Math.ceil(fontSize * 1.2),
    height = logicalHeight * fontScale;
  const position = useSharedValue(reduced ? digit : 0);
  const entered = useRef(false);
  useEffect(() => {
    position.value = reduced
      ? digit
      : withDelay(
          entered.current ? 0 : delay,
          withTiming(digit, {
            duration: 900,
            easing: Easing.out(Easing.cubic),
          }),
        );
    entered.current = true;
    return () => cancelAnimation(position);
  }, [digit, delay, reduced, position]);
  const column = useAnimatedStyle(() => ({
    transform: [{ translateY: -position.value * height }],
  }));
  return (
    <View
      style={{
        height,
        width: fontSize * 0.67 * fontScale,
        overflow: "hidden",
      }}
    >
      <Animated.View style={column}>
        {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((value) => (
          <Text
            key={value}
            style={[
              {
                ...tokens.type.section,
                color: colors.text,
                fontVariant: ["tabular-nums"],
                textAlign: "center",
              },
              style,
              { lineHeight: logicalHeight },
            ]}
          >
            {value}
          </Text>
        ))}
      </Animated.View>
    </View>
  );
}
export function NumberTicker({
  value,
  label,
  style,
  locale,
}: {
  value: number;
  label: string;
  style?: StyleProp<TextStyle>;
  locale?: string;
}) {
  useThemeRevision();
  const reduced = useMotionPreference();
  const formatted = formatCount(value, locale);
  return (
    <View
      accessible
      accessibilityLabel={`${formatted} ${label}`}
      style={{ overflow: "hidden" }}
    >
      <View
        accessible={false}
        aria-hidden
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
        style={{
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {Array.from(formatted).map((character, index) =>
          /\d/.test(character) ? (
            <Reel
              key={formatted.length - index}
              digit={Number(character)}
              style={style}
              delay={index * 40}
              reduced={reduced}
            />
          ) : (
            <Text key={formatted.length - index} style={style}>
              {character}
            </Text>
          ),
        )}
      </View>
    </View>
  );
}
