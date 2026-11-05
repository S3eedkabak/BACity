import Animated, {
  interpolateColor,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";
import { useMotionPreference } from "./useMotionPreference";
import { useThemeRevision } from "../../theme/appearance";
import { useEffect, useState } from "react";
import { Text, TextInput, TextInputProps, View } from "react-native";
import { AnimatedPressable } from "../motion/Motion";
import { colors } from "../../theme/colors";
import { tokens } from "../../theme/tokens";
export function AppTextField({
  label,
  error,
  secure = false,
  ...props
}: TextInputProps & { label: string; error?: string; secure?: boolean }) {
  useThemeRevision();
  const [focused, setFocused] = useState(false);
  const [visible, setVisible] = useState(false);
  const reduced = useMotionPreference(),
    focus = useSharedValue(0);
  useEffect(() => {
    focus.value = withTiming(Number(focused), { duration: reduced ? 0 : 150 });
  }, [focused, reduced, focus]);
  const border = useAnimatedStyle(() => ({
    borderColor: error
      ? colors.danger
      : interpolateColor(
          focus.value,
          [0, 1],
          [colors.border, colors.primaryDark],
        ),
  }));
  return (
    <View style={{ gap: 8 }}>
      <Text
        style={{
          ...tokens.type.metadata,
          color: focused ? colors.primaryDark : colors.textMuted,
        }}
      >
        {label}
      </Text>
      <Animated.View
        style={[
          {
            flexDirection: "row",
            alignItems: "center",
            borderRadius: props.multiline ? 16 : 26,
            borderWidth: 1,
            borderColor: error
              ? colors.danger
              : focused
                ? colors.primaryDark
                : colors.border,
            backgroundColor: colors.surfaceAlt,
          },
          border,
        ]}
      >
        <TextInput
          {...props}
          accessibilityLabel={props.accessibilityLabel ?? label}
          secureTextEntry={secure && !visible}
          placeholderTextColor={colors.textMuted}
          onFocus={(event) => {
            setFocused(true);
            props.onFocus?.(event);
          }}
          onBlur={(event) => {
            setFocused(false);
            props.onBlur?.(event);
          }}
          style={[
            {
              flex: 1,
              minWidth: 0,
              minHeight: 52,
              paddingHorizontal: 16,
              paddingVertical: 12,
              ...tokens.type.body,
              color: colors.text,
            },
            props.multiline && { minHeight: 112, textAlignVertical: "top" },
            props.style,
          ]}
        />
        {secure && (
          <AnimatedPressable
            accessibilityRole="button"
            accessibilityLabel={visible ? "Hide password" : "Show password"}
            aria-pressed={visible}
            accessibilityState={{ checked: visible }}
            onPress={() => setVisible((value) => !value)}
            style={{ minHeight: 48, padding: 12, justifyContent: "center" }}
          >
            <Text style={{ ...tokens.type.caption, color: colors.primaryDark }}>
              {visible ? "Hide" : "Show"}
            </Text>
          </AnimatedPressable>
        )}
      </Animated.View>
      {!!error && (
        <Text
          accessibilityRole="alert"
          style={{ ...tokens.type.caption, color: colors.danger }}
        >
          {error}
        </Text>
      )}
    </View>
  );
}
