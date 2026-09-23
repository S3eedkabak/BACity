import { Ionicons } from "@expo/vector-icons";
import { FlatList, StyleSheet, Text, View } from "react-native";
import { useAuthStore } from "../../src/store/authStore";
import { useSavedEvents } from "../../src/hooks/useEvents";
import { EventCard } from "../../src/components/EventCard";
import { EmptyState } from "../../src/components/EmptyState";
import { LoadingState } from "../../src/components/LoadingState";
import { colors } from "../../src/theme/colors";

export default function SavedScreen() {
  const token = useAuthStore((s) => s.token);
  const { data, isLoading, isError } = useSavedEvents();

  if (!token) {
    return <View style={styles.guest}><View style={styles.icon}><Ionicons name="bookmark" size={26} color={colors.accent} /></View><Text style={styles.title}>Your plans live here</Text><Text style={styles.subtitle}>Swipe right on something you love, then find it here whenever you need it.</Text><Text style={styles.loginHint}>Log in from You to start saving.</Text></View>;
  }
  if (isLoading) return <LoadingState />;
  if (isError) return <EmptyState title="Couldn't load saved events" subtitle="Try again in a moment." />;

  return (
    <FlatList
      style={styles.container}
      contentContainerStyle={styles.content}
      data={data ?? []}
      keyExtractor={(item) => item.id}
      showsVerticalScrollIndicator={false}
      ListHeaderComponent={<View style={styles.header}><Text style={styles.eyebrow}>YOUR PICKS</Text><Text style={styles.heading}>Saved</Text><Text style={styles.count}>{data?.length ?? 0} events</Text></View>}
      renderItem={({ item }) => <EventCard event={item} />}
      ListEmptyComponent={<EmptyState title="Nothing saved yet" subtitle="Your best finds will collect here." />}
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: 18, paddingBottom: 110 },
  header: { paddingTop: 10, paddingBottom: 18 },
  eyebrow: { color: colors.accent, fontSize: 10, fontWeight: "900", letterSpacing: 1.4 },
  heading: { color: colors.text, fontSize: 34, fontWeight: "900", letterSpacing: -1, marginTop: 2 },
  count: { color: colors.textMuted, fontSize: 12, marginTop: 5 },
  guest: { flex: 1, backgroundColor: colors.background, alignItems: "center", justifyContent: "center", padding: 42 },
  icon: { width: 64, height: 64, borderRadius: 32, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center", marginBottom: 18 },
  title: { color: colors.text, fontSize: 23, fontWeight: "900" },
  subtitle: { color: colors.textMuted, textAlign: "center", lineHeight: 21, marginTop: 8, fontSize: 14 },
  loginHint: { color: colors.accent, fontSize: 12, fontWeight: "800", marginTop: 20 },
});