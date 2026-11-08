import { ContentStages } from "../../src/components/navigation/SceneMotion";
import { themedStyles, useThemeRevision } from "../../src/theme/appearance";
import { SaveEventAction } from "../../src/components/interactions/SaveEventAction";
import { availabilityLabel } from "../../src/map/eventAvailability";
import { eventCoordinates } from "../../src/map/eventLocation";
import { useViewOnMap } from "../../src/map/eventTarget";
import { Button } from "../../src/components/CommunityUI";
import { EventMedia } from "../../src/components/EventMedia";
import { MediaScrim } from "../../src/components/MediaScrim";
import { Discussion } from "../../src/components/Discussion";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { AnimatedPressable as Pressable } from "../../src/components/motion/Motion";
import { SafeAreaView } from "../../src/components/navigation/ContentSafeArea";
import { useInfiniteQuery } from "@tanstack/react-query";
import { eventOccurrences } from "../../src/api/events";
import { useLayoutEffect, useState } from "react";
import {
  IconButton,
  ListItem,
  OverflowMenu,
} from "../../src/components/SocialUI";
import { externalLinking as Linking } from "../../src/api/externalLinking";
import { router, useLocalSearchParams, useNavigation } from "expo-router";
import { AppIcon } from "../../src/components/AppIcon";
import { useEvent } from "../../src/hooks/useEvents";
import { useAuthStore } from "../../src/store/authStore";
import { LoadingState } from "../../src/components/LoadingState";
import { EmptyState } from "../../src/components/EmptyState";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";
import { PlusGateAction } from "../../src/plus/usePlusGate";
import { eventChainsRoute } from "../../src/eventChains/presentation";
import { useMeaningfulLoading } from "../../src/components/loading/LoadingExperience";

