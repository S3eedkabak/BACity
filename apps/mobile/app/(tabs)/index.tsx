import { Ionicons } from "@expo/vector-icons";
import { useMemo } from "react";
import { RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { useEvents } from "../../src/hooks/useEvents";
import { EventDeck } from "../../src/components/EventDeck";
import { EmptyState } from "../../src/components/EmptyState";
import { LoadingState } from "../../src/components/LoadingState";
import { colors } from "../../src/theme/colors";

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export default function HomeScreen() {
  const { data, isLoading, isError, refetch, isRefetching } = useEvents({ limit: 50 });
  const events = useMemo(() => data?.items ?? [], [data]);

  if (isLoading) return <LoadingState />;
  if (isError) return <EmptyState title={"Couldn" + "’t load BACity"} subtitle="Check that the API is running and try again." />;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.accent} />}
      showsVerticalScrollIndicator={false}>
      <View style={styles.header}>
        <View>
          <Text style={styles.eyebrow}>{greeting()}</Text>
          <Text style={styles.logo}>BACity<Text style={styles.logoDot}>.</Text></Text>
        </View>
        <View style={styles.locationPill}>
          <Ionicons name="location" size={14} color={colors.accent} />
          <Text style={styles.locationText}>Bratislava</Text>
        </View>
      </View>

      <View style={styles.intro}>
        <Text style={styles.heading}>Find your next{"\n"}thing to do.</Text>
        <Text style={styles.subheading}>Swipe through what’s happening around the city.</Text>
      </View>

      {events.length ? <EventDeck events={events} /> : <EmptyState title="The city is quiet" subtitle="Run the crawler and fresh events will appear here." />}

      <View style={styles.tip}>
        <View style={styles.tipIcon}><Ionicons name="hand-left-outline" size={18} color={colors.accent} /></View>
        <View style={{ flex: 1 }}>
          <Text style={styles.tipTitle}>Your feed gets smarter</Text>
          <Text style={styles.tipText}>Save what you love. Pass on what you do not. Your choices become your taste profile.</Text>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { paddingHorizontal: 18, paddingTop: 8, paddingBottom: 30 },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 24 },
  eyebrow: { color: colors.textMuted, fontSize: 12, fontWeight: "700", letterSpacing: 0.4 },
  logo: { color: colors.text, fontSize: 28, fontWeight: "900", letterSpacing: -1.3, marginTop: 1 },
  logoDot: { color: colors.accent },
  locationPill: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 11, paddingVertical: 8, borderRadius: 99, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  locationText: { color: colors.text, fontSize: 12, fontWeight: "700" },
  intro: { marginBottom: 6 },
  heading: { color: colors.text, fontSize: 34, lineHeight: 37, fontWeight: "900", letterSpacing: -1.1 },
  subheading: { color: colors.textMuted, fontSize: 14, lineHeight: 20, marginTop: 8, maxWidth: 310 },
  tip: { flexDirection: "row", gap: 12, padding: 15, borderRadius: 18, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, marginTop: 4 },
  tipIcon: { width: 38, height: 38, borderRadius: 19, backgroundColor: colors.surfaceAlt, alignItems: "center", justifyContent: "center" },
  tipTitle: { color: colors.text, fontSize: 13, fontWeight: "800" },
  tipText: { color: colors.textMuted, fontSize: 11, lineHeight: 17, marginTop: 3 },
});