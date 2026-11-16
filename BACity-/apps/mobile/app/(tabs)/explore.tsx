import { ContentStages } from "../../src/components/navigation/SceneMotion";
import { MapFilters } from "../../src/map/MapFilters";
import { SegmentedControl } from "../../src/components/interactions/SegmentedControl";
import { SectionTransition } from "../../src/components/navigation/SceneMotion";
import { TabScene } from "../../src/components/navigation/SceneMotion";
import { themedStyles, useThemeRevision } from "../../src/theme/appearance";
import { FollowAction } from "../../src/components/interactions/FollowAction";
import { useCallback, useEffect, useRef, useState } from "react";
import { FlatList, StyleSheet, Text, TextInput, View } from "react-native";
import { AnimatedPressable as Pressable } from "../../src/components/motion/Motion";
import { externalLinking as Linking } from "../../src/api/externalLinking";
import { SafeAreaView } from "../../src/components/navigation/ContentSafeArea";
import { AppIcon } from "../../src/components/AppIcon";
import { router, useLocalSearchParams } from "expo-router";
import { apiRequest } from "../../src/api/client";
import { EventCard } from "../../src/components/EventCard";
import { EmptyState } from "../../src/components/EmptyState";
import {
  IconButton,
  ListItem,
  OverflowMenu,
  ProfileRow,
  SkeletonList,
} from "../../src/components/SocialUI";
import { Chip } from "../../src/components/CommunityUI";
import { EventMedia } from "../../src/components/EventMedia";
import { useAuthStore } from "../../src/store/authStore";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";
import type { EventCategory, EventListResponse } from "../../src/types/event";
import { useMeaningfulLoading } from "../../src/components/loading/LoadingExperience";

type Domain = "events" | "places" | "people" | "organizers";
const DOMAINS: {
  id: Domain;
  label: string;
  icon: import("../../src/components/AppIcon").AppIconName;
}[] = [
  { id: "events", label: "Events", icon: "calendar-outline" },
  { id: "places", label: "Places", icon: "location-outline" },
  { id: "people", label: "People", icon: "people-outline" },
  { id: "organizers", label: "Organizers", icon: "business-outline" },
];
const CATEGORIES: EventCategory[] = [
  "Music",
  "Culture",
  "Nightlife",
  "Food & Drink",
  "Markets",
  "Workshops",
  "Family",
  "Other",
];

