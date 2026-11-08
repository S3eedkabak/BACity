import { useMotionPreference } from "../src/components/interactions/useMotionPreference";
import { LoginCard } from "../src/components/interactions/LoginCard";
import { AppTextField } from "../src/components/interactions/AppTextField";
import { PasswordStrengthIndicator } from "../src/components/interactions/PasswordStrengthIndicator";
import { MorphActionButton } from "../src/components/interactions/ActionButton";
import { useRef } from "react";
import { themedStyles, useThemeRevision } from "../src/theme/appearance";
import { AppIcon } from "../src/components/AppIcon";
import * as AppleAuthentication from "expo-apple-authentication";
import { router, useLocalSearchParams } from "expo-router";
import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  NativeModules,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { AnimatedPressable as Pressable } from "../src/components/motion/Motion";
import { SafeAreaView } from "../src/components/navigation/ContentSafeArea";
import { BrandMark } from "../src/components/BrandMark";
import { useAuthStore } from "../src/store/authStore";
import { colors } from "../src/theme/colors";
import { fonts } from "../src/theme/fonts";

const GoogleNative =
  Platform.OS !== "web" && NativeModules.RNGoogleSignin
    ? require("@react-native-google-signin/google-signin")
    : null;

export default function AuthScreen() {
  useThemeRevision();
  const params = useLocalSearchParams<{ mode?: string }>();
  const initialMode = useMemo(
    () => (params.mode === "register" ? "register" : "login"),
    [params.mode],
  );
  const [mode, setMode] = useState<"login" | "register">(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const lock = useRef(false);
  const formScroll = useRef<ScrollView>(null);
  const reduced = useMotionPreference();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const login = useAuthStore((s) => s.login);
  const register = useAuthStore((s) => s.register);
  const completeNativeOAuth = useAuthStore((s) => s.completeNativeOAuth);

  async function submit() {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      if (mode === "login") {
        await login(email.trim(), password);
      } else {
        await register(email.trim(), password, displayName.trim() || undefined);
      }
      // The root owns authenticated Home entry and its session greeting.
    } catch (e: any) {
      setError(e?.message ?? "Could not continue");
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  async function signInWithApple() {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      const credential = await AppleAuthentication.signInAsync({
        requestedScopes: [
          AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
          AppleAuthentication.AppleAuthenticationScope.EMAIL,
        ],
      });
      if (!credential.identityToken || !credential.authorizationCode)
        throw new Error("Apple did not return complete sign-in credentials.");
      const displayName =
        [credential.fullName?.givenName, credential.fullName?.familyName]
          .filter(Boolean)
          .join(" ") || null;
      await completeNativeOAuth(
        "apple",
        credential.identityToken,
        credential.authorizationCode,
        displayName,
      );
      // The root owns authenticated Home entry.
    } catch (e: any) {
      if (e?.code !== "ERR_REQUEST_CANCELED")
        setError(e?.message ?? "Apple sign in could not be completed");
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  async function signInWithGoogle() {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      if (!GoogleNative)
        throw new Error(
          "Google sign in requires a BACity development or production build.",
        );
      const webClientId = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID;
      const iosClientId = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID;
      if (!webClientId || (Platform.OS === "ios" && !iosClientId))
        throw new Error("Google sign in is not configured for this build.");
      GoogleNative.GoogleSignin.configure({
        webClientId,
        iosClientId,
        offlineAccess: false,
      });
      if (Platform.OS === "android")
        await GoogleNative.GoogleSignin.hasPlayServices({
          showPlayServicesUpdateDialog: true,
        });
      const response = await GoogleNative.GoogleSignin.signIn();
      if (response.type !== "success") return;
      if (!response.data.idToken)
        throw new Error("Google did not return an identity token.");
      await completeNativeOAuth("google", response.data.idToken);
      // The root owns authenticated Home entry.
    } catch (e: any) {
      setError(e?.message ?? "Google sign in could not be completed");
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={styles.safe} edges={["bottom"]}>
      <KeyboardAvoidingView
        style={styles.safe}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          ref={formScroll}
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <LoginCard
            title={
              mode === "login"
                ? "Your plans are waiting."
                : "Make Bratislava yours."
            }
            subtitle={
              mode === "login"
                ? "Sign in to pick up where you left off."
                : "Save events and shape your own city feed."
            }
          >
            {mode === "register" && (
              <AppTextField
                label="Display name"
                value={displayName}
                onChangeText={setDisplayName}
                autoComplete="name"
                editable={!busy}
              />
            )}
            <AppTextField
              label="Email"
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              autoComplete="email"
              keyboardType="email-address"
              editable={!busy}
            />
            <AppTextField
              label="Password"
              value={password}
              onChangeText={setPassword}
              secure
              autoCapitalize="none"
              autoCorrect={false}
              autoComplete={
                mode === "register" ? "new-password" : "current-password"
              }
              editable={!busy}
              onSubmitEditing={() => void submit()}
            />
            {mode === "register" && (
              <PasswordStrengthIndicator password={password} />
            )}

            {!!error && (
              <View style={styles.errorBox}>
                <AppIcon
                  name="alert-circle-outline"
                  size={18}
                  color={colors.danger}
                />
                <Text accessibilityRole="alert" style={styles.error}>
                  {error}
                </Text>
              </View>
            )}

            <View style={{ marginTop: 20 }}>
              <MorphActionButton
                stretch
                title={mode === "login" ? "Log in" : "Create account"}
                state={busy ? "loading" : error ? "error" : "idle"}
                onPress={() => void submit()}
              />
            </View>

            {Platform.OS !== "web" && (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Continue with Google"
                disabled={busy}
                style={({ pressed }) => [
                  styles.googleButton,
                  pressed && styles.pressed,
                  busy && styles.disabled,
                ]}
                onPress={signInWithGoogle}
              >
                <Text style={styles.googleMark}>G</Text>
                <Text style={styles.googleText}>Continue with Google</Text>
              </Pressable>
            )}

            {Platform.OS === "ios" && (
              <AppleAuthentication.AppleAuthenticationButton
                buttonType={
                  AppleAuthentication.AppleAuthenticationButtonType.CONTINUE
                }
                buttonStyle={
                  AppleAuthentication.AppleAuthenticationButtonStyle.BLACK
                }
                cornerRadius={17}
                style={styles.appleButton}
                onPress={signInWithApple}
              />
            )}

            {mode === "login" && (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Forgot your password?"
                onPress={() =>
                  router.push({
                    pathname: "/account",
                    params: { action: "forgot" },
                  })
                }
                style={styles.textButton}
              >
                <Text style={styles.textButtonLabel}>
                  Forgot your password?
                </Text>
              </Pressable>
            )}

            <Pressable
              accessibilityRole="button"
              accessibilityLabel={
                mode === "login"
                  ? "Create an account instead"
                  : "Log in instead"
              }
              disabled={busy}
              style={styles.switch}
              onPress={() => {
                setError("");
                setMode(mode === "login" ? "register" : "login");
                Keyboard.dismiss();
                formScroll.current?.scrollTo({ y: 0, animated: !reduced });
              }}
            >
              <Text style={styles.switchMuted}>
                {mode === "login"
                  ? "New to BACity? "
                  : "Already have an account? "}
              </Text>
              <Text style={styles.switchStrong}>
                {mode === "login" ? "Create one" : "Log in"}
              </Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Privacy information and terms"
              onPress={() => router.push("/privacy")}
              style={styles.textButton}
            >
              <Text style={styles.textButtonLabel}>
                Privacy information & terms
              </Text>
            </Pressable>
          </LoginCard>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = themedStyles(() => ({
  safe: { flex: 1, backgroundColor: colors.background },
  content: {
    width: "100%",
    maxWidth: 760,
    alignSelf: "center",
    flexGrow: 1,
    paddingHorizontal: 20,
    paddingBottom: 34,
  },
  errorBox: {
    marginTop: 14,
    padding: 12,
    borderRadius: 16,
    backgroundColor: colors.dangerSurface,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  error: {
    flex: 1,
    color: colors.danger,
    fontFamily: fonts.medium,
    fontSize: 12,
  },
  pressed: { opacity: 0.9 },
  disabled: { opacity: 0.6 },
  textButton: { alignItems: "center", paddingVertical: 15 },
  appleButton: { width: "100%", height: 52, marginTop: 10 },
  googleButton: {
    width: "100%",
    minHeight: 52,
    marginTop: 10,
    borderRadius: 17,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 9,
  },
  googleMark: {
    color: "#4285F4",
    fontFamily: fonts.black,
    fontWeight: "800",
    fontSize: 19,
  },
  googleText: {
    color: colors.text,
    fontFamily: fonts.semibold,
    fontWeight: "600",
    fontSize: 13,
  },
  textButtonLabel: {
    color: colors.primaryDark,
    fontFamily: fonts.semibold,
    fontWeight: "600",
    fontSize: 12,
  },
  switch: {
    marginTop: "auto",
    paddingTop: 36,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    flexWrap: "wrap",
  },
  switchMuted: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 12,
  },
  switchStrong: {
    color: colors.text,
    fontFamily: fonts.black,
    fontWeight: "800",
    fontSize: 12,
  },
}));
