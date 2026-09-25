import { Ionicons } from "@expo/vector-icons";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { EventOut } from "../types/event";
import { colors } from "../theme/colors";
import { imageForCategory } from "../theme/categoryImages";
import { fonts } from "../theme/fonts";
import { AceSurface } from "./ui/AceSurface";

function formatWhen(iso: string) {
  const d = new Date(iso);
  return (
    d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" }) +
    " · " +
    d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
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
      style={({ pressed }) => [styles.pressable, pressed && styles.pressed]}
      onPress={() => router.push("/event/" + event.id)}
    >
      <AceSurface style={styles.card}>
        <View style={styles.imageWrap}>
          <Image source={{ uri: image }} style={styles.image} />
          <View style={styles.imageShade} />
          <View style={styles.imageBadge}>
            <Text style={styles.imageBadgeText}>{event.category}</Text>
          </View>
        </View>

        <View style={styles.body}>
          <View style={styles.metaRow}>
            <Text style={[styles.price, event.price === 0 && styles.free]}>{price(event)}</Text>
            <View style={styles.arrow}>
              <Ionicons name="arrow-up-right" size={14} color={colors.text} />
            </View>
          </View>

          <Text style={styles.title} numberOfLines={2}>{event.title}</Text>

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
      </AceSurface>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  pressable: { marginBottom: 13 },
  pressed: { transform: [{ scale: 0.987 }], opacity: 0.97 },
  card: {
    flexDirection: "row",
    minHeight: 132,
    borderRadius: 24,
  },
  imageWrap: {
    width: 112,
    minHeight: 132,
    overflow: "hidden",
    backgroundColor: colors.primarySoft,
  },
  image: { width: "100%", height: "100%" },
  imageShade: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(39,35,41,0.08)",
  },
  imageBadge: {
    position: "absolute",
    left: 9,
    top: 9,
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: 99,
    backgroundColor: "rgba(39,35,41,0.78)",
  },
  imageBadgeText: {
    color: colors.white,
    fontFamily: fonts.semibold,
    fontSize: 8,
    letterSpacing: 0.3,
  },
  body: { flex: 1, padding: 13 },
  metaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  price: { color: colors.textMuted, fontFamily: fonts.semibold, fontSize: 9 },
  free: { color: colors.free },
  title: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 16,
    lineHeight: 19,
    marginBottom: 8,
    paddingRight: 4,
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
  arrow: {
    width: 30,
    height: 30,
    borderRadius: 12,
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },
});
