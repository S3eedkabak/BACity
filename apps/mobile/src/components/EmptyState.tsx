import { StyleSheet, Text, View } from "react-native";
import { colors } from "../theme/colors";

export function EmptyState({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>{title}</Text>
      {subtitle && <Text style={styles.subtitle}>{subtitle}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { paddingVertical: 48, alignItems: "center", gap: 6 },
  title: { color: colors.text, fontSize: 15, fontWeight: "600" },
  subtitle: { color: colors.textMuted, fontSize: 13, textAlign: "center", paddingHorizontal: 32 },
});