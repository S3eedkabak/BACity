import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router, useLocalSearchParams } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { EventChainItem, EventChainMode } from "../src/api/eventChains";
import { EmptyState } from "../src/components/EmptyState";
import { ScreenHeader, SkeletonList } from "../src/components/SocialUI";
import { eventDetailRoute, isValidRenderedChain, resolveEventChainsView } from "../src/eventChains/presentation";
import { useEventChains } from "../src/hooks/useEventChains";
import { plusPaywallRoute } from "../src/plus/policy";
import { usePlusGate } from "../src/plus/usePlusGate";
import { colors } from "../src/theme/colors";
import { fonts } from "../src/theme/fonts";
import { PremiumIntro, PlanStop } from "../src/components/PremiumUI";
import { useBACityWaiting } from "../src/components/BACityMotion";

const MODES: { value: EventChainMode; label: string }[] = [
  { value: "before", label: "Before" },
  { value: "full", label: "Full" },
  { value: "after", label: "After" },
];

function ChainEventRow({ item }: { item: EventChainItem }) {
  return <PlanStop event={item.event} reason={item.reasons[0]} anchor={item.is_anchor} />;
}

export default function EventChainsScreen() {
  const { anchorEventId } = useLocalSearchParams<{ anchorEventId: string }>();
  const gate = usePlusGate();
  const [mode, setMode] = useState<EventChainMode>("full");
  const [alternative, setAlternative] = useState(0);
  const query = useEventChains(anchorEventId, mode, gate.decision === "allow");
  useBACityWaiting(gate.decision === "allow" && query.isPending && !query.data, "Finding events that fit together");
  const chains = query.data?.chains ?? [];
  const state = resolveEventChainsView(gate.decision, query.isPending, query.isError, chains.length);

  useEffect(() => {
    if (gate.decision === "paywall" || gate.decision === "error") {
      router.replace(plusPaywallRoute("event_chains", gate.decision === "error"));
    }
  }, [gate.decision]);

  useEffect(() => setAlternative(0), [mode, chains.length]);

  if (state === "guarding") {
    return <SafeAreaView style={styles.safe}><View style={styles.guard}><ActivityIndicator color={colors.primary} /></View></SafeAreaView>;
  }

  const selected = chains[alternative];
  const renderable = selected && isValidRenderedChain(selected, anchorEventId);
  return <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
    <ScreenHeader title="Event Chains" />
    <ScrollView
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={query.isRefetching} onRefresh={() => void query.refetch()} tintColor={colors.primary} />}
    >
      <PremiumIntro icon="git-network-outline" title="One event. A whole evening." subtitle="Explore what fits before and after your selected event, with room to move between venues." />
      <View style={styles.modes}>{MODES.map(option => <Pressable
        key={option.value}
        onPress={() => setMode(option.value)}
        style={[styles.mode, mode === option.value && styles.modeActive]}
      ><Text style={[styles.modeText, mode === option.value && styles.modeTextActive]}>{option.label}</Text></Pressable>)}</View>

      {state === "loading" ? <SkeletonList rows={3} /> : null}
      {state === "error" ? <EmptyState title="Chains couldn't load" subtitle="The selected event and normal discovery remain available." action="Try again" onAction={() => void query.refetch()} /> : null}
      {state === "empty" ? <EmptyState title="No compatible events found" subtitle="BACity won't loosen timing or transition constraints just to fill a chain." action="Try another mode" onAction={() => setMode(mode === "full" ? "before" : "full")} /> : null}

      {state === "results" && chains.length > 1 ? <View style={styles.alternatives}>{chains.map((chain, index) => <Pressable
        key={chain.id}
        onPress={() => setAlternative(index)}
        style={[styles.alternative, alternative === index && styles.alternativeActive]}
      ><Text style={[styles.alternativeText, alternative === index && styles.alternativeTextActive]}>Option {index + 1}</Text></Pressable>)}</View> : null}

      {state === "results" && renderable ? <View style={styles.timeline}>{selected.items.map(item => <ChainEventRow key={`${selected.id}-${item.event.id}`} item={item} />)}</View> : null}
      {state === "results" && !renderable ? <EmptyState title="This chain couldn't be displayed safely" action="Retry" onAction={() => void query.refetch()} /> : null}
    </ScrollView>
  </SafeAreaView>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background }, guard: { flex: 1, alignItems: "center", justifyContent: "center" },
  content: { width: '100%', maxWidth: 760, alignSelf: 'center', paddingHorizontal: 18, paddingBottom: 40, flexGrow: 1 },
  kicker: { color: colors.primaryDark, fontFamily: fonts.black, fontWeight: '800', fontSize: 12, letterSpacing: 1.5, marginTop: 10 },
  heading: { color: colors.text, fontFamily: fonts.black, fontWeight: '800', fontSize: 28, letterSpacing: -1, marginTop: 6 },
  subtitle: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12, lineHeight: 18, marginTop: 7 },
  modes: { flexDirection: "row", gap: 8, marginVertical: 20 }, mode: { flex: 1, minHeight: 44, borderRadius: 15, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface },
  modeActive: { backgroundColor: colors.primary, borderColor: colors.primary }, modeText: { color: colors.textMuted, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12 }, modeTextActive: { color: colors.white },
  alternatives: { flexDirection: "row", gap: 8, marginBottom: 12 }, alternative: { minHeight: 44, paddingHorizontal: 14, borderRadius: 13, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" },
  alternativeActive: { backgroundColor: colors.primary }, alternativeText: { color: colors.primaryDark, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12 }, alternativeTextActive: { color: colors.white },
  timeline: { gap: 10 }, eventRow: { minHeight: 112, flexDirection: "row", alignItems: "center", gap: 12, padding: 14, borderRadius: 20, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  anchorRow: { borderColor: colors.primary, backgroundColor: colors.primarySoft }, pressed: { opacity: .72 },
  timelineDot: { width: 38, height: 38, borderRadius: 14, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" }, anchorDot: { backgroundColor: colors.primary },
  eventCopy: { flex: 1, minWidth: 0 }, eventTop: { flexDirection: "row", alignItems: "center", gap: 8 }, eventTime: { color: colors.primaryDark, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12 },
  anchorBadge: { color: colors.primaryDark, fontFamily: fonts.black, fontWeight: '800', fontSize: 7, letterSpacing: .8 }, eventTitle: { color: colors.text, fontFamily: fonts.black, fontWeight: '800', fontSize: 15, lineHeight: 19, marginTop: 4 },
  eventVenue: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12, marginTop: 3 }, reason: { color: colors.primaryDark, fontFamily: fonts.medium, fontSize: 12, marginTop: 6 },
});
