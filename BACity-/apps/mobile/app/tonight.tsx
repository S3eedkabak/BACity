import { useEffect, useMemo } from "react";
import { ActivityIndicator, Pressable, SectionList, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { EmptyState } from "../src/components/EmptyState";
import { EventCard } from "../src/components/EventCard";
import { ScreenHeader, SkeletonList } from "../src/components/SocialUI";
import { useToggleSaveEvent } from "../src/hooks/useEvents";
import { useTonight } from "../src/hooks/useTonight";
import { plusPaywallRoute } from "../src/plus/policy";
import { usePlusGate } from "../src/plus/usePlusGate";
import { useRecommendationLocation } from "../src/recommendations/useRecommendationLocation";
import { groupTonightItems, resolveTonightView, tonightLocationCopy } from "../src/tonight/presentation";
import { colors } from "../src/theme/colors";
import { fonts } from "../src/theme/fonts";

export default function TonightScreen() {
  const gate = usePlusGate();
  const location = useRecommendationLocation(gate.decision === "allow");
  const query = useTonight(gate.decision === "allow", location.coordinates);
  const save = useToggleSaveEvent();
  const items = query.data?.items ?? [];
  const sections = useMemo(() => groupTonightItems(items), [items]);
  const state = resolveTonightView(gate.decision, query.isPending, query.isError, items.length);

  useEffect(() => {
    if (gate.decision === "paywall" || gate.decision === "error") {
      router.replace(plusPaywallRoute("tonight", gate.decision === "error"));
    }
  }, [gate.decision]);

  if (state === "guarding") {
    return <SafeAreaView style={styles.safe}><View style={styles.guard}><ActivityIndicator color={colors.primary} /></View></SafeAreaView>;
  }

  const locationText = query.data
    ? tonightLocationCopy(query.data.location_used)
    : location.coordinates
      ? "Using an approximate current location"
      : "Citywide picks work without location";

  return <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
    <SectionList
      sections={state === "results" ? sections : []}
      keyExtractor={item => item.event.id}
      contentContainerStyle={styles.content}
      refreshing={query.isRefetching}
      onRefresh={() => void query.refetch()}
      ListHeaderComponent={<>
        <ScreenHeader title="Tonight / Right Now" />
        <View style={styles.intro}>
          <Text style={styles.kicker}>BACity+</Text>
          <Text style={styles.title}>What can you realistically do tonight?</Text>
          <Text style={styles.subtitle}>A small set of events that are underway, starting soon, or still ahead this evening.</Text>
        </View>
        <View style={styles.location}>
          <Ionicons name={query.data?.location_used ? "navigate" : "navigate-outline"} size={17} color={colors.primaryDark} />
          <Text style={styles.locationText}>{locationText}</Text>
          <Pressable onPress={() => void (location.enabled ? location.disable() : location.enable())}>
            <Text style={styles.locationAction}>{location.enabled ? "Turn off" : "Use location"}</Text>
          </Pressable>
          {location.enabled && ["denied", "unavailable", "timeout", "error"].includes(location.status)
            ? <Pressable onPress={() => void location.retry()}><Text style={styles.locationAction}>Retry</Text></Pressable>
            : null}
        </View>
        {state === "loading" ? <SkeletonList rows={4} /> : null}
        {state === "error" ? <EmptyState title="Tonight couldn't load" subtitle="Your normal BACity discovery feed is still available." action="Try again" onAction={() => void query.refetch()} /> : null}
        {state === "empty" ? <EmptyState title="No realistic Tonight picks" subtitle="BACity won't stretch the time window or show tomorrow afternoon just to fill this screen." action="Explore all events" onAction={() => router.push("/(tabs)/explore")} /> : null}
      </>}
      renderSectionHeader={({ section }) => <Text style={styles.section}>{section.title}</Text>}
      renderItem={({ item }) => <EventCard
        event={item.event}
        explanation={item.reasons[0]}
        saved={item.saved}
        saving={save.isPending && save.variables?.id === item.event.id}
        onToggleSave={() => save.mutate({ id: item.event.id, saved: item.saved })}
      />}
      ListFooterComponent={<Pressable onPress={() => router.push("/(tabs)/discover")} style={styles.allEvents}><Text style={styles.allEventsText}>Back to normal discovery</Text></Pressable>}
      showsVerticalScrollIndicator={false}
    />
  </SafeAreaView>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background }, guard: { flex: 1, alignItems: "center", justifyContent: "center" },
  content: { paddingHorizontal: 18, paddingBottom: 36, flexGrow: 1 },
  intro: { paddingTop: 16, paddingBottom: 18 }, kicker: { color: colors.primaryDark, fontFamily: fonts.black, fontSize: 10, letterSpacing: 1.5 },
  title: { color: colors.text, fontFamily: fonts.black, fontSize: 29, lineHeight: 33, letterSpacing: -1, marginTop: 7 },
  subtitle: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 13, lineHeight: 19, marginTop: 8 },
  location: { minHeight: 48, flexDirection: "row", alignItems: "center", gap: 8, borderTopWidth: StyleSheet.hairlineWidth, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: colors.border, marginBottom: 8 },
  locationText: { flex: 1, color: colors.textMuted, fontFamily: fonts.regular, fontSize: 10 },
  locationAction: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 10, paddingVertical: 10 },
  section: { color: colors.text, backgroundColor: colors.background, fontFamily: fonts.black, fontSize: 19, paddingTop: 20, paddingBottom: 10 },
  allEvents: { minHeight: 48, alignItems: "center", justifyContent: "center", marginTop: 8 }, allEventsText: { color: colors.primaryDark, fontFamily: fonts.semibold, fontSize: 12 },
});
