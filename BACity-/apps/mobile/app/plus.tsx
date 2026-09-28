import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { colors } from "../src/theme/colors";
import { fonts } from "../src/theme/fonts";
import { dismissPlusPaywall, isPlusFeature, PLUS_FEATURES } from "../src/plus/policy";

export default function PlusPaywallScreen() {
  const params = useLocalSearchParams<{ feature?: string | string[]; unavailable?: string }>();
  const feature = isPlusFeature(params.feature) ? params.feature : null;
  const dismiss = () => dismissPlusPaywall(
    () => router.canGoBack(),
    () => router.back(),
    path => router.replace(path),
  );

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <View style={styles.header}>
        <View style={styles.headerSpace} />
        <Text style={styles.brand}>BACity+</Text>
        <Pressable accessibilityRole="button" accessibilityLabel="Dismiss BACity Plus" onPress={dismiss} style={({ pressed }) => [styles.close, pressed && styles.pressed]}>
          <Ionicons name="close" size={22} color={colors.text} />
        </Pressable>
      </View>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.mark}><Ionicons name="sparkles" size={34} color={colors.white} /></View>
        <Text style={styles.title}>Premium discovery tools for deciding what to do.</Text>
        {feature ? <Text style={styles.context}>{PLUS_FEATURES[feature]} is planned as a BACity+ feature.</Text> : null}
        {params.unavailable === "1" ? <Text style={styles.notice}>We could not verify your access right now. Try again when your connection is available.</Text> : null}
        <View style={styles.list}>
          {Object.values(PLUS_FEATURES).map(label => (
            <View key={label} style={styles.row}>
              <View style={styles.check}><Ionicons name="checkmark" size={15} color={colors.primaryDark} /></View>
              <Text style={styles.label}>{label}</Text>
            </View>
          ))}
        </View>
        <Text style={styles.coming}>Purchasing and pricing are not available yet.</Text>
        <Pressable accessibilityRole="button" onPress={dismiss} style={({ pressed }) => [styles.button, pressed && styles.pressed]}>
          <Text style={styles.buttonText}>Not now</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: { minHeight: 58, paddingHorizontal: 12, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  headerSpace: { width: 44 }, brand: { color: colors.text, fontFamily: fonts.black, fontSize: 18 },
  close: { width: 44, height: 44, borderRadius: 16, alignItems: "center", justifyContent: "center" },
  content: { flexGrow: 1, paddingHorizontal: 24, paddingTop: 30, paddingBottom: 32, alignItems: "center" },
  mark: { width: 72, height: 72, borderRadius: 25, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center", marginBottom: 24 },
  title: { maxWidth: 330, color: colors.text, fontFamily: fonts.black, fontSize: 29, lineHeight: 33, letterSpacing: -1, textAlign: "center" },
  context: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 13, lineHeight: 19, textAlign: "center", marginTop: 14 },
  notice: { width: "100%", color: colors.danger, fontFamily: fonts.medium, fontSize: 12, lineHeight: 18, textAlign: "center", backgroundColor: "#FFF0F1", borderRadius: 14, padding: 12, marginTop: 14 },
  list: { width: "100%", marginTop: 30, gap: 12 },
  row: { minHeight: 44, flexDirection: "row", alignItems: "center", gap: 12 },
  check: { width: 30, height: 30, borderRadius: 11, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" },
  label: { color: colors.text, fontFamily: fonts.semibold, fontSize: 14 },
  coming: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12, lineHeight: 18, textAlign: "center", marginTop: 28 },
  button: { width: "100%", minHeight: 54, borderRadius: 18, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center", marginTop: 18 },
  buttonText: { color: colors.white, fontFamily: fonts.black, fontSize: 14 }, pressed: { opacity: .75, transform: [{ scale: .98 }] },
});
