import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { useMemo } from "react";
import {
  Image,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useEvents } from "../../src/hooks/useEvents";
import { EventCard } from "../../src/components/EventCard";
import { EmptyState } from "../../src/components/EmptyState";
import { LoadingState } from "../../src/components/LoadingState";
import { BrandMark } from "../../src/components/BrandMark";
import { useAuthStore } from "../../src/store/authStore";
import { imageForCategory } from "../../src/theme/categoryImages";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";
import { EventOut } from "../../src/types/event";

const FILTERS = ["All", "Music", "Culture", "Nightlife", "Free"];

function dateParts(iso: string) {
  const date = new Date(iso);
  return {
    day: date.toLocaleDateString(undefined, { weekday: "short" }).toUpperCase(),
    date: date.toLocaleDateString(undefined, { day: "numeric", month: "short" }),
    time: date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }),
  };
}

function priceLabel(event: EventOut) {
  if (event.price === 0) return "FREE";
  if (event.price == null) return "PRICE TBD";
  return `${event.price} ${event.currency ?? "EUR"}`;
}

function FeaturedEvent({ event }: { event: EventOut }) {
  const date = dateParts(event.start_time);
  return (
    <Pressable
      onPress={() => router.push("/event/" + event.id)}
      style={({ pressed }) => [styles.featured, pressed && styles.pressed]}
    >
      <Image
        source={{ uri: event.image_url || imageForCategory(event.category) }}
        style={styles.featuredImage}
      />
      <View style={styles.featuredShade} />
      <View style={styles.featuredTop}>
        <View style={styles.dateBadge}>
          <Text style={styles.dateDay}>{date.day}</Text>
          <Text style={styles.dateDate}>{date.date}</Text>
        </View>
        <View style={styles.priceBadge}>
          <Text style={styles.priceText}>{priceLabel(event)}</Text>
        </View>
      </View>
      <View style={styles.featuredBottom}>
        <View style={styles.categoryBadge}>
          <Text style={styles.categoryText}>{event.category}</Text>
        </View>
        <Text style={styles.featuredTitle} numberOfLines={2}>
          {event.title}
        </Text>
        <View style={styles.metaRow}>
          <Ionicons name="location-outline" size={15} color={colors.white} />
          <Text style={styles.metaText} numberOfLines={1}>
            {event.venue?.name ?? event.address ?? "Bratislava"}
          </Text>
          <View style={styles.metaDot} />
          <Text style={styles.metaText}>{date.time}</Text>
        </View>
      </View>
    </Pressable>
  );
}

