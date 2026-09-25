import { Ionicons } from "@expo/vector-icons";
import { useMemo } from "react";
import {
  ImageBackground,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { router } from "expo-router";
import { useEvents } from "../../src/hooks/useEvents";
import { EventDeck } from "../../src/components/EventDeck";
import { EmptyState } from "../../src/components/EmptyState";
import { LoadingState } from "../../src/components/LoadingState";
import { categoryImages } from "../../src/theme/categoryImages";
import { colors } from "../../src/theme/colors";
import { fonts } from "../../src/theme/fonts";

const CATEGORIES = [
  { label: "Party", image: categoryImages.party, icon: "musical-notes-outline" as const },
  { label: "Museums", image: categoryImages.museum, icon: "color-palette-outline" as const },
  { label: "Markets", image: categoryImages.market, icon: "basket-outline" as const },
  { label: "Workshops", image: categoryImages.workshop, icon: "construct-outline" as const },
];

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export default function HomeScreen() {
  const { data, isLoading, isError, refetch, isRefetching } = useEvents({ limit: 50 });
  const events = useMemo(() => data?.items ?? [], [data]);

  if (isLoading) return <LoadingState />;
  if (isError) {
    return (
      <EmptyState
        title={"Couldn't load BACity"}
        subtitle="Check that the API is running and pull down to retry."
      />
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={isRefetching}
          onRefresh={refetch}
          tintColor={colors.primary}
        />
      }
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.topRow}>
        <View>
          <Text style={styles.greeting}>{greeting()}</Text>
          <Text style={styles.logo}>
            BA<Text style={styles.logoAccent}>City</Text>
          </Text>
        </View>
        <Pressable style={styles.location} onPress={() => router.push("/(tabs)/profile")}>
          <Ionicons name="location" size={14} color={colors.primary} />
          <Text style={styles.locationText}>Bratislava</Text>
          <Ionicons name="chevron-down" size={13} color={colors.textMuted} />
        </Pressable>
      </View>

      <View style={styles.heroCopy}>
        <View style={styles.eyebrowPill}>
          <View style={styles.eyebrowDot} />
          <Text style={styles.eyebrowText}>DISCOVER BRATISLAVA</Text>
        </View>
        <Text style={styles.heroTitle}>What's your{"\n"}vibe today?</Text>
        <Text style={styles.heroSubtitle}>
          Find something worth leaving the house for.
        </Text>
      </View>

      <Pressable style={styles.searchCta} onPress={() => router.push("/(tabs)/explore")}>
        <View style={styles.searchIcon}>
          <Ionicons name="search" size={19} color={colors.primary} />
        </View>
        <Text style={styles.searchText}>Search events, places, vibes...</Text>
        <View style={styles.searchArrow}>
          <Ionicons name="arrow-forward" size={17} color={colors.white} />
        </View>
      </Pressable>

      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Pick a mood</Text>
        <Text style={styles.sectionHint}>browse</Text>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.categoryRow}
      >
        {CATEGORIES.map((category) => (
          <Pressable
            key={category.label}
            style={styles.categoryTile}
            onPress={() => router.push("/(tabs)/explore")}
          >
            <ImageBackground
              source={{ uri: category.image }}
              style={styles.categoryImage}
              imageStyle={styles.categoryImageRadius}
            >
              <View style={styles.categoryShade} />
              <View style={styles.categoryIcon}>
                <Ionicons name={category.icon} size={17} color={colors.white} />
              </View>
              <Text style={styles.categoryLabel}>{category.label}</Text>
            </ImageBackground>
          </Pressable>
        ))}
      </ScrollView>

      <View style={[styles.sectionHeader, styles.eventsHeader]}>
        <View>
          <Text style={styles.sectionTitle}>Happening now</Text>
          <Text style={styles.sectionSub}>Real events, fresh from the city.</Text>
        </View>
        <Pressable onPress={() => router.push("/(tabs)/explore")}>
          <Text style={styles.seeAll}>See all</Text>
        </Pressable>
      </View>

      {events.length ? (
        <EventDeck events={events} />
      ) : (
        <EmptyState
          title="The city is quiet"
          subtitle="Run the crawler and fresh events will appear here."
        />
      )}

      <View style={styles.footerNote}>
        <View style={styles.footerDot} />
        <Text style={styles.footerText}>Curated for Bratislava</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { paddingHorizontal: 18, paddingTop: 10, paddingBottom: 110 },
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 22,
  },
  greeting: {
    color: colors.textMuted,
    fontFamily: fonts.medium,
    fontSize: 11,
    letterSpacing: 0.2,
  },
  logo: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 29,
    letterSpacing: -1.2,
    marginTop: 1,
  },
  logoAccent: { color: colors.primary },
  location: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: 11,
    paddingVertical: 9,
    borderRadius: 99,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  locationText: { color: colors.text, fontFamily: fonts.semibold, fontSize: 11 },
  heroCopy: { marginBottom: 19 },
  eyebrowPill: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: 99,
    backgroundColor: colors.primarySoft,
    marginBottom: 12,
  },
  eyebrowDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.primary,
  },
  eyebrowText: {
    color: colors.primaryDark,
    fontFamily: fonts.semibold,
    fontSize: 9,
    letterSpacing: 1.1,
  },
  heroTitle: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 38,
    lineHeight: 39,
    letterSpacing: -1.6,
  },
  heroSubtitle: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 14,
    marginTop: 9,
  },
  searchCta: {
    height: 58,
    borderRadius: 22,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 8,
    marginBottom: 26,
    shadowColor: colors.shadow,
    shadowOpacity: 0.08,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 5 },
  },
  searchIcon: {
    width: 42,
    height: 42,
    borderRadius: 14,
    backgroundColor: colors.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },
  searchText: {
    flex: 1,
    color: colors.textMuted,
    fontFamily: fonts.medium,
    fontSize: 12,
    marginLeft: 10,
  },
  searchArrow: {
    width: 42,
    height: 42,
    borderRadius: 14,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    marginBottom: 11,
  },
  sectionTitle: {
    color: colors.text,
    fontFamily: fonts.black,
    fontSize: 19,
    letterSpacing: -0.5,
  },
  sectionHint: {
    color: colors.primary,
    fontFamily: fonts.semibold,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 1,
  },
  categoryRow: { gap: 10, paddingRight: 8 },
  categoryTile: {
    width: 116,
    height: 128,
    borderRadius: 21,
    overflow: "hidden",
    shadowColor: colors.shadow,
    shadowOpacity: 0.14,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 5 },
  },
  categoryImage: { flex: 1, justifyContent: "space-between", padding: 11 },
  categoryImageRadius: { borderRadius: 21 },
  categoryShade: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(35,25,29,0.28)",
  },
  categoryIcon: {
    width: 34,
    height: 34,
    borderRadius: 12,
    backgroundColor: "rgba(255,127,134,0.9)",
    alignItems: "center",
    justifyContent: "center",
  },
  categoryLabel: {
    color: colors.white,
    fontFamily: fonts.black,
    fontSize: 14,
  },
  eventsHeader: { marginTop: 27, alignItems: "flex-end" },
  sectionSub: {
    color: colors.textMuted,
    fontFamily: fonts.regular,
    fontSize: 11,
    marginTop: 2,
  },
  seeAll: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 11 },
  footerNote: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
    marginTop: 10,
  },
  footerDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.primary,
  },
  footerText: { color: colors.textMuted, fontFamily: fonts.medium, fontSize: 10 },
});