function ExploreScreen() {
  useThemeRevision();
  const params = useLocalSearchParams<{
    domain?: Domain;
    category?: EventCategory;
    free_only?: string;
  }>();
  const token = useAuthStore((state) => state.token);
  const [filters, setFilters] = useState(false);
  const [organizerMenu, setOrganizerMenu] = useState<any>(null);
  const [freeOnly, setFreeOnly] = useState(params.free_only === "1");
  const [domain, setDomain] = useState<Domain>(
    params.domain && DOMAINS.some((item) => item.id === params.domain)
      ? params.domain
      : "events",
  );
  const [query, setQuery] = useState("");
  const [term, setTerm] = useState("");
  const [category, setCategory] = useState<EventCategory | null>(null);
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [more, setMore] = useState(false);
  const request = useRef(0);
  const abort = useRef<AbortController | null>(null);
  const initialFinished = useRef(false);
  useEffect(() => {
    if (!loading) initialFinished.current = true;
  }, [loading]);
  useMeaningfulLoading(
    "explore",
    loading &&
      !initialFinished.current &&
      !items.length &&
      !query &&
      !category &&
      !freeOnly &&
      domain === "events",
  );
  useEffect(() => {
    if (params.domain && DOMAINS.some((item) => item.id === params.domain))
      setDomain(params.domain);
  }, [params.domain]);
  useEffect(() => {
    setCategory(
      params.category && CATEGORIES.includes(params.category)
        ? params.category
        : null,
    );
    setFreeOnly(params.free_only === "1");
  }, [params.category, params.free_only]);
  useEffect(() => {
    const timer = setTimeout(() => setTerm(query.trim()), 300);
    return () => clearTimeout(timer);
  }, [query]);
  const load = useCallback(
    async (append = false) => {
      const id = ++request.current;
      abort.current?.abort();
      const controller = new AbortController();
      abort.current = controller;
      const signal = controller.signal;
      const offset = append ? items.length : 0;
      setLoading(true);
      setError("");
      try {
        let result: any[];
        if (domain === "events") {
          if (term)
            result = await apiRequest<any[]>("/events/search", {
              signal,
              params: { q: term, limit: 50 },
            });
          else
            result = (
              await apiRequest<EventListResponse>("/events", {
                signal,
                params: {
                  category: category || undefined,
                  free_only: freeOnly || undefined,
                  offset,
                  limit: 20,
                },
              })
            ).items;
        } else if (domain === "places")
          result = await apiRequest<any[]>("/community/places", {
            signal,
            params: { q: term, offset },
          });
        else if (domain === "people")
          result = token
            ? await apiRequest<any[]>("/community/people", {
                auth: true,
                signal,
                params: { q: term, offset, limit: 20 },
              })
            : [];
        else
          result = await apiRequest<any[]>("/community/organizations", {
            signal,
            params: { q: term },
          });
        if (id === request.current) {
          setItems((current) => (append ? [...current, ...result] : result));
          setMore(
            ((domain === "events" && !term) || domain === "people") &&
              result.length === 20,
          );
        }
      } catch (e: any) {
        if (id === request.current) setError(e.message);
      } finally {
        if (id === request.current) setLoading(false);
      }
    },
    [category, freeOnly, domain, items.length, term, token],
  );
  useEffect(() => {
    setItems([]);
    void load(false);
  }, [domain, term, category, freeOnly, token]);
  useEffect(
    () => () => {
      ++request.current;
      abort.current?.abort();
    },
    [],
  );

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <FlatList
        data={items}
        keyExtractor={(item, index) => item.id || String(index)}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={
          <ContentStages>
            <Text style={styles.heading}>Explore Bratislava</Text>
            <View style={styles.search}>
              <AppIcon name="search" size={20} color={colors.primaryDark} />
              <TextInput
                accessibilityLabel="Search BACity"
                placeholder={`Search ${domain}`}
                placeholderTextColor={colors.textMuted}
                value={query}
                onChangeText={setQuery}
                autoCorrect={false}
                style={styles.input}
              />
              {query ? (
                <Pressable
                  accessibilityRole="button"
                  style={{
                    minWidth: 48,
                    minHeight: 48,
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                  accessibilityLabel="Clear search"
                  onPress={() => setQuery("")}
                >
                  <AppIcon
                    name="close-circle"
                    size={20}
                    color={colors.textMuted}
                  />
                </Pressable>
              ) : null}
            </View>
            <SegmentedControl
              label="Discovery section"
              value={domain}
              options={DOMAINS}
              onChange={(value) => {
                setDomain(value);
                setCategory(null);
              }}
            />
            {domain === "events" && !term ? (
              <View style={styles.filterSummary}>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="Event filters"
                  onPress={() => setFilters(true)}
                  style={styles.filterButton}
                >
                  <AppIcon
                    name="options-outline"
                    size={20}
                    color={colors.primaryDark}
                  />
                  <Text style={styles.domainText}>
                    {category || "All interests"}
                    {freeOnly ? " · Free" : ""}
                  </Text>
                </Pressable>
                {category || freeOnly ? (
                  <IconButton
                    icon="close-circle-outline"
                    label="Clear filters"
                    onPress={() => {
                      setCategory(null);
                      setFreeOnly(false);
                    }}
                  />
                ) : null}
              </View>
            ) : null}
            <View style={styles.resultHeader}>
              <Text style={styles.resultTitle}>
                {term
                  ? `Results for “${term}”`
                  : domain === "events"
                    ? "Happening in Bratislava"
                    : `Discover ${domain}`}
              </Text>
              <Text style={styles.count}>{items.length}</Text>
            </View>
            {error ? (
              <EmptyState
                title="Discovery couldn’t load"
                subtitle="Check your connection. Your search is still here."
                action="Try again"
                onAction={() => void load(false)}
              />
            ) : null}
            {loading && !items.length ? <SkeletonList rows={4} /> : null}
            {domain === "people" && !token ? (
              <EmptyState
                title="Sign in to find people"
                subtitle="Member discovery respects profile privacy and block settings."
                action="Sign in"
                onAction={() =>
                  router.push({ pathname: "/auth", params: { mode: "login" } })
                }
              />
            ) : null}
          </ContentStages>
        }
        ListEmptyComponent={
          !loading && !error && !(domain === "people" && !token) ? (
            <EmptyState
              scene="search"
              title="No matches found"
              subtitle="Try another search or browse a different section."
            />
          ) : null
        }
        renderItem={({ item }) => (
          <SectionTransition identity={domain}>
            {domain === "events" ? (
              <EventCard event={item} />
            ) : domain === "people" ? (
              <ProfileRow
                profile={item}
                subtitle={`${item.neighborhood || item.city || "Bratislava"}${item.reputation_level ? ` · ${item.reputation_level}` : ""}`}
                onPress={() => router.push(`/member/${item.id}`)}
              />
            ) : domain === "places" ? (
              <Pressable
                onPress={() => router.push(`/place/${item.id}`)}
                style={({ pressed }) => [
                  styles.place,
                  pressed && styles.pressed,
                ]}
              >
                <EventMedia
                  category={item.category}
                  style={styles.placeMedia}
                />
                <View style={styles.placeCopy}>
                  <Text style={styles.placeTitle}>{item.name}</Text>
                  <Text style={styles.placeCategory}>
                    {item.category || "Local place"}
                  </Text>
                  <Text style={styles.placeAddress} numberOfLines={1}>
                    {item.address}
                  </Text>
                </View>
                <AppIcon
                  name="chevron-forward"
                  size={17}
                  color={colors.textMuted}
                />
              </Pressable>
            ) : (
              <View style={styles.organizer}>
                <View style={styles.organizerTop}>
                  <View style={styles.orgIcon}>
                    <AppIcon
                      name="business-outline"
                      size={20}
                      color={colors.primaryDark}
                    />
                  </View>
                  <View style={styles.placeCopy}>
                    <Text style={styles.placeTitle}>{item.name}</Text>
                    <Text style={styles.placeCategory}>
                      {item.verified
                        ? "Verified organizer"
                        : "Community organizer"}
                    </Text>
                  </View>
                </View>
                {item.description ? (
                  <Text style={styles.orgDescription} numberOfLines={3}>
                    {item.description}
                  </Text>
                ) : null}
                <View style={styles.orgActions}>
                  <FollowAction type="organizer" id={item.id} />
                  {item.website ? (
                    <Text
                      style={styles.link}
                      onPress={() => Linking.openURL(item.website)}
                    >
                      Website
                    </Text>
                  ) : null}
                  <IconButton
                    icon="ellipsis-horizontal"
                    label={`Options for ${item.name}`}
                    onPress={() => setOrganizerMenu(item)}
                  />
                </View>
              </View>
            )}
          </SectionTransition>
        )}
        ListFooterComponent={
          more ? (
            <Pressable
              disabled={loading}
              onPress={() => load(true)}
              style={styles.loadMore}
            >
              <Text style={styles.link}>
                {loading ? "Loading…" : "Load more"}
              </Text>
            </Pressable>
          ) : null
        }
      />
      <OverflowMenu
        visible={filters}
        title="Find what fits"
        onClose={() => setFilters(false)}
      >
        <MapFilters
          simple
          value={{ category: category || undefined, free_only: freeOnly }}
          onChange={(value) => {
            setCategory((value.category as EventCategory) || null);
            setFreeOnly(!!value.free_only);
          }}
          onDone={() => setFilters(false)}
        />
      </OverflowMenu>
      <OverflowMenu
        visible={!!organizerMenu}
        title={organizerMenu?.name || "Organizer options"}
        onClose={() => setOrganizerMenu(null)}
      >
        <ListItem
          icon="business-outline"
          title="Claim / manage"
          subtitle="Ownership verification is required"
          onPress={() => {
            const id = organizerMenu.id;
            setOrganizerMenu(null);
            router.push({ pathname: "/organizer", params: { claim: id } });
          }}
        />
      </OverflowMenu>
    </SafeAreaView>
  );
}

const styles = themedStyles(() => ({
  placeMedia: { width: 64, height: 72, borderRadius: 12 },
  filterSummary: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 4,
  },
  filterButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    minHeight: 48,
    paddingHorizontal: 0,
    borderRadius: 0,
  },
  safe: { flex: 1, backgroundColor: colors.background },
  content: {
    width: "100%",
    maxWidth: 760,
    alignSelf: "center",
    paddingHorizontal: 18,
    paddingTop: 12,
    paddingBottom: 92,
    flexGrow: 1,
  },
  heading: {
    color: colors.text,
    fontFamily: fonts.black,
    fontWeight: "800",
    fontSize: 23,
    letterSpacing: -0.5,
  },
  search: {
    minHeight: 48,
    marginTop: 12,
    borderRadius: 14,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 15,
  },
  input: {
    flex: 1,
    color: colors.text,
    fontFamily: fonts.regular,
    fontSize: 14,
  },
  domainText: {
    color: colors.textMuted,
    fontFamily: fonts.semibold,
    fontWeight: "600",
    fontSize: 12,
  },
  resultHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
  },
  resultTitle: {
    color: colors.text,
    fontFamily: fonts.black,
    fontWeight: "800",
    fontSize: 18,
  },
  count: {
    color: colors.textMuted,
    fontFamily: fonts.semibold,
    fontWeight: "600",
    fontSize: 12,
  },
  place: {
    minHeight: 82,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  pressed: { opacity: 0.68 },
  placeCopy: { flex: 1 },
  placeTitle: {
    color: colors.text,
    fontFamily: fonts.semibold,
    fontWeight: "600",
    fontSize: 14,
  },
  placeCategory: {
    color: colors.primaryDark,
    fontFamily: fonts.medium,
    fontSize: 12,
    marginTop: 2,
  },
  placeAddress: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 12,
    marginTop: 3,
  },
  organizer: {
    paddingVertical: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  organizerTop: { flexDirection: "row", alignItems: "center", gap: 12 },
  orgIcon: {
    width: 50,
    height: 50,
    borderRadius: 18,
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },
  orgDescription: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 9,
  },
  orgActions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 18,
    marginTop: 11,
  },
  link: {
    color: colors.primaryDark,
    fontFamily: fonts.semibold,
    fontWeight: "600",
    fontSize: 12,
  },
  loadMore: { alignItems: "center", padding: 18 },
}));

export default function AnimatedExploreScreen() {
  return (
    <TabScene>
      <ExploreScreen />
    </TabScene>
  );
}
