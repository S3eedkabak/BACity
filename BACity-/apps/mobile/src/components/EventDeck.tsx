import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useRef, useState } from "react";
import {
  Animated,
  Dimensions,
  Image,
  PanResponder,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as eventsApi from "../api/events";
import { EventOut } from "../types/event";
import { useAuthStore } from "../store/authStore";
import { colors } from "../theme/colors";

const { width: SCREEN_WIDTH } = Dimensions.get("window");
const SWIPE_THRESHOLD = SCREEN_WIDTH * 0.25;

function formatDate(iso: string) {
  const d = new Date(iso);
  return {
    day: d.toLocaleDateString(undefined, { weekday: "short" }).toUpperCase(),
    date: d.toLocaleDateString(undefined, { day: "numeric", month: "short" }),
    time: d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }),
  };
}

function priceLabel(event: EventOut) {
  if (event.price === 0) return "FREE";
  if (event.price == null) return "PRICE TBD";
  return `${event.price} ${event.currency ?? "EUR"}`;
}

function Card({ event, position, total }: { event: EventOut; position: number; total: number }) {
  const date = formatDate(event.start_time);
  const rotate = useRef(new Animated.Value(0)).current;
  const scale = useRef(new Animated.Value(1)).current;
  const [leaving, setLeaving] = useState<"like" | "pass" | null>(null);
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  const save = useMutation({
    mutationFn: () => eventsApi.saveEvent(event.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["saved-events"] }),
  });

  const finish = (direction: "like" | "pass") => {
    setLeaving(direction);
    Animated.parallel([
      Animated.timing(rotate, { toValue: direction === "like" ? 1 : -1, duration: 260, useNativeDriver: true }),
      Animated.timing(scale, { toValue: 0.92, duration: 260, useNativeDriver: true }),
    ]).start(({ finished }) => {
      if (finished && direction === "like" && token) save.mutate();
      if (finished) router.push({ pathname: "/event/[id]", params: { id: event.id, fromDeck: "true" } });
    });
  };

  const pan = useRef(new Animated.ValueXY()).current;
  const panResponder = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dx) > 8 || Math.abs(g.dy) > 8,
      onPanResponderMove: (_, g) => {
        pan.setValue({ x: g.dx, y: g.dy * 0.12 });
        rotate.setValue(g.dx / SCREEN_WIDTH);
      },
      onPanResponderRelease: (_, g) => {
        if (Math.abs(g.dx) > SWIPE_THRESHOLD) {
          const direction = g.dx > 0 ? "like" : "pass";
          Animated.parallel([
            Animated.timing(pan, { toValue: { x: direction === "like" ? SCREEN_WIDTH * 1.35 : -SCREEN_WIDTH * 1.35, y: g.dy * 0.12 }, duration: 240, useNativeDriver: true }),
            Animated.timing(scale, { toValue: 0.92, duration: 240, useNativeDriver: true }),
          ]).start(() => {
            if (direction === "like" && token) save.mutate();
            router.push({ pathname: "/event/[id]", params: { id: event.id, fromDeck: "true" } });
          });
        } else {
          Animated.spring(pan, { toValue: { x: 0, y: 0 }, useNativeDriver: true }).start();
          Animated.spring(rotate, { toValue: 0, useNativeDriver: true }).start();
        }
      },
    })
  ).current;

  const cardTransform = [
    ...pan.getTranslateTransform(),
    { rotate: rotate.interpolate({ inputRange: [-1, 0, 1], outputRange: ["-9deg", "0deg", "9deg"] }) },
    { scale },
  ];

  return (
    <Animated.View
      {...panResponder.panHandlers}
      style={[styles.card, cardTransform, position > 0 && styles.behindCard]}
    >
      <View style={styles.imageWrap}>
        {event.image_url ? (
          <Image source={{ uri: event.image_url }} style={styles.image} resizeMode="cover" />
        ) : (
          <View style={styles.fallback}>
            <View style={styles.fallbackOrbOne} />
            <View style={styles.fallbackOrbTwo} />
            <Ionicons name="sparkles" size={48} color="#FFFFFF" />
          </View>
        )}
        <View style={styles.imageShade} />
        <View style={styles.topRow}>
          <View style={styles.categoryPill}>
            <Text style={styles.categoryText}>{event.category}</Text>
          </View>
          <View style={styles.pricePill}>
            <Text style={styles.priceText}>{priceLabel(event)}</Text>
          </View>
        </View>
        {leaving && (
          <View style={[styles.verdict, leaving === "like" ? styles.likeVerdict : styles.passVerdict]}>
            <Text style={styles.verdictText}>{leaving === "like" ? "SAVED" : "PASS"}</Text>
          </View>
        )}
        <View style={styles.imageBottom}>
          <Text style={styles.title}>{event.title}</Text>
          <View style={styles.locationLine}>
            <Ionicons name="location-outline" size={15} color="#fff" />
            <Text style={styles.location} numberOfLines={1}>{event.venue?.name ?? event.address ?? "Bratislava"}</Text>
          </View>
        </View>
      </View>

      <View style={styles.info}>
        <View style={styles.dateBox}>
          <Text style={styles.dateDay}>{date.day}</Text>
          <Text style={styles.dateNumber}>{date.date}</Text>
        </View>
        <View style={styles.infoCopy}>
          <Text style={styles.time}>{date.time}</Text>
          <Text style={styles.hint}>Swipe right to save · left to pass</Text>
        </View>
        <Pressable style={styles.details} onPress={() => router.push(`/event/${event.id}`)}>
          <Ionicons name="arrow-forward" size={20} color={colors.text} />
        </Pressable>
      </View>

      <Text style={styles.counter}>{position + 1} / {total}</Text>
    </Animated.View>
  );
}

