import { FeaturedEvent } from '../../src/components/FeaturedEvent';
import { usePullRefresh } from "../../src/hooks/usePullRefresh";
import { SaveEventAction } from "../../src/components/interactions/SaveEventAction";
import { SegmentedControl } from "../../src/components/interactions/SegmentedControl";
import { ContentEntrance, ContentStages, TabScene } from "../../src/components/navigation/SceneMotion";
import { useNotificationSummary } from "../../src/hooks/useNotifications";
import { themedStyles, useThemeRevision } from "../../src/theme/appearance";
import { NotificationBell } from "../../src/components/interactions/NotificationBell";
import { AppIcon } from "../../src/components/AppIcon";
import { router } from "expo-router";
import { useMemo, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ActivityIndicator,
  FlatList,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { AnimatedPressable as Pressable } from "../../src/components/motion/Motion";
import { SafeAreaView } from "../../src/components/navigation/ContentSafeArea";
import { getNotifications } from "../../src/api/community";
import { apiRequest } from "../../src/api/client";
import { RecommendationItem } from "../../src/api/recommendations";
import { BrandMark } from "../../src/components/BrandMark";
import { EmptyState } from "../../src/components/EmptyState";
import { EventCard } from "../../src/components/EventCard";
import { EventMedia } from "../../src/components/EventMedia";
import { MediaScrim } from "../../src/components/MediaScrim";
import { LoadingState } from "../../src/components/LoadingState";
import {
  IconButton,
  SectionHeader,
  SkeletonList,
} from "../../src/components/SocialUI";
import { useEvents } from "../../src/hooks/useEvents";
import { useRecommendations } from "../../src/hooks/useRecommendations";
import {
  excludeFeaturedEvent,
  selectFeaturedEvent,
} from "../../src/recommendations/homeFeed";
import { useRecommendationLocation } from "../../src/recommendations/useRecommendationLocation";
import { useAuthStore } from "../../src/store/authStore";
import { colors } from "../../src/theme/colors";
import { fontStyles } from "../../src/theme/fonts";
import { EventOut } from "../../src/types/event";
import { tokens } from "../../src/theme/tokens";
import { useEventNavigation } from "../../src/hooks/useEventNavigation";
import { useMajorTransition } from "../../src/components/loading/LoadingExperience";

const FILTERS = ["All", "Music", "Culture", "Nightlife", "Free"];

function preferredExplanation(reasons: string[]) {
  return (
    reasons.find((reason) => reason !== "Matches your interests") ?? reasons[0]
  );
}

function PlusEntry({ onOpen }: { onOpen: () => void }) {
  useThemeRevision();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="Enter BACity Plus"
      onPress={onOpen}
      style={({ pressed }) => [styles.plusEntry, pressed && styles.pressed]}
    >
      <View style={styles.plusMark}>
        <AppIcon name="sparkles" size={24} color={colors.white} />
      </View>
      <View style={styles.plusCopy}>
        <Text style={styles.plusLabel}>BACITÝ+</Text>
        <Text style={styles.plusTitle}>Plans around your time & mood</Text>
      </View>
      <View style={styles.plusArrow}>
        <AppIcon name="arrow-forward" size={20} color={colors.primaryDark} />
      </View>
    </Pressable>
  );
}

