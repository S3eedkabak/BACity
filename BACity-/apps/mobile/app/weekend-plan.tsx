import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import type { WeekendMode, WeekendPlanAlternative, WeekendPlanDay } from "../src/api/weekendPlans";
import { Button, Chip } from "../src/components/CommunityUI";
import { EmptyState } from "../src/components/EmptyState";
import { ScreenHeader, SkeletonList } from "../src/components/SocialUI";
import { useWeekendPlans } from "../src/hooks/useWeekendPlans";
import { plusPaywallRoute } from "../src/plus/policy";
import { usePlusGate } from "../src/plus/usePlusGate";
import { useRecommendationLocation } from "../src/recommendations/useRecommendationLocation";
import { colors } from "../src/theme/colors";
import { fonts } from "../src/theme/fonts";
import type { EventCategory } from "../src/types/event";
import { defaultWeekendStart, isChronologicalWeekendPlan, resolveWeekendView, validateWeekendStart, weekendEventRoute, weekendPlanNotice } from "../src/weekend/presentation";
import { PremiumIntro, PlanStop } from "../src/components/PremiumUI";
import { TemporalField } from "../src/components/TemporalField";
import { useBACityWaiting } from "../src/components/BACityMotion";

const CATEGORIES: EventCategory[] = ["Music", "Culture", "Arts", "Theatre", "Exhibitions", "Festivals", "Family", "Community"];
const MODES: { value: WeekendMode; label: string }[] = [
  { value: "saturday", label: "Saturday" },
  { value: "sunday", label: "Sunday" },
  { value: "weekend", label: "Full weekend" },
];
const STRATEGY_LABELS = { relaxed: "Relaxed", culture_heavy: "Culture-heavy", something_different: "Something different" } as const;

function DayTimeline({ day }: { day: WeekendPlanDay }) {
  return <View style={styles.daySection}>
    <View style={styles.dayHeading}><Text style={styles.dayTitle}>{day.day}</Text><Text style={styles.dayDate}>{day.date}</Text></View>
    {!day.items.length ? <Text style={styles.dayEmpty}>No events safely fit this day.</Text> : day.items.map((item, index) => <PlanStop key={item.event.id} event={item.event} reason={item.reasons[0]} last={index === day.items.length - 1} />)}
  </View>;
}

function WeekendResult({ plan }: { plan: WeekendPlanAlternative }) {
  if (!isChronologicalWeekendPlan(plan)) return <EmptyState title="This plan couldn't be displayed safely" />;
  return <View style={styles.result}>
    <Text style={styles.planTitle}>{STRATEGY_LABELS[plan.strategy]}</Text>
    <Text style={styles.planExplanation}>{plan.explanation}</Text>
    {weekendPlanNotice(plan) ? <Text style={styles.limited}>{weekendPlanNotice(plan)}</Text> : null}
    {plan.days.map(day => <DayTimeline key={day.date} day={day} />)}
  </View>;
}

