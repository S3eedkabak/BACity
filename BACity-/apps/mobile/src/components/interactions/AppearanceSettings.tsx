import { Text, View } from "react-native";
import { useAppearance, type AppearanceMode } from "../../theme/appearance";
import { colors } from "../../theme/colors";
import { tokens } from "../../theme/tokens";
import { AnimatedPressable } from "../motion/Motion";
export function AppearanceSettings() {
  const { mode, setMode, error } = useAppearance();
  return (
    <View style={{ gap: 8 }}>
      <Text
        accessibilityRole="header"
        style={{ ...tokens.type.action, color: colors.text }}
      >
        Appearance
      </Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
        {(["system", "light", "dark"] as AppearanceMode[]).map((value) => (
          <AnimatedPressable
            key={value}
            accessibilityRole="radio"
            aria-checked={value === mode}
            accessibilityState={{ checked: value === mode }}
            onPress={() => setMode(value)}
            style={{
              minHeight: 48,
              padding: 12,
              borderRadius: 16,
              backgroundColor:
                mode === value ? colors.primarySoft : colors.surfaceAlt,
              justifyContent: "center",
            }}
          >
            <Text
              style={{
                ...tokens.type.action,
                color: mode === value ? colors.primaryDark : colors.text,
              }}
            >
              {value === "system"
                ? "Use device setting"
                : value === "light"
                  ? "Light"
                  : "Dark"}
            </Text>
          </AnimatedPressable>
        ))}
      </View>
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