function HomeScreen() {
  const pullRefresh = usePullRefresh(refresh);
  useThemeRevision();
  const revealed = useRef(new Set<string>());
  const user = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.token);
  const location = useRecommendationLocation(!!token);
  const major = useMajorTransition();
  const recommendations = useRecommendations(!!token, location.coordinates);
  const fallback = useEvents({ limit: 24 });
  const activity = useNotificationSummary();
  const promotions = useQuery({
    queryKey: ["promotions"],
    queryFn: () => apiRequest<any[]>("/promotions"),
    staleTime: 60_000,
  });
  const personalized = useMemo(
    () => recommendations.data?.pages.flat() ?? [],
    [recommendations.data],
  );
  const generic = useMemo<RecommendationItem[]>(
    () =>
      (fallback.data?.items ?? []).map((event) => ({
        event,
        reasons: ["Upcoming in Bratislava"],
        saved: false,
      })),
    [fallback.data],
  );
  const featured = selectFeaturedEvent(fallback.data?.items ?? []);
  const items = excludeFeaturedEvent(
    token ? personalized : generic,
    featured?.id,
  );
  const loading = token ? recommendations.isLoading : fallback.isLoading;
  const failed = token ? recommendations.isError : fallback.isError;
  const unreadMessages = (activity.data?.messages ?? 0) > 0;

  async function refresh() {
    const requests: Promise<unknown>[] = [
      fallback.refetch(),
      promotions.refetch(),
    ];
    if (token) requests.push(recommendations.refetch(), activity.refetch());
    await Promise.all(requests);
  }

  const fixedHeader = (
    <View style={styles.topbar}>
      <BrandMark compact />
      <View style={styles.topActions}>
        <IconButton
          icon="search"
          label="Search and explore"
          onPress={() => router.push("/(tabs)/explore")}
        />
        <NotificationBell />
      </View>
    </View>
  );

  const header = (
    <>
      <ContentEntrance><View style={styles.intro}>
        <Text style={styles.kicker}>{user ? "YOUR BRATISLAVA" : "LIVE MOMENT"}</Text>
        <Text style={styles.headline}>Find your next{'\n'}city moment.</Text>
        <Text style={styles.subtitle}>{user ? "Good events, chosen around you." : "Good events. Local places. Your Bratislava."}</Text>
      </View></ContentEntrance>
      <SegmentedControl
        label="Event interests"
        options={FILTERS.map((id) => ({ id, label: id }))}
        value="All"
        onChange={(filter) =>
          router.push({
            pathname: "/(tabs)/explore",
            params:
              filter === "Free"
                ? { free_only: "1" }
                : filter === "All"
                  ? {}
                  : { category: filter },
          })
        }
      />
      {fallback.isError && !featured ? (
        <EmptyState
          title="The city feed is offline"
          subtitle="Check the API connection and try again."
          action="Try again"
          onAction={() => void fallback.refetch()}
        />
      ) : featured ? (
        <ContentEntrance index={1}><FeaturedEvent event={featured} /></ContentEntrance>
      ) : !fallback.isLoading ? (
        <EmptyState
          title="The city is quiet"
          subtitle="Fresh events will appear here as soon as BACity finds them."
        />
      ) : (
        <LoadingState />
      )}
      <SectionHeader
        title={token ? "For you" : "Happening in Bratislava"}
        action="Explore"
        onAction={() => router.push("/(tabs)/explore")}
      />
      {loading ? <SkeletonList rows={5} /> : null}
      {failed && !items.length ? (
        <EmptyState
          title="Your city feed is offline"
          subtitle="Cached content will remain when available. Check your connection and retry."
          action="Try again"
          onAction={() => void refresh()}
        />
      ) : null}
      {!loading && !failed && !items.length ? (
        <EmptyState
          title="Nothing upcoming yet"
          subtitle="BACity will show fresh Bratislava events here as they arrive."
          action="Explore events"
          onAction={() => router.push("/(tabs)/explore")}
        />
      ) : null}
    </>
  );

  const footer = (
    <>
      <PlusEntry
        onOpen={() => {
          router.push("/plus-experience");
        }}
      />

      {recommendations.isFetchingNextPage ? (
        <ActivityIndicator style={styles.pageLoader} color={colors.primary} />
      ) : null}
      {recommendations.isFetchNextPageError ? (
        <Pressable
          style={styles.retryPage}
          onPress={() => void recommendations.fetchNextPage()}
        >
          <Text style={styles.locationLink}>Couldn’t load more · Retry</Text>
        </Pressable>
      ) : null}
      {!!promotions.data?.length ? (
        <>
          <SectionHeader title="Supported local picks" />
          {promotions.data.slice(0, 2).map((item) => (
            <EventCard
              key={item.event.id}
              event={item.event}
              variant="home"
              explanation={item.label}
            />
          ))}
        </>
      ) : null}
      <Pressable
        style={styles.communityBanner}
        onPress={() => router.push("/(tabs)/contribute")}
      >
        <View style={styles.communityIcon}>
          <AppIcon name="people-outline" size={20} color={colors.primaryDark} />
        </View>
        <View style={styles.communityCopy}>
          <Text style={styles.communityTitle}>Know something we don’t?</Text>
          <Text style={styles.communityText}>
            Add an event or local tip and help the city stay current.
          </Text>
        </View>
        <AppIcon name="arrow-forward" size={18} color={colors.text} />
      </Pressable>
    </>
  );

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={{ paddingHorizontal: tokens.layout.gutter }}>{fixedHeader}</View>
      <FlatList
        data={loading && !items.length ? [] : items}
        keyExtractor={(item) => item.event.id}
        renderItem={({ item, index }) => {
          const entranceDelay =
            index < 3 && !revealed.current.has(item.event.id)
              ? index * tokens.motion.stagger
              : undefined;
          revealed.current.add(item.event.id);
          return (
            <ContentEntrance index={entranceDelay == null ? 0 : entranceDelay / tokens.motion.stagger}><EventCard
              presentation="row"
              event={item.event}
              explanation={preferredExplanation(item.reasons)}
            /></ContentEntrance>
          );
        }}
        ListHeaderComponent={header}
        ListFooterComponent={footer}
        contentContainerStyle={styles.content}
        style={styles.container}
        showsVerticalScrollIndicator={false}
        refreshing={pullRefresh.refreshing}
        onRefresh={pullRefresh.onRefresh}
        onEndReachedThreshold={0.45}
        initialNumToRender={6}
        maxToRenderPerBatch={6}
        windowSize={7}
        onEndReached={() => {
          if (
            token &&
            recommendations.hasNextPage &&
            !recommendations.isFetchingNextPage
          )
            void recommendations.fetchNextPage();
        }}
      />
    </SafeAreaView>
  );
}

