import { useState } from "react";
import { Platform, Pressable, Text, View } from "react-native";
import DateTimePicker from "@react-native-community/datetimepicker";
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
  const [open, setOpen] = useState(false);
  const parsed = new Date(`${value}T12:00:00`);
  const date = Number.isFinite(+parsed) ? parsed : new Date();
  return (
    <View style={{ gap: 4, flex: 1 }}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${label}, ${value ? date.toLocaleDateString() : "Choose date"}`}
        onPress={() => setOpen((v) => !v)}
        style={{
          minHeight: 52,
          borderBottomWidth: 1,
          borderColor: colors.border,
          justifyContent: "center",
        }}
      >
        <Text style={{ ...tokens.type.caption, color: colors.textMuted }}>
          {label}
        </Text>
        <Text style={{ ...tokens.type.body, color: colors.text }}>
          {value
            ? date.toLocaleDateString(undefined, {
                day: "numeric",
                month: "short",
                year: "numeric",
              })
            : "Choose date"}
        </Text>
      </Pressable>
      {open && (
        <DateTimePicker
          themeVariant={getColorMode()}
          value={date}
          mode="date"
          display={Platform.OS === "ios" ? "inline" : "default"}
          onChange={(event, next) => {
            if (Platform.OS === "android") setOpen(false);
            if (event.type === "set" && next)
              onChange(
                `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}-${String(next.getDate()).padStart(2, "0")}`,
              );
          }}
        />
      )}
      {open && Platform.OS === "ios" && (
        <Pressable
          accessibilityRole="button"
          onPress={() => {
            if (!value)
              onChange(
                `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`,
              );
            setOpen(false);
          }}
          style={{ minHeight: 48, justifyContent: "center" }}
        >
          <Text style={{ color: colors.primaryDark }}>Done</Text>
        </Pressable>
      )}
    </View>
  );
}
