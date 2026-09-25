import { PropsWithChildren } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { BrandMark } from "./BrandMark";
import { colors } from "../theme/colors";
import { fonts } from "../theme/fonts";

export function Page({ title, children }: PropsWithChildren<{ title: string }>) {
  return (
    <SafeAreaView style={ui.safe} edges={["top"]}>
      <ScrollView
        contentContainerStyle={ui.page}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={ui.topbar}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Go back"
            onPress={() => router.back()}
            style={({ pressed }) => [ui.back, pressed && ui.pressed]}
          >
            <Ionicons name="chevron-back" size={20} color={colors.text} />
          </Pressable>
          <BrandMark compact />
          <View style={ui.topbarSpacer} />
        </View>
        <Text accessibilityRole="header" style={ui.title}>
          {title}
        </Text>
        {children}
      </ScrollView>
    </SafeAreaView>
  );
}

export function Card({ children }: PropsWithChildren) {
  return <View style={ui.card}>{children}</View>;
}

export function Button({
  title,
  onPress,
  busy = false,
}: {
  title: string;
  onPress: () => void;
  busy?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={busy}
      onPress={onPress}
      style={({ pressed }) => [
        ui.button,
        pressed && ui.buttonPressed,
        busy && ui.disabled,
      ]}
    >
      {busy ? (
        <ActivityIndicator color={colors.white} />
      ) : (
        <Text style={ui.buttonText}>{title}</Text>
      )}
    </Pressable>
  );
}

export function Field({
  label,
  value,
  onChange,
  multiline,
  secure,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
  secure?: boolean;
}) {
  return (
    <View style={ui.field}>
      <Text style={ui.label}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        value={value}
        onChangeText={onChange}
        multiline={multiline}
        secureTextEntry={secure}
        autoCapitalize="none"
        placeholderTextColor={colors.textMuted}
        style={[ui.input, multiline && ui.inputMultiline]}
      />
    </View>
  );
}

export function Chip({
  title,
  active = false,
  onPress,
}: {
  title: string;
  active?: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      onPress={onPress}
      style={({ pressed }) => [
        ui.chip,
        active && ui.chipActive,
        pressed && ui.pressed,
      ]}
    >
      <Text style={[ui.chipText, active && ui.chipTextActive]}>{title}</Text>
    </Pressable>
  );
}

export function Notice({ text }: { text: string | null | undefined }) {
  return text ? (
    <View style={ui.noticeBox}>
      <Ionicons name="information-circle-outline" size={17} color={colors.primaryDark} />
      <Text accessibilityRole="alert" style={ui.notice}>
        {text}
      </Text>
    </View>
  ) : null;
}

export const ui = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  page: {
    paddingHorizontal: 18,
    gap: 14,
    backgroundColor: colors.background,
    flexGrow: 1,
    paddingBottom: 72,
  },
  topbar: {
    minHeight: 52,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  back: {
    width: 40,
    height: 40,
    borderRadius: 15,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  pressed: { opacity: 0.7, transform: [{ scale: 0.96 }] },
  topbarSpacer: { width: 40 },
  title: {
    fontSize: 31,
    lineHeight: 35,
    letterSpacing: -1,
    fontFamily: fonts.black,
    color: colors.text,
    marginTop: 4,
    marginBottom: 2,
  },
  heading: {
    fontSize: 18,
    lineHeight: 22,
    fontFamily: fonts.black,
    color: colors.text,
    letterSpacing: -0.35,
  },
  text: {
    fontSize: 14,
    lineHeight: 21,
    fontFamily: fonts.regular,
    color: colors.text,
  },
  muted: {
    fontSize: 12,
    lineHeight: 18,
    fontFamily: fonts.regular,
    color: colors.textMuted,
  },
  card: {
    padding: 16,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    gap: 11,
    shadowColor: colors.shadow,
    shadowOpacity: 0.08,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 7 },
    elevation: 2,
  },
  field: { gap: 7 },
  label: {
    color: colors.textMuted,
    fontFamily: fonts.semibold,
    fontSize: 10,
    letterSpacing: 0.65,
    textTransform: "uppercase",
  },
  input: {
    minHeight: 52,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 17,
    paddingHorizontal: 15,
    paddingVertical: 13,
    color: colors.text,
    backgroundColor: colors.surfaceAlt,
    fontFamily: fonts.regular,
    fontSize: 14,
  },
  inputMultiline: { minHeight: 110, textAlignVertical: "top" },
  button: {
    backgroundColor: colors.primary,
    paddingHorizontal: 16,
    paddingVertical: 13,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 48,
    shadowColor: colors.primaryDark,
    shadowOpacity: 0.16,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
  },
  buttonPressed: { transform: [{ scale: 0.985 }], opacity: 0.92 },
  disabled: { opacity: 0.55 },
  buttonText: {
    color: colors.white,
    fontFamily: fonts.semibold,
    fontSize: 13,
    textAlign: "center",
  },
  chip: {
    minHeight: 36,
    paddingHorizontal: 14,
    borderRadius: 18,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  chipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  chipText: {
    color: colors.textMuted,
    fontFamily: fonts.semibold,
    fontSize: 10,
  },
  chipTextActive: { color: colors.white },
  noticeBox: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
    padding: 12,
    borderRadius: 16,
    backgroundColor: colors.primarySoft,
  },
  notice: {
    flex: 1,
    color: colors.primaryDark,
    fontFamily: fonts.medium,
    fontSize: 12,
    lineHeight: 18,
  },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
});
