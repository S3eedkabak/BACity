import { Ionicons } from "@expo/vector-icons";
import { Video, ResizeMode } from "expo-av";
import { router } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Linking,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { BrandMark } from "../src/components/BrandMark";
import { API_URL } from "../src/api/client";
import * as authApi from "../src/api/auth";
import { colors } from "../src/theme/colors";
import { fonts } from "../src/theme/fonts";

type Provider = "google" | "apple";

export default function WelcomeScreen() {
  const [videoFailed, setVideoFailed] = useState(false);
  const [providerBusy, setProviderBusy] = useState<Provider | null>(null);
  const [providers, setProviders] = useState<authApi.OAuthStatus | null>(null);

  useEffect(() => {
    authApi.oauthStatus().then(setProviders).catch(() => setProviders(null));
  }, []);

  async function continueWith(provider: Provider) {
    setProviderBusy(provider);
    try {
      const status = providers ?? (await authApi.oauthStatus());
      setProviders(status);
      if (!status[provider]) {
        Alert.alert(
          provider === "google" ? "Google sign in needs setup" : "Apple sign in needs setup",
          "The BACity server is ready for this provider, but its OAuth credentials have not been configured yet."
        );
        return;
      }
      await Linking.openURL(`${API_URL}/auth/oauth/${provider}/start`);
    } catch (error: any) {
      Alert.alert("Could not start sign in", error?.message ?? "Check that the BACity API is running.");
    } finally {
      setProviderBusy(null);
    }
  }

  return (
    <View style={styles.container}>
      <StatusBar style="light" />
      {!videoFailed && (
        <Video
          source={require("../assets/bratislava-welcome.mp4")}
          style={StyleSheet.absoluteFill}
          resizeMode={ResizeMode.COVER}
          shouldPlay
          isMuted
          isLooping
          useNativeControls={false}
          onError={() => setVideoFailed(true)}
        />
      )}
      <View style={styles.fallback} pointerEvents="none" />
      <View style={styles.topShade} pointerEvents="none" />
      <View style={styles.bottomShade} pointerEvents="none" />

      <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
        <View style={styles.top}>
          <BrandMark light compact />
          <View style={styles.cityChip}>
            <Ionicons name="location" size={13} color={colors.white} />
            <Text style={styles.cityText}>Bratislava</Text>
          </View>
        </View>

        <View style={styles.copy}>
          <Text style={styles.eyebrow}>YOUR CITY, LIVE</Text>
          <Text style={styles.title}>Find the moments{"
"}you'd otherwise miss.</Text>
          <Text style={styles.subtitle}>
            Events, local gems and useful city knowledge, all in one place.
          </Text>
        </View>

        <View style={styles.actions}>
          <Pressable
            style={({ pressed }) => [styles.primary, pressed && styles.pressed]}
            onPress={() => router.push({ pathname: "/auth", params: { mode: "register" } })}
          >
            <Text style={styles.primaryText}>Get started</Text>
            <Ionicons name="arrow-forward" size={18} color={colors.white} />
          </Pressable>

          <View style={styles.socialRow}>
            <Pressable
              style={({ pressed }) => [styles.social, pressed && styles.pressed]}
              onPress={() => continueWith("google")}
              disabled={providerBusy !== null}
            >
              {providerBusy === "google" ? (
                <ActivityIndicator color={colors.text} size="small" />
              ) : (
                <Text style={styles.googleMark}>G</Text>
              )}
              <Text style={styles.socialText}>Continue with Google</Text>
            </Pressable>

            <Pressable
              style={({ pressed }) => [styles.social, pressed && styles.pressed]}
              onPress={() => continueWith("apple")}
              disabled={providerBusy !== null}
            >
              {providerBusy === "apple" ? (
                <ActivityIndicator color={colors.text} size="small" />
              ) : (
                <Ionicons name="logo-apple" size={20} color={colors.text} />
              )}
              <Text style={styles.socialText}>Continue with Apple</Text>
            </Pressable>
          </View>

          <Pressable
            style={styles.loginLink}
            onPress={() => router.push({ pathname: "/auth", params: { mode: "login" } })}
          >
            <Text style={styles.loginMuted}>Already a member? </Text>
            <Text style={styles.loginStrong}>Log in</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#2A2024" },
  fallback: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(39,35,41,0.12)",
  },
  topShade: {
    ...StyleSheet.absoluteFillObject,
    bottom: "58%",
    backgroundColor: "rgba(15,10,12,0.18)",
  },
  bottomShade: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    height: "68%",
    backgroundColor: "rgba(20,13,16,0.58)",
  },
  safe: { flex: 1, paddingHorizontal: 20, justifyContent: "space-between" },
  top: {
    paddingTop: 8,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  cityChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 99,
    backgroundColor: "rgba(20,13,16,0.38)",
  },
  cityText: { color: colors.white, fontFamily: fonts.semibold, fontSize: 11 },
  copy: { marginTop: "auto", paddingBottom: 20 },
  eyebrow: {
    color: colors.primary,
    fontFamily: fonts.black,
    fontSize: 10,
    letterSpacing: 1.8,
    marginBottom: 10,
  },
  title: {
    color: colors.white,
    fontFamily: fonts.black,
    fontSize: 39,
    lineHeight: 41,
    letterSpacing: -1.6,
  },
  subtitle: {
    color: "rgba(255,255,255,0.78)",
    fontFamily: fonts.regular,
    fontSize: 14,
    lineHeight: 21,
    marginTop: 12,
    maxWidth: 330,
  },
  actions: { gap: 11, paddingBottom: 8 },
  primary: {
    minHeight: 56,
    borderRadius: 19,
    backgroundColor: colors.primary,
    paddingHorizontal: 18,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 9,
  },
  primaryText: { color: colors.white, fontFamily: fonts.black, fontSize: 14 },
  socialRow: { flexDirection: "row", gap: 10 },
  social: {
    flex: 1,
    minHeight: 54,
    borderRadius: 18,
    backgroundColor: "rgba(255,255,255,0.94)",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 9,
  },
  googleMark: {
    color: "#4285F4",
    fontFamily: fonts.black,
    fontSize: 20,
  },
  socialText: { color: colors.text, fontFamily: fonts.semibold, fontSize: 13 },
  pressed: { opacity: 0.9, transform: [{ scale: 0.985 }] },
  loginLink: {
    minHeight: 40,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
  },
  loginMuted: { color: "rgba(255,255,255,0.72)", fontFamily: fonts.regular, fontSize: 12 },
  loginStrong: { color: colors.white, fontFamily: fonts.semibold, fontSize: 12 },
});
