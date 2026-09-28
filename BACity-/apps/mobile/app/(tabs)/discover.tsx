import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { ActivityIndicator, FlatList, Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { getNotifications } from "../../src/api/community";
import { apiRequest } from "../../src/api/client";
import { RecommendationItem } from "../../src/api/recommendations";
import { BrandMark } from "../../src/components/BrandMark";
import { EmptyState } from "../../src/components/EmptyState";
import { EventCard } from "../../src/components/EventCard";
import { LoadingState } from "../../src/components/LoadingState";
import { IconButton, SectionHeader, SkeletonList } from "../../src/components/SocialUI";
import { useEvents, useToggleSaveEvent } from "../../src/hooks/useEvents";
import { useRecommendations } from "../../src/hooks/useRecommendations";
import { excludeFeaturedEvent, selectFeaturedEvent } from "../../src/recommendations/homeFeed";
import { useRecommendationLocation } from "../../src/recommendations/useRecommendationLocation";
import { useAuthStore } from "../../src/store/authStore";
import { imageForCategory } from "../../src/theme/categoryImages";
import { PlusGateAction } from "../../src/plus/usePlusGate";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";
import { EventOut } from "../../src/types/event";
import { eveningPlanRoute } from "../../src/evening/presentation";
import { weekendPlanRoute } from "../../src/weekend/presentation";

const FILTERS = ["All", "Music", "Culture", "Nightlife", "Free"];

function preferredExplanation(reasons: string[]) {
  return reasons.find((reason) => reason !== "Matches your interests") ?? reasons[0];
}

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

function LocationPreference({ location }: { location: ReturnType<typeof useRecommendationLocation> }) {
  if (location.enabled === null) {
    return <View style={styles.locationCard}>
      <View style={styles.locationIcon}><Ionicons name="navigate-outline" size={19} color={colors.primaryDark} /></View>
      <View style={styles.locationCopy}>
        <Text style={styles.locationTitle}>Find events near you</Text>
        <Text style={styles.locationText}>BACity can use one approximate, foreground location. You can continue without it.</Text>
      </View>
      <View style={styles.locationActions}>
        <Pressable accessibilityRole="button" onPress={() => void location.enable()} style={styles.locationPrimary}><Text style={styles.locationPrimaryText}>Enable</Text></Pressable>
        <Pressable accessibilityRole="button" onPress={() => void location.disable()} style={styles.locationSecondary}><Text style={styles.locationSecondaryText}>Not now</Text></Pressable>
      </View>
    </View>;
  }

  const statusCopy = location.status === "granted"
    ? "Using an approximate current location"
    : location.status === "locating"
      ? "Finding your approximate location…"
      : location.status === "blocked"
        ? "BACity location is on, but OS permission is blocked"
        : location.status === "denied"
          ? "BACity location is on, but OS permission was denied"
          : location.status === "unavailable"
            ? "Location services are unavailable"
            : location.status === "timeout"
              ? "No location fix yet · check the emulator or GPS"
              : location.status === "outside-area"
                ? "Outside Bratislava · using the citywide feed"
                : location.enabled
                  ? "Location could not be read · using the citywide feed"
                  : "Location-based recommendations are off";

  return <View style={styles.locationStatus}>
    <Ionicons name={location.status === "granted" ? "navigate" : "navigate-outline"} size={16} color={colors.primaryDark} />
    <Text style={styles.locationStatusText}>{statusCopy}</Text>
    {location.status === "blocked" ? <Pressable onPress={() => void location.openSettings()}><Text style={styles.locationLink}>Settings</Text></Pressable> : null}
    {location.enabled && ["denied", "unavailable", "timeout", "error"].includes(location.status) ? <Pressable onPress={() => void location.retry()}><Text style={styles.locationLink}>Retry</Text></Pressable> : null}
    <Pressable onPress={() => void (location.enabled ? location.disable() : location.enable())}>
      <Text style={styles.locationLink}>{location.enabled ? "Turn off" : "Enable"}</Text>
    </Pressable>
  </View>;
}

function TonightEntry() {
  return <PlusGateAction feature="tonight" onAllowed={() => router.push("/tonight")}>
    {({ onPress, loading }) => <Pressable
      accessibilityRole="button"
      accessibilityLabel="Open Tonight and Right Now"
      disabled={loading}
      onPress={onPress}
      style={({ pressed }) => [styles.tonightEntry, pressed && styles.pressed, loading && styles.tonightDisabled]}
    >
      <View style={styles.tonightIcon}><Ionicons name="moon" size={21} color={colors.white} /></View>
      <View style={styles.tonightCopy}><Text style={styles.tonightTitle}>Tonight / Right Now</Text><Text style={styles.tonightText}>A small set of realistic options for this evening.</Text></View>
      {loading ? <ActivityIndicator color={colors.primaryDark} /> : <Ionicons name="chevron-forward" size={18} color={colors.text} />}
    </Pressable>}
  </PlusGateAction>;
}

function EveningPlanEntry() {
  return <PlusGateAction feature="build_my_evening" onAllowed={() => router.push(eveningPlanRoute())}>
    {({ onPress, loading }) => <Pressable
      accessibilityRole="button"
      accessibilityLabel="Build My Evening"
      disabled={loading}
      onPress={onPress}
      style={({ pressed }) => [styles.tonightEntry, pressed && styles.pressed, loading && styles.tonightDisabled]}
    >
      <View style={styles.eveningIcon}><Ionicons name="sparkles" size={21} color={colors.white} /></View>
      <View style={styles.tonightCopy}><Text style={styles.tonightTitle}>Build My Evening</Text><Text style={styles.tonightText}>Turn a free evening into a realistic plan.</Text></View>
      {loading ? <ActivityIndicator color={colors.primaryDark} /> : <Ionicons name="chevron-forward" size={18} color={colors.text} />}
    </Pressable>}
  </PlusGateAction>;
}

function WeekendPlanEntry() {
  return <PlusGateAction feature="weekend_generator" onAllowed={() => router.push(weekendPlanRoute())}>
    {({ onPress, loading }) => <Pressable
      accessibilityRole="button"
      accessibilityLabel="Open Weekend Generator"
      disabled={loading}
      onPress={onPress}
      style={({ pressed }) => [styles.tonightEntry, pressed && styles.pressed, loading && styles.tonightDisabled]}
    >
      <View style={styles.weekendIcon}><Ionicons name="calendar" size={21} color={colors.white} /></View>
      <View style={styles.tonightCopy}><Text style={styles.tonightTitle}>Weekend Generator</Text><Text style={styles.tonightText}>Build a realistic Saturday, Sunday, or full weekend.</Text></View>
      {loading ? <ActivityIndicator color={colors.primaryDark} /> : <Ionicons name="chevron-forward" size={18} color={colors.text} />}
    </Pressable>}
  </PlusGateAction>;
}

function GroupsEntry() {
  return <Pressable
    accessibilityRole="button"
    accessibilityLabel="Open Groups and Group Match"
    onPress={() => router.push("/groups")}
    style={({ pressed }) => [styles.tonightEntry, pressed && styles.pressed]}
  >
    <View style={styles.groupsIcon}><Ionicons name="people" size={21} color={colors.white} /></View>
    <View style={styles.tonightCopy}><Text style={styles.tonightTitle}>Groups & Group Match</Text><Text style={styles.tonightText}>Create with BACity+, or join and vote for free.</Text></View>
    <Ionicons name="chevron-forward" size={18} color={colors.text} />
  </Pressable>;
}

export default function HomeScreen() {
  const user = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.token);
  const location = useRecommendationLocation(!!token);
  const recommendations = useRecommendations(!!token, location.coordinates);
  const fallback = useEvents({ limit: 24 });
  const activity = useQuery({ queryKey: ["notifications"], queryFn: getNotifications, enabled: !!token, staleTime: 30_000 });
  const promotions = useQuery({ queryKey: ["promotions"], queryFn: () => apiRequest<any[]>("/promotions"), staleTime: 60_000 });
  const save = useToggleSaveEvent();
  const personalized = useMemo(() => recommendations.data?.pages.flat() ?? [], [recommendations.data]);
  const generic = useMemo<RecommendationItem[]>(
    () => (fallback.data?.items ?? []).map((event) => ({ event, reasons: ["Upcoming in Bratislava"], saved: false })),
    [fallback.data]
  );
  const featured = selectFeaturedEvent(fallback.data?.items ?? []);
  const items = excludeFeaturedEvent(token ? personalized : generic, featured?.id);
  const loading = token ? recommendations.isLoading : fallback.isLoading;
  const failed = token ? recommendations.isError : fallback.isError;
  const refreshing = fallback.isRefetching || (!!token && recommendations.isRefetching && !recommendations.isFetchingNextPage);
  const unreadActivity = activity.data?.some((item) => !item.read_at && item.kind !== "message") ?? false;
  const unreadMessages = activity.data?.some((item) => !item.read_at && item.kind === "message") ?? false;

  async function refresh() {
    const requests: Promise<unknown>[] = [fallback.refetch(), promotions.refetch()];
    if (token) requests.push(recommendations.refetch(), activity.refetch());
    await Promise.all(requests);
  }

  if (fallback.isLoading) return <LoadingState />;

  const header = <>
    <View style={styles.topbar}>
      <BrandMark compact />
      <View style={styles.topActions}>
        <IconButton icon="search" label="Search and explore" onPress={() => router.push("/(tabs)/explore")} />
        <IconButton icon="notifications-outline" label="Notifications" badge={unreadActivity} onPress={() => router.push("/notifications")} />
        <IconButton icon="chatbubble-ellipses-outline" label="Messages" badge={unreadMessages} onPress={() => router.push("/messages")} />
      </View>
    </View>
    <View style={styles.intro}>
      <Text style={styles.kicker}>{user ? "YOUR BRATISLAVA" : "LIVE MOMENT"}</Text>
      <Text style={styles.headline}>Explore <Text style={styles.headlineAccent}>the city</Text></Text>
      <Text style={styles.subtitle}>{user ? "A feed shaped by your interests, saves and local follows." : "Fresh events around Bratislava, with or without an account."}</Text>
    </View>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filters}>
      {FILTERS.map((filter, index) => <Pressable key={filter} style={[styles.filter, index === 0 && styles.filterActive]} onPress={() => router.push("/(tabs)/explore")}>
        <Text style={[styles.filterText, index === 0 && styles.filterTextActive]}>{filter}</Text>
      </Pressable>)}
    </ScrollView>
    {fallback.isError ? <EmptyState
      title="The city feed is offline"
      subtitle="Check the API connection and try again."
      action="Try again"
      onAction={() => void fallback.refetch()}
    /> : featured ? <FeaturedEvent event={featured} /> : !fallback.isLoading ? <EmptyState
      title="The city is quiet"
      subtitle="Fresh events will appear here as soon as BACity finds them."
    /> : null}
    <TonightEntry />
    <EveningPlanEntry />
    <WeekendPlanEntry />
    <GroupsEntry />
    {token ? <LocationPreference location={location} /> : null}
    <SectionHeader title={token ? "For you" : "Happening in Bratislava"} action="Explore" onAction={() => router.push("/(tabs)/explore")} />
    {loading ? <SkeletonList rows={5} /> : null}
    {failed && !items.length ? <EmptyState title="Your city feed is offline" subtitle="Cached content will remain when available. Check your connection and retry." action="Try again" onAction={() => void refresh()} /> : null}
    {!loading && !failed && !items.length ? <EmptyState title="Nothing upcoming yet" subtitle="BACity will show fresh Bratislava events here as they arrive." action="Explore events" onAction={() => router.push("/(tabs)/explore")} /> : null}
  </>;

  const footer = <>
    {recommendations.isFetchingNextPage ? <ActivityIndicator style={styles.pageLoader} color={colors.primary} /> : null}
    {recommendations.isFetchNextPageError ? <Pressable style={styles.retryPage} onPress={() => void recommendations.fetchNextPage()}><Text style={styles.locationLink}>Couldn’t load more · Retry</Text></Pressable> : null}
    {!!promotions.data?.length ? <>
      <SectionHeader title="Supported local picks" />
      {promotions.data.slice(0, 2).map((item) => <EventCard key={item.event.id} event={item.event} explanation={item.label} />)}
    </> : null}
    <Pressable style={styles.communityBanner} onPress={() => router.push("/(tabs)/contribute")}>
      <View style={styles.communityIcon}><Ionicons name="people-outline" size={20} color={colors.primaryDark} /></View>
      <View style={styles.communityCopy}><Text style={styles.communityTitle}>Know something we don’t?</Text><Text style={styles.communityText}>Add an event or local tip and help the city stay current.</Text></View>
      <Ionicons name="arrow-forward" size={18} color={colors.text} />
    </Pressable>
  </>;

  return <SafeAreaView style={styles.safe} edges={["top"]}>
    <FlatList
      data={loading && !items.length ? [] : items}
      keyExtractor={(item) => item.event.id}
      renderItem={({ item }) => <EventCard
        event={item.event}
        explanation={preferredExplanation(item.reasons)}
        saved={item.saved}
        saving={save.isPending && save.variables?.id === item.event.id}
        onToggleSave={token ? () => save.mutate({ id: item.event.id, saved: item.saved }) : undefined}
      />}
      ListHeaderComponent={header}
      ListFooterComponent={footer}
      contentContainerStyle={styles.content}
      style={styles.container}
      showsVerticalScrollIndicator={false}
      refreshing={refreshing}
      onRefresh={() => void refresh()}
      onEndReachedThreshold={0.45}
      onEndReached={() => {
        if (token && recommendations.hasNextPage && !recommendations.isFetchingNextPage) void recommendations.fetchNextPage();
      }}
    />
  </SafeAreaView>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  container: { flex: 1, backgroundColor: colors.background },
  content: { paddingHorizontal: 18, paddingTop: 12, paddingBottom: 112 },
  topbar: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 26 },
  topActions: { flexDirection: "row", alignItems: "center", gap: 7 },
  intro: { marginBottom: 17 },
  kicker: { color: colors.primaryDark, fontFamily: fonts.black, fontSize: 9, letterSpacing: 1.7 },
  headline: { color: colors.text, fontFamily: fonts.regular, fontSize: 38, lineHeight: 41, letterSpacing: -1.7, marginTop: 5 },
  headlineAccent: { fontFamily: fonts.black, fontStyle: "italic" },
  subtitle: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12, lineHeight: 18, marginTop: 8, maxWidth: 335 },
  filters: { gap: 8, paddingRight: 10, paddingBottom: 16 },
  filter: { paddingHorizontal: 16, minHeight: 36, borderRadius: 18, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center" },
  filterActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  filterText: { color: colors.textMuted, fontFamily: fonts.semibold, fontSize: 10 },
  filterTextActive: { color: colors.white },
  tonightEntry: { minHeight: 78, flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 22, paddingHorizontal: 14, marginTop: 16 },
  tonightDisabled: { opacity: .65 }, tonightIcon: { width: 46, height: 46, borderRadius: 17, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" },
  eveningIcon: { width: 46, height: 46, borderRadius: 17, backgroundColor: colors.primaryDark, alignItems: "center", justifyContent: "center" },
  weekendIcon: { width: 46, height: 46, borderRadius: 17, backgroundColor: "#7557A8", alignItems: "center", justifyContent: "center" },
  groupsIcon: { width: 46, height: 46, borderRadius: 17, backgroundColor: "#347A72", alignItems: "center", justifyContent: "center" },
  tonightCopy: { flex: 1 }, tonightTitle: { color: colors.text, fontFamily: fonts.black, fontSize: 15 }, tonightText: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 10, lineHeight: 15, marginTop: 3 },
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
  locationCard: { marginTop: 18, padding: 14, borderRadius: 22, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, flexDirection: "row", alignItems: "center", flexWrap: "wrap", gap: 10 },
  locationIcon: { width: 42, height: 42, borderRadius: 15, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" },
  locationCopy: { flex: 1, minWidth: 210 },
  locationTitle: { color: colors.text, fontFamily: fonts.black, fontSize: 12 },
  locationText: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 10, lineHeight: 15, marginTop: 2 },
  locationActions: { width: "100%", flexDirection: "row", gap: 8 },
  locationPrimary: { minHeight: 38, borderRadius: 14, paddingHorizontal: 14, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" },
  locationPrimaryText: { color: colors.white, fontFamily: fonts.semibold, fontSize: 10 },
  locationSecondary: { minHeight: 38, borderRadius: 14, paddingHorizontal: 14, backgroundColor: colors.surfaceAlt, alignItems: "center", justifyContent: "center" },
  locationSecondaryText: { color: colors.text, fontFamily: fonts.semibold, fontSize: 10 },
  locationStatus: { marginTop: 18, minHeight: 48, borderRadius: 17, paddingHorizontal: 12, backgroundColor: colors.primarySoft, flexDirection: "row", alignItems: "center", gap: 7 },
  locationStatusText: { flex: 1, color: colors.textMuted, fontFamily: fonts.medium, fontSize: 10 },
  locationLink: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 10 },
  pageLoader: { paddingVertical: 18 },
  retryPage: { alignItems: "center", paddingVertical: 16 },
  communityBanner: { marginTop: 18, padding: 14, borderRadius: 22, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, flexDirection: "row", alignItems: "center", gap: 11 },
  communityIcon: { width: 44, height: 44, borderRadius: 15, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" },
  communityCopy: { flex: 1 },
  communityTitle: { color: colors.text, fontFamily: fonts.black, fontSize: 12 },
  communityText: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 10, lineHeight: 15, marginTop: 2 },
});