export default function WeekendPlanScreen() {
  const gate = usePlusGate();
  const initialDate = useMemo(() => defaultWeekendStart(), []);
  const [weekendStart, setWeekendStart] = useState(initialDate);
  const [mode, setMode] = useState<WeekendMode>("weekend");
  const [categories, setCategories] = useState<EventCategory[]>([]);
  const [validation, setValidation] = useState<string | null>(null);
  const [alternative, setAlternative] = useState(0);
  const [editing, setEditing] = useState(true);
  const location = useRecommendationLocation(gate.decision === "allow");
  const generation = useWeekendPlans();
  useBACityWaiting(gate.decision === "allow" && generation.isPending, "Composing your weekend");
  const plans = generation.data?.plans ?? [];
  const submitted = generation.data !== undefined || generation.isPending || generation.isError;
  const state = resolveWeekendView(gate.decision, submitted, generation.isPending, generation.isError, plans.length);

  useEffect(() => {
    if (gate.decision === "paywall" || gate.decision === "error") {
      router.replace(plusPaywallRoute("weekend_generator", gate.decision === "error"));
    }
  }, [gate.decision]);
  useEffect(() => setAlternative(0), [generation.data]);

  function toggleCategory(category: EventCategory) {
    setCategories(current => {
      if (current.includes(category)) return current.filter(value => value !== category);
      if (current.length >= 6) {
        setValidation("Choose up to six interests for one weekend.");
        return current;
      }
      setValidation(null);
      return [...current, category];
    });
  }

  function generate() {
    const problem = validateWeekendStart(weekendStart);
    setValidation(problem);
    if (problem) return;
    setEditing(false);
    generation.mutate({
      weekend_start: weekendStart,
      mode,
      categories,
      ...(location.coordinates ?? {}),
    });
  }

  if (state === "guarding") {
    return <SafeAreaView style={styles.safe}><View style={styles.guard}><ActivityIndicator color={colors.primary} /></View></SafeAreaView>;
  }

  const selected = plans[alternative];
  return <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
    <ScreenHeader title="Weekend Generator" />
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}><ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <PremiumIntro icon="sunny-outline" title="Make the weekend yours" subtitle="Discover a slower rhythm, a cultural escape, or something completely different." />

      {submitted && <Button variant="secondary" title={`${editing ? 'Hide' : 'Adjust'} weekend & interests`} onPress={() => setEditing(value => !value)} />}
      {(!submitted || editing) && <View style={styles.form}>
        <TemporalField label="Weekend starting Saturday" value={weekendStart} onChange={setWeekendStart} />
        <Text style={styles.label}>PLAN</Text>
        <View style={styles.chips}>{MODES.map(option => <Chip key={option.value} title={option.label} active={mode === option.value} onPress={() => setMode(option.value)} />)}</View>
        <Text style={styles.label}>OPTIONAL INTERESTS</Text>
        <View style={styles.chips}>{CATEGORIES.map(category => <Chip key={category} title={category} active={categories.includes(category)} onPress={() => toggleCategory(category)} />)}</View>
        <View style={styles.locationRow}>
          <Ionicons name={location.coordinates ? "navigate" : "navigate-outline"} size={18} color={colors.primaryDark} />
          <Text style={styles.locationText}>{location.coordinates ? "Using approximate location for practical first-event ranking" : "Location is optional"}</Text>
          <Pressable onPress={() => void (location.enabled ? location.disable() : location.enable())}><Text style={styles.locationAction}>{location.enabled ? "Turn off" : "Use"}</Text></Pressable>
        </View>
        {validation ? <Text accessibilityRole="alert" style={styles.error}>{validation}</Text> : null}
        <Button title={generation.data ? "Regenerate weekend" : "Generate weekend"} busy={generation.isPending} onPress={generate} />
      </View>}

      {state === "error" ? <EmptyState title="Weekend plans couldn't load" subtitle="Normal BACity discovery is still available." action="Try again" onAction={generate} /> : null}
      {state === 'loading' ? <SkeletonList rows={3} /> : null}
      {state === "empty" ? <EmptyState title="No realistic weekend plan found" subtitle="BACity won't invent events or weaken planning constraints." action="Adjust the weekend or interests" onAction={() => generation.reset()} /> : null}
      {state === "results" && !editing ? <>
        <View style={styles.alternatives}>{plans.map((plan, index) => <Pressable key={plan.id} onPress={() => setAlternative(index)} style={[styles.alternative, alternative === index && styles.alternativeActive]}><Text style={[styles.alternativeText, alternative === index && styles.alternativeTextActive]}>{STRATEGY_LABELS[plan.strategy]}</Text></Pressable>)}</View>
        {selected ? <WeekendResult plan={selected} /> : null}
      </> : null}
    </ScrollView></KeyboardAvoidingView>
  </SafeAreaView>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background }, guard: { flex: 1, alignItems: "center", justifyContent: "center" }, content: { width: '100%', maxWidth: 760, alignSelf: 'center', paddingHorizontal: 18, paddingBottom: 42 },
  kicker: { color: colors.primaryDark, fontFamily: fonts.black, fontWeight: '800', fontSize: 12, letterSpacing: 1.5, marginTop: 10 }, heading: { color: colors.text, fontFamily: fonts.black, fontWeight: '800', fontSize: 28, letterSpacing: -1, marginTop: 6 },
  subtitle: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12, lineHeight: 18, marginTop: 7 }, form: { marginTop: 18, gap: 12 }, label: { color: colors.textMuted, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12, letterSpacing: .8 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 7 }, locationRow: { minHeight: 48, flexDirection: "row", alignItems: "center", gap: 8, borderTopWidth: StyleSheet.hairlineWidth, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
  locationText: { flex: 1, color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12 }, locationAction: { color: colors.primaryDark, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12, padding: 10 }, error: { color: colors.danger, fontFamily: fonts.medium, fontSize: 12 },
  alternatives: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 24, marginBottom: 12 }, alternative: { minHeight: 44, paddingHorizontal: 13, borderRadius: 13, backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" },
  alternativeActive: { backgroundColor: colors.primary }, alternativeText: { color: colors.primaryDark, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12 }, alternativeTextActive: { color: colors.white }, result: { gap: 7 },
  planTitle: { color: colors.text, fontFamily: fonts.black, fontWeight: '800', fontSize: 21 }, planExplanation: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12, lineHeight: 18 }, limited: { color: colors.primaryDark, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12, marginTop: 4 },
  daySection: { gap: 9, marginTop: 16 }, dayHeading: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between" }, dayTitle: { color: colors.text, fontFamily: fonts.black, fontWeight: '800', fontSize: 17 }, dayDate: { color: colors.textMuted, fontFamily: fonts.medium, fontSize: 12 }, dayEmpty: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12, paddingVertical: 14 },
  eventRow: { minHeight: 104, flexDirection: "row", alignItems: "center", gap: 12, padding: 14, borderRadius: 20, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border }, pressed: { opacity: .7 },
  timeBox: { minWidth: 52, height: 38, borderRadius: 14, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" }, timeText: { color: colors.white, fontFamily: fonts.black, fontWeight: '800', fontSize: 12 },
  eventCopy: { flex: 1, minWidth: 0 }, eventTitle: { color: colors.text, fontFamily: fonts.black, fontWeight: '800', fontSize: 15, lineHeight: 19 }, eventVenue: { color: colors.textMuted, fontFamily: fonts.regular, fontSize: 12, marginTop: 3 }, reason: { color: colors.primaryDark, fontFamily: fonts.medium, fontSize: 12, marginTop: 6 },
});