const styles = themedStyles(() => ({
  intro: { marginBottom: tokens.space.lg },
  kicker: { ...tokens.type.eyebrow, color: colors.primaryDark },
  headline: { ...tokens.type.pageTitle, color: colors.text, marginTop: tokens.space.sm },
  headlineAccent: { ...fontStyles.black, fontWeight: '800', fontStyle: "italic" },
  subtitle: { color: colors.textMuted, ...tokens.type.metadata, marginTop: 12, maxWidth: 335 },
  safe: { flex: 1, backgroundColor: colors.background },
  container: { flex: 1, backgroundColor: colors.background },
  content: {
    width: "100%",
    maxWidth: tokens.layout.maxWidth,
    alignSelf: "center",
    paddingHorizontal: tokens.layout.gutter,
    paddingTop: 12,
    paddingBottom: tokens.layout.contentBottom,
  },
  plusEntry: {
    minHeight: 80,
    borderRadius: 20,
    backgroundColor: colors.primarySoft,
    padding: 16,
    marginTop: 16,
    marginBottom: 16,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  plusMark: {
    width: 48,
    height: 48,
    borderRadius: 17,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  plusCopy: { flex: 1, minWidth: 0 },
  plusLabel: {
    color: colors.primaryDark,
    ...fontStyles.black,
    fontWeight: "800",
    fontSize: 11,
    letterSpacing: 1.6,
  },
  plusTitle: {
    color: colors.text,
    ...fontStyles.semibold,
    fontWeight: "600",
    fontSize: 15,
    marginTop: 4,
  },
  plusArrow: {
    width: 42,
    height: 42,
    borderRadius: 15,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  topbar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: tokens.space.lg,
  },
  topActions: { flexDirection: "row", alignItems: "center", gap: 0 },
  pressed: { opacity: 0.95 },
  locationLink: {
    color: colors.primaryDark,
    ...fontStyles.semibold,
    fontWeight: "600",
    fontSize: 12,
  },
  pageLoader: { paddingVertical: 18 },
  retryPage: { alignItems: "center", paddingVertical: 16 },
  communityBanner: {
    marginTop: 18,
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
  communityTitle: {
    color: colors.text,
    ...fontStyles.black,
    fontWeight: "800",
    fontSize: 12,
  },
  communityText: {
    color: colors.textMuted,
    ...fontStyles.regular,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 2,
  },
}));

export default function AnimatedHomeScreen() {
  return (
    <TabScene>
      <HomeScreen />
    </TabScene>
  );
}
