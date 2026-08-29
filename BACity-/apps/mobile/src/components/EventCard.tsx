import { Pressable, StyleSheet, Text, View } from "react-native";
import { Link } from "expo-router";
import { EventOut } from "../types/event";
import { colors } from "../theme/colors";

function formatWhen(iso: string): string {
  const d = new Date(iso);
  const day = d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
  const time = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  return `${day} · ${time}`;
}

function formatPrice(price: number | null, currency: string | null): string {
  if (price === null || price === undefined) return "Price unknown";
  if (price === 0) return "Free";
  return `${price} ${currency ?? "EUR"}`;
}

export function EventCard({ event }: { event: EventOut }) {
  return (
    <Link href={`/event/${event.id}`} asChild>
      <Pressable style={styles.card}>
        <View style={styles.rowBetween}>
          <Text style={styles.category}>{event.category.toUpperCase()}</Text>
          <Text style={[styles.price, event.price === 0 && styles.priceFree]}>
            {formatPrice(event.price, event.currency)}
          </Text>
        </View>
        <Text style={styles.title} numberOfLines={2}>{event.title}</Text>
        <Text style={styles.when}>{formatWhen(event.start_time)}</Text>
        {event.venue?.name && <Text style={styles.venue}>{event.venue.name}</Text>}
      </Pressable>
    </Link>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", marginBottom: 6 },
  category: { color: colors.accent, fontSize: 11, fontWeight: "700", letterSpacing: 0.5 },
  price: { color: colors.textMuted, fontSize: 12, fontWeight: "600" },
  priceFree: { color: colors.free },
  title: { color: colors.text, fontSize: 16, fontWeight: "700", marginBottom: 4 },
  when: { color: colors.textMuted, fontSize: 13 },
  venue: { color: colors.textMuted, fontSize: 13, marginTop: 2 },
});