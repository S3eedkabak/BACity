import { Ionicons } from "@expo/vector-icons";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { EventOut } from "../types/event";
import { colors } from "../theme/colors";

function formatWhen(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" }) +
    " · " + d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function price(event: EventOut) {
  if (event.price === 0) return "FREE";
  if (event.price == null) return "TBD";
  return `${event.price} ${event.currency ?? "EUR"}`;
}

export function EventCard({ event }: { event: EventOut }) {
  return (
    <Pressable style={styles.card} onPress={() => router.push(`/event/${event.id}`)}>
      {event.image_url ? (
        <Image source={{ uri: event.image_url }} style={styles.image} />
      ) : (
        <View style={styles.fallback}><Ionicons name="sparkles" size={26} color={colors.accent} /></View>
      )}
      <View style={styles.body}>
        <View style={styles.metaRow}>
          <Text style={styles.category}>{event.category.toUpperCase()}</Text>
          <Text style={[styles.price, event.price === 0 && styles.free]}>{price(event)}</Text>
        </View>
        <Text style={styles.title} numberOfLines={2}>{event.title}</Text>
        <View style={styles.detail}><Ionicons name="calendar-outline" size={14} color={colors.textMuted} /><Text style={styles.detailText}>{formatWhen(event.start_time)}</Text></View>
        <View style={styles.detail}><Ionicons name="location-outline" size={14} color={colors.textMuted} /><Text style={styles.detailText} numberOfLines={1}>{event.venue?.name ?? event.address ?? "Bratislava"}</Text></View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { flexDirection: "row", minHeight: 132, backgroundColor: colors.surface, borderRadius: 20, marginBottom: 12, overflow: "hidden", borderWidth: 1, borderColor: colors.border },
  image: { width: 116, height: 132, backgroundColor: colors.surfaceAlt },
  fallback: { width: 116, height: 132, backgroundColor: colors.surfaceAlt, alignItems: "center", justifyContent: "center" },
  body: { flex: 1, padding: 13 },
  metaRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 6 },
  category: { color: colors.accent, fontSize: 9, fontWeight: "900", letterSpacing: 0.8 },
  price: { color: colors.textMuted, fontSize: 10, fontWeight: "800" },
  free: { color: colors.free },
  title: { color: colors.text, fontSize: 15, lineHeight: 19, fontWeight: "800", marginBottom: 8 },
  detail: { flexDirection: "row", alignItems: "center", gap: 5, marginTop: 3 },
  detailText: { color: colors.textMuted, fontSize: 11, flex: 1 },
});