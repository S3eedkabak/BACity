import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from "react-native";
import { AnimatedPressable as Pressable } from '../src/components/motion/Motion';
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { AppIcon } from "../src/components/AppIcon";
import { EveningPlanAlternative } from "../src/api/eveningPlans";
import { Button, Chip } from "../src/components/CommunityUI";
import { EmptyState } from "../src/components/EmptyState";
import { ScreenHeader, SkeletonList } from "../src/components/SocialUI";
import { defaultEveningParameters, eveningEventRoute, eveningPlanNotice, isChronologicalPlan, resolveEveningView, validateEveningParameters } from "../src/evening/presentation";
import { useEveningPlans } from "../src/hooks/useEveningPlans";
import { plusPaywallRoute } from "../src/plus/policy";
import { usePlusGate } from "../src/plus/usePlusGate";
import { useRecommendationLocation } from "../src/recommendations/useRecommendationLocation";
import { colors } from "../src/theme/colors";
import { fonts } from "../src/theme/fonts";
import { EventCategory } from "../src/types/event";
import { PremiumIntro, PlanStop } from "../src/components/PremiumUI";
import { TemporalField } from "../src/components/TemporalField";
import { useBrandedLoading } from "../src/components/loading/LoadingExperience";

const CATEGORIES: EventCategory[] = ["Music", "Culture", "Arts", "Nightlife", "Theatre", "Comedy", "Family", "Community"];
const STRATEGY_LABELS = { best_match: "Best match", relaxed: "Relaxed", something_different: "Something different" } as const;

function PlanTimeline({ plan }: { plan: EveningPlanAlternative }) {
  if (!isChronologicalPlan(plan)) return <EmptyState title="This plan couldn't be displayed safely" />;
  return <View style={styles.timeline}>{plan.items.map((item, index) => <PlanStop key={item.event.id} event={item.event} reason={item.reasons[0]} last={index === plan.items.length - 1} />)}</View>;
}

