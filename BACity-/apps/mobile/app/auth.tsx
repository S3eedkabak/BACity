import { Ionicons } from "@expo/vector-icons";
import * as AppleAuthentication from "expo-apple-authentication";
import { router, useLocalSearchParams } from "expo-router";
import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  NativeModules,
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

const GoogleNative = Platform.OS !== "web" && NativeModules.RNGoogleSignin
  ? require("@react-native-google-signin/google-signin")
  : null;

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
  const completeNativeOAuth = useAuthStore((s) => s.completeNativeOAuth);

  async function submit() {
    setBusy(true);
    setError("");
    try {
      if (mode === "login") {
        await login(email.trim(), password);
      } else {
        await register(email.trim(), password, displayName.trim() || undefined);
      }
      router.replace("/(tabs)/discover");
    } catch (e: any) {
      setError(e?.message ?? "Could not continue");
    } finally {
      setBusy(false);
    }
  }

  async function signInWithApple() {
    setBusy(true); setError("");
    try {
      const credential = await AppleAuthentication.signInAsync({ requestedScopes: [AppleAuthentication.AppleAuthenticationScope.FULL_NAME, AppleAuthentication.AppleAuthenticationScope.EMAIL] });
      if (!credential.identityToken || !credential.authorizationCode) throw new Error("Apple did not return complete sign-in credentials.");
      const displayName = [credential.fullName?.givenName, credential.fullName?.familyName].filter(Boolean).join(" ") || null;
      await completeNativeOAuth("apple", credential.identityToken, credential.authorizationCode, displayName);
      router.replace("/(tabs)/discover");
    } catch (e: any) {
      if (e?.code !== "ERR_REQUEST_CANCELED") setError(e?.message ?? "Apple sign in could not be completed");
    } finally { setBusy(false); }
  }

  async function signInWithGoogle() {
    setBusy(true); setError("");
    try {
      if (!GoogleNative) throw new Error("Google sign in requires a BACity development or production build.");
      const webClientId = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID;
      const iosClientId = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID;
      if (!webClientId || (Platform.OS === "ios" && !iosClientId)) throw new Error("Google sign in is not configured for this build.");
      GoogleNative.GoogleSignin.configure({ webClientId, iosClientId, offlineAccess: false });
      if (Platform.OS === "android") await GoogleNative.GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: true });
      const response = await GoogleNative.GoogleSignin.signIn();
      if (response.type !== "success") return;
      if (!response.data.idToken) throw new Error("Google did not return an identity token.");
      await completeNativeOAuth("google", response.data.idToken);
      router.replace("/(tabs)/discover");
    } catch (e: any) { setError(e?.message ?? "Google sign in could not be completed"); }
    finally { setBusy(false); }
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
            <Pressable accessibilityRole="button" accessibilityLabel="Back" style={styles.back} onPress={() => router.canGoBack() ? router.back() : router.replace("/welcome")}>
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
            accessibilityRole="button"
            accessibilityLabel={mode === "login" ? "Log in" : "Create account"}
            accessibilityState={{ disabled: busy, busy }}
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

          {Platform.OS !== "web" && <Pressable accessibilityRole="button" accessibilityLabel="Continue with Google" disabled={busy} style={({ pressed }) => [styles.googleButton, pressed && styles.pressed, busy && styles.disabled]} onPress={signInWithGoogle}>
            <Text style={styles.googleMark}>G</Text><Text style={styles.googleText}>Continue with Google</Text>
          </Pressable>}

          {Platform.OS === "ios" && <AppleAuthentication.AppleAuthenticationButton
            buttonType={AppleAuthentication.AppleAuthenticationButtonType.CONTINUE}
            buttonStyle={AppleAuthentication.AppleAuthenticationButtonStyle.BLACK}
            cornerRadius={17}
            style={styles.appleButton}
            onPress={signInWithApple}
          />}

          {mode === "login" && (
            <Pressable accessibilityRole="button" accessibilityLabel="Forgot your password?" onPress={() => router.push({ pathname: "/account", params: { action: "forgot" } })} style={styles.textButton}>
              <Text style={styles.textButtonLabel}>Forgot your password?</Text>
            </Pressable>
          )}

          <Pressable
            accessibilityRole="button"
            accessibilityLabel={mode === "login" ? "Create an account instead" : "Log in instead"}
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
          <Pressable accessibilityRole="button" accessibilityLabel="Privacy information and terms" onPress={() => router.push('/privacy')} style={styles.textButton}>
            <Text style={styles.textButtonLabel}>Privacy information & terms</Text>
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  content: { width: '100%', maxWidth: 760, alignSelf: 'center', flexGrow: 1, paddingHorizontal: 20, paddingBottom: 34 },
  top: {
    minHeight: 56,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  back: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  spacer: { width: 48 },
  hero: { paddingTop: 32, paddingBottom: 28 },
  eyebrow: {
    color: colors.primaryDark,
    fontFamily: fonts.black, fontWeight: '800',
    fontSize: 12,
    letterSpacing: 1.7,
  },
  title: {
    color: colors.text,
    fontFamily: fonts.black, fontWeight: '800',
    fontSize: 44,
    lineHeight: 47,
    letterSpacing: -1.5,
    marginTop: 9,
  },
  subtitle: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 16,
    lineHeight: 24,
    marginTop: 10,
    maxWidth: 335,
  },
  form: { gap: 14 },
  field: { gap: 7 },
  label: {
    color: colors.textMuted,
    fontFamily: fonts.semibold, fontWeight: '600',
    fontSize: 12,
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
    fontSize: 16,
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
  primaryText: { color: colors.white, fontFamily: fonts.black, fontWeight: '800', fontSize: 16 },
  pressed: { opacity: 0.9, transform: [{ scale: 0.985 }] },
  disabled: { opacity: 0.6 },
  textButton: { alignItems: "center", paddingVertical: 15 },
  appleButton: { width: "100%", height: 52, marginTop: 10 },
  googleButton: { width: "100%", minHeight: 52, marginTop: 10, borderRadius: 17, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 9 },
  googleMark: { color: "#4285F4", fontFamily: fonts.black, fontWeight: '800', fontSize: 19 },
  googleText: { color: colors.text, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 13 },
  textButtonLabel: { color: colors.primaryDark, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12 },
  switch: {
    marginTop: "auto",
    paddingTop: 36,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    flexWrap: "wrap",
  },
  switchMuted: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12 },
  switchStrong: { color: colors.text, fontFamily: fonts.black, fontWeight: '800', fontSize: 12 },
});
