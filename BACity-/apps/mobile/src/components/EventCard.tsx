import { Ionicons } from "@expo/vector-icons";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { EventOut } from "../types/event";
import { colors } from "../theme/colors";
import { imageForCategory } from "../theme/categoryImages";
import { fonts } from "../theme/fonts";

function formatWhen(iso: string) {
  const d = new Date(iso);
  return (
    d.toLocaleDateString(undefined, {
      weekday: "short",
      day: "numeric",
      month: "short",
    }) +
    " · " +
    d.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    })
  );
}

function price(event: EventOut) {
  if (event.price === 0) return "FREE";
  if (event.price == null) return "TBD";
  return event.price + " " + (event.currency ?? "EUR");
}

export function EventCard({ event }: { event: EventOut }) {
  const image = event.image_url || imageForCategory(event.category);

  return (
    <Pressable
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
      onPress={() => router.push("/event/" + event.id)}
    >
      <Image source={{ uri: image }} style={styles.image} />
      <View style={styles.body}>
        <View style={styles.metaRow}>
          <View style={styles.categoryPill}>
            <Text style={styles.category}>{event.category}</Text>
          </View>
          <Text style={[styles.price, event.price === 0 && styles.free]}>{price(event)}</Text>
        </View>
        <Text style={styles.title} numberOfLines={2}>
          {event.title}
        </Text>
        <View style={styles.detail}>
          <Ionicons name="calendar-outline" size={14} color={colors.primary} />
          <Text style={styles.detailText}>{formatWhen(event.start_time)}</Text>
        </View>
        <View style={styles.detail}>
          <Ionicons name="location-outline" size={14} color={colors.primary} />
          <Text style={styles.detailText} numberOfLines={1}>
            {event.venue?.name ?? event.address ?? "Bratislava"}
          </Text>
        </View>
      </View>
      <View style={styles.chevron}>
        <Ionicons name="open-outline" size={14} color={colors.text} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    minHeight: 136,
    backgroundColor: colors.surface,
    borderRadius: 24,
    marginBottom: 12,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: colors.border,
    shadowColor: colors.shadow,
    shadowOpacity: 0.09,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 7 },
    elevation: 2,
  },
  pressed: {
    transform: [{ scale: 0.985 }],
    opacity: 0.96,
  },
  image: {
    width: 116,
    height: 136,
    backgroundColor: colors.primarySoft,
  },
  body: { flex: 1, padding: 14, paddingRight: 36 },
  metaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  categoryPill: {
    backgroundColor: colors.primarySoft,
    paddingHorizontal: 9,
    paddingVertical: 5,
    borderRadius: 99,
  },
  category: {
    color: colors.primaryDark,
    fontFamily: fonts.semibold,
    fontSize: 8,
    letterSpacing: 0.4,
  },
  price: { color: colors.textMuted, fontFamily: fonts.semibold, fontSize: 9 },
  free: { color: colors.free },
  title: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 16,
    lineHeight: 20,
    marginBottom: 7,
  },
  detail: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    marginTop: 3,
  },
  detailText: {
    color: colors.textMuted,
    fontFamily: fonts.medium,
    fontSize: 10,
    flex: 1,
  },
  chevron: {
    position: "absolute",
    right: 10,
    bottom: 10,
    width: 30,
    height: 30,
    borderRadius: 11,
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },
});