export default function HomeScreen() {
  const { data, isLoading, isError, refetch, isRefetching } = useEvents({ limit: 24 });
  const user = useAuthStore((s) => s.user);
  const events = useMemo(() => data?.items ?? [], [data]);
  const featured = events[0];
  const more = events.slice(1, 7);
  const initial = (user?.display_name || user?.email || "B")[0].toUpperCase();

  if (isLoading) return <LoadingState />;

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
      refreshControl={
        <RefreshControl
          refreshing={isRefetching}
          onRefresh={refetch}
          tintColor={colors.primary}
        />
      }
    >
      <View style={styles.topbar}>
        <View>
          <Text style={styles.hello}>{user ? "Welcome back" : "Live in Bratislava"}</Text>
          <BrandMark compact />
        </View>
        <View style={styles.topActions}>
          <Pressable style={styles.iconButton} onPress={() => router.push("/(tabs)/explore")}>
            <Ionicons name="search" size={19} color={colors.text} />
          </Pressable>
          <Pressable style={styles.iconButton} onPress={() => router.push("/community")}>
            <Ionicons name="notifications-outline" size={19} color={colors.text} />
          </Pressable>
          <Pressable style={styles.avatar} onPress={() => router.push("/(tabs)/profile")}>
            <Text style={styles.avatarText}>{initial}</Text>
          </Pressable>
        </View>
      </View>

      <View style={styles.intro}>
        <Text style={styles.kicker}>LIVE MOMENT</Text>
        <Text style={styles.headline}>
          Explore <Text style={styles.headlineAccent}>the events</Text>
        </Text>
        <Text style={styles.subtitle}>Small gigs, markets, culture and the things the city forgot to advertise.</Text>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.filters}
      >
        {FILTERS.map((filter, index) => (
          <Pressable
            key={filter}
            style={[styles.filter, index === 0 && styles.filterActive]}
            onPress={() => router.push("/(tabs)/explore")}
          >
            <Text style={[styles.filterText, index === 0 && styles.filterTextActive]}>{filter}</Text>
          </Pressable>
        ))}
      </ScrollView>

      {isError ? (
        <EmptyState
          title="The city feed is offline"
          subtitle="Check the API connection and try again."
          action="Try again"
          onAction={() => refetch()}
        />
      ) : featured ? (
        <>
          <FeaturedEvent event={featured} />

          <View style={styles.sectionHeader}>
            <View>
              <Text style={styles.sectionTitle}>More happening</Text>
              <Text style={styles.sectionCaption}>Fresh picks around Bratislava</Text>
            </View>
            <Pressable onPress={() => router.push("/(tabs)/explore")}>
              <Text style={styles.seeAll}>See all</Text>
            </Pressable>
          </View>

          {more.map((event) => (
            <EventCard key={event.id} event={event} />
          ))}
        </>
      ) : (
        <EmptyState
          title="The city is quiet"
          subtitle="Fresh events will appear here as soon as BACity finds them."
        />
      )}

      <Pressable style={styles.communityBanner} onPress={() => router.push("/community")}>
        <View style={styles.communityIcon}>
          <Ionicons name="people-outline" size={20} color={colors.primaryDark} />
        </View>
        <View style={styles.communityCopy}>
          <Text style={styles.communityTitle}>Know something we don't?</Text>
          <Text style={styles.communityText}>Add an event or local tip and help the city stay current.</Text>
        </View>
        <Ionicons name="arrow-forward" size={18} color={colors.text} />
      </Pressable>
    </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  container: { flex: 1, backgroundColor: colors.background },
  content: { paddingHorizontal: 18, paddingTop: 12, paddingBottom: 112 },
  topbar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 28,
  },
  hello: {
    color: colors.textMuted,
    fontFamily: fonts.medium,
    fontSize: 10,
    marginBottom: 1,
  },
  topActions: { flexDirection: "row", alignItems: "center", gap: 7 },
  iconButton: {
    width: 40,
    height: 40,
    borderRadius: 15,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 15,
    backgroundColor: colors.text,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: { color: colors.white, fontFamily: fonts.black, fontSize: 13 },
  intro: { marginBottom: 17 },
  kicker: {
    color: colors.primaryDark,
    fontFamily: fonts.black,
    fontSize: 9,
    letterSpacing: 1.7,
  },
  headline: {
    color: colors.text,
    fontFamily: fonts.regular,
    fontSize: 38,
    lineHeight: 41,
    letterSpacing: -1.7,
    marginTop: 5,
  },
  headlineAccent: { fontFamily: fonts.black, fontStyle: "italic" },
  subtitle: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 8,
    maxWidth: 330,
  },
  filters: { gap: 8, paddingRight: 10, paddingBottom: 18 },
  filter: {
    paddingHorizontal: 16,
    minHeight: 36,
    borderRadius: 18,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  filterActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  filterText: { color: colors.textMuted, fontFamily: fonts.semibold, fontSize: 10 },
  filterTextActive: { color: colors.white },
  featured: {
    height: 408,
    borderRadius: 28,
    overflow: "hidden",
    backgroundColor: colors.primarySoft,
    shadowColor: colors.shadow,
    shadowOpacity: 0.18,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 9 },
    elevation: 6,
  },
  pressed: { opacity: 0.95, transform: [{ scale: 0.992 }] },
  featuredImage: { width: "100%", height: "100%" },
  featuredShade: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(25,18,21,0.28)",
  },
  featuredTop: {
    position: "absolute",
    left: 14,
    right: 14,
    top: 14,
    flexDirection: "row",
    justifyContent: "space-between",
  },
  dateBadge: {
    backgroundColor: "rgba(255,255,255,0.94)",
    borderRadius: 17,
    paddingHorizontal: 11,
    paddingVertical: 9,
    alignItems: "center",
  },
  dateDay: { color: colors.primaryDark, fontFamily: fonts.black, fontSize: 8, letterSpacing: 0.7 },
  dateDate: { color: colors.text, fontFamily: fonts.black, fontSize: 12, marginTop: 2 },
  priceBadge: {
    alignSelf: "flex-start",
    backgroundColor: "rgba(39,35,41,0.78)",
    borderRadius: 99,
    paddingHorizontal: 11,
    paddingVertical: 8,
  },
  priceText: { color: colors.white, fontFamily: fonts.semibold, fontSize: 9 },
  featuredBottom: { position: "absolute", left: 17, right: 17, bottom: 17 },
  categoryBadge: {
    alignSelf: "flex-start",
    backgroundColor: colors.primary,
    borderRadius: 99,
    paddingHorizontal: 10,
    paddingVertical: 6,
    marginBottom: 8,
  },
  categoryText: { color: colors.white, fontFamily: fonts.black, fontSize: 9 },
  featuredTitle: {
    color: colors.white,
    fontFamily: fonts.black,
    fontSize: 27,
    lineHeight: 30,
    letterSpacing: -0.7,
  },
  metaRow: { flexDirection: "row", alignItems: "center", gap: 5, marginTop: 9 },
  metaText: {
    color: "rgba(255,255,255,0.9)",
    fontFamily: fonts.medium,
    fontSize: 10,
    maxWidth: 190,
  },
  metaDot: { width: 3, height: 3, borderRadius: 2, backgroundColor: "rgba(255,255,255,0.65)", marginHorizontal: 3 },
  sectionHeader: {
    marginTop: 28,
    marginBottom: 12,
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
  },
  sectionTitle: { color: colors.text, fontFamily: fonts.black, fontSize: 20, letterSpacing: -0.5 },
  sectionCaption: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 10, marginTop: 2 },
  seeAll: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 11 },
  communityBanner: {
    marginTop: 12,
    padding: 14,
    borderRadius: 22,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: "row",
    alignItems: "center",
    gap: 11,
  },
  communityIcon: {
    width: 44,
    height: 44,
    borderRadius: 15,
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },
  communityCopy: { flex: 1 },
  communityTitle: { color: colors.text, fontFamily: fonts.black, fontSize: 12 },
  communityText: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 10, lineHeight: 15, marginTop: 2 },
});
