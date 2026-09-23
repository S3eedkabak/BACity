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
import { imageForCategory } from "../theme/categoryImages";
import { fonts } from "../theme/fonts";

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
  return event.price + " " + (event.currency ?? "EUR");
}

function Card({
  event,
  position,
  total,
  onSwiped,
}: {
  event: EventOut;
  position: number;
  total: number;
  onSwiped: (direction: "like" | "pass") => void;
}) {
  const date = formatDate(event.start_time);
  const scale = useRef(new Animated.Value(1)).current;
  const pan = useRef(new Animated.ValueXY()).current;
  const [leaving, setLeaving] = useState<"like" | "pass" | null>(null);
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();

  const save = useMutation({
    mutationFn: () => eventsApi.saveEvent(event.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["saved-events"] }),
  });

  const completeSwipe = (direction: "like" | "pass") => {
    setLeaving(direction);
    const toX = direction === "like" ? SCREEN_WIDTH * 1.35 : -SCREEN_WIDTH * 1.35;

    Animated.parallel([
      Animated.timing(pan, {
        toValue: { x: toX, y: 0 },
        duration: 220,
        useNativeDriver: true,
      }),
      Animated.timing(scale, {
        toValue: 0.94,
        duration: 220,
        useNativeDriver: true,
      }),
    ]).start(() => {
      if (direction === "like" && token) save.mutate();
      onSwiped(direction);
    });
  };

  const panResponder = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, gesture) =>
        Math.abs(gesture.dx) > 8 || Math.abs(gesture.dy) > 8,
      onPanResponderMove: (_, gesture) => {
        pan.setValue({ x: gesture.dx, y: gesture.dy * 0.08 });
      },
      onPanResponderRelease: (_, gesture) => {
        if (Math.abs(gesture.dx) > SWIPE_THRESHOLD) {
          completeSwipe(gesture.dx > 0 ? "like" : "pass");
        } else {
          Animated.spring(pan, {
            toValue: { x: 0, y: 0 },
            useNativeDriver: true,
          }).start();
        }
      },
    })
  ).current;

  return (
    <Animated.View
      {...panResponder.panHandlers}
      style={[
        styles.card,
        { transform: [...pan.getTranslateTransform(), { scale }] },
        position > 0 && styles.behindCard,
      ]}
    >
      <View style={styles.imageWrap}>
        <Image
          source={{ uri: event.image_url || imageForCategory(event.category) }}
          style={styles.image}
          resizeMode="cover"
        />
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
          <Text style={styles.title} numberOfLines={2}>{event.title}</Text>
          <View style={styles.locationLine}>
            <Ionicons name="location-outline" size={15} color="#fff" />
            <Text style={styles.location} numberOfLines={1}>
              {event.venue?.name ?? event.address ?? "Bratislava"}
            </Text>
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
          <Text style={styles.hint}>Right to save · left to pass</Text>
        </View>
        <Pressable style={styles.details} onPress={() => router.push("/event/" + event.id)}>
          <Ionicons name="arrow-forward" size={19} color={colors.white} />
        </Pressable>
      </View>

      <Text style={styles.counter}>{position + 1} / {total}</Text>
    </Animated.View>
  );
}

export function EventDeck({ events }: { events: EventOut[] }) {
  const [index, setIndex] = useState(0);

  if (!events.length || index >= events.length) {
    return (
      <View style={styles.done}>
        <View style={styles.doneIcon}>
          <Ionicons name="checkmark" size={27} color={colors.white} />
        </View>
        <Text style={styles.doneTitle}>You're all caught up</Text>
        <Text style={styles.doneText}>
          You've seen this batch. Explore the city for more.
        </Text>
      </View>
    );
  }

  const visible = events.slice(index, index + 2);

  return (
    <View style={styles.deck}>
      {visible.slice().reverse().map((event, reversed) => {
        const position = visible.length - 1 - reversed;
        return (
          <Card
            key={event.id}
            event={event}
            position={position}
            total={events.length}
            onSwiped={() => setIndex((current) => current + 1)}
          />
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  deck: { height: 560, width: "100%", alignItems: "center", justifyContent: "center" },
  card: {
    position: "absolute",
    width: "100%",
    height: 540,
    borderRadius: 28,
    backgroundColor: colors.surface,
    overflow: "hidden",
    shadowColor: colors.shadow,
    shadowOpacity: 0.2,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 10 },
    elevation: 8,
  },
  behindCard: { transform: [{ scale: 0.96 }, { translateY: 10 }] },
  imageWrap: { height: 385, overflow: "hidden", backgroundColor: colors.primarySoft },
  image: { width: "100%", height: "100%" },
  imageShade: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(32,23,28,0.24)" },
  topRow: {
    position: "absolute",
    top: 16,
    left: 16,
    right: 16,
    flexDirection: "row",
    justifyContent: "space-between",
  },
  categoryPill: {
    backgroundColor: "rgba(39,35,41,0.78)",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 99,
  },
  categoryText: { color: "#fff", fontFamily: fonts.semibold, fontSize: 10 },
  pricePill: { backgroundColor: colors.white, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 99 },
  priceText: { color: colors.text, fontFamily: fonts.semibold, fontSize: 10 },
  imageBottom: { position: "absolute", left: 18, right: 18, bottom: 18 },
  title: {
    color: "#fff",
    fontFamily: fonts.black,
    fontSize: 27,
    lineHeight: 30,
    letterSpacing: -0.7,
  },
  locationLine: { flexDirection: "row", alignItems: "center", gap: 5, marginTop: 8 },
  location: { color: "rgba(255,255,255,0.9)", fontFamily: fonts.medium, fontSize: 12, flex: 1 },
  verdict: {
    position: "absolute",
    top: 135,
    paddingHorizontal: 20,
    paddingVertical: 9,
    borderRadius: 12,
    borderWidth: 3,
  },
  likeVerdict: { left: 22, borderColor: "#A5E7CB" },
  passVerdict: { right: 22, borderColor: "#FFB0B5" },
  verdictText: { color: "#fff", fontFamily: fonts.black, fontSize: 18 },
  info: { flex: 1, flexDirection: "row", alignItems: "center", paddingHorizontal: 17, gap: 11 },
  dateBox: {
    width: 55,
    height: 55,
    borderRadius: 16,
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },
  dateDay: { color: colors.primaryDark, fontFamily: fonts.black, fontSize: 8 },
  dateNumber: { color: colors.text, fontFamily: fonts.semibold, fontSize: 13, marginTop: 2 },
  infoCopy: { flex: 1 },
  time: { color: colors.text, fontFamily: fonts.black, fontSize: 14 },
  hint: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 10, marginTop: 3 },
  details: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  counter: {
    position: "absolute",
    right: 17,
    bottom: 7,
    color: colors.textMuted,
    fontFamily: fonts.medium,
    fontSize: 9,
  },
  done: { height: 350, alignItems: "center", justifyContent: "center", padding: 35 },
  doneIcon: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 15,
  },
  doneTitle: { color: colors.text, fontFamily: fonts.black, fontSize: 20 },
  doneText: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 13,
    textAlign: "center",
    lineHeight: 19,
    marginTop: 7,
  },
});
