import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { AppLoadingScreen } from "../src/components/AppLoadingScreen";
import { useAuthStore } from "../src/store/authStore";
import { colors } from "../src/theme/colors";
import { fonts } from "../src/theme/fonts";

export default function OAuthScreen() {
  const { code, error } = useLocalSearchParams<{ code?: string; error?: string }>();
  const completeOAuth = useAuthStore((s) => s.completeOAuth);
  const started = useRef(false);
  const [message, setMessage] = useState(error ?? "");

  useEffect(() => {
    if (started.current || error || !code) return;
    started.current = true;
    completeOAuth(code)
      .then(() => router.replace("/(tabs)"))
      .catch((e: any) => setMessage(e?.message ?? "Sign in could not be completed"));
  }, [code, completeOAuth, error]);

  if (!message) return <AppLoadingScreen />;

  return (
    <View style={styles.container}>
      <View style={styles.icon}>
        <Ionicons name="alert-circle-outline" size={28} color={colors.danger} />
      </View>
      <Text style={styles.title}>Sign in didn't finish</Text>
      <Text style={styles.message}>{message}</Text>
      <Pressable style={styles.button} onPress={() => router.replace("/welcome")}>
        <Text style={styles.buttonText}>Back to sign in</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 34,
  },
  icon: {
    width: 62,
    height: 62,
    borderRadius: 22,
    backgroundColor: "#FFF0F1",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 18,
  },
  title: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 24,
    textAlign: "center",
  },
  message: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 13,
    lineHeight: 20,
    textAlign: "center",
    marginTop: 8,
  },
  button: {
    marginTop: 20,
    minHeight: 50,
    paddingHorizontal: 20,
    borderRadius: 17,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  buttonText: { color: colors.white, fontFamily: fonts.semibold, fontSize: 13 },
});
