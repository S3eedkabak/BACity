import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { BrandMark } from "../src/components/BrandMark";
import { useAuthStore } from "../src/store/authStore";
import { colors } from "../src/theme/colors";
import { fonts } from "../src/theme/fonts";

export default function AuthScreen() {
  const params = useLocalSearchParams<{ mode?: string }>();
  const initialMode = useMemo(() => (params.mode === "register" ? "register" : "login"), [params.mode]);
  const [mode, setMode] = useState<"login" | "register">(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const login = useAuthStore((s) => s.login);
  const register = useAuthStore((s) => s.register);

  async function submit() {
    setBusy(true);
    setError("");
    try {
      if (mode === "login") {
        await login(email.trim(), password);
      } else {
        await register(email.trim(), password, displayName.trim() || undefined);
      }
      router.replace("/(tabs)");
    } catch (e: any) {
      setError(e?.message ?? "Could not continue");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <KeyboardAvoidingView
        style={styles.safe}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.top}>
            <Pressable style={styles.back} onPress={() => router.back()}>
              <Ionicons name="chevron-back" size={20} color={colors.text} />
            </Pressable>
            <BrandMark compact />
            <View style={styles.spacer} />
          </View>

          <View style={styles.hero}>
            <Text style={styles.eyebrow}>{mode === "login" ? "WELCOME BACK" : "JOIN THE CITY"}</Text>
            <Text style={styles.title}>
              {mode === "login" ? "Your plans are waiting." : "Make Bratislava yours."}
            </Text>
            <Text style={styles.subtitle}>
              {mode === "login"
                ? "Sign in to pick up where you left off."
                : "Save events, contribute local knowledge and shape your own city feed."}
            </Text>
          </View>

          <View style={styles.form}>
            {mode === "register" && (
              <View style={styles.field}>
                <Text style={styles.label}>Display name</Text>
                <TextInput
                  style={styles.input}
                  value={displayName}
                  onChangeText={setDisplayName}
                  placeholder="How people will see you"
                  placeholderTextColor={colors.textMuted}
                />
              </View>
            )}
            <View style={styles.field}>
              <Text style={styles.label}>Email</Text>
              <TextInput
                style={styles.input}
                value={email}
                onChangeText={setEmail}
                placeholder="you@example.com"
                placeholderTextColor={colors.textMuted}
                autoCapitalize="none"
                keyboardType="email-address"
                autoComplete="email"
              />
            </View>
            <View style={styles.field}>
              <Text style={styles.label}>Password</Text>
              <TextInput
                style={styles.input}
                value={password}
                onChangeText={setPassword}
                placeholder="At least 8 characters"
                placeholderTextColor={colors.textMuted}
                secureTextEntry
                autoCapitalize="none"
              />
            </View>
          </View>

          {!!error && (
            <View style={styles.errorBox}>
              <Ionicons name="alert-circle-outline" size={18} color={colors.danger} />
              <Text style={styles.error}>{error}</Text>
            </View>
          )}

          <Pressable
            disabled={busy}
            style={({ pressed }) => [styles.primary, pressed && styles.pressed, busy && styles.disabled]}
            onPress={submit}
          >
            {busy ? (
              <ActivityIndicator color={colors.white} />
            ) : (
              <>
                <Text style={styles.primaryText}>
                  {mode === "login" ? "Log in" : "Create account"}
                </Text>
                <Ionicons name="arrow-forward" size={18} color={colors.white} />
              </>
            )}
          </Pressable>

          {mode === "login" && (
            <Pressable onPress={() => router.push("/account")} style={styles.textButton}>
              <Text style={styles.textButtonLabel}>Forgot your password?</Text>
            </Pressable>
          )}

          <Pressable
            style={styles.switch}
            onPress={() => {
              setError("");
              setMode(mode === "login" ? "register" : "login");
            }}
          >
            <Text style={styles.switchMuted}>
              {mode === "login" ? "New to BACity? " : "Already have an account? "}
            </Text>
            <Text style={styles.switchStrong}>
              {mode === "login" ? "Create one" : "Log in"}
            </Text>
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  content: { flexGrow: 1, paddingHorizontal: 20, paddingBottom: 34 },
  top: {
    minHeight: 56,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  back: {
    width: 42,
    height: 42,
    borderRadius: 16,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  spacer: { width: 42 },
  hero: { paddingTop: 38, paddingBottom: 30 },
  eyebrow: {
    color: colors.primaryDark,
    fontFamily: fonts.black,
    fontSize: 10,
    letterSpacing: 1.7,
  },
  title: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 38,
    lineHeight: 40,
    letterSpacing: -1.5,
    marginTop: 9,
  },
  subtitle: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 14,
    lineHeight: 21,
    marginTop: 10,
    maxWidth: 335,
  },
  form: { gap: 14 },
  field: { gap: 7 },
  label: {
    color: colors.textMuted,
    fontFamily: fonts.semibold,
    fontSize: 10,
    letterSpacing: 0.7,
    textTransform: "uppercase",
  },
  input: {
    minHeight: 56,
    borderRadius: 18,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 16,
    color: colors.text,
    fontFamily: fonts.regular,
    fontSize: 14,
  },
  errorBox: {
    marginTop: 14,
    padding: 12,
    borderRadius: 16,
    backgroundColor: "#FFF0F1",
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  error: { flex: 1, color: colors.danger, fontFamily: fonts.medium, fontSize: 12 },
  primary: {
    minHeight: 56,
    borderRadius: 19,
    backgroundColor: colors.primary,
    marginTop: 20,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 9,
  },
  primaryText: { color: colors.white, fontFamily: fonts.black, fontSize: 14 },
  pressed: { opacity: 0.9, transform: [{ scale: 0.985 }] },
  disabled: { opacity: 0.6 },
  textButton: { alignItems: "center", paddingVertical: 15 },
  textButtonLabel: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 12 },
  switch: {
    marginTop: "auto",
    paddingTop: 36,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
  },
  switchMuted: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12 },
  switchStrong: { color: colors.text, fontFamily: fonts.black, fontSize: 12 },
});
