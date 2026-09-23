import { useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAuthStore } from "../../src/store/authStore";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";

export default function ProfileScreen() {
  const { user, token, login, register, logout } = useAuthStore();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    setError(null);
    setSubmitting(true);
    try {
      mode === "login"
        ? await login(email, password)
        : await register(email, password, displayName || undefined);
    } catch (e: any) {
      setError(e?.message ?? "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  if (token && user) {
    return (
      <View style={styles.container}>
        <View style={styles.accountHero}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>
              {(user.display_name || user.email)[0].toUpperCase()}
            </Text>
          </View>
          <Text style={styles.eyebrow}>YOUR BACITY</Text>
          <Text style={styles.heading}>{user.display_name || "City explorer"}</Text>
          <Text style={styles.email}>{user.email}</Text>
        </View>

        <View style={styles.card}>
          <View style={styles.cardIcon}>
            <Ionicons name="heart" size={18} color={colors.primary} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.cardTitle}>Your taste</Text>
            <Text style={styles.cardText}>
              {user.interests.length
                ? user.interests.join(" · ")
                : "Save a few events and your taste will start taking shape."}
            </Text>
          </View>
        </View>

        <Pressable style={styles.logout} onPress={logout}>
          <Ionicons name="log-out-outline" size={18} color={colors.danger} />
          <Text style={styles.logoutText}>Log out</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.authArt}>
        <View style={styles.artLineOne} />
        <View style={styles.artLineTwo} />
        <View style={styles.artDot} />
        <Ionicons name="sparkles" size={24} color={colors.white} />
      </View>

      <Text style={styles.eyebrow}>{mode === "login" ? "WELCOME BACK" : "JOIN BACITY"}</Text>
      <Text style={styles.heading}>
        {mode === "login" ? "Good to see you." : "Make the city yours."}
      </Text>
      <Text style={styles.subheading}>
        {mode === "login"
          ? "Your saved plans are waiting."
          : "Save events and build a feed around your taste."}
      </Text>

      <View style={styles.form}>
        {mode === "register" && (
          <TextInput
            style={styles.input}
            placeholder="Display name"
            placeholderTextColor={colors.textMuted}
            value={displayName}
            onChangeText={setDisplayName}
          />
        )}
        <TextInput
          style={styles.input}
          placeholder="Email"
          placeholderTextColor={colors.textMuted}
          autoCapitalize="none"
          keyboardType="email-address"
          value={email}
          onChangeText={setEmail}
        />
        <TextInput
          style={styles.input}
          placeholder="Password"
          placeholderTextColor={colors.textMuted}
          secureTextEntry
          value={password}
          onChangeText={setPassword}
        />
      </View>

      {error && <Text style={styles.error}>{error}</Text>}

      <Pressable style={styles.button} onPress={handleSubmit} disabled={submitting}>
        {submitting ? (
          <ActivityIndicator color={colors.white} />
        ) : (
          <>
            <Text style={styles.buttonText}>
              {mode === "login" ? "Sign in" : "Create account"}
            </Text>
            <Ionicons name="arrow-forward" size={18} color={colors.white} />
          </>
        )}
      </Pressable>

      <Pressable onPress={() => setMode(mode === "login" ? "register" : "login")}>
        <Text style={styles.switch}>
          {mode === "login"
            ? "New here? Create an account"
            : "Already have an account? Sign in"}
        </Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: 20 },
  authArt: {
    height: 175,
    borderRadius: 30,
    backgroundColor: colors.primary,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 24,
  },
  artLineOne: {
    position: "absolute",
    width: 270,
    height: 140,
    borderWidth: 2,
    borderColor: "rgba(255,255,255,0.2)",
    borderRadius: 120,
    transform: [{ rotate: "-14deg" }],
  },
  artLineTwo: {
    position: "absolute",
    width: 190,
    height: 190,
    borderWidth: 2,
    borderColor: "rgba(255,255,255,0.18)",
    borderRadius: 100,
    transform: [{ rotate: "22deg" }],
  },
  artDot: {
    position: "absolute",
    width: 110,
    height: 110,
    borderRadius: 55,
    backgroundColor: "rgba(255,255,255,0.12)",
  },
  accountHero: {
    paddingTop: 10,
    paddingBottom: 16,
  },
  avatar: {
    width: 72,
    height: 72,
    borderRadius: 27,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 18,
  },
  avatarText: { color: colors.white, fontFamily: fonts.black, fontSize: 27 },
  eyebrow: {
    color: colors.primaryDark,
    fontFamily: fonts.semibold,
    fontSize: 9,
    letterSpacing: 1.4,
  },
  heading: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 32,
    lineHeight: 36,
    letterSpacing: -1,
    marginTop: 3,
  },
  email: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12, marginTop: 4 },
  subheading: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 13,
    lineHeight: 19,
    marginTop: 7,
    marginBottom: 18,
  },
  form: { gap: 10 },
  input: {
    height: 52,
    borderRadius: 17,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.text,
    fontFamily: fonts.regular,
    paddingHorizontal: 15,
  },
  button: {
    height: 54,
    borderRadius: 18,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: 9,
    marginTop: 5,
  },
  buttonText: { color: colors.white, fontFamily: fonts.black, fontSize: 13 },
  switch: {
    color: colors.primaryDark,
    textAlign: "center",
    marginTop: 16,
    fontFamily: fonts.semibold,
    fontSize: 11,
  },
  error: { color: colors.danger, marginBottom: 8, fontFamily: fonts.medium, fontSize: 11 },
  card: {
    flexDirection: "row",
    gap: 12,
    alignItems: "center",
    padding: 15,
    borderRadius: 20,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    marginTop: 8,
  },
  cardIcon: {
    width: 42,
    height: 42,
    borderRadius: 15,
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },
  cardTitle: { color: colors.text, fontFamily: fonts.semibold, fontSize: 13 },
  cardText: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 11, lineHeight: 16, marginTop: 3 },
  logout: {
    flexDirection: "row",
    gap: 8,
    alignItems: "center",
    marginTop: 22,
    alignSelf: "flex-start",
    padding: 10,
  },
  logoutText: { color: colors.danger, fontFamily: fonts.semibold },
});