function formatWhen(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    timeZone: "Europe/Bratislava",
    weekday: "long",
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function EventDetailScreen() {
  useThemeRevision();
  const [menu, setMenu] = useState(false);
  const navigation = useNavigation();
  useLayoutEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <IconButton
          icon="ellipsis-horizontal"
          label="Event actions"
          onPress={() => setMenu(true)}
        />
      ),
    });
  }, [navigation]);
  const viewOnMap = useViewOnMap();
  const { id } = useLocalSearchParams<{ id: string }>();
  const token = useAuthStore((s) => s.token);
  const { data: event, isLoading, isError, refetch } = useEvent(id);
  useMeaningfulLoading("event-details", isLoading && !event);
  const availability = useInfiniteQuery({
    queryKey: ["event-availability", event?.id],
    queryFn: ({ pageParam, signal }) =>
      eventOccurrences(event!.id, pageParam, signal),
    initialPageParam: 0,
    getNextPageParam: (page) => page.next_offset ?? undefined,
    enabled: event?.identity_kind === "recurring",
    staleTime: 30000,
  });

  if (isLoading) return <LoadingState variant="detail" />;
  if (!event)
    return (
      <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
        <EmptyState
          title={isError ? "Couldn't load this event" : "Event not found"}
          action="Try again"
          onAction={() => void refetch()}
        />
      </SafeAreaView>
    );

  const price =
    event.price === 0
      ? "Free"
      : event.price == null
        ? "Price unknown"
        : event.price + " " + (event.currency ?? "EUR");

  return (
    <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          keyboardShouldPersistTaps="handled"
          style={styles.container}
          contentContainerStyle={styles.content}
          showsVerticalScrollIndicator={false}
        ><ContentStages>
          {event.image_url ? (
            <View style={styles.hero}>
              <EventMedia
                uri={event.image_url}
                category={event.category}
                style={styles.heroImage}
              />
              <MediaScrim />
              <View style={styles.heroTop}>
                <View style={styles.heroBadges}>
                  <View style={styles.categoryPill}>
                    <Text style={styles.category}>{event.category}</Text>
                  </View>

                  {event.price === 0 && (
                    <View style={styles.freePill}>
                      <Text style={styles.freeText}>FREE</Text>
                    </View>
                  )}
                </View>
              </View>
              <View style={styles.heroText}>
                <Text style={styles.title}>{event.title}</Text>
                <View style={styles.locationLine}>
                  <AppIcon
                    name="location-outline"
                    size={15}
                    color={colors.white}
                  />
                  <Text style={styles.location}>
                    {event.venue?.name ?? event.address ?? "Bratislava"}
                  </Text>
                </View>
              </View>
            </View>
          ) : (
            <View
              style={{ paddingHorizontal: 20, paddingVertical: 16, gap: 8 }}
            >
              <Text style={{ color: colors.primaryDark, fontSize: 13 }}>
                {event.category}
              </Text>
              <Text
                style={{
                  color: colors.text,
                  fontSize: 26,
                  lineHeight: 32,
                  fontWeight: "700",
                }}
              >
                {event.title}
              </Text>
              <Text style={{ color: colors.textMuted, fontSize: 14 }}>
                {event.venue?.name ?? event.address ?? "Bratislava"}
              </Text>
            </View>
          )}

          <View style={styles.infoGrid}>
            <View style={styles.infoCard}>
              <View style={styles.infoIcon}>
                <AppIcon
                  name="calendar-outline"
                  size={18}
                  color={colors.primary}
                />
              </View>
              <Text style={styles.label}>WHEN</Text>
              <Text style={styles.value}>{availabilityLabel(event)}</Text>
            </View>

            <View style={styles.infoCard}>
              <View style={styles.infoIcon}>
                <AppIcon
                  name="pricetag-outline"
                  size={18}
                  color={colors.primary}
                />
              </View>
              <Text style={styles.label}>PRICE</Text>
              <Text style={styles.value}>{price}</Text>
            </View>
          </View>

          {event.identity_kind === "recurring" && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Upcoming availability</Text>
              {availability.isPending && (
                <Text style={styles.value}>Loading times…</Text>
              )}
              {availability.isError && (
                <Pressable
                  accessibilityRole="button"
                  onPress={() => void availability.refetch()}
                >
                  <Text style={styles.value}>Couldn’t load times · Retry</Text>
                </Pressable>
              )}
              {availability.data?.pages
                .flatMap((page) => page.items)
                .map((item) => (
                  <Text key={item.id} style={styles.value}>
                    {item.start_precision === "date"
                      ? new Date(item.start_time).toLocaleDateString(
                          undefined,
                          { timeZone: "Europe/Bratislava" },
                        )
                      : formatWhen(item.start_time)}
                  </Text>
                ))}
              {availability.data?.pages[0]?.total === 0 && (
                <Text style={styles.value}>
                  No confirmed upcoming sessions.
                </Text>
              )}
              {availability.hasNextPage && (
                <Pressable
                  accessibilityRole="button"
                  onPress={() => void availability.fetchNextPage()}
                >
                  <Text style={styles.sourceText}>
                    {availability.isFetchingNextPage
                      ? "Loading…"
                      : "More times"}
                  </Text>
                </Pressable>
              )}
              {!!event.offers?.length && (
                <Text style={styles.sectionTitle}>Ticket options</Text>
              )}
              {event.offers?.map((offer) => (
                <Pressable
                  key={offer.source_url}
                  accessibilityRole="button"
                  onPress={() => void Linking.openURL(offer.source_url)}
                >
                  <Text style={styles.sourceText}>
                    {offer.label}
                    {offer.price != null
                      ? ` · ${offer.price} ${offer.currency ?? "EUR"}`
                      : ""}
                  </Text>
                </Pressable>
              ))}
            </View>
          )}
          {event.description && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>About this event</Text>
              <Text style={styles.description}>{event.description}</Text>
            </View>
          )}

          {!!event.source_url && (
            <Pressable
              style={styles.sourceButton}
              onPress={() => Linking.openURL(event.source_url)}
            >
              <Text style={styles.sourceText}>View original event</Text>
              <AppIcon
                name="arrow-up-outline"
                size={16}
                color={colors.primaryDark}
              />
            </Pressable>
          )}
          {event.venue && (
            <Button
              variant="secondary"
              title={"More at " + event.venue.name}
              onPress={() => router.push(`/venue/${event.venue!.id}`)}
            />
          )}
          <Discussion id={event.id} kind="event" />
        </ContentStages></ScrollView>
        <View
          style={{ paddingVertical: 12, backgroundColor: colors.background }}
        >
          <SaveEventAction event={event} expanded />
        </View>
      </KeyboardAvoidingView>
      <OverflowMenu
        visible={menu}
        title="Event actions"
        onClose={() => setMenu(false)}
      >
        <PlusGateAction
          feature="event_chains"
          onAllowed={() => {
            setMenu(false);
            router.push(eventChainsRoute(event.id));
          }}
        >
          {({ onPress, loading }) => (
            <ListItem
              icon="git-branch-outline"
              title={loading ? "Checking access…" : "Build around this event"}
              subtitle="Find compatible events before or after"
              onPress={loading ? undefined : onPress}
            />
          )}
        </PlusGateAction>
        {eventCoordinates(event) ? (
          <ListItem
            icon="map-outline"
            title="View on Map"
            onPress={() => {
              setMenu(false);
              viewOnMap(event);
            }}
          />
        ) : (
          <Text style={styles.value}>Exact map location unavailable</Text>
        )}
        <ListItem
          icon="share-outline"
          title="Share event"
          onPress={() => {
            setMenu(false);
            void Share.share({
              title: event.title,
              message:
                event.title + (event.source_url ? "\n" + event.source_url : ""),
            });
          }}
        />
        <ListItem
          icon="albums-outline"
          title="Add to a collection"
          onPress={() => {
            setMenu(false);
            router.push({
              pathname: "/collection",
              params: { type: "event", id },
            });
          }}
        />
        <ListItem
          icon="create-outline"
          title="Suggest a correction"
          onPress={() => {
            setMenu(false);
            router.push({
              pathname: "/correction",
              params: { type: "event", id },
            });
          }}
        />
      </OverflowMenu>
    </SafeAreaView>
  );
}