export default function EveningPlanScreen() {
  const gate = usePlusGate();
  const defaults = useMemo(() => defaultEveningParameters(), []);
  const [date, setDate] = useState(defaults.date);
  const [startTime, setStartTime] = useState(defaults.startTime);
  const [endTime, setEndTime] = useState(defaults.endTime);
  const [categories, setCategories] = useState<EventCategory[]>([]);
  const [validation, setValidation] = useState<string | null>(null);
  const [alternative, setAlternative] = useState(0);
  const [editing, setEditing] = useState(true);
  const location = useRecommendationLocation(gate.decision === "allow");
  const generation = useEveningPlans();
  useBrandedLoading('plan-generation', generation.isPending);
  const plans = generation.data?.plans ?? [];
  const submitted = generation.data !== undefined || generation.isPending || generation.isError;
  const state = resolveEveningView(gate.decision, submitted, generation.isPending, generation.isError, plans.length);

  useEffect(() => {
    if (gate.decision === "paywall" || gate.decision === "error") {
      router.replace(plusPaywallRoute("build_my_evening", gate.decision === "error"));
    }
  }, [gate.decision]);
  useEffect(() => setAlternative(0), [generation.data]);

  function toggleCategory(category: EventCategory) {
    setCategories(current => {
      if (current.includes(category)) return current.filter(value => value !== category);
      if (current.length >= 6) {
        setValidation("Choose up to six interests for one evening.");
        return current;
      }
      setValidation(null);
      return [...current, category];
    });
  }

  function generate() {
    const problem = validateEveningParameters(date, startTime, endTime);
    setValidation(problem);
    if (problem) return;
    setEditing(false);
    generation.mutate({
      date,
      start_time: startTime,
      end_time: endTime,
      categories,
      ...(location.coordinates ?? {}),
    });
  }

  if (state === "guarding") {
    return <SafeAreaView style={styles.safe}><View style={styles.guard}><ActivityIndicator color={colors.primary} /></View></SafeAreaView>;
  }

  const selected = plans[alternative];
  return <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
    <ScreenHeader title="Build My Evening" />
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}><ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <PremiumIntro icon="moon-outline" title="Make this evening count" subtitle="A few real events, thoughtfully composed around your time and interests." />

      {submitted && <Button variant="secondary" title={`${editing ? 'Hide' : 'Adjust'} time & interests`} onPress={() => setEditing(value => !value)} />}
      {(!submitted || editing) && <View style={styles.form}>
        <TemporalField label="Your evening" value={date} onChange={setDate} />
        <View style={styles.split}><View style={styles.flex}><TemporalField mode="time" label="From" value={startTime} onChange={setStartTime} /></View><View style={styles.flex}><TemporalField mode="time" label="Until" value={endTime} onChange={setEndTime} /></View></View>
        <Text style={styles.label}>INTERESTS FOR THIS EVENING</Text>
        <View style={styles.chips}>{CATEGORIES.map(category => <Chip key={category} title={category} active={categories.includes(category)} onPress={() => toggleCategory(category)} />)}</View>
        <View style={styles.locationRow}>
          <AppIcon name={location.coordinates ? "navigate" : "navigate-outline"} size={18} color={colors.primaryDark} />
          <Text style={styles.locationText}>{location.coordinates ? "Using approximate location for first-event convenience" : "Location is optional"}</Text>
          <Pressable onPress={() => void (location.enabled ? location.disable() : location.enable())}><Text style={styles.locationAction}>{location.enabled ? "Turn off" : "Use"}</Text></Pressable>
        </View>
        {validation ? <Text accessibilityRole="alert" style={styles.error}>{validation}</Text> : null}
        <Button title={generation.data ? "Regenerate plans" : "Build my evening"} busy={generation.isPending} onPress={generate} />
      </View>}

      {state === "error" ? <EmptyState title="Plans couldn't be generated" subtitle="Your normal BACity discovery remains available." action="Try again" onAction={generate} /> : null}
      {state === 'loading' ? <SkeletonList rows={3} /> : null}
      {state === "empty" ? <EmptyState title="No realistic plan found" subtitle="BACity won't invent activities or weaken transition constraints." action="Adjust your time or interests" onAction={() => generation.reset()} /> : null}
      {state === "results" && !editing ? <>
        <View style={styles.alternatives}>{plans.map((plan, index) => <Pressable key={plan.id} onPress={() => setAlternative(index)} style={[styles.alternative, alternative === index && styles.alternativeActive]}><Text style={[styles.alternativeText, alternative === index && styles.alternativeTextActive]}>{STRATEGY_LABELS[plan.strategy]}</Text></Pressable>)}</View>
        {selected ? <View style={styles.result}>
          <Text style={styles.planTitle}>{STRATEGY_LABELS[selected.strategy]}</Text>
          <Text style={styles.planExplanation}>{selected.explanation}</Text>
          {eveningPlanNotice(selected.limited) ? <Text style={styles.limited}>{eveningPlanNotice(selected.limited)}</Text> : null}
          <PlanTimeline plan={selected} />
        </View> : null}
      </> : null}
    </ScrollView></KeyboardAvoidingView>
  </SafeAreaView>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background }, guard: { flex: 1, alignItems: "center", justifyContent: "center" }, content: { width: '100%', maxWidth: 760, alignSelf: 'center', paddingHorizontal: 18, paddingBottom: 42 },
  kicker: { color: colors.primaryDark, fontFamily: fonts.black, fontWeight: '800', fontSize: 12, letterSpacing: 1.5, marginTop: 10 }, heading: { color: colors.text, fontFamily: fonts.black, fontWeight: '800', fontSize: 28, letterSpacing: -1, marginTop: 6 },
  subtitle: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12, lineHeight: 18, marginTop: 7 }, form: { marginTop: 18, gap: 12 }, split: { flexDirection: "row", gap: 9 }, flex: { flex: 1, minWidth: 0 },
  label: { color: colors.textMuted, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12, letterSpacing: .8 }, chips: { flexDirection: "row", flexWrap: "wrap", gap: 7 },
  locationRow: { minHeight: 48, flexDirection: "row", alignItems: "center", gap: 8, borderTopWidth: StyleSheet.hairlineWidth, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: colors.border }, locationText: { flex: 1, color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12 }, locationAction: { color: colors.primaryDark, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12, padding: 10 },
  error: { color: colors.danger, fontFamily: fonts.medium, fontSize: 12 }, alternatives: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 24, marginBottom: 12 }, alternative: { minHeight: 44, paddingHorizontal: 13, borderRadius: 13, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" },
  alternativeActive: { backgroundColor: colors.primary }, alternativeText: { color: colors.primaryDark, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12 }, alternativeTextActive: { color: colors.white }, result: { gap: 5 },
  planTitle: { color: colors.text, fontFamily: fonts.black, fontWeight: '800', fontSize: 21 }, planExplanation: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12, lineHeight: 18 }, limited: { color: colors.primaryDark, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12, marginTop: 5 },
  timeline: { gap: 10, marginTop: 10 }, eventRow: { minHeight: 108, flexDirection: "row", alignItems: "center", gap: 12, padding: 14, borderRadius: 20, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border }, pressed: { opacity: .7 },
  order: { width: 36, height: 36, borderRadius: 14, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" }, orderText: { color: colors.white, fontFamily: fonts.black, fontWeight: '800', fontSize: 12 },
  eventCopy: { flex: 1, minWidth: 0 }, eventTime: { color: colors.primaryDark, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12 }, eventTitle: { color: colors.text, fontFamily: fonts.black, fontWeight: '800', fontSize: 15, lineHeight: 19, marginTop: 4 }, eventVenue: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12, marginTop: 3 }, reason: { color: colors.primaryDark, fontFamily: fonts.medium, fontSize: 12, marginTop: 6 },
});
