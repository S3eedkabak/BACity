import { PropsWithChildren } from "react";
import { StyleProp, StyleSheet, View, ViewStyle } from "react-native";
import { colors } from "../../theme/colors";

type Props = PropsWithChildren<{
  style?: StyleProp<ViewStyle>;
  tone?: "surface" | "soft" | "dark";
}>;

export function AceSurface({ children, style, tone = "surface" }: Props) {
  return (
    <View
      style={[
        styles.base,
        tone === "surface" && styles.surface,
        tone === "soft" && styles.soft,
        tone === "dark" && styles.dark,
        style,
      ]}
    >
      <View pointerEvents="none" style={styles.glow} />
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  base: {
    overflow: "hidden",
    borderWidth: 1,
    shadowColor: colors.shadow,
    shadowOpacity: 0.08,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 7 },
    elevation: 3,
  },
  surface: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
  },
  soft: {
    backgroundColor: colors.surfaceAlt,
    borderColor: colors.border,
  },
  dark: {
    backgroundColor: colors.text,
    borderColor: "rgba(255,255,255,0.08)",
  },
  glow: {
    position: "absolute",
    width: 180,
    height: 180,
    borderRadius: 90,
    top: -120,
    right: -70,
    backgroundColor: "rgba(255,127,134,0.08)",
  },
});
