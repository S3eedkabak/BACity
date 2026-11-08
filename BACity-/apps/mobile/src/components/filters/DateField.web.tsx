import { createElement } from "react";
import { Text, View } from "react-native";
import { colors, getColorMode } from "../../theme/colors";
import { tokens } from "../../theme/tokens";
export function DateField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <View style={{ gap: 4, flex: 1 }}>
      <Text style={{ ...tokens.type.caption, color: colors.textMuted }}>
        {label}
      </Text>
      {createElement("input", {
        "aria-label": label,
        type: "date",
        value,
        onChange: (event: any) => onChange(event.target.value),
        style: {
          minHeight: 48,
          minWidth: 0,
          width: "100%",
          boxSizing: "border-box",
          border: "none",
          borderBottom: `1px solid ${colors.border}`,
          background: colors.surfaceAlt,
          color: colors.text,
          padding: 8,
          font: "inherit",
          colorScheme: getColorMode(),
        },
      })}
    </View>
  );
}