const styles = themedStyles(() => ({
  container: { flex: 1, backgroundColor: colors.background },
  content: {
    width: "100%",
    maxWidth: 760,
    alignSelf: "center",
    paddingBottom: 45,
  },
  hero: {
    minHeight: 220,
    height: 250,
    marginHorizontal: 14,
    borderRadius: 28,
    overflow: "hidden",
    backgroundColor: colors.primarySoft,
  },
  heroImage: { width: "100%", height: "100%" },
  heroTop: {
    position: "absolute",
    top: 16,
    left: 16,
    right: 16,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  heroBadges: {
    flexDirection: "row",
    gap: 7,
    alignItems: "center",
  },
  categoryPill: {
    backgroundColor: "rgba(39,35,41,0.78)",
    paddingHorizontal: 11,
    paddingVertical: 7,
    borderRadius: 99,
  },
  category: {
    color: colors.white,
    fontFamily: fonts.semibold,
    fontWeight: "600",
    fontSize: 12,
  },
  freePill: {
    backgroundColor: colors.successSurface,
    paddingHorizontal: 11,
    paddingVertical: 7,
    borderRadius: 99,
  },
  freeText: {
    color: colors.free,
    fontFamily: fonts.black,
    fontWeight: "800",
    fontSize: 12,
  },
  heroText: { position: "absolute", left: 18, right: 18, bottom: 20 },
  title: {
    color: colors.white,
    fontFamily: fonts.black,
    fontWeight: "800",
    fontSize: 25,
    lineHeight: 33,
    letterSpacing: -0.8,
  },
  locationLine: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    marginTop: 8,
  },
  location: {
    color: colors.white,
    fontFamily: fonts.medium,
    fontSize: 12,
    flex: 1,
  },
  infoGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 16,
    paddingHorizontal: 20,
    marginTop: 20,
  },
  infoCard: {
    flex: 1,
    minWidth: 140,
    paddingVertical: 8,
  },
  infoIcon: {
    width: 38,
    height: 38,
    borderRadius: 13,
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 10,
  },
  label: {
    color: colors.textMuted,
    fontFamily: fonts.semibold,
    fontWeight: "600",
    fontSize: 12,
    letterSpacing: 1,
  },
  value: {
    color: colors.text,
    fontFamily: fonts.semibold,
    fontWeight: "600",
    fontSize: 12,
    lineHeight: 18,
    marginTop: 4,
  },
  section: { paddingHorizontal: 18, paddingTop: 22 },
  sectionTitle: {
    color: colors.text,
    fontFamily: fonts.black,
    fontWeight: "800",
    fontSize: 19,
  },
  description: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 13,
    lineHeight: 21,
    marginTop: 8,
  },
  sourceButton: {
    alignSelf: "center",
    flexDirection: "row",
    gap: 7,
    alignItems: "center",
    padding: 10,
  },
  sourceText: {
    color: colors.primaryDark,
    fontFamily: fonts.semibold,
    fontWeight: "600",
    fontSize: 12,
  },
}));
