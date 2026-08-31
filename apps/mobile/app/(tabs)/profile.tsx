import { useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
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
    setError(null); setSubmitting(true);
    try { mode === "login" ? await login(email, password) : await register(email, password, displayName || undefined); }
    catch (e: any) { setError(e?.message ?? "Something went wrong"); }
    finally { setSubmitting(false); }
  }

  if (token && user) return (
    <View style={styles.container}>
      <View style={styles.avatar}><Text style={styles.avatarText}>{(user.display_name || user.email)[0].toUpperCase()}</Text></View>
      <Text style={styles.eyebrow}>YOUR ACCOUNT</Text>
      <Text style={styles.heading}>{user.display_name || "BACity explorer"}</Text>
      <Text style={styles.email}>{user.email}</Text>
      <View style={styles.card}>
        <View style={styles.cardIcon}><Ionicons name="heart" size={18} color={colors.accent} /></View>
        <View style={{ flex: 1 }}><Text style={styles.cardTitle}>Your interests</Text><Text style={styles.cardText}>{user.interests.length ? user.interests.join(" · ") : "Build your taste by saving events."}</Text></View>
      </View>
      <Pressable style={styles.logout} onPress={logout}><Ionicons name="log-out-outline" size={18} color={colors.danger} /><Text style={styles.logoutText}>Log out</Text></Pressable>
    </View>
  );

  return (
    <View style={styles.container}>
      <View style={styles.avatar}><Ionicons name="person" size={26} color={colors.accent} /></View>
      <Text style={styles.eyebrow}>{mode === "login" ? "WELCOME BACK" : "JOIN BACITY"}</Text>
      <Text style={styles.heading}>{mode === "login" ? "Welcome back." : "Make the city yours."}</Text>
      <Text style={styles.subheading}>{mode === "login" ? "Your saved plans are waiting." : "Save events and build a feed around your taste."}</Text>
      {mode === "register" && <TextInput style={styles.input} placeholder="Display name" placeholderTextColor={colors.textMuted} value={displayName} onChangeText={setDisplayName} />}
      <TextInput style={styles.input} placeholder="Email" placeholderTextColor={colors.textMuted} autoCapitalize="none" keyboardType="email-address" value={email} onChangeText={setEmail} />
      <TextInput style={styles.input} placeholder="Password" placeholderTextColor={colors.textMuted} secureTextEntry value={password} onChangeText={setPassword} />
      {error && <Text style={styles.error}>{error}</Text>}
      <Pressable style={styles.button} onPress={handleSubmit} disabled={submitting}>{submitting ? <ActivityIndicator color={colors.background} /> : <Text style={styles.buttonText}>{mode === "login" ? "Log in" : "Create account"}</Text>}</Pressable>
      <Pressable onPress={() => setMode(mode === "login" ? "register" : "login")}><Text style={styles.switch}>{mode === "login" ? "New here? Create an account" : "Already have an account? Log in"}</Text></Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: 20 },
  avatar: { width: 58, height: 58, borderRadius: 29, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center", marginBottom: 18 },
  avatarText: { color: colors.accent, fontSize: 22, fontWeight: "900" },
  eyebrow: { color: colors.accent, fontSize: 10, fontWeight: "900", letterSpacing: 1.4 },
  heading: { color: colors.text, fontSize: 32, lineHeight: 36, fontWeight: "900", letterSpacing: -0.9, marginTop: 3 },
  email: { color: colors.textMuted, fontSize: 13, marginTop: 4 },
  subheading: { color: colors.textMuted, fontSize: 14, lineHeight: 20, marginTop: 7, marginBottom: 20 },
  card: { flexDirection: "row", gap: 12, alignItems: "center", padding: 15, borderRadius: 19, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, marginTop: 24 },
  cardIcon: { width: 40, height: 40, borderRadius: 14, backgroundColor: colors.surfaceAlt, alignItems: "center", justifyContent: "center" },
  cardTitle: { color: colors.text, fontWeight: "800", fontSize: 13 },
  cardText: { color: colors.textMuted, fontSize: 11, marginTop: 3 },
  input: { height: 52, borderRadius: 16, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, color: colors.text, paddingHorizontal: 15, marginBottom: 10 },
  button: { height: 52, borderRadius: 16, backgroundColor: colors.accent, alignItems: "center", justifyContent: "center", marginTop: 4 },
  buttonText: { color: colors.background, fontWeight: "900", fontSize: 13 },
  switch: { color: colors.accent, textAlign: "center", marginTop: 17, fontSize: 12, fontWeight: "800" },
  error: { color: colors.danger, marginBottom: 10, fontSize: 12 },
  logout: { flexDirection: "row", gap: 8, alignItems: "center", marginTop: 25, alignSelf: "flex-start", padding: 10 },
  logoutText: { color: colors.danger, fontWeight: "800" },
});