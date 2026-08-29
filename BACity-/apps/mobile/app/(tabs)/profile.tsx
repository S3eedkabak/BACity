/**
 * Profile screen (spec section 37): register/login form when logged out,
 * account summary + logout when logged in.
 */
import { useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useAuthStore } from "../../src/store/authStore";
import { colors } from "../../src/theme/colors";

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
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(email, password, displayName || undefined);
      }
    } catch (e: any) {
      setError(e?.message ?? "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  if (token && user) {
    return (
      <View style={styles.container}>
        <Text style={styles.heading}>{user.display_name || user.email}</Text>
        <Text style={styles.muted}>{user.email}</Text>
        <Text style={[styles.muted, { marginTop: 16 }]}>
          Interests: {user.interests.length > 0 ? user.interests.join(", ") : "none set yet"}
        </Text>
        <Pressable style={[styles.button, styles.buttonDanger]} onPress={() => logout()}>
          <Text style={styles.buttonText}>Log out</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>{mode === "login" ? "Log in" : "Create an account"}</Text>

      {mode === "register" && (
        <TextInput
          style={styles.input}
          placeholder="Display name (optional)"
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

      {error && <Text style={styles.error}>{error}</Text>}

      <Pressable style={styles.button} onPress={handleSubmit} disabled={submitting}>
        {submitting ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>{mode === "login" ? "Log in" : "Register"}</Text>
        )}
      </Pressable>

      <Pressable onPress={() => setMode(mode === "login" ? "register" : "login")}>
        <Text style={styles.switchMode}>
          {mode === "login" ? "Need an account? Register" : "Already have an account? Log in"}
        </Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: 20 },
  heading: { color: colors.text, fontSize: 22, fontWeight: "800", marginBottom: 16 },
  muted: { color: colors.textMuted, fontSize: 14 },
  input: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: 12,
    color: colors.text,
    marginBottom: 12,
  },
  button: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    padding: 14,
    alignItems: "center",
    marginTop: 4,
  },
  buttonDanger: { backgroundColor: colors.danger, marginTop: 24 },
  buttonText: { color: "#fff", fontWeight: "700" },
  switchMode: { color: colors.accent, textAlign: "center", marginTop: 16, fontSize: 13 },
  error: { color: colors.danger, marginBottom: 12, fontSize: 13 },
});