export function EventDeck({ events }: { events: EventOut[] }) {
  const [index, setIndex] = useState(0);
  const visible = events.slice(index, index + 2);

  if (!events.length || index >= events.length) {
    return (
      <View style={styles.done}>
        <View style={styles.doneIcon}><Ionicons name="checkmark" size={30} color={colors.background} /></View>
        <Text style={styles.doneTitle}>You're all caught up</Text>
        <Text style={styles.doneText}>You've seen every event in this batch. Check Explore for more.</Text>
      </View>
    );
  }

  return (
    <View style={styles.deck}>
      {visible.slice().reverse().map((event, reversed) => {
        const position = visible.length - 1 - reversed;
        return <Card key={event.id} event={event} position={position} total={events.length} />;
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  deck: { height: 590, width: "100%", alignItems: "center", justifyContent: "center" },
  card: {
    position: "absolute", width: "100%", height: 570, borderRadius: 28,
    backgroundColor: colors.surface, overflow: "hidden",
    shadowColor: "#000", shadowOpacity: 0.35, shadowRadius: 24, shadowOffset: { width: 0, height: 12 }, elevation: 10,
  },
  behindCard: { transform: [{ scale: 0.96 }, { translateY: 12 }] },
  imageWrap: { height: 405, overflow: "hidden", backgroundColor: colors.surfaceAlt },
  image: { width: "100%", height: "100%" },
  imageShade: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(0,0,0,0.24)" },
  fallback: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: "#24213F" },
  fallbackOrbOne: { position: "absolute", width: 260, height: 260, borderRadius: 130, backgroundColor: "#7C6CFF", opacity: 0.45, top: -70, right: -50 },
  fallbackOrbTwo: { position: "absolute", width: 190, height: 190, borderRadius: 95, backgroundColor: "#21D4FD", opacity: 0.35, bottom: -55, left: -35 },
  topRow: { position: "absolute", top: 18, left: 18, right: 18, flexDirection: "row", justifyContent: "space-between" },
  categoryPill: { backgroundColor: "rgba(10,10,16,0.72)", paddingHorizontal: 12, paddingVertical: 8, borderRadius: 99 },
  categoryText: { color: "#fff", fontSize: 11, fontWeight: "800", letterSpacing: 0.7 },
  pricePill: { backgroundColor: "#fff", paddingHorizontal: 12, paddingVertical: 8, borderRadius: 99 },
  priceText: { color: "#111", fontSize: 11, fontWeight: "800" },
  imageBottom: { position: "absolute", left: 20, right: 20, bottom: 20 },
  title: { color: "#fff", fontSize: 29, lineHeight: 33, fontWeight: "900", letterSpacing: -0.7 },
  locationLine: { flexDirection: "row", alignItems: "center", gap: 5, marginTop: 9 },
  location: { color: "rgba(255,255,255,0.88)", fontSize: 13, flex: 1 },
  verdict: { position: "absolute", top: 145, paddingHorizontal: 22, paddingVertical: 10, borderRadius: 12, borderWidth: 3, transform: [{ rotate: "-12deg" }] },
  likeVerdict: { left: 24, borderColor: "#65E6A6" },
  passVerdict: { right: 24, borderColor: "#FF6B7A", transform: [{ rotate: "12deg" }] },
  verdictText: { color: "#fff", fontSize: 20, fontWeight: "900" },
  info: { flex: 1, flexDirection: "row", alignItems: "center", paddingHorizontal: 18, gap: 12 },
  dateBox: { width: 56, height: 56, borderRadius: 16, backgroundColor: colors.surfaceAlt, alignItems: "center", justifyContent: "center" },
  dateDay: { color: colors.accent, fontSize: 9, fontWeight: "900" },
  dateNumber: { color: colors.text, fontSize: 14, fontWeight: "800", marginTop: 2 },
  infoCopy: { flex: 1 },
  time: { color: colors.text, fontSize: 15, fontWeight: "800" },
  hint: { color: colors.textMuted, fontSize: 11, marginTop: 3 },
  details: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.surfaceAlt, alignItems: "center", justifyContent: "center" },
  counter: { position: "absolute", right: 18, bottom: 8, color: colors.textMuted, fontSize: 10 },
  done: { height: 400, alignItems: "center", justifyContent: "center", padding: 40 },
  doneIcon: { width: 64, height: 64, borderRadius: 32, backgroundColor: colors.accent, alignItems: "center", justifyContent: "center", marginBottom: 16 },
  doneTitle: { color: colors.text, fontSize: 21, fontWeight: "900" },
  doneText: { color: colors.textMuted, fontSize: 14, textAlign: "center", lineHeight: 21, marginTop: 8 },
});